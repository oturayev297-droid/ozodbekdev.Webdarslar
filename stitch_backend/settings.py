"""
Django settings for stitch_backend project.

Maxfiy qiymatlar .env faylidan o'qiladi (django-environ).
Namuna uchun .env.example ga qarang.
"""

from pathlib import Path

import environ

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
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'core',
    'billing',
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "landing"


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
    CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1")]


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
