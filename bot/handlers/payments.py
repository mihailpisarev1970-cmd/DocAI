import asyncio
import logging

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery

import services.backend_client as backend
from config import PAYMENT_POLL_INTERVAL, PAYMENT_POLL_TIMEOUT
from keyboards.inline import plan_selection_kb, payment_kb
from keyboards.reply import main_menu

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text.in_({'💳 Купить подписку', '💎 Тарифы'}))
async def cmd_buy(message: Message):
    await message.answer(
        "💎 <b>Выберите подходящий тариф:</b>",
        reply_markup=plan_selection_kb()
    )


async def _wait_for_payment(callback: CallbackQuery, inv_id: int) -> None:
    """Опрашивает бэкенд и сообщает пользователю, когда оплата подтвердится."""
    waited = 0
    while waited < PAYMENT_POLL_TIMEOUT:
        await asyncio.sleep(PAYMENT_POLL_INTERVAL)
        waited += PAYMENT_POLL_INTERVAL
        try:
            data = await backend.get_payment_status(inv_id)
        except Exception as exc:
            logger.warning('Не удалось получить статус заказа #%s: %s', inv_id, exc)
            continue

        if data.get('paid'):
            await callback.message.answer(
                "✅ <b>Оплата получена!</b>\n\n"
                f"Тариф <b>{data.get('plan_name', data.get('plan'))}</b> активирован.\n"
                "Лимиты обновлены — можно отправлять документы.",
                reply_markup=main_menu(),
            )
            return

        if data.get('status') == 'failed':
            await callback.message.answer(
                "⚠️ Платёж не был подтверждён. Если деньги списались — напишите в поддержку.",
                reply_markup=main_menu(),
            )
            return

    await callback.message.answer(
        "⏳ Платёж пока не подтверждён.\n\n"
        "Если вы уже оплатили, откройте «👤 Профиль» через пару минут — лимиты обновятся автоматически.",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data.startswith('pay_robokassa:'))
async def process_robokassa_payment(callback: CallbackQuery):
    plan_slug = callback.data.split(':')[1]
    await callback.answer("Генерирую ссылку...")
    await callback.message.edit_text("⏳ Генерирую ссылку на оплату...")

    try:
        payment_data = await backend.create_payment(callback.from_user.id, plan_slug)
        url = payment_data['confirmation_url']
        inv_id = payment_data.get('order_id') or payment_data.get('inv_id')
    except Exception:
        logger.exception('Ошибка создания платежа для tg_id=%s, план=%s',
                         callback.from_user.id, plan_slug)
        await callback.message.edit_text(
            "❌ Не удалось создать платёж.\n\n"
            "Попробуйте ещё раз через минуту или напишите в поддержку."
        )
        return

    amount = payment_data.get('amount', '')
    test_note = ''
    if payment_data.get('is_test'):
        test_note = "\n\n🧪 <i>Включён тестовый режим — реальные деньги не списываются.</i>"

    text = (
        f"💳 <b>К оплате: {amount} ₽</b>\n\n"
        "Нажмите кнопку ниже, чтобы перейти к оплате."
        f"{test_note}"
    )

    try:
        await callback.message.edit_text(text, reply_markup=payment_kb(url))
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=payment_kb(url))

    # Параллельно ждём подтверждения оплаты и пишем пользователю, когда оно придёт.
    if inv_id:
        asyncio.create_task(_wait_for_payment(callback, inv_id))