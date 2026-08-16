"""
Botni webhooksiz ishga tushiradi.

MUAMMO. Telegram webhook uchun OCHIQ HTTPS manzil talab qiladi —
`127.0.0.1` ga u yeta olmaydi va `http://` ni qabul qilmaydi. Ya'ni
deploydan oldin webhook o'rnatib bo'lmaydi va bot jim turadi.

YECHIM. Bu buyruq teskarisini qiladi: Telegram bizga yubormaydi,
BIZ undan so'rab turamiz (`getUpdates`). Hech qanday ochiq manzil,
tunnel yoki sertifikat kerak emas — kompyuter shunchaki chiqishga
so'rov yuboradi.

    python manage.py telegram_poll

XABARLAR WEBHOOK BILAN BIR XIL QAYTA ISHLANADI: ikkalasi ham
`telegram.handle_update` ni chaqiradi. Aks holda lokalda ishlagan
narsa serverda ishlamay qolardi.

QACHON QAYSI BIRI:

    telegram_poll  — lokal ishlash va HTTPS hali yo'q payt.
                     Jarayon doim ishlab turishi kerak.
    webhook        — production. Jarayon kerak emas, Telegram
                     o'zi yuboradi va bu tezroq hamda arzonroq.

IKKALASI BIR VAQTDA ISHLAMAYDI — Telegram webhook o'rnatilgan
bo'lsa `getUpdates` ga 409 xato beradi. Shuning uchun buyruq avval
webhookni tekshiradi va kerak bo'lsa o'chirishni taklif qiladi.
"""

import json
import logging
import signal
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from billing import telegram

logger = logging.getLogger(__name__)

#: Telegram so'rovni shuncha soniya USHLAB TURADI, agar yangilanish
#: bo'lmasa. Uzun so'rov ("long polling") — shuning uchun bo'sh
#: sikl aylanmaydi va tarmoq bekorga band bo'lmaydi.
LONG_POLL_SECONDS = 25

#: Tarmoq uzilganda shuncha kutib qayta urinadi.
RETRY_SECONDS = 5

API = "https://api.telegram.org/bot{token}/{method}"


def call(method: str, **params):
    """Telegram API ga so'rov. Xato bo'lsa `TelegramApiError`."""
    url = API.format(token=settings.TELEGRAM_BOT_TOKEN, method=method)
    if params:
        url += '?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=LONG_POLL_SECONDS + 10) as response:
        return json.load(response)


class Command(BaseCommand):
    help = "Telegram botni webhooksiz ishga tushiradi (lokal ishlash uchun)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--drop-webhook', action='store_true',
            help="Webhook o'rnatilgan bo'lsa uni o'chiradi",
        )
        parser.add_argument(
            '--once', action='store_true',
            help="Kutayotgan xabarlarni bir marta olib chiqadi va to'xtaydi",
        )

    def handle(self, *args, **options):
        if not telegram.is_configured():
            raise CommandError(
                "TELEGRAM_BOT_TOKEN bo'sh. Botni @BotFather da yarating "
                "va tokenni .env ga yozing."
            )

        me = call('getMe').get('result', {})
        self.stdout.write(self.style.SUCCESS(
            f"Bot: @{me.get('username')} ({me.get('first_name')})"
        ))

        # ── Webhook bilan birga ishlamaydi ──
        hook = call('getWebhookInfo').get('result', {})
        if hook.get('url'):
            if not options['drop_webhook']:
                raise CommandError(
                    "Webhook o'rnatilgan — Telegram bir vaqtda ikkalasiga "
                    "ruxsat bermaydi.\n"
                    "  * Serverda ishlayotgan bo'lsa bu buyruq kerak emas.\n"
                    "  * Lokal sinash uchun: --drop-webhook qo'shing "
                    "(keyin serverda qaytadan o'rnatasiz)."
                )
            call('deleteWebhook')
            self.stdout.write(self.style.WARNING("Webhook o'chirildi."))

        self._running = True

        def stop(_signum, _frame):
            # Ctrl+C bosilganda joriy so'rov tugagach chiqamiz —
            # yarim qayta ishlangan yangilanish qolmasin.
            self._running = False
            self.stdout.write("\nTo'xtatilmoqda...")

        signal.signal(signal.SIGINT, stop)

        link = f"https://t.me/{me.get('username')}"
        self.stdout.write(
            f"Tinglanmoqda. O'quvchilar {link} ga kirib profilidagi "
            f"havoladan hisobini ulaydi.\nTo'xtatish: Ctrl+C\n"
        )

        offset = None
        handled = 0

        while self._running:
            try:
                params = {'timeout': LONG_POLL_SECONDS}
                if offset is not None:
                    params['offset'] = offset
                data = call('getUpdates', **params)
            except urllib.error.HTTPError as exc:
                # 409 — webhook qayta o'rnatilgan
                self.stderr.write(f"Telegram xatosi: {exc.code}")
                time.sleep(RETRY_SECONDS)
                continue
            except Exception as exc:                      # tarmoq uzilishi
                self.stderr.write(f"Tarmoq xatosi: {exc}")
                time.sleep(RETRY_SECONDS)
                continue

            updates = data.get('result') or []
            for update in updates:
                # OFFSET HAR DOIM SURILADI, hatto qayta ishlashda xato
                # bo'lsa ham: aks holda bitta buzuq xabar botni abadiy
                # o'sha yerda ushlab turardi.
                offset = update['update_id'] + 1
                try:
                    processed = telegram.handle_update(update)
                except Exception:
                    logger.exception("[TELEGRAM] Yangilanish qayta ishlanmadi")
                    continue

                if not processed:
                    continue
                handled += 1

                # FAQAT RAQAM CHIQARILADI, ism emas.
                #
                # Ism Telegram foydalanuvchisi yozgan matn va unda
                # istalgan belgi bo'lishi mumkin. Windows konsoli
                # cp1251 da ishlaganda uni chiqarib bo'lmaydi va
                # buyruq `UnicodeEncodeError` bilan yiqilardi —
                # xabar qayta ishlangan bo'lsa ham. Ya'ni begona
                # odamning ismi butun botni to'xtatib qo'yardi.
                chat_id = ((update.get('message') or {}).get('chat') or {}).get('id')
                self.stdout.write(f"  xabar qayta ishlandi -> chat {chat_id}")

            if options['once']:
                break

        self.stdout.write(self.style.SUCCESS(
            f"To'xtadi. Qayta ishlangan: {handled} ta"
        ))
