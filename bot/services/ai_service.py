import base64
import logging
from io import BytesIO
from PIL import Image
import imageio_ffmpeg # <-- Импортируем для поиска ffmpeg
from pydub import AudioSegment
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

logger = logging.getLogger(__name__)

# Подключаемся к AIDostup
_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL 
)

# Указываем pydub, где искать ffmpeg (берем системный)
AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()

_SYSTEM_PROMPT = """\
Ты — опытный юрист-эксперт по договорам и официальным документам (DocAI). 
Твоя задача — провести детальный анализ документа, выявить скрытые риски, невыгодные условия и дать практические советы по защите интересов клиента.

Если пользователь задает короткий вопрос (например, "Что такое неустойка?"), отвечай кратко и по делу, как юрист. Не нужно использовать полную структуру анализа документа, если это просто вопрос.

Формат ответа на ДОКУМЕНТ строго такой:

📄 <b>Тип документа</b>
[Краткое название документа]

📋 <b>Суть документа</b>
[2-3 предложения, объясняющие, о чем вообще этот документ и какие главные обязательства он накладывает.]

🔴 <b>Главные риски и опасные пункты</b>
[Найди 2-4 пункта, которые наиболее опасны для человека, подписывающего документ (например: огромные штрафы, односторонний отказ, скрытые комиссии).]

🟢 <b>Что здесь хорошо (плюсы для вас)</b>
[Если в договоре есть адекватные условия — похвали их. Если плюсов нет, напиши "Явных плюсов не обнаружено".]

⚖️ <b>Что нужно исправить или уточнить</b>
1. [Конкретный пункт, который нужно поменять]
2. [Что нужно потребовать у второй стороны]

💡 <b>Совет юриста</b>
[Один самый важный практический совет по этому документу.]

---
<i>DocAI — информационный анализ, не является официальной юридической консультацией.</i>
"""

async def analyze_text(text: str) -> str:
    """Анализирует обычный текст или вопрос"""
    response = await _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user', 'content': text},
        ],
        max_tokens=2000,
    )
    return response.choices[0].message.content

async def analyze_image(image_bytes: bytes) -> str:
    """Анализирует одно фото документа"""
    return await analyze_images([image_bytes])

async def analyze_images(images_bytes: list[bytes]) -> str:
    """Анализирует несколько картинок (например, страницы скана PDF)"""
    content = [{'type': 'text', 'text': 'Проанализируй этот документ как юрист. Найди риски и дай советы.'}]
    
    for img_bytes in images_bytes:
        try:
            img = Image.open(BytesIO(img_bytes))
            img_format = img.format.lower() if img.format else 'jpeg'
            if img_format not in ['jpeg', 'png', 'webp', 'gif']:
                img_format = 'jpeg'
        except Exception:
            img_format = 'jpeg'

        b64_image = base64.b64encode(img_bytes).decode('utf-8')
        image_url = f"data:image/{img_format};base64,{b64_image}"
        
        content.append({
            'type': 'image_url', 
            'image_url': {'url': image_url}
        })

    response = await _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user', 'content': content},
        ],
        max_tokens=2000,
    )
    return response.choices[0].message.content

async def transcribe_voice(audio_bytes: bytes, filename: str) -> str:
    """Распознает речь, конвертируя OGG в WAV для совместимости с gpt-4o-transcribe"""
    try:
        # 1. Конвертируем OGG (из Telegram) в WAV
        audio = AudioSegment.from_file(BytesIO(audio_bytes), format="ogg")
        
        # Экспортируем в WAV в тот же буфер
        wav_buffer = BytesIO()
        audio.export(wav_buffer, format="wav")
        wav_bytes = wav_buffer.getvalue()

        # 2. Отправляем уже WAV в AIDostup
        file_tuple = ("voice.wav", wav_bytes)
        
        response = await _client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=file_tuple,
            language="ru"
        )
        return response.text
    except Exception as e:
        logger.exception('Ошибка распознавания речи: %s', e)
        return ""