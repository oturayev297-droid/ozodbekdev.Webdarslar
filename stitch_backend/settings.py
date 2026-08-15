"""
Django settings for stitch_backend project.

Maxfiy qiymatlar .env faylidan o'qiladi (django-environ).
Namuna uchun .env.example ga qarang.
"""

import sys
from pathlib import Path

import environ
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    DATABASE_URL=(str, ""),
    USE_X_ACCEL_REDIRECT=(bool, False),
    EMAIL_HOST=(str, "smtp.gmail.com"),
    EMAIL_PORT=(int, 587),
    EMAIL_HOST_USER=(str, ""),
    EMAIL_HOST_PASSWORD=(str, ""),
    DEFAULT_FROM_EMAIL=(str, ""),
    TELEGRAM_BOT_TOKEN=(str, ""),
    TELEGRAM_BOT_USERNAME=(str, ""),
    TELEGRAM_ADMIN_CHAT_IDS=(list, []),
    PAYME_MERCHANT_ID=(str, ""),
    PAYME_KEY=(str, ""),
    PAYME_ACCOUNT_FIELD=(str, "order_id"),
    CLICK_SERVICE_ID=(str, ""),
    CLICK_MERCHANT_ID=(str, ""),
    CLICK_SECRET_KEY=(str, ""),
    ANTHROPIC_API_KEY=(str, ""),
    ANTHROPIC_MODEL=(str, "claude-opus-5"),
    ANTHROPIC_EFFORT=(str, "low"),
    FRONTEND_ORIGINS=(list, []),
    FRONTEND_URL=(str, ""),
    VIDEO_STORAGE_BUCKET=(str, ""),
    VIDEO_STORAGE_ENDPOINT=(str, ""),
    VIDEO_STORAGE_ACCESS_KEY=(str, ""),
    VIDEO_STORAGE_SECRET_KEY=(str, ""),
    VIDEO_STORAGE_REGION=(str, "auto"),
)
environ.Env.read_env(BASE_DIR / ".env")


# --------------------------------------------------------------------------
# Asosiy
# --------------------------------------------------------------------------

SECRET_KEY = env("DJANGO_SECRET_KEY")

DEBUG = env("DJANGO_DEBUG")

ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# Himoyalangan videolarni nginx uzatsinmi (production) yoki Django (lokal)
USE_X_ACCEL_REDIRECT = env("USE_X_ACCEL_REDIRECT")


# --------------------------------------------------------------------------
# Ilovalar
# --------------------------------------------------------------------------

INSTALLED_APPS = [
    # `django.contrib.admin` OLIB TASHLANDI — uning o'rnini `/panel/`
    # egalladi. `contenttypes` va `auth` qoladi: ular admin uchun
    # emas, foydalanuvchi va huquqlar tizimi uchun kerak.
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'rest_framework',
    'corsheaders',
    'core',
    'billing',
    'panel',
    'api',
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # CORS eng tepada — CommonMiddleware javobni qaytarib yuborishidan
    # OLDIN sarlavhalarni qo'shishi kerak, aks holda redirect va xato
    # javoblarda CORS sarlavhasi bo'lmaydi va brauzer ularni bloklaydi.
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "stitch_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        'DIRS': [BASE_DIR / 'templates'],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "billing.gating.subscription_context",
                "panel.context.panel_badges",
            ],
        },
    },
]

WSGI_APPLICATION = "stitch_backend.wsgi.application"


# --------------------------------------------------------------------------
# Baza — DATABASE_URL berilsa PostgreSQL, aks holda SQLite
# --------------------------------------------------------------------------

if env("DATABASE_URL"):
    DATABASES = {"default": env.db("DATABASE_URL")}
    DATABASES["default"]["CONN_MAX_AGE"] = 60
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# --------------------------------------------------------------------------
# Parol validatsiyasi
# --------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# O'QUVCHI SAHIFALARI ENDI REACT FRONTENDDA.
#
# `LOGIN_URL` faqat panel uchun kerak: `@login_required` uni
# ishlatadi. Panelning o'z kirish sahifasi bor va u `staff_required`
# bilan himoyalangan, lekin Django ba'zi hollarda (masalan
# `login_required` bilan bezatilgan fayl uzatish ko'rinishlari)
# baribir shu manzilga yo'naltiradi.
LOGIN_URL = "panel:login"


# --------------------------------------------------------------------------
# Til va vaqt
# --------------------------------------------------------------------------

LANGUAGE_CODE = "uz"

TIME_ZONE = "Asia/Tashkent"

USE_I18N = True

USE_TZ = True


# --------------------------------------------------------------------------
# Statik va media fayllar
# --------------------------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Yuklanadigan fayl uchun maksimal hajm (RAM da ushlanadigan qism)
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------------------------------
# Email — parolni tiklash kodlari uchun
# --------------------------------------------------------------------------
#
# SMTP sozlanmagan bo'lsa CONSOLE rejimi: xat terminalga chiqadi,
# tashqariga hech narsa ketmaydi. Lokal ishlab chiqishda kodni shu
# yerdan o'qib olasiz.
#
# GMAIL UCHUN: oddiy hisob paroli ISHLAMAYDI. 2FA yoqilgan bo'lishi va
# "App password" (16 belgi) yaratilishi shart:
#   https://myaccount.google.com/apppasswords

EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env("EMAIL_PORT")
# App password'da Google bo'shliq bilan ko'rsatadi — nusxalaganda ular qolib ketadi
EMAIL_HOST_USER = env("EMAIL_HOST_USER").strip()
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD").replace(" ", "")
EMAIL_USE_TLS = EMAIL_PORT == 587
EMAIL_USE_SSL = EMAIL_PORT == 465
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL") or EMAIL_HOST_USER or "noreply@localhost"

EMAIL_CONFIGURED = bool(EMAIL_HOST_USER and EMAIL_HOST_PASSWORD)
if EMAIL_CONFIGURED:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# --------------------------------------------------------------------------
# Telegram — to'lov xabarnomalari
# --------------------------------------------------------------------------
#
# Token bo'sh bo'lsa MOCK rejim: hech qayerga so'rov ketmaydi, xabar
# matni logga yoziladi. Bot @BotFather orqali yaratiladi.
#
# TELEGRAM_ADMIN_CHAT_IDS — to'lov so'rovlari haqida xabar oladigan
# adminlar. O'z chat ID ingizni bilish uchun botga /start yozing va
# logga qarang, yoki @userinfobot dan so'rang.

TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN").strip()
TELEGRAM_BOT_USERNAME = env("TELEGRAM_BOT_USERNAME").strip().lstrip('@')
TELEGRAM_ADMIN_CHAT_IDS = [str(x).strip() for x in env("TELEGRAM_ADMIN_CHAT_IDS") if str(x).strip()]

#: Webhook manzilidagi maxfiy qism — tashqi so'rovlar bot nomidan
#: soxta xabar yubora olmasligi uchun. Bo'sh bo'lsa webhook yopiq.
TELEGRAM_WEBHOOK_SECRET = env.str("TELEGRAM_WEBHOOK_SECRET", default="")


# --------------------------------------------------------------------------
# To'lov tizimlari (Payme, Click)
# --------------------------------------------------------------------------
#
# Kalitlar bo'sh bo'lsa tugmalar KO'RINMAYDI va qo'lda tasdiqlash oqimi
# ishlaydi. Avtomatik to'lov qo'shimcha, o'rnini bosuvchi emas.
#
# DIQQAT — BIRLIKLAR HAR XIL:
#   Payme summani TIYINDA yuboradi (bizning amount_tiyin bilan bir xil)
#   Click  summani SO'MDA yuboradi (kasrli son)
# Shu sabab ikkalasi alohida modulda.

PAYME_MERCHANT_ID = env("PAYME_MERCHANT_ID").strip()
PAYME_KEY = env("PAYME_KEY").strip()
#: Payme kabinetida sozlangan maydon nomi (bizda — to'lov so'rovi raqami)
PAYME_ACCOUNT_FIELD = env("PAYME_ACCOUNT_FIELD").strip() or "order_id"

CLICK_SERVICE_ID = env("CLICK_SERVICE_ID").strip()
CLICK_MERCHANT_ID = env("CLICK_MERCHANT_ID").strip()
CLICK_SECRET_KEY = env("CLICK_SECRET_KEY").strip()


# --------------------------------------------------------------------------
# AI Mentor (Claude API)
# --------------------------------------------------------------------------
#
# Kalit bo'sh bo'lsa chat sozlanmagan xabarini beradi va modelga so'rov
# ketmaydi — sayt buzilmaydi.
#
# EFFORT: dasturlash tushunchasini tushuntirish chuqur fikrlashni talab
# qilmaydi, shuning uchun standart "low" — javob tez keladi va arzon.
# Murakkabroq javob kerak bo'lsa "medium" qiling.

ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY").strip()
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL").strip() or "claude-opus-5"
ANTHROPIC_EFFORT = env("ANTHROPIC_EFFORT").strip() or "low"


# --------------------------------------------------------------------------
# Xavfsizlik — faqat productionda (DEBUG=False) yoqiladi
# --------------------------------------------------------------------------

SESSION_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 2 hafta
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 kun
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    # O'z domenlarimiz qo'shiladi. Frontend manzillari yuqorida
    # allaqachon kiritilgan — ular ustiga YOZILMAYDI.
    CSRF_TRUSTED_ORIGINS += [
        f"https://{h}" for h in ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1")
    ]


# --------------------------------------------------------------------------
# Video ombori — S3 mos bulut (Cloudflare R2, AWS S3, Backblaze B2)
# --------------------------------------------------------------------------
#
# BO'SH BO'LSA ESKI YO'L ISHLAYDI: nginx X-Accel-Redirect yoki lokal
# fayl. Ya'ni bu sozlama QO'SHIMCHA, o'rnini bosuvchi emas — mavjud
# server hech narsa o'zgartirmasdan ishlashda davom etadi.
#
# NEGA KERAK: Railway va shunga o'xshash platformalarda fayl tizimi
# vaqtinchalik (har deployda o'chadi) va nginx yo'q. 5 GB video u yerda
# yashay olmaydi.
#
# R2 UCHUN endpoint: https://<account_id>.r2.cloudflarestorage.com
# Bucket OCHIQ BO'LMASLIGI kerak — kirish faqat imzolangan havola bilan.

VIDEO_STORAGE_BUCKET = env("VIDEO_STORAGE_BUCKET").strip()
VIDEO_STORAGE_ENDPOINT = env("VIDEO_STORAGE_ENDPOINT").strip().rstrip('/')
VIDEO_STORAGE_ACCESS_KEY = env("VIDEO_STORAGE_ACCESS_KEY").strip()
VIDEO_STORAGE_SECRET_KEY = env("VIDEO_STORAGE_SECRET_KEY").strip()
VIDEO_STORAGE_REGION = env("VIDEO_STORAGE_REGION").strip()


# --------------------------------------------------------------------------
# REST API — alohida deploy qilinadigan frontend uchun
# --------------------------------------------------------------------------
#
# AUTENTIFIKATSIYA — SESSIYA COOKIE, token emas.
#
# Token localStorage da saqlanadi va sahifadagi HAR QANDAY skript uni
# o'qiy oladi. Sessiya cookie esa `HttpOnly` — JavaScript unga umuman
# yeta olmaydi. Bu XSS ning eng og'ir oqibatini (hisobni butunlay
# o'g'irlash) yo'qotadi.
#
# BUNING NARXI: cookie ishlashi uchun frontend va backend BIR XIL
# saytdan ko'rinishi kerak. Vercel'da buni `rewrites` hal qiladi:
#
#     /api/*  ->  https://<railway-domeni>/api/*
#
# Shunda brauzer uchun cookie BIRINCHI TOMON bo'lib qoladi va Safari
# ning uchinchi tomon cookie bloklashiga tushmaydi. Boshqa yo'l —
# `SameSite=None` — Safari va iOS da ishonchsiz.

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        # FAIL CLOSED: yangi manzil huquq belgilashni unutsa ham
        # ochiq qolmaydi.
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Anonim so'rovlar: login va parol tiklashni bombardimon
        # qilishdan himoya. Ichkaridagi cheklovlar (`core.lockout`,
        # `ai_mentor`) bundan MUSTAQIL ishlaydi.
        "anon": "60/min",
    },
}

# DEBUG da brauzerda ochib ko'rish qulay bo'lsin
if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append(
        "rest_framework.renderers.BrowsableAPIRenderer"
    )

# TESTDA CHEKLOV O'CHIRILADI.
#
# DRF cheklovi holatni KESHDA saqlaydi, kesh esa testlar orasida
# tozalanmaydi — bir necha yuz test ketma-ket ishlaganda hisob
# to'lib, ALOQASI YO'Q testlar 429 bilan yiqila boshlaydi. Bunday
# yiqilish chalg'ituvchi: kodda hech narsa buzilmagan.
#
# Cheklovning O'ZI `api/tests.py` da alohida sinaladi.
if "test" in sys.argv:
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"anon": None}

# Frontend manzillari: "https://oson.vercel.app,https://oson.uz"
FRONTEND_ORIGINS = [o.strip().rstrip('/') for o in env("FRONTEND_ORIGINS") if o.strip()]
FRONTEND_URL = env("FRONTEND_URL").strip().rstrip('/')

# NUSXA, ishora emas: `+=` ro'yxatni JOYIDA o'zgartiradi va ikkalasi
# bir obyekt bo'lsa, quyidagi lokal manzillar FRONTEND_ORIGINS ga ham
# yopishib qolardi.
CORS_ALLOWED_ORIGINS = list(FRONTEND_ORIGINS)
# Cookie yuborilishi uchun MAJBURIY. Busiz brauzer sessiyani
# jo'natmaydi va har so'rov 403 bo'lardi.
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + ["x-csrftoken"]

if DEBUG:
    # Lokal frontend (Vite 5173, Next 3000)
    CORS_ALLOWED_ORIGINS += [
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5173", "http://127.0.0.1:5173",
    ]

# ─── CSRF ISHONCHLI MANZILLARI ───
#
# Django 4 dan boshlab POST so'rovda `Origin` sarlavhasi shu ro'yxat
# bilan solishtiriladi. Frontend BOSHQA PORTDA yoki boshqa domenda
# tursa, u bu yerda bo'lishi SHART — aks holda har bir kirish, har bir
# forma "CSRF Failed: Origin checking failed" bilan rad etiladi.
#
# Bu ro'yxat DEBUG da ham kerak: lokal frontend :3000 da, backend
# :8000 da ishlaydi va brauzer uchun bu ikki xil manba.
CSRF_TRUSTED_ORIGINS = list(FRONTEND_ORIGINS)

if DEBUG:
    CSRF_TRUSTED_ORIGINS += [
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:8000", "http://127.0.0.1:8000",
    ]


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

(BASE_DIR / "logs").mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console", "file"],
            "level": "ERROR",
            "propagate": False,
        },
        "core": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
