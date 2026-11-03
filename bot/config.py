import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
BACKEND_URL: str = os.getenv('BACKEND_URL', 'http://127.0.0.1:8000')
BOT_API_KEY: str = os.getenv('BOT_API_KEY', '')

OPENAI_API_KEY: str = os.getenv('OPENAI_API_KEY', '')
OPENAI_BASE_URL: str = os.getenv('OPENAI_BASE_URL', 'https://aidostup.site/v1')
OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', 'claude-opus-5-5')

# Ожидание подтверждения оплаты от Robokassa
PAYMENT_POLL_TIMEOUT: int = int(os.getenv('PAYMENT_POLL_TIMEOUT', '180'))
PAYMENT_POLL_INTERVAL: int = int(os.getenv('PAYMENT_POLL_INTERVAL', '5'))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in .env")
if not BOT_API_KEY:
    raise ValueError("BOT_API_KEY is not set in .env")