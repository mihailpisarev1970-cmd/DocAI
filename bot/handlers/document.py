import io
import pymupdf as fitz
from docx import Document as DocxDocument
from aiogram import Bot, Router, F
from aiogram.types import Message

import services.backend_client as backend
import services.ai_service as ai
from keyboards.reply import main_menu

router = Router()

@router.message(F.document)
async def handle_document(message: Message, bot: Bot):
    tg_id = message.from_user.id
    doc = message.document
    file_name = doc.file_name.lower() if doc.file_name else ""

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

    status_msg = await message.answer('📄 Читаю документ...')

    try:
        file = await bot.get_file(doc.file_id)
        buf = io.BytesIO()
        await bot.download_file(file.file_path, buf)
        file_bytes = buf.getvalue()

        text = ""
        ai_response = ""

        # Обработка PDF (текстовые и сканы)
        if file_name.endswith('.pdf') or doc.mime_type == 'application/pdf':
            pdf = fitz.open(stream=file_bytes, filetype='pdf')
            
            for page in pdf:
                text += page.get_text()
            
            if len(text.strip()) > 50:
                await status_msg.edit_text('🔍 Анализирую текст PDF...')
                ai_response = await ai.analyze_text(text[:15000])
            else:
                await status_msg.edit_text('📄 PDF оказался сканом. Распознаю страницы через Vision (ИИ)...')
                pages_to_read = min(3, len(pdf))
                images_bytes = []
                for i in range(pages_to_read):
                    pix = pdf[i].get_pixmap(matrix=fitz.Matrix(2, 2))
                    images_bytes.append(pix.tobytes("png"))
                ai_response = await ai.analyze_images(images_bytes)
            
            pdf.close()

        # Обработка Word
        elif file_name.endswith('.docx') or 'wordprocessingml' in doc.mime_type:
            await status_msg.edit_text('🔍 Анализирую Word документ...')
            docx_file = DocxDocument(io.BytesIO(file_bytes))
            text = '\n'.join([para.text for para in docx_file.paragraphs])
            ai_response = await ai.analyze_text(text[:15000])

        # Обработка TXT
        elif file_name.endswith('.txt') or doc.mime_type == 'text/plain':
            await status_msg.edit_text('🔍 Анализирую TXT файл...')
            try:
                text = file_bytes.decode('utf-8')
            except UnicodeDecodeError:
                text = file_bytes.decode('windows-1251')
            ai_response = await ai.analyze_text(text[:15000])
        
        else:
            await status_msg.edit_text('❌ Этот формат не поддерживается. Отправьте PDF, Word (docx), TXT или фото.')
            return

        # Сохраняем и списываем
        await backend.save_document(
            tg_id=tg_id,
            doc_type=f"Файл {file_name.split('.')[-1].upper() if file_name else 'DOC'}",
            summary=text[:100] + "..." if text else "Анализ скана PDF",
            full_response=ai_response
        )
        inc_result = await backend.increment_usage(tg_id)

        # Отправляем ответ
        await status_msg.delete()
        await message.answer(ai_response)
        
        rem = inc_result.get('remaining', 0)
        await message.answer(f"<i>Осталось анализов: {rem}</i>", parse_mode="HTML")

    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка при обработке файла: {e}")