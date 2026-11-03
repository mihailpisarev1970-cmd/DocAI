"""Настройки для запуска тестов Robokassa локально:
реальные ключи магазина не нужны — подставляем тестовые значения.
"""
import os

# Отключаем чтение backend/.env, чтобы тестовые значения не перетирались.
os.environ['SKIP_DOTENV'] = '1'

# Важно: переменные должны быть установлены ДО импорта config.settings,
# потому что settings.py читает их через os.getenv на этапе импорта.
os.environ['ROBOKASSA_LOGIN'] = 'test_shop'
os.environ['ROBOKASSA_PASSWORD1'] = 'test_pass1'
os.environ['ROBOKASSA_PASSWORD2'] = 'test_pass2'
os.environ['ROBOKASSA_HASH_ALGORITHM'] = 'MD5'
os.environ['ROBOKASSA_TEST_MODE'] = 'True'
os.environ['ROBOKASSA_USE_TEST_PASSWORDS'] = 'False'
os.environ['ROBOKASSA_TEST_PASSWORD1'] = ''
os.environ['ROBOKASSA_TEST_PASSWORD2'] = ''
os.environ['BOT_API_KEY'] = 'test-bot-api-key'

from config.settings import *  # noqa: F401,F403,E402

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
