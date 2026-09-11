"""
AI Mentor — Google Gemini orqali
================================

Ilgari bu `if q.includes('python')` ko'rinishidagi qattiq kodlangan
shartlar to'plami edi: 4-5 ta savoldan boshqasiga javob bera olmasdi,
lekin interfeysda "AI Mentor" deb turardi. Endi haqiqiy model ishlaydi.

MODEL: Gemini, uning OpenAI bilan mos API'si orqali — `openai`
kutubxonasi `GEMINI_BASE_URL` ga yo'naltiriladi. Model nomi
`settings.GEMINI_MODEL` (standart `gemini-2.5-flash`).

MOCK REJIM: `GEMINI_API_KEY` bo'sh bo'lsa modelga so'rov ketmaydi va
o'quvchi tushunarli xabar oladi — sahifa buzilmaydi. Email va Telegram
bilan bir xil naqsh.

SHAXSIY MA'LUMOT YUBORILMAYDI: modelga faqat tizim ko'rsatmasi
(platforma bilimi va katalog), o'quvchining savollari va dars mavzusi
ketadi. Ism, login, email va foydalanuvchi raqami so'rovga QO'SHILMAYDI —
`user` faqat bazadagi tarix va kvota uchun ishlatiladi.

XATO PROCESSNI O'LDIRMAYDI: har qanday xato ushlanadi, logga yoziladi
va o'quvchiga `MentorError` bo'lib qaytadi. So'rov `REQUEST_TIMEOUT`
bilan cheklangan — gunicorn `--timeout 120` dan ancha qisqa. Busiz
osilib qolgan so'rov worker'ni o'ldirardi (parol tiklashdagi SMTP bilan
aynan shunday bo'lgan). 429 (Gemini band) alohida: o'quvchiga "10
soniyadan keyin" deyiladi.

CHEKLOV: har bir so'rov pul yoki kvota turadi, shuning uchun
foydalanuvchi bo'yicha kunlik va daqiqalik cheklov bor. Busiz bitta
o'quvchi tunda skript bilan minglab so'rov yuborib kvotani tugatardi.

STREAMING ATAYLAB ISHLATILMAGAN: bu loyiha gunicorn'ning sinxron
worker'larida ishlaydi (DEPLOY.md), va oqim butun javob davomida bitta
worker'ni band qilib turadi — 3 worker bilan 3 ta bir vaqtdagi suhbat
butun saytni to'xtatib qo'yardi.

BILIM: mentor sayt, sahifalar, qoidalar va kurslar haqida
`core.mentor_knowledge` dan biladi. Dars sahifasida savol berilsa,
o'sha darsning matni va kod namunasi ham kontekstga qo'shiladi.
"""

import logging
import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from . import mentor_knowledge

logger = logging.getLogger(__name__)

#: Gemini'ning OpenAI bilan mos API manzili
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

#: Bitta so'rov necha soniya kutiladi. Gunicorn `--timeout 120` dan
#: ancha qisqa bo'lishi SHART — aks holda osilgan so'rov worker'ni
#: o'ldiradi.
REQUEST_TIMEOUT = 30

#: Gemini band bo'lganda (429) o'quvchiga beriladigan xabar va
#: brauzerga `Retry-After` sifatida ketadigan soniya.
BUSY_MESSAGE = "Mentor band, 10 soniyadan keyin urinib ko'ring."
BUSY_RETRY_AFTER = 10

UNAVAILABLE_MESSAGE = "AI Mentor hozir javob bera olmayapti. Keyinroq urinib ko'ring."

#: Bitta foydalanuvchi bir daqiqada nechta savol bera oladi
MAX_PER_MINUTE = 5

#: Bitta foydalanuvchi bir kunda nechta savol bera oladi
MAX_PER_DAY = 60

#: Suhbatning nechta oxirgi almashuvi modelga yuboriladi.
#: Cheklovsiz uzun suhbat har so'rovda qayta yuborilib, xarajat
#: kvadratik o'sardi.
HISTORY_TURNS = 6

#: Javob uzunligi. Fikrlash ham shu chegara ichida — shuning uchun
#: javob matniga joy qolishi uchun bemalol qo'yilgan.
MAX_TOKENS = 4096

#: Foydalanuvchi savolining maksimal uzunligi (belgi)
MAX_QUESTION_LENGTH = 2000

#: Dars matnining kontekstga qo'shiladigan qismi (belgi). Eng uzun
#: yozma dars ~2300 belgi, ya'ni amalda hammasi to'liq ketadi. Chegara
#: kelajakdagi juda uzun dars har savolda qimmatga tushmasligi uchun;
#: qisqartirilsa bu modelga OCHIQ aytiladi.
MAX_LESSON_TEXT = 12000


SYSTEM_PROMPT = """Sen — ozodbekdev.uz onlayn ta'lim platformasidagi dasturlash o'qituvchisisan.

## Til

Har doim FAQAT o'zbek tilida, lotin alifbosida javob berasan. Savol rus,
ingliz yoki boshqa tilda kelsa ham javob o'zbekcha bo'ladi; faqat o'quvchi
boshqa tilda javob berishni aniq so'rasa — o'sha tilda. Kod, kalit so'zlar
va dasturlash atamalari o'zgarmaydi, lekin kod ichidagi izohlar va
tushuntirishlar o'zbekcha.

Platformada besh yo'nalish o'qitiladi: Python, Django, JavaScript, React va
Sun'iy intellekt. Sayt, sahifalar, qoidalar va kurslar haqidagi bilim hamda
darslar katalogi quyida berilgan — platforma haqidagi savolga shu asosda
javob ber.

## Qanday javob berasan

Sen boshlovchilar bilan ishlaysan. Atamani birinchi marta ishlatganingda
qavs ichida qisqacha izohla. Javobni misolsiz qoldirma: tushuncha
tushuntirilganda ishlaydigan kod bo'lagi ber.

Uzunlikni savolga qarab tanla. "For sikli nima?" degan savolga bir necha
jumla va bitta misol yetarli — bo'limlar, sarlavhalar va ro'yxatlar
kerak emas. Murakkab savolga batafsil javob ber.

## Nima qilmaysan

O'quvchining topshirig'ini o'rniga yechib bermaysan. Vazifa yoki test
javobini so'rasa: tushunchani tushuntirasan, o'xshash (lekin aynan o'sha
emas) misol berasan va keyingi qadamni aytasan. To'g'ridan-to'g'ri
tayyor javob berish o'rganishga to'sqinlik qiladi — buni o'quvchiga
do'stona ohangda aytib qo'y.

Savol dasturlashga umuman aloqasiz bo'lsa (masalan ob-havo, siyosat,
shaxsiy maslahat), qisqa va xushmuomala ravishda platforma mavzusiga
qaytar.

Bilmagan narsangni bilaman deb aytmaysan. Kutubxona yoki freymvorkning
aniq versiyasiga oid tafsilotga ishonching komil bo'lmasa, shuni ochiq
ayt va rasmiy hujjatga qarashni tavsiya qil.

## Formatlash

Javob chatda HTML sifatida ko'rsatiladi. Kodni ```til bilan boshlanadigan
blok ichiga ol. Qalin matn uchun **ikkita yulduzcha** ishlat. Sarlavha
belgilarini (#) ishlatma."""


class MentorError(Exception):
    """
    Foydalanuvchiga ko'rsatiladigan xato.

    `retry_after` — soniya; berilsa API javobiga `Retry-After`
    sarlavhasi qo'shiladi (Gemini band bo'lganda).
    """

    def __init__(self, message, status=400, retry_after=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.retry_after = retry_after


def is_configured() -> bool:
    return bool(getattr(settings, 'GEMINI_API_KEY', ''))


# ==========================================================================
# Cheklov
# ==========================================================================


def check_quota(user):
    """
    Foydalanuvchi kvotasini tekshiradi.

    Bazadan sanaladi, cache'dan emas: cache har worker'da alohida va
    server qayta yuklansa nolga tushardi — pul bilan bog'liq cheklov
    uchun bu yetarli emas (`core.lockout` bilan bir xil sabab).
    """
    from .models import MentorMessage

    now = timezone.now()

    minute_count = MentorMessage.objects.filter(
        user=user, created_at__gte=now - timedelta(minutes=1)
    ).count()
    if minute_count >= MAX_PER_MINUTE:
        raise MentorError(
            "Juda tez so'rayapsiz. Bir daqiqadan keyin qayta urinib ko'ring.",
            status=429,
        )

    day_count = MentorMessage.objects.filter(
        user=user, created_at__gte=now - timedelta(days=1)
    ).count()
    if day_count >= MAX_PER_DAY:
        raise MentorError(
            f"Kunlik chegara ({MAX_PER_DAY} savol) tugadi. Ertaga davom eting.",
            status=429,
        )


# ==========================================================================
# Suhbat tarixi
# ==========================================================================


def _history(user):
    """
    Oxirgi almashuvlar — modelga kontekst sifatida yuboriladi.

    Tarix SERVERDA saqlanadi, klientdan qabul qilinmaydi. Aks holda
    o'quvchi o'zi yozgan soxta "assistant" javoblarini yuborib modelni
    boshqarib olardi (prompt injection).

    Faqat savol va javob matni — kim yozgani (ism, login) qo'shilmaydi.
    """
    from .models import MentorMessage

    rows = list(
        MentorMessage.objects.filter(user=user)
        .order_by('-created_at')[:HISTORY_TURNS]
    )
    rows.reverse()

    messages = []
    for row in rows:
        messages.append({'role': 'user', 'content': row.question})
        if row.answer:
            messages.append({'role': 'assistant', 'content': row.answer})
    return messages


# ==========================================================================
# Asosiy chaqiruv
# ==========================================================================


def ask(user, question: str, lesson=None) -> dict:
    """
    Savolga javob qaytaradi.

    Qaytaradi: `{'answer': str, 'mock': bool}`
    """
    question = (question or '').strip()
    if not question:
        raise MentorError("Savol bo'sh.")
    if len(question) > MAX_QUESTION_LENGTH:
        raise MentorError(
            f"Savol juda uzun (ko'pi bilan {MAX_QUESTION_LENGTH} belgi)."
        )

    if not is_configured():
        return {
            'answer': (
                "AI Mentor hozircha sozlanmagan. Administrator "
                "<code>GEMINI_API_KEY</code> ni qo'shishi kerak.<br><br>"
                "Shu vaqt ichida darslar, testlar va kod muharriri "
                "to'liq ishlaydi."
            ),
            'mock': True,
        }

    check_quota(user)

    answer = _call_model(user, question, lesson)

    from .models import MentorMessage

    MentorMessage.objects.create(
        user=user,
        question=question[:MAX_QUESTION_LENGTH],
        answer=answer,
        lesson=lesson,
    )

    return {'answer': _to_html(answer), 'mock': False}


def _call_model(user, question: str, lesson) -> str:
    """
    Gemini'ga so'rov. `user` faqat tarix va logdagi raqam uchun —
    so'rovga uning hech bir ma'lumoti qo'shilmaydi.
    """
    import openai

    content = question
    if lesson is not None:
        content = f"{_lesson_context(lesson)}\n\nSavol: {question}"

    messages = (
        [{'role': 'system', 'content': _system_prompt()}]
        + _history(user)
        + [{'role': 'user', 'content': content}]
    )

    try:
        client = openai.OpenAI(
            api_key=settings.GEMINI_API_KEY,
            base_url=GEMINI_BASE_URL,
            timeout=REQUEST_TIMEOUT,
            # Qayta urinish YO'Q: 429 da o'quvchi darhol "band" xabarini
            # oladi; SDK ning o'zi kutib qayta urinsa, so'rov gunicorn
            # timeout'iga yaqinlashib, worker'ni band qilib turardi.
            max_retries=0,
        )
        response = client.chat.completions.create(
            model=settings.GEMINI_MODEL,
            messages=messages,
            max_tokens=MAX_TOKENS,
            # Chat uchun kechikish muhim. Dasturlash tushunchasini
            # tushuntirish chuqur fikrlashni talab qilmaydi.
            reasoning_effort=settings.GEMINI_REASONING_EFFORT,
        )
    except openai.RateLimitError:
        logger.warning("[MENTOR] Gemini band (429), user=%s", user.pk)
        raise MentorError(BUSY_MESSAGE, status=429, retry_after=BUSY_RETRY_AFTER)
    except openai.APITimeoutError:
        logger.error("[MENTOR] Gemini %s soniyada javob bermadi", REQUEST_TIMEOUT)
        raise MentorError(
            "Mentor hozir javob bermadi. Birozdan keyin urinib ko'ring.", status=503
        )
    except openai.APIConnectionError:
        logger.error("[MENTOR] Gemini bilan aloqa yo'q")
        raise MentorError("Tarmoqda nosozlik. Keyinroq urinib ko'ring.", status=503)
    except openai.APIStatusError as exc:
        logger.error("[MENTOR] Gemini xatosi %s: %s", exc.status_code, exc.message)
        raise MentorError(UNAVAILABLE_MESSAGE, status=503)
    except Exception:
        # Kutilmagan har qanday xato — faqat logga. Process yashayveradi.
        logger.exception("[MENTOR] Gemini so'rovida kutilmagan xato")
        raise MentorError(UNAVAILABLE_MESSAGE, status=503)

    try:
        return _read_answer(user, response)
    except MentorError:
        raise
    except Exception:
        logger.exception("[MENTOR] Gemini javobini o'qib bo'lmadi")
        raise MentorError(UNAVAILABLE_MESSAGE, status=503)


def _read_answer(user, response) -> str:
    choices = getattr(response, 'choices', None) or []
    choice = choices[0] if choices else None

    # Xavfsizlik filtri javobni to'xtatishi mumkin — bu HTTP 200 bilan
    # keladi, shuning uchun matnni o'qishdan OLDIN tekshiriladi.
    if choice is not None and choice.finish_reason == 'content_filter':
        logger.info("[MENTOR] Rad etildi, user=%s", user.pk)
        raise MentorError(
            "Bu savolga javob bera olmayman. Dasturlashga oid savol bering."
        )

    text = ((choice.message.content if choice is not None else None) or '').strip()
    if not text:
        # Masalan fikrlash `max_tokens` ni to'ldirib qo'ysa (`length`)
        logger.warning(
            "[MENTOR] Bo'sh javob, finish_reason=%s",
            getattr(choice, 'finish_reason', None),
        )
        raise MentorError(
            "Javob olinmadi. Savolni boshqacha ifodalab ko'ring.", status=503
        )

    usage = getattr(response, 'usage', None)
    details = getattr(usage, 'prompt_tokens_details', None)
    logger.info(
        "[MENTOR] user=%s in=%s out=%s kesh=%s",
        user.pk,
        getattr(usage, 'prompt_tokens', None),
        getattr(usage, 'completion_tokens', None),
        getattr(details, 'cached_tokens', None),
    )
    return text


def _system_prompt() -> str:
    """
    Tizim ko'rsatmasi: ko'rsatma, platforma bilimi, keyin kurs katalogi.

    TARTIB BARQAROR: o'zgarmas qism birinchi, katalog (faqat admin
    kontentni o'zgartirganda o'zgaradi) keyin, o'quvchining savoli va
    dars matni esa alohida xabarlarda — eng oxirida. Gemini so'rovning
    takrorlanadigan boshlanishini o'zi keshlaydi.
    """
    return f"{SYSTEM_PROMPT}\n\n{mentor_knowledge.GUIDE}\n\n{mentor_knowledge.catalog()}"


def _lesson_context(lesson) -> str:
    """
    O'quvchi turgan dars — nomi, joyi, ko'nikma izohi, matni va kodi.

    Ilgari faqat NOMI yuborilardi va "bu yerda nima deyilgan?" degan
    savolga model dars matnini ko'rmay javob berardi. Qulflangan dars
    bu yerga kelmaydi — `api.views.MentorAskView` uni oldinroq rad etadi.
    """
    parts = [
        f"O'quvchi hozir [{lesson.id}] \"{lesson.title}\" darsida turibdi "
        f"({lesson.module.category.name} kursi, \"{lesson.module.title}\" moduli)."
    ]

    note = mentor_knowledge.LESSON_NOTES.get(lesson.id)
    if note:
        parts.append(f"Dars haqida: {note}")

    theory = (lesson.theory or '').strip()
    if len(theory) >= mentor_knowledge.TEXT_MIN_CHARS:
        if len(theory) > MAX_LESSON_TEXT:
            theory = theory[:MAX_LESSON_TEXT] + "\n[... matn shu yerda qisqartirildi]"
        parts.append(f"<dars_matni>\n{theory}\n</dars_matni>")
    else:
        parts.append(
            "Bu darsning yozma matni yo'q — mazmuni faqat videoda."
        )

    code = (lesson.practice_code or '').strip()
    if code:
        parts.append(f"<kod_namunasi>\n{code}\n</kod_namunasi>")

    return "\n\n".join(parts)


# ==========================================================================
# Ko'rsatish
# ==========================================================================


def _to_html(text: str) -> str:
    """
    Markdown'ning kichik qismini HTML ga aylantiradi.

    To'liq markdown kutubxonasi ATAYLAB olinmadi: model javobi chatga
    `innerHTML` bilan qo'yiladi, shuning uchun HTML ni O'ZIMIZ quramiz
    va faqat kerakli teglarni chiqaramiz. Model matnini to'g'ridan-to'g'ri
    HTML deb qabul qilish XSS yo'li bo'lardi.
    """
    from django.utils.html import escape

    parts = []
    # Kod bloklarini ajratib olamiz — ichidagi ** qalin qilinmasligi kerak
    for i, chunk in enumerate(re.split(r'```(?:[\w+-]*)\n?(.*?)```', text, flags=re.S)):
        if i % 2 == 1:
            parts.append(
                '<pre class="bg-black/40 border border-white/10 rounded-xl '
                'p-4 my-3 overflow-x-auto text-[11px] leading-relaxed">'
                f'<code>{escape(chunk.rstrip())}</code></pre>'
            )
            continue

        safe = escape(chunk)
        safe = re.sub(r'`([^`\n]+)`',
                      r'<code class="bg-white/10 px-1.5 py-0.5 rounded text-[11px]">\1</code>',
                      safe)
        safe = re.sub(r'\*\*([^*\n]+)\*\*', r'<strong>\1</strong>', safe)
        parts.append(safe.replace('\n', '<br>'))

    return "".join(parts)
