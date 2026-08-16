"""
Telegram xabarnomalar
=====================

NEGA KERAK: to'lov qo'lda tasdiqlanadi. Admin so'rovni ko'rmaguncha
o'quvchi kutadi — email esa soatlab ochilmasligi mumkin. Telegram
adminni darhol xabardor qiladi va o'quvchiga karta rekvizitlarini
panelga kirmasdan yetkazadi.

ASOSIY QOIDA (emailService bilan bir xil): BU YERDAGI HECH BIR FUNKSIYA
XATO TASHLAMAYDI. Telegram ishlamasa ham to'lov oqimi davom etadi —
xabar yuborilmagani uchun tasdiqlangan to'lov bekor bo'lib qolmasligi
kerak. Nosozlik faqat logga yoziladi.

MOCK REJIM: `TELEGRAM_BOT_TOKEN` bo'sh bo'lsa hech qayerga so'rov
ketmaydi, xabar matni logga yoziladi. Lokal ishlab chiqish uchun.

ULANISH: o'quvchining `chat_id` si kerak. Uni telefon raqamisiz olish
uchun bir martalik havola beriladi — `t.me/<bot>?start=<kod>`. Kod
bazada XESHLANGAN holda saqlanadi (parol tiklash kodi kabi), chunki
havola Telegram tarixida qolib ketadi.
"""

import hashlib
import logging
import secrets
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from . import dates

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}/{method}"

#: Tarmoq kutish vaqti. Uzun bo'lsa admin panelidagi "Tasdiqlash"
#: tugmasi Telegram javob bermaguncha osilib turardi.
TIMEOUT = 5

#: Ulash havolasi shuncha vaqt amal qiladi
LINK_TTL = timedelta(hours=24)


def is_configured() -> bool:
    return bool(getattr(settings, 'TELEGRAM_BOT_TOKEN', ''))


def _post(method: str, payload: dict) -> bool:
    """
    Telegram API ga so'rov. HECH QACHON xato tashlamaydi.

    Qaytaradi: yuborildimi (mock rejimda ham True).
    """
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        logger.info("[TELEGRAM] (mock) %s -> %s", method, payload.get('text', payload))
        return True

    try:
        response = requests.post(
            API_BASE.format(token=token, method=method), json=payload, timeout=TIMEOUT
        )
        data = response.json()
        if not data.get('ok'):
            logger.warning(
                "[TELEGRAM] %s rad etildi: %s", method, data.get('description')
            )
            return False
        return True
    except Exception as exc:
        logger.error("[TELEGRAM] %s yuborilmadi: %s", method, exc)
        return False


def send(chat_id, text: str) -> bool:
    """Bitta chatga xabar."""
    if not chat_id:
        return False
    return _post('sendMessage', {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True,
    })


def send_to_admins(text: str) -> bool:
    """
    Adminlarga xabar.

    Chat ID lar `.env` da vergul bilan: `TELEGRAM_ADMIN_CHAT_IDS=111,222`.
    Bo'sh bo'lsa jimgina o'tkazib yuboriladi — bu xato emas, shunchaki
    sozlanmagan.
    """
    ids = getattr(settings, 'TELEGRAM_ADMIN_CHAT_IDS', [])
    if not ids:
        logger.info("[TELEGRAM] (adminlar sozlanmagan) %s", text[:120])
        return False
    ok = True
    for chat_id in ids:
        ok = send(chat_id, text) and ok
    return ok


def user_chat_id(user):
    """
    Foydalanuvchining Telegram chat ID si (ulanmagan bo'lsa None).

    Bo'sh satr emas, aynan None qaytaradi: CharField standarti `''` bo'lgani
    uchun chaqiruvchi "ulanganmi" degan savolga `is not None` bilan javob
    izlasa, ulanmagan foydalanuvchi ham ulangandek ko'rinardi.
    """
    profile = getattr(user, 'profile', None)
    if not profile:
        return None
    return getattr(profile, 'telegram_chat_id', '') or None


# ==========================================================================
# Hisobni ulash
# ==========================================================================


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_link_token(user):
    """
    Bir martalik ulash kodi yaratadi va `t.me` havolasini qaytaradi.

    Avvalgi ishlatilmagan kodlar bekor qilinadi — bir vaqtda bitta
    amaldagi havola bo'lsin.
    """
    from .models import TelegramLinkToken

    TelegramLinkToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )

    raw = secrets.token_urlsafe(24)
    TelegramLinkToken.objects.create(
        user=user,
        token_hash=hash_token(raw),
        expires_at=timezone.now() + LINK_TTL,
    )

    bot = getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or 'bot'
    return f"https://t.me/{bot}?start={raw}"


def consume_link_token(raw_token: str, chat_id):
    """
    Botga kelgan `/start <kod>` ni qayta ishlaydi.

    Muvaffaqiyatli bo'lsa foydalanuvchini qaytaradi, aks holda None.
    """
    from .models import TelegramLinkToken

    record = (
        TelegramLinkToken.objects.select_related('user__profile')
        .filter(
            token_hash=hash_token((raw_token or '').strip()),
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .first()
    )
    if not record:
        return None

    record.used_at = timezone.now()
    record.save(update_fields=['used_at'])

    profile = record.user.profile
    profile.telegram_chat_id = str(chat_id)
    profile.save(update_fields=['telegram_chat_id'])

    logger.info("[TELEGRAM] Hisob ulandi: user=%s chat=%s", record.user.username, chat_id)
    return record.user


# ==========================================================================
# To'lov oqimi xabarlari
# ==========================================================================


def notify_request_created(payment_request):
    """Adminga: yangi to'lov so'rovi keldi."""
    user = payment_request.user
    name = getattr(getattr(user, 'profile', None), 'full_name', '') or user.username
    return send_to_admins(
        f"💳 <b>Yangi to'lov so'rovi</b>\n\n"
        f"O'quvchi: <b>{name}</b> (@{user.username})\n"
        f"Muddat: {payment_request.months} oy\n"
        f"Summa: <b>{dates.format_money(payment_request.amount_tiyin)}</b>\n\n"
        f"Admin panelda karta rekvizitlarini bering."
    )


def notify_card_issued(payment_request, cards):
    """O'quvchiga: karta rekvizitlari."""
    chat_id = user_chat_id(payment_request.user)
    if not chat_id:
        # Telegrami ulanmagan o'quvchi — bu xato emas. Rekvizitlarni
        # u saytdan ko'radi, shuning uchun to'lov oqimi to'xtamaydi.
        return False

    if not cards:
        return send(
            chat_id,
            "Karta rekvizitlari hali kiritilmagan. Administrator bilan bog'laning.",
        )

    lines = [
        f"💳 <b>To'lov uchun rekvizitlar</b>\n",
        f"Muddat: {payment_request.months} oy",
        f"Summa: <b>{dates.format_money(payment_request.amount_tiyin)}</b>\n",
    ]
    for card in cards:
        lines.append(f"<code>{card['number']}</code>")
        detail = " · ".join(x for x in (card.get('holder'), card.get('bank')) if x)
        if detail:
            lines.append(detail)
        if card.get('note'):
            lines.append(f"<i>{card['note']}</i>")
        lines.append("")

    lines.append("Pulni o'tkazgach chek rasmini shu yerga yuboring va saytdagi")
    lines.append("<b>«Chekni yubordim»</b> tugmasini bosing.")

    return send(chat_id, "\n".join(lines))


def notify_receipt_sent(payment_request, hold_days):
    """Adminga: chek yuborildi, tekshirish kerak."""
    user = payment_request.user
    name = getattr(getattr(user, 'profile', None), 'full_name', '') or user.username
    return send_to_admins(
        f"🧾 <b>Chek yuborildi — tekshirish kerak</b>\n\n"
        f"O'quvchi: <b>{name}</b> (@{user.username})\n"
        f"Muddat: {payment_request.months} oy\n"
        f"Summa: <b>{dates.format_money(payment_request.amount_tiyin)}</b>\n"
        f"Kanal: {payment_request.get_receipt_source_display()}\n\n"
        f"⏳ Kirish {hold_days} kun ochiq qoladi — shu muddatda tasdiqlang."
    )


def notify_confirmed(user, months, amount_tiyin, new_end):
    """O'quvchiga: to'lov tasdiqlandi."""
    return send(
        user_chat_id(user),
        f"✅ <b>To'lovingiz tasdiqlandi</b>\n\n"
        f"Muddat: {months} oy\n"
        f"Summa: {dates.format_money(amount_tiyin)}\n"
        f"Obuna: <b>{dates.format_date(new_end)}</b> gacha\n\n"
        f"Barcha darslar ochildi. Muvaffaqiyat tilaymiz!"
    )


def notify_rejected(user, reason):
    """O'quvchiga: to'lov rad etildi."""
    return send(
        user_chat_id(user),
        f"❌ <b>To'lov rad etildi</b>\n\n"
        f"Sabab: {reason}\n\n"
        f"Savolingiz bo'lsa administratorga yozing. Yangi so'rov yuborishingiz mumkin."
    )


def notify_expiring(user, days_left, end_date, grace_days):
    """O'quvchiga: obuna tugayapti."""
    if days_left == 0:
        text = (
            f"⏰ <b>Obunangiz bugun tugaydi</b>\n\n"
            f"Yana {grace_days} kun kirishingiz ochiq qoladi, undan keyin "
            f"bepul darslardan boshqasi yopiladi."
        )
    else:
        text = (
            f"⏰ <b>Obunangizga {days_left} kun qoldi</b>\n\n"
            f"Tugash sanasi: {dates.format_date(end_date)}\n\n"
            f"Muddat tugamasdan to'lasangiz qolgan kunlaringiz yo'qolmaydi — "
            f"yangi muddat eski sanadan qo'shiladi."
        )
    return send(user_chat_id(user), text)


def notify_new_registration(user) -> bool:
    """
    Yangi ro'yxatdan o'tish haqida ADMINGA xabar.

    NEGA KERAK: yangi hisob ruxsat kutib turadi va o'quvchi hech narsa
    ko'rmaydi. Admin buni bilmasa, odam kunlab kutib qolardi va
    ehtimol butunlay ketib qolardi.
    """
    profile = getattr(user, 'profile', None)
    full_name = (profile.full_name if profile else '') or user.username

    return send_to_admins(
        "Yangi ro'yxatdan o'tish\n\n"
        f"Ism   : {full_name}\n"
        f"Login : {user.username}\n"
        f"Email : {user.email or '—'}\n\n"
        "Ruxsat kutilmoqda. Panelda ko'rib chiqing:\n"
        "/panel/oquvchilar/?state=pending"
    )


def notify_approved(user) -> bool:
    """O'quvchiga ruxsat berilgani haqida xabar."""
    return send(
        user_chat_id(user),
        "Sizga ruxsat berildi!\n\n"
        "Endi saytga kirib bepul darslarni ko'rishingiz mumkin.\n"
        "Barcha darslar uchun obuna rasmiylashtiring.",
    )


def notify_rejected_registration(user, reason: str) -> bool:
    """Ruxsat berilmagani haqida xabar. Sabab o'quvchiga KO'RSATILADI."""
    text = "Hisobingizga ruxsat berilmadi."
    if reason:
        text += f"\n\nSabab: {reason}"
    text += "\n\nSavollaringiz bo'lsa biz bilan bog'laning."
    return send(user_chat_id(user), text)


# ==========================================================================
# Kiruvchi yangilanishlar
# ==========================================================================


def handle_update(update: dict) -> bool:
    """
    Telegram dan kelgan bitta yangilanishni qayta ishlaydi.

    IKKI JOYDAN CHAQIRILADI va shuning uchun shu yerda turibdi:

      * `billing.views.telegram_webhook` — productionda, Telegram
        o'zi HTTPS orqali yuborganda;
      * `manage.py telegram_poll` — lokal ishlashda va HTTPS hali
        yo'q paytda, Telegram dan xabar SO'RAB olinadi.

    Ikkalasi bir xil ishlashi SHART: aks holda lokalda ishlagan
    narsa serverda ishlamay qolardi yoki teskarisi.

    `True` qaytarsa — yangilanish tanildi va javob berildi.
    """
    message = update.get('message') or {}
    chat_id = (message.get('chat') or {}).get('id')
    text = (message.get('text') or '').strip()

    if not chat_id or not text.startswith('/start'):
        # Boshqa xabarlarga javob berilmaydi. Bot suhbatdosh emas —
        # u faqat xabarnoma yetkazadi.
        return False

    parts = text.split(maxsplit=1)
    token = parts[1] if len(parts) > 1 else ''

    if not token:
        # BOTNI BIRINCHI MARTA OCHGAN ODAM shu yerga tushadi: u
        # Telegram'dagi «Start» tugmasini bosadi va hech qanday
        # token bo'lmaydi. Ilgari unga "Havola eskirgan" deb javob
        # berilardi — u hech qanday havola ochmagan bo'lsa ham.
        send(
            chat_id,
            "👋 <b>Salom!</b>\n\n"
            "Bu bot to'lov rekvizitlari, tasdiq javobi va obuna "
            "eslatmalarini yetkazadi.\n\n"
            "Ulash uchun saytdagi <b>Profil</b> sahifasiga kiring va "
            "«Telegramni ulash» tugmasini bosing — havola shu yerga "
            "olib keladi."
        )
        return True

    user = consume_link_token(token, chat_id)

    if user:
        name = getattr(getattr(user, 'profile', None), 'full_name', '') or user.username
        send(
            chat_id,
            f"✅ <b>Hisob ulandi</b>\n\nSalom, {name}!\n\n"
            f"Endi to'lov rekvizitlari, tasdiq javobi va obuna "
            f"eslatmalari shu yerga keladi."
        )
    else:
        send(
            chat_id,
            "Havola eskirgan yoki allaqachon ishlatilgan.\n\n"
            "Saytdagi profil sahifasidan yangi havola oling."
        )
    return True
