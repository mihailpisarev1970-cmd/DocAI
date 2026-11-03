import io
from aiogram import Bot, Router, F
from aiogram.types import Message

import services.backend_client as backend
import services.ai_service as ai
from keyboards.reply import main_menu

router = Router()

@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot):
    tg_id = message.from_user.id

    # Проверка лимитов
    user_info = await backend.get_or_create_user(
        tg_id, message.from_user.username, message.from_user.full_name
    )
    if user_info.get('remaining', 0) <= 0:
        await message.answer(
            "⛔ <b>Анализы закончились!</b>\n\n"
            "Вы использовали все бесплатные анализы.\n"
            "Оформите подписку Personal, чтобы продолжить.",
            reply_markup=main_menu()
        )
        return

    status_msg = await message.answer('📸 Распознаю текст на фото, пожалуйста подождите...')

    try:
        # 1. Скачиваем фото из Telegram
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        
        buf = io.BytesIO()
        await bot.download_file(file.file_path, buf)
        image_bytes = buf.getvalue()

        # 2. Отправляем в Claude
        ai_response = await ai.analyze_image(image_bytes)

        # 3. Сохраняем и списываем лимит
        await backend.save_document(
            tg_id=tg_id,
            doc_type="Фото документа",
            summary="Распознавание фото",
            full_response=ai_response
        )
        inc_result = await backend.increment_usage(tg_id)

        # 4. Отправляем ответ
        await status_msg.delete()
        await message.answer(ai_response)
        
        rem = inc_result.get('remaining', 0)
        await message.answer(f"<i>Осталось анализов: {rem}</i>", parse_mode="HTML")

    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка при обработке фото: {e}")