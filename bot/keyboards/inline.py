from urllib.parse import quote

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def plan_selection_kb() -> InlineKeyboardMarkup:
    """Меню выбора тарифа"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='⭐ Personal (30 генераций) — 399 ₽', callback_data='pay_robokassa:personal')],
        [InlineKeyboardButton(text='👑 Business (Безлимит) — 1490 ₽/мес', callback_data='pay_robokassa:business')],
    ])


def payment_kb(url: str) -> InlineKeyboardMarkup:
    """Кнопка-ссылка для перехода на страницу оплаты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='💸 Перейти к оплате', url=url)],
    ])


def ref_share_kb(ref_link: str) -> InlineKeyboardMarkup:
    """Кнопка «Поделиться» для реферальной ссылки"""
    share_text = 'Попробуй DocAI — разбор документов за минуту. Моя ссылка:'
    share_url = (
        'https://t.me/share/url?url=' + quote(ref_link, safe='')
        + '&text=' + quote(share_text, safe='')
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📤 Поделиться с друзьями', url=share_url)],
    ])
