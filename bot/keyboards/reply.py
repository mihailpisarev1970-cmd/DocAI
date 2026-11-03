from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='📤 Отправить документ')],
            [
                KeyboardButton(text='👤 Профиль'),
                KeyboardButton(text='💎 Тарифы'),
            ],
            [
                KeyboardButton(text='👥 Реферальная программа'),
                KeyboardButton(text='📖 Инструкция'), # <-- Изменили кнопку
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder='Фото, PDF или текст документа…',
    )