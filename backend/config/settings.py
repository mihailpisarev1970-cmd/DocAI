import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
# В тестовом окружении загрузку можно отключить флагом SKIP_DOTENV=1,
# чтобы не перетирать тестовые значения ROBOKASSA_*.
if os.getenv('SKIP_DOTENV') != '1':
    load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Безопасность и ключи ---
SECRET_KEY  = os.getenv('SECRET_KEY', 'django-insecure-change-me-in-production')
BOT_API_KEY = os.getenv('BOT_API_KEY', '')

# --- Robokassa ---
ROBOKASSA_LOGIN = os.getenv('ROBOKASSA_LOGIN', '')
ROBOKASSA_PASSWORD1 = os.getenv('ROBOKASSA_PASSWORD1', '')
ROBOKASSA_PASSWORD2 = os.getenv('ROBOKASSA_PASSWORD2', '')
# Пароль №3 нужен только если включено подтверждение ответа ResultURL подписью
# (формат OK{InvId}+SignatureValue). Также используется для Success/Fail URL.
ROBOKASSA_PASSWORD3 = os.getenv('ROBOKASSA_PASSWORD3', '')

# Тестовые пароли из блока «Тестовые настройки» личного кабинета Robokassa.
# Используются только если ROBOKASSA_USE_TEST_PASSWORDS=True.
ROBOKASSA_TEST_PASSWORD1 = os.getenv('ROBOKASSA_TEST_PASSWORD1', '')
ROBOKASSA_TEST_PASSWORD2 = os.getenv('ROBOKASSA_TEST_PASSWORD2', '')
ROBOKASSA_USE_TEST_PASSWORDS = os.getenv('ROBOKASSA_USE_TEST_PASSWORDS', 'False') == 'True'

# Алгоритм расчёта контрольной суммы из технических настроек магазина:
# MD5 | SHA1 | SHA256 | SHA512
ROBOKASSA_HASH_ALGORITHM = os.getenv('ROBOKASSA_HASH_ALGORITHM', 'MD5')

# Тестовый режим: добавляет IsTest=1 в платёжную ссылку.
ROBOKASSA_TEST_MODE = os.getenv('ROBOKASSA_TEST_MODE', 'True') == 'True'

# Публичный адрес бэкенда (нужен для SuccessURL/FailURL и ResultURL).
# На VPS: https://api.ваш-домен.ru
BACKEND_PUBLIC_URL = os.getenv('BACKEND_PUBLIC_URL', '').rstrip('/')

# Ссылка на бота — показывается пользователю после оплаты.
BOT_LINK = os.getenv('BOT_LINK', 'https://t.me/')

# Срок действия подписки в днях после успешной оплаты.
SUBSCRIPTION_PERIOD_DAYS = int(os.getenv('SUBSCRIPTION_PERIOD_DAYS', '30'))

# --- Фискализация (ФЗ-54) ---
# Передавать ли чек (Receipt) в Robokassa. Включать, если к магазину
# подключена онлайн-касса.
ROBOKASSA_SEND_RECEIPT = os.getenv('ROBOKASSA_SEND_RECEIPT', 'True') == 'True'
# Ставка НДС в чеке: none (без НДС), vat0, vat10, vat20, vat110, vat120
ROBOKASSA_RECEIPT_TAX = os.getenv('ROBOKASSA_RECEIPT_TAX', 'none')

# --- Реферальная программа ---
# Сколько бонусных анализов получает пригласивший после оплаты друга.
REFERRAL_BONUS_ANALYSES = int(os.getenv('REFERRAL_BONUS_ANALYSES', '30'))
# Сколько бонусных анализов получает приглашённый при регистрации по ссылке.
REFERRAL_WELCOME_BONUS = int(os.getenv('REFERRAL_WELCOME_BONUS', '0'))
# Максимум начислений одному пригласившему (0 = без ограничений).
REFERRAL_MAX_BONUSES = int(os.getenv('REFERRAL_MAX_BONUSES', '0'))

DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

# Защита запросов (включается на продакшене за nginx с HTTPS).
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = os.getenv('SECURE_COOKIES', 'True') == 'True'
    CSRF_COOKIE_SECURE = os.getenv('SECURE_COOKIES', 'True') == 'True'

# --- Логирование ---
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} [{levelname}] {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'backend.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'encoding': 'utf-8',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'api': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# --- Приложения ---
INSTALLED_APPS = [
    'jazzmin',                          # должен быть перед django.contrib.admin
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'config.wsgi.application'

# --- База данных ---
# По умолчанию PostgreSQL (продакшен). SQLite оставлен как fallback,
# если DB_ENGINE=sqlite3 — удобно для локальной разработки без Docker.
DB_ENGINE = os.getenv('DB_ENGINE', 'postgresql')

if DB_ENGINE == 'sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'docai'),
            'USER': os.getenv('DB_USER', 'docai'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'docai-db'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '60')),
            'CONN_HEALTH_CHECKS': True,
            'OPTIONS': {
                'connect_timeout': 10,
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- Локализация ---
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# --- Статика ---
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Django REST Framework ---
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['api.authentication.BotApiKeyAuthentication'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    # Robokassa присылает ResultURL как application/x-www-form-urlencoded,
    # поэтому кроме JSON нужен FormParser (иначе вебхук отбивается с 415).
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
}

# ─── Настройки Jazzmin (Админка) ──────────────────────────────────────────────

JAZZMIN_SETTINGS = {
    "site_title": "DocAI Admin",
    "site_header": "DocAI",
    "site_brand": "DocAI",
    "welcome_sign": "Добро пожаловать в панель управления DocAI",
    "copyright": "DocAI © 2026",
    "search_model": ["api.user", "api.document", "auth.user"],
    "topmenu_links": [
        {"name": "Главная",       "url": "admin:index"},
        {"name": "Пользователи",  "model": "api.user"},
        {"name": "Документы",     "model": "api.document"},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "order_with_respect_to": ["api", "auth"],
    "icons": {
        "auth":           "fas fa-shield-alt",
        "auth.user":      "fas fa-user-cog",
        "auth.group":     "fas fa-users",
        "api":            "fas fa-robot",
        "api.user":       "fas fa-user-circle",
        "api.document":   "fas fa-file-alt",
        "api.plan":       "fas fa-crown",
        "api.paymentlog": "fas fa-ruble-sign",
    },
    "default_icon_parents":  "fas fa-folder-open",
    "default_icon_children": "fas fa-dot-circle",
    "related_modal_active": True,
    "use_google_fonts_cdn": True,
    "changeform_format": "horizontal_tabs",
}

JAZZMIN_UI_TWEAKS = {
    "navbar":                     "navbar-white navbar-light",
    "navbar_fixed":               True,
    "sidebar_fixed":              True,
    "sidebar":                    "sidebar-dark-primary",
    "theme":                      "flatly",
    "actions_sticky_top":         True,
    "button_classes": {
        "primary":   "btn-primary",
        "secondary": "btn-outline-secondary",
        "info":      "btn-outline-info",
        "warning":   "btn-warning",
        "danger":    "btn-danger",
        "success":   "btn-success",
    },
}