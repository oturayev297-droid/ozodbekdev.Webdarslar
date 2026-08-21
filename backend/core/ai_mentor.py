"""
AI Mentor — Claude API orqali
=============================

Ilgari bu `if q.includes('python')` ko'rinishidagi qattiq kodlangan
shartlar to'plami edi: 4-5 ta savoldan boshqasiga javob bera olmasdi,
lekin interfeysda "AI Mentor" deb turardi. Endi haqiqiy model ishlaydi.

MOCK REJIM: `ANTHROPIC_API_KEY` bo'sh bo'lsa modelga so'rov ketmaydi va
o'quvchi tushunarli xabar oladi — sahifa buzilmaydi. Email va Telegram
bilan bir xil naqsh.

CHEKLOV: har bir so'rov pul turadi, shuning uchun foydalanuvchi bo'yicha
kunlik va daqiqalik cheklov bor. Busiz bitta o'quvchi tunda skript bilan
minglab so'rov yuborib hisobni bo'shatib qo'yardi.

STREAMING ATAYLAB ISHLATILMAGAN: bu loyiha gunicorn'ning sinxron
worker'larida ishlaydi (DEPLOY.md), va oqim butun javob davomida bitta
worker'ni band qilib turadi — 3 worker bilan 3 ta bir vaqtdagi suhbat
butun saytni to'xtatib qo'yardi. `max_tokens` kichik (4096), demak javob
HTTP timeout'iga yaqin ham kelmaydi.
"""

import logging
import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

#: Bitta foydalanuvchi bir daqiqada nechta savol bera oladi
MAX_PER_MINUTE = 5

#: Bitta foydalanuvchi bir kunda nechta savol bera oladi
MAX_PER_DAY = 60

#: Suhbatning nechta oxirgi almashuvi modelga yuboriladi.
#: Cheklovsiz uzun suhbat har so'rovda qayta yuborilib, xarajat
#: kvadratik o'sardi.
HISTORY_TURNS = 6

#: Javob uzunligi. Fikrlash (thinking) ham shu chegara ichida —
#: shuning uchun javob matniga joy qolishi uchun bemalol qo'yilgan.
MAX_TOKENS = 4096

#: Foydalanuvchi savolining maksimal uzunligi (belgi)
MAX_QUESTION_LENGTH = 2000


SYSTEM_PROMPT = """Sen — ozodbekdev.uz onlayn ta'lim platformasidagi dasturlash o'qituvchisisan.

Platformada to'rt yo'nalish o'qitiladi: Python, Django, JavaScript va React.

## Qanday javob berasan

O'zbek tilida, lotin alifbosida yozasan. Savol rus yoki ingliz tilida
kelsa ham javobni o'zbekcha berasan, faqat foydalanuvchi boshqa tilni
aniq so'rasa — o'sha tilda.

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
    """Foydalanuvchiga ko'rsatiladigan xato."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def is_configured() -> bool:
    return bool(getattr(settings, 'ANTHROPIC_API_KEY', ''))


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
                "<code>ANTHROPIC_API_KEY</code> ni qo'shishi kerak.<br><br>"
                "Shu vaqt ichida darslar, testlar va kod muharriri "
                "to'liq ishlaydi."
            ),
            'mock': True,
        }

    check_quota(user)

    answer = _call_claude(user, question, lesson)

    from .models import MentorMessage

    MentorMessage.objects.create(
        user=user,
        question=question[:MAX_QUESTION_LENGTH],
        answer=answer,
        lesson=lesson,
    )

    return {'answer': _to_html(answer), 'mock': False}


def _call_claude(user, question: str, lesson) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Dars konteksti — o'quvchi "bu yerda nima deyilgan?" deb so'rasa
    # model qaysi dars haqida gapirayotganini bilsin.
    context = ""
    if lesson is not None:
        context = (
            f"\n\nO'quvchi hozir \"{lesson.title}\" darsini ko'rmoqda "
            f"({lesson.module.category.name} yo'nalishi)."
        )

    messages = _history(user) + [{'role': 'user', 'content': question + context}]

    try:
        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
            # Tizim ko'rsatmasi o'zgarmaydi, shuning uchun keshlanadi —
            # har so'rovda uni qayta hisoblash ortiqcha pul.
            system=[{
                'type': 'text',
                'text': SYSTEM_PROMPT,
                'cache_control': {'type': 'ephemeral'},
            }],
            # Chat uchun kechikish muhim. Dasturlash tushunchasini
            # tushuntirish chuqur fikrlashni talab qilmaydi.
            output_config={'effort': settings.ANTHROPIC_EFFORT},
            messages=messages,
        )
    except anthropic.RateLimitError:
        logger.warning("[MENTOR] API cheklovi (user=%s)", user.pk)
        raise MentorError(
            "Hozir juda ko'p so'rov bor. Bir daqiqadan keyin urinib ko'ring.",
            status=503,
        )
    except anthropic.APIStatusError as exc:
        logger.error("[MENTOR] API xatosi %s: %s", exc.status_code, exc.message)
        raise MentorError(
            "AI Mentor hozir javob bera olmayapti. Keyinroq urinib ko'ring.",
            status=503,
        )
    except anthropic.APIConnectionError:
        logger.error("[MENTOR] Aloqa xatosi")
        raise MentorError(
            "Tarmoqda nosozlik. Keyinroq urinib ko'ring.", status=503
        )

    # Modelning xavfsizlik tekshiruvi so'rovni rad etishi mumkin — bu
    # HTTP 200 bilan keladi, shuning uchun `content` ni o'qishdan OLDIN
    # tekshiriladi. Aks holda `content[0]` bo'sh ro'yxatda yiqilardi.
    if response.stop_reason == 'refusal':
        logger.info("[MENTOR] Rad etildi (user=%s)", user.pk)
        raise MentorError(
            "Bu savolga javob bera olmayman. Dasturlashga oid savol bering."
        )

    text = "".join(
        block.text for block in response.content if block.type == 'text'
    ).strip()

    if not text:
        raise MentorError(
            "Javob olinmadi. Savolni boshqacha ifodalab ko'ring.", status=503
        )

    logger.info(
        "[MENTOR] user=%s in=%s out=%s kesh=%s",
        user.pk,
        response.usage.input_tokens,
        response.usage.output_tokens,
        response.usage.cache_read_input_tokens,
    )
    return text


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
