import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
import services.backend_client as backend

from handlers import start, text, document, photo, payments, profile, menu_commands, voice, admin_tools  # <-- Добавили voice и admin_tools

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(menu_commands.router)
    dp.include_router(payments.router)
    dp.include_router(profile.router)
    dp.include_router(photo.router)
    dp.include_router(document.router)
    dp.include_router(voice.router)  # <--- Подключили голос
    dp.include_router(admin_tools.router)  # <--- Команды админа (/check_orders)
    dp.include_router(text.router)   # Текст должен быть последним, чтобы перехватывать остальное

    logging.info('Bot started!')
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await backend.close()
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())