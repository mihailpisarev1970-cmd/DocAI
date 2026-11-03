import logging
import os

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

import services.backend_client as backend

logger = logging.getLogger(__name__)

router = Router()

# Кому доступна сверка платежей: tg_id через запятую в ADMIN_TG_IDS
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv('ADMIN_TG_IDS', '238583074').split(',')
    if x.strip().isdigit()
}


def _is_admin(tg_id: int) -> bool:
    return tg_id in ADMIN_IDS


@router.message(Command('check_orders'))
async def cmd_check_orders(message: Message):
    """Сверяет неоплаченные заказы с Robokassa. Только для админа."""
    tg_id = message.from_user.id
    if not _is_admin(tg_id):
        return

    status = await message.answer("🔄 Проверяю заказы в Robokassa...")

    try:
        data = await backend.reconcile_all_pending(hours=72)
    except Exception:
        logger.exception('Ошибка сверки платежей')
        await status.edit_text("❌ Не удалось выполнить сверку. Попробуйте позже.")
        return

    checked = data.get('checked', 0)
    activated = data.get('activated', 0)
    results = data.get('results', [])

    if checked == 0:
        await status.edit_text("✅ Неоплаченных заказов за последние 72 часа нет.")
        return

    lines = [
        f"🔍 <b>Сверка платежей</b>\n",
        f"Проверено: <b>{checked}</b>",
        f"Активировано: <b>{activated}</b>\n",
    ]

    for r in results:
        inv = r.get('inv_id', '?')
        amount = r.get('amount', '?')
        st = r.get('status')
        msg = r.get('message', '')

        if st == 'activated':
            icon = '✅'
        elif st == 'not_paid':
            icon = '⏳'
        else:
            icon = '⚠️'

        lines.append(f"{icon} #{inv} — {amount} ₽\n   {msg}")

    await status.edit_text("\n".join(lines))


@router.message(Command('reconcile'))
async def cmd_reconcile(message: Message):
    """Сверка конкретного заказа: /reconcile 793686596"""
    tg_id = message.from_user.id
    if not _is_admin(tg_id):
        return

    parts = (message.text or '').split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Использование: <code>/reconcile 793686596</code>")
        return

    inv_id = int(parts[1].strip())
    status = await message.answer(f"🔄 Проверяю заказ #{inv_id}...")

    try:
        data = await backend.reconcile_payment(inv_id)
    except Exception:
        logger.exception('Ошибка сверки заказа %s', inv_id)
        await status.edit_text(f"❌ Не удалось проверить заказ #{inv_id}.")
        return

    st = data.get('status')
    msg = data.get('message', '')

    if st == 'activated':
        icon = '✅'
    elif st == 'not_paid':
        icon = '⏳'
    else:
        icon = '⚠️'

    await status.edit_text(f"{icon} <b>Заказ #{inv_id}</b>\n\n{msg}")
