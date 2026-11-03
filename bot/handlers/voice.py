from aiogram import Bot, Router, F
from aiogram.types import Message
import io

import services.backend_client as backend
import services.ai_service as ai
from keyboards.reply import main_menu

router = Router()

@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot):
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

    status_msg = await message.answer('🎤 Слушаю и распознаю вашу речь...')

    try:
        # 1. Скачиваем аудио
        file = await bot.get_file(message.voice.file_id)
        buf = io.BytesIO()
        await bot.download_file(file.file_path, buf)
        
        # 2. Распознаем речь
        text = await ai.transcribe_voice(buf.getvalue(), "voice.ogg")
        
        if not text:
            await status_msg.edit_text("❌ Не удалось распознать речь. Попробуйте еще раз или напишите текстом.")
            return

        await status_msg.edit_text(f'🔍 Вы сказали: "{text}"\n\nАнализирую...')

        # 3. Отправляем текст в ИИ
        ai_response = await ai.analyze_text(text)

        # 4. Сохраняем и списываем
        await backend.save_document(
            tg_id=tg_id,
            doc_type="Голосовой запрос",
            summary=text[:100],
            full_response=ai_response
        )
        inc_result = await backend.increment_usage(tg_id)

        # 5. Отправляем ответ
        await status_msg.delete()
        await message.answer(ai_response)
        
        rem = inc_result.get('remaining', 0)
        await message.answer(f"<i>Осталось анализов: {rem}</i>", parse_mode="HTML")

    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка при обработке голоса: {e}")