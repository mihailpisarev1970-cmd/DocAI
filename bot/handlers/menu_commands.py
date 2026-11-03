from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
import services.backend_client as backend
from keyboards.inline import plan_selection_kb, ref_share_kb

router = Router()

# --- Обработка нажатий на нижние кнопки ---
# Кнопка «💎 Тарифы» обрабатывается в handlers/payments.py (там же выбор тарифа).

@router.message(Command('vip'))
async def cmd_vip(message: Message):
    await message.answer(
        "💎 <b>Выберите подходящий тариф:</b>",
        reply_markup=plan_selection_kb()
    )

@router.message(F.text == '👥 Реферальная программа')
@router.message(Command('ref'))
async def cmd_ref(message: Message):
    tg_id = message.from_user.id
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{tg_id}"

    try:
        stats = await backend.get_referral_stats(tg_id)
    except Exception:
        stats = {}

    invited_total = stats.get('invited_total', 0)
    invited_paid = stats.get('invited_paid', 0)
    bonus_earned = stats.get('bonus_earned', 0)
    bonus_balance = stats.get('bonus_balance', 0)
    per_ref = stats.get('bonus_per_referral', 30)

    text = (
        "👥 <b>Реферальная программа</b>\n\n"
        f"Приглашайте друзей и получайте <b>{per_ref} анализов</b> "
        "за каждого, кто оформит подписку.\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        "📊 <b>Ваша статистика:</b>\n"
        f"• Приглашено: <b>{invited_total}</b>\n"
        f"• Из них оплатили: <b>{invited_paid}</b>\n"
        f"• Заработано анализов: <b>{bonus_earned}</b>\n"
        f"• Бонусный баланс: <b>{bonus_balance}</b>\n\n"
        "<i>Просто отправьте ссылку другу. Бонус начислится автоматически "
        "после его первой оплаты.</i>"
    )

    await message.answer(text, reply_markup=ref_share_kb(ref_link))

@router.message(F.text == '📖 Инструкция')
@router.message(Command('help'))
async def cmd_help(message: Message):
    # Ваш ник в Telegram (без @)
    my_nickname = "pisarev_pro_digital" 
    
    await message.answer(
        "\n\n<b>Как получить максимальный результат от Экспресс-юриста</b>\n\n"
        "Я помогу разобраться в любом документе, но чтобы я дал самый точный ответ, следуйте этим правилам:\n\n"
        "1️⃣ <b>Отправляйте весь документ целиком.</b> Если прислать только одну страницу или вырванный пункт, я могу не увидеть важные условия в других разделах. Лучше всего отправлять фото всех страниц, PDF или Word.\n\n"
        "2️⃣ <b>Задавайте короткие вопросы!</b> Если вам непонятен какой-то термин (например, «аванс», «неустойка», «субсидиарная ответственность») или конкретный пункт договора — просто напишите мне об этом текстом. Я объясню значение простыми словами.\n\n"
        "3️⃣ <b>Говорите голосом!</b> Если вам удобнее, просто запишите голосовое сообщение. Я распознаю вашу речь и задам этот вопрос юристу-нейросети. Например: «Что значит пункт 4.2?», «Какие риски в этом договоре?».\n\n"
        "4️⃣ <b>Качество фото:</b> Делайте снимки при хорошем освещении. Текст должен быть четким. Если я не смог распознать текст, попробуйте перепечатать его вручную.\n\n"
        "💡 <b>Совет:</b> Если у вас есть договор, но вы хотите уточнить что-то конкретное, сначала отправьте весь документ, а в следующем сообщении задайте свой вопрос. Я проанализирую всё вместе.\n\n"
        f"✉️ <b>По любым вопросам пишите:</b> <a href='https://t.me/{my_nickname}'>@{my_nickname}</a>"
    )

@router.message(F.text == '📤 Отправить документ')
async def cmd_send_doc(message: Message):
    await message.answer("Пришлите <b>фото</b>, <b>PDF</b>, <b>Word</b>, <b>текст</b> документа или запишите <b>голосовое сообщение</b> с вопросом!")