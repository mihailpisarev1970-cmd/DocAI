import logging

from aiogram import Router
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message

import services.backend_client as backend
from keyboards.reply import main_menu

logger = logging.getLogger(__name__)

router = Router()


def _parse_referrer_id(payload: str | None) -> int | None:
    """Извлекает tg_id пригласившего из payload вида 'ref_123456789'."""
    if not payload:
        return None
    payload = payload.strip()
    if not payload.startswith('ref_'):
        return None
    raw = payload[4:]
    if not raw.isdigit():
        return None
    return int(raw)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    tg_id = message.from_user.id
    referrer_id = _parse_referrer_id(command.args)

    if referrer_id:
        logger.info(
            'Пользователь tg_id=%s пришёл по реферальной ссылке от tg_id=%s',
            tg_id, referrer_id,
        )

    user_data = await backend.get_or_create_user(
        tg_id=tg_id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        referrer_id=referrer_id,
    )

    plan = user_data.get('plan', 'free')
    remaining = user_data.get('remaining', 3)
    bonus = user_data.get('bonus_analyses', 0)

    text = (
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"Я DocAI — помогу разобраться в официальных документах.\n"
        f"Твой тариф: <b>{plan.capitalize()}</b> (осталось анализов: <b>{remaining}</b>).\n\n"
    )

    if user_data.get('created') and referrer_id:
        text += "🎁 Вы пришли по приглашению — спасибо, что заглянули!\n\n"

    if bonus:
        text += f"🎁 Бонусных анализов: <b>{bonus}</b>\n\n"

    text += "Используйте кнопки внизу экрана для навигации 👇"

    await message.answer(text, reply_markup=main_menu())
