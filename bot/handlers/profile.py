from aiogram import Router, F
from aiogram.types import Message
import services.backend_client as backend
from keyboards.reply import main_menu

router = Router()

@router.message(F.text == '👤 Профиль')
async def cmd_profile(message: Message):
    tg_id = message.from_user.id
    user_info = await backend.get_or_create_user(
        tg_id, message.from_user.username, message.from_user.full_name
    )
    
    plan = user_info.get('plan', 'free').capitalize()
    remaining = user_info.get('remaining', 0)
    limit = user_info.get('analyses_limit', 3)
    
    await message.answer(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🆔 ID: <code>{tg_id}</code>\n"
        f"💎 Тариф: <b>{plan}</b>\n"
        f"📊 Осталось анализов: <b>{remaining}</b> из <b>{limit}</b>\n\n"
        f"Чтобы продлить лимиты, нажмите «💎 Тарифы» и выберите подходящий тариф.",
        reply_markup=main_menu()
    )