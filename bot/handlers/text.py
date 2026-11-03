from aiogram import Router, F
from aiogram.types import Message
import services.backend_client as backend
import services.ai_service as ai
from keyboards.reply import main_menu

router = Router()

@router.message(F.text)
async def handle_text(message: Message):
    # Пропускаем команды и нажатия на кнопки меню
    menu_texts = ['📤 Отправить документ', '👤 Профиль', '💎 Тарифы', '👥 Реферальная программа', '📖 Инструкция']
    if message.text.startswith('/') or message.text in menu_texts:
        return

    tg_id = message.from_user.id

    # Проверка лимитов
    user_info = await backend.get_or_create_user(
        tg_id, message.from_user.username, message.from_user.full_name
    )
    if user_info.get('remaining', 0) <= 0:
        await message.answer(
            "⛔ <b>Анализы закончились!</b>\n\n"
            "Оформите подписку Personal, чтобы продолжить.",
            reply_markup=main_menu()
        )
        return

    status_msg = await message.answer("🔍 Анализирую...")

    try:
        ai_response = await ai.analyze_text(message.text)

        await backend.save_document(
            tg_id=tg_id,
            doc_type="Текстовый запрос",
            summary=message.text[:100],
            full_response=ai_response
        )
        inc_result = await backend.increment_usage(tg_id)

        await status_msg.delete()
        await message.answer(ai_response)
        
        rem = inc_result.get('remaining', 0)
        await message.answer(f"<i>Осталось анализов: {rem}</i>", parse_mode="HTML")

    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")