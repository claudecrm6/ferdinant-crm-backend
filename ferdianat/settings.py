import dj_database_url
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-8+k$-y13*x@1s+zp&t+8f921-si=0=oe(q9!@tap)i^_t%6%1!',
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.environ.get(
    'DJANGO_ALLOWED_HOSTS',
    '.railway.app'
).split(',')


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ferdianat.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, '..', 'frontend')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ferdianat.wsgi.application'

# PostgreSQL (Railway) — SQLite fallback local uchun
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = []

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===================== RATE LIMITING =====================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

CORS_ALLOWED_ORIGINS = os.environ.get(
    'DJANGO_CORS_ORIGINS',
    'https://ferdinant-crm-frontend.netlify.app'
).split(',')

# Frontend boshqa domenda (Netlify) turgani uchun cookie cross-site yuboriladi —
# buning uchun brauzer talabiga ko'ra CORS so'rovlarida credentials (cookie)
# yuborilishiga ruxsat berishimiz kerak. CORS_ALLOWED_ORIGINS yuqorida qat'iy
# ro'yxat bilan cheklangani uchun bu xavfsiz (wildcard "*" EMAS).
CORS_ALLOW_CREDENTIALS = True

# ===================== AUTH COOKIE (httpOnly session token) =====================
# Token endi frontendga umuman yuborilmaydi/JS orqali o'qilmaydi — faqat
# httpOnly cookie sifatida saqlanadi. Shu bilan XSS orqali token o'g'irlash
# imkoni yo'qoladi.
AUTH_COOKIE_NAME = 'crm_session'
# Railway'da HTTPS ostida ishlaydi — production'da har doim Secure bo'lsin.
# Faqat lokal (http://localhost) DEBUG rejimida Secure=False qilamiz, aks holda
# brauzer cookie'ni umuman o'rnatmaydi.
AUTH_COOKIE_SECURE = not DEBUG
# Frontend (Netlify) va backend (Railway) turli domenlarda bo'lgani uchun
# cross-site cookie kerak — buning uchun SameSite=None va Secure=True shart.
AUTH_COOKIE_SAMESITE = 'None' if not DEBUG else 'Lax'
AUTH_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 kun

# ===================== TELEGRAM — QARZDORLIK ESLATMALARI =====================
# Frontendda (auth-guard.js) ishlatilayotgan bot bilan bir xil bot ishlatiladi.
# Xavfsizroq bo'lishi uchun bularni Railway/Heroku'da environment variable
# sifatida sozlash tavsiya etiladi (TELEGRAM_BOT_TOKEN, TELEGRAM_GROUP_CHAT_ID).
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
# Qarzdorlar ro'yxati va ogohlantirishlar yuboriladigan umumiy chat/guruh.
TELEGRAM_GROUP_CHAT_ID = os.environ.get('TELEGRAM_GROUP_CHAT_ID', '-1001827066150')

# Login/logout kabi tizim eventlari GURUHGA emas, shu shaxsiy chat_id'larga
# (vergul bilan ajratilgan) yuboriladi. Railway/Heroku'da
# TELEGRAM_ADMIN_CHAT_IDS="5538148203,8629268614" kabi env variable orqali
# ham sozlash mumkin.
TELEGRAM_ADMIN_CHAT_IDS = [
    cid.strip()
    for cid in os.environ.get('TELEGRAM_ADMIN_CHAT_IDS', '5538148203,8629268614').split(',')
    if cid.strip()
]

RATELIMIT_VIEW = 'api.views.ratelimited_error'