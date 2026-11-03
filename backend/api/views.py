import uuid
import time
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from . import robokassa
from .models import User, Plan, PaymentLog, Document, RobokassaOrder, ReferralLog, _next_month_first

logger = logging.getLogger(__name__)

@api_view(['POST'])
def get_or_create_user(request):
    tg_id = request.data.get('tg_id')
    if not tg_id:
        return Response({'error': 'tg_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    user, created = User.objects.get_or_create(
        tg_id=tg_id,
        defaults={'username': request.data.get('username'), 'full_name': request.data.get('full_name')}
    )

    # --- Привязка реферера (только для новых пользователей) ---
    referrer_id = request.data.get('referrer_id')
    if created and referrer_id:
        _attach_referrer(user, referrer_id)

    return Response({
        'tg_id': user.tg_id,
        'plan': user.plan,
        'remaining': user.get_remaining(),
        'analyses_limit': user._get_plan_limit(),
        'bonus_analyses': user.bonus_analyses,
        'created': created,
    })


def _attach_referrer(user: User, referrer_id) -> None:
    """Привязывает пригласившего к новому пользователю.

    Правила:
      * нельзя пригласить самого себя;
      * пригласивший должен существовать;
      * связь создаётся один раз (OneToOne на referred).
    """
    try:
        referrer_tg_id = int(referrer_id)
    except (TypeError, ValueError):
        logger.warning('Некорректный referrer_id=%r', referrer_id)
        return

    if referrer_tg_id == user.tg_id:
        logger.info('Попытка самоприглашения: tg_id=%s', user.tg_id)
        return

    referrer = User.objects.filter(tg_id=referrer_tg_id).first()
    if referrer is None:
        logger.warning('Реферер tg_id=%s не найден', referrer_tg_id)
        return

    user.referrer_id = referrer_tg_id
    user.save(update_fields=['referrer_id'])

    ReferralLog.objects.create(
        referrer=referrer,
        referred=user,
        bonus_granted=False,
        bonus_amount=0,
    )
    logger.info('Реферал привязан: %s → %s', referrer_tg_id, user.tg_id)

    # Приветственный бонус приглашённому (по умолчанию 0)
    welcome = settings.REFERRAL_WELCOME_BONUS
    if welcome > 0:
        user.bonus_analyses += welcome
        user.save(update_fields=['bonus_analyses'])
        logger.info('Приветственный бонус +%s анализов для tg_id=%s', welcome, user.tg_id)


@api_view(['GET'])
def referral_stats(request, tg_id: int):
    """Статистика реферальной программы для пользователя."""
    user = User.objects.filter(tg_id=tg_id).first()
    if not user:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    logs = ReferralLog.objects.filter(referrer=user)
    total = logs.count()
    paid = logs.filter(bonus_granted=True).count()
    earned = sum(log.bonus_amount for log in logs.filter(bonus_granted=True))

    return Response({
        'tg_id': user.tg_id,
        'invited_total': total,
        'invited_paid': paid,
        'bonus_earned': earned,
        'bonus_balance': user.bonus_analyses,
        'bonus_per_referral': settings.REFERRAL_BONUS_ANALYSES,
    })

@api_view(['GET'])
def get_plans(request):
    plans = Plan.objects.filter(is_active=True).prefetch_related('prices')
    data = []
    for p in plans:
        prices = {pr.currency: str(pr.amount) for pr in p.prices.all()}
        data.append({
            'slug': p.slug,
            'name': p.name,
            'analyses_limit': p.analyses_limit,
            'prices': prices
        })
    return Response(data)

def _generate_inv_id() -> int:
    """Уникальный номер счёта для Robokassa.

    Начинаем с 1, чтобы InvId никогда не был нулём (Robokassa это запрещает).
    Начальное значение привязано к времени, чтобы номера заказов не пересекались
    с уже существующими в базе после перезапуска.
    """
    base = int(time.time()) % 1_000_000_000
    last = RobokassaOrder.objects.order_by('-inv_id').values_list('inv_id', flat=True).first()
    candidate = max(base, (last or 0) + 1)
    while RobokassaOrder.objects.filter(inv_id=candidate).exists():
        candidate += 1
    return candidate


@api_view(['POST'])
def create_payment(request):
    """Создаёт заказ и возвращает ссылку на страницу оплаты Robokassa."""
    tg_id = request.data.get('tg_id')
    plan_slug = request.data.get('plan')
    email = (request.data.get('email') or '').strip()

    if not tg_id:
        return Response({'error': 'tg_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        plan = Plan.objects.get(slug=plan_slug, is_active=True)
    except Plan.DoesNotExist:
        return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)

    price = plan.get_price('RUB')
    if price is None:
        return Response(
            {'error': f'Для тарифа «{plan.name}» не задана цена в RUB'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user, _ = User.objects.get_or_create(
        tg_id=tg_id,
        defaults={
            'username': request.data.get('username'),
            'full_name': request.data.get('full_name'),
        },
    )

    if not robokassa.is_configured():
        logger.error('Robokassa не настроена: проверьте ROBOKASSA_* в backend/.env')
        return Response(
            {'error': 'Оплата временно недоступна: платёжный модуль не настроен'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    public_url = getattr(settings, 'BACKEND_PUBLIC_URL', '')
    success_url = f'{public_url}/api/payments/robokassa/success/' if public_url else ''
    fail_url = f'{public_url}/api/payments/robokassa/fail/' if public_url else ''

    order = None
    for _attempt in range(5):
        inv_id = _generate_inv_id()
        try:
            with transaction.atomic():
                order = RobokassaOrder.objects.create(
                    inv_id=inv_id,
                    user=user,
                    plan=plan,
                    amount=price,
                    currency='RUB',
                    is_test=settings.ROBOKASSA_TEST_MODE,
                    status='pending',
                    email=email,
                )
            break
        except IntegrityError:
            logger.warning('Коллизия InvId=%s, пробуем другой номер', inv_id)

    if order is None:
        return Response(
            {'error': 'Не удалось создать заказ, попробуйте ещё раз'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    description = f'Подписка DocAI «{plan.name}» на {settings.SUBSCRIPTION_PERIOD_DAYS} дней'

    receipt = ''
    if getattr(settings, 'ROBOKASSA_SEND_RECEIPT', False):
        receipt = robokassa.build_receipt(
            description=description,
            amount=order.amount,
            tax=getattr(settings, 'ROBOKASSA_RECEIPT_TAX', 'none'),
        )

    try:
        payment_url = robokassa.build_payment_url(
            inv_id=order.inv_id,
            amount=order.amount,
            description=description,
            shp={'Shp_order': order.inv_id},
            email=email,
            success_url=success_url,
            fail_url=fail_url,
            is_test=settings.ROBOKASSA_TEST_MODE,
            receipt=receipt,
        )
    except robokassa.RobokassaError as exc:
        order.status = 'failed'
        order.failure_reason = str(exc)[:255]
        order.save(update_fields=['status', 'failure_reason'])
        logger.exception('Не удалось сформировать ссылку на оплату для заказа #%s', order.inv_id)
        return Response({'error': 'Платёжный модуль временно недоступен'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    logger.info(
        'Создан заказ #%s: tg_id=%s план=%s сумма=%s тест=%s',
        order.inv_id, tg_id, plan.slug, order.amount, order.is_test,
    )

    return Response({
        'order_id': order.inv_id,
        'inv_id': order.inv_id,
        'amount': robokassa.format_sum(order.amount),
        'plan': plan.slug,
        'is_test': order.is_test,
        'confirmation_url': payment_url,
    })

def _grant_referral_bonus(referred_user: User) -> int:
    """Начисляет бонус пригласившему после оплаты приглашённого.

    Возвращает количество начисленных анализов (0, если бонус не положен).
    Вызывается внутри транзакции активации подписки.
    """
    log = ReferralLog.objects.select_for_update().filter(
        referred=referred_user, bonus_granted=False,
    ).first()
    if log is None:
        return 0

    if not referred_user.referrer_id:
        return 0

    referrer = User.objects.select_for_update().filter(tg_id=referred_user.referrer_id).first()
    if referrer is None:
        logger.warning('Реферер tg_id=%s не найден при начислении бонуса', referred_user.referrer_id)
        return 0

    bonus = settings.REFERRAL_BONUS_ANALYSES
    if bonus <= 0:
        return 0

    # Ограничение на количество начислений (0 = без ограничений)
    max_bonuses = settings.REFERRAL_MAX_BONUSES
    if max_bonuses > 0:
        already = ReferralLog.objects.filter(referrer=referrer, bonus_granted=True).count()
        if already >= max_bonuses:
            logger.info('Лимит реферальных бонусов для tg_id=%s достигнут', referrer.tg_id)
            return 0

    referrer.bonus_analyses += bonus
    referrer.save(update_fields=['bonus_analyses'])

    log.bonus_granted = True
    log.bonus_amount = bonus
    log.save(update_fields=['bonus_granted', 'bonus_amount'])

    logger.info(
        'Реферальный бонус: +%s анализов для tg_id=%s (пригласил tg_id=%s)',
        bonus, referrer.tg_id, referred_user.tg_id,
    )
    return bonus


def _activate_subscription(order: RobokassaOrder) -> None:
    """Начисляет подписку по оплаченному заказу.

    Вызывается внутри транзакции и только один раз на заказ, поэтому повторные
    уведомления Robokassa не приведут к двойному начислению.
    """
    user = order.user
    plan = order.plan
    now = timezone.now()

    if user.subscription_expires and user.subscription_expires > now:
        user.subscription_expires += timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS)
    else:
        user.subscription_expires = now + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS)

    user.plan = plan.slug
    user.usage_count = 0
    # Счётчик должен сброситься в начале следующего месяца, иначе
    # reset_if_needed() сбросит его повторно/несвоевременно.
    user.usage_reset = _next_month_first(now)
    user.save(update_fields=['plan', 'usage_count', 'usage_reset', 'subscription_expires'])

    PaymentLog.objects.create(
        user=user,
        plan=plan.slug,
        telegram_charge_id=f'robokassa_{order.inv_id}',
        stars_amount=0,
        method_slug='robokassa',
        amount=order.amount,
        currency=order.currency,
        provider_payment_id=str(order.inv_id),
    )


@api_view(['GET', 'POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def robokassa_result(request):
    """Принимает уведомления от Robokassa об успешной оплате (ResultURL)."""
    data = request.GET.dict() if request.method == 'GET' else request.POST.dict()

    inv_id = data.get('InvId', '')
    out_sum = data.get('OutSum', '')
    signature = data.get('SignatureValue', '')

    if not inv_id or not out_sum or not signature:
        logger.warning('Robokassa ResultURL: неполный набор параметров %s', list(data.keys()))
        return HttpResponse('ERROR: missing params', status=400)

    if not robokassa.verify_result_signature(data):
        logger.error(
            'Robokassa ResultURL: неверная подпись. InvId=%s OutSum=%s Signature=%s',
            inv_id, out_sum, signature,
        )
        return HttpResponse('ERROR: bad signature', status=400)

    try:
        inv_id_int = int(inv_id)
    except (TypeError, ValueError):
        logger.error('Robokassa ResultURL: некорректный InvId=%r', inv_id)
        return HttpResponse('ERROR: bad InvId', status=400)

    with transaction.atomic():
        try:
            order = RobokassaOrder.objects.select_for_update().get(inv_id=inv_id_int)
        except RobokassaOrder.DoesNotExist:
            logger.error('Robokassa ResultURL: заказ #%s не найден', inv_id_int)
            return HttpResponse(f'ERROR{inv_id_int}', status=400)

        # Идемпотентность: повторное уведомление не должно начислять дни заново.
        if order.status in ('activated', 'paid'):
            logger.info('Robokassa ResultURL: заказ #%s уже обработан (%s)', order.inv_id, order.status)
            return HttpResponse(f'OK{order.inv_id}')

        # Заказ с несовпавшей суммой требует ручной проверки в админке:
        # автоматически не активируем, чтобы исключить подделку суммы.
        if order.status == 'failed' and order.failure_reason.startswith('Сумма не совпадает'):
            logger.error(
                'Robokassa ResultURL: заказ #%s заблокирован после расхождения суммы (%s)',
                order.inv_id, order.failure_reason,
            )
            return HttpResponse(f'OK{order.inv_id}')

        try:
            paid = Decimal(out_sum)
        except Exception:
            logger.error('Robokassa ResultURL: некорректная сумма OutSum=%r', out_sum)
            return HttpResponse('ERROR: bad sum', status=400)

        # Сверяем сумму с сохранённой в заказе.
        if round(paid, 2) != round(order.amount, 2):
            order.status = 'failed'
            order.failure_reason = f'Сумма не совпадает: оплачено {out_sum}, ожидалось {order.amount}'[:255]
            order.save(update_fields=['status', 'failure_reason'])
            logger.error(
                'Robokassa ResultURL: сумма не совпадает. Заказ #%s: оплачено %s, ожидалось %s',
                order.inv_id, out_sum, order.amount,
            )
            # OK, чтобы Robokassa не повторяла: заказ помечен проблемным в админке.
            return HttpResponse(f'OK{order.inv_id}')

        order.payment_method = (data.get('PaymentMethod') or '')[:50]
        order.email = (data.get('EMail') or order.email)[:255]
        order.paid_at = timezone.now()
        order.status = 'paid'

        try:
            fee = data.get('Fee')
            if fee:
                order.fee = Decimal(fee)
        except Exception:
            pass

        order.save()

        referral_bonus = 0
        try:
            _activate_subscription(order)
            referral_bonus = _grant_referral_bonus(order.user)
            order.status = 'activated'
            order.save(update_fields=['status'])
        except Exception as exc:
            order.status = 'failed'
            order.failure_reason = f'Ошибка активации: {exc}'[:255]
            order.save(update_fields=['status', 'failure_reason'])
            logger.exception('Robokassa: оплата прошла, но активация не удалась. Заказ #%s', order.inv_id)
            # ERROR, чтобы Robokassa повторила уведомление и мы попробовали ещё раз.
            return HttpResponse(f'ERROR{order.inv_id}', status=500)

    logger.info(
        'Robokassa: заказ #%s оплачен. tg_id=%s план=%s сумма=%s способ=%s',
        order.inv_id, order.user.tg_id, order.plan.slug, order.amount, order.payment_method or '—',
    )
    if referral_bonus:
        logger.info('Начислен реферальный бонус: +%s анализов', referral_bonus)
    return HttpResponse(f'OK{order.inv_id}')


def reconcile_pending_order(order: RobokassaOrder) -> dict:
    """Сверяет конкретный pending-заказ с Robokassa и активирует при оплате.

    Возвращает словарь с результатом:
        status    — 'activated' | 'not_paid' | 'error'
        message   — человекочитаемое описание
        paid      — активирован ли тариф
    """
    from .payment_checker import RobokassaCheckError, get_operation_state, is_paid

    if order.status == 'activated':
        return {'status': 'activated', 'paid': True, 'message': 'Заказ уже активирован'}

    try:
        state = get_operation_state(order.inv_id)
    except RobokassaCheckError as exc:
        logger.warning('Не удалось проверить заказ #%s: %s', order.inv_id, exc)
        return {'status': 'error', 'paid': False, 'message': str(exc)}

    state_code = str(state.get('state'))
    logger.info('Заказ #%s: State.Code=%s (%s)', order.inv_id, state_code, state.get('method'))

    if not is_paid(state):
        messages = {
            '5': 'Оплата не завершена',
            '10': 'Операция отменена, деньги не получены',
            '20': 'Средства захолдированы',
            '50': 'Деньги получены, идёт зачисление',
            '60': 'Отказ в зачислении, деньги возвращены',
            '80': 'Операция приостановлена',
        }
        return {
            'status': 'not_paid',
            'paid': False,
            'message': messages.get(state_code, f'Статус операции: {state_code}'),
            'state_code': state_code,
        }

    # --- Оплачено: активируем ---
    with transaction.atomic():
        locked = RobokassaOrder.objects.select_for_update().get(pk=order.pk)
        if locked.status == 'activated':
            return {'status': 'activated', 'paid': True, 'message': 'Заказ уже активирован'}

        locked.status = 'paid'
        locked.paid_at = timezone.now()
        locked.payment_method = (state.get('payment_method') or state.get('inc_sum') and 'SBP' or '')[:50]
        locked.save(update_fields=['status', 'paid_at', 'payment_method'])

        referral_bonus = 0
        try:
            _activate_subscription(locked)
            referral_bonus = _grant_referral_bonus(locked.user)
            locked.status = 'activated'
            locked.save(update_fields=['status'])
        except Exception as exc:
            locked.status = 'failed'
            locked.failure_reason = f'Ошибка активации при сверке: {exc}'[:255]
            locked.save(update_fields=['status', 'failure_reason'])
            logger.exception('Сверка: активация заказа #%s не удалась', locked.inv_id)
            return {'status': 'error', 'paid': False, 'message': f'Ошибка активации: {exc}'}

    logger.info('Сверка: заказ #%s активирован (tg_id=%s)', locked.inv_id, locked.user.tg_id)
    return {
        'status': 'activated',
        'paid': True,
        'message': 'Оплата найдена в Robokassa и активирована',
        'referral_bonus': referral_bonus,
        'inv_id': locked.inv_id,
        'plan': locked.plan.slug,
    }


@api_view(['POST'])
def reconcile_payment(request, inv_id: int):
    """Проверяет статус заказа в Robokassa и активирует, если оплачен."""
    order = RobokassaOrder.objects.filter(inv_id=inv_id).select_related('user', 'plan').first()
    if not order:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

    result = reconcile_pending_order(order)
    return Response(result)


@api_view(['POST'])
def reconcile_all_pending(request):
    """Сверяет все pending-заказы за последние N часов."""
    hours = int(request.data.get('hours', 72))
    since = timezone.now() - timedelta(hours=hours)

    orders = RobokassaOrder.objects.filter(
        status='pending', created_at__gte=since,
    ).select_related('user', 'plan').order_by('-created_at')

    results = []
    for order in orders:
        res = reconcile_pending_order(order)
        res['inv_id'] = order.inv_id
        res['tg_id'] = order.user.tg_id
        res['amount'] = robokassa.format_sum(order.amount)
        results.append(res)

    activated = [r for r in results if r.get('status') == 'activated']
    return Response({
        'checked': len(results),
        'activated': len(activated),
        'results': results,
    })


def _render_status_page(title: str, message: str, icon: str, color: str) -> str:
    """Простая HTML-страница для SuccessURL/FailURL без внешних зависимостей."""
    bot_link = getattr(settings, 'BOT_LINK', 'https://t.me/')
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — DocAI</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
      background: #f1f5f9; padding: 24px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }}
    .card {{
      background: #fff; border-radius: 18px; padding: 40px 32px; max-width: 460px; width: 100%;
      text-align: center; box-shadow: 0 12px 32px rgba(15, 23, 42, .10);
    }}
    .icon {{ font-size: 56px; line-height: 1; margin-bottom: 16px; }}
    h1 {{ margin: 0 0 12px; font-size: 22px; color: {color}; }}
    p {{ margin: 0 0 28px; font-size: 15px; line-height: 1.6; color: #475569; }}
    a.btn {{
      display: inline-block; padding: 14px 28px; border-radius: 12px; background: {color};
      color: #fff; text-decoration: none; font-weight: 600; font-size: 15px;
    }}
    .brand {{ margin-top: 26px; font-size: 12px; color: #94a3b8; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">{icon}</div>
    <h1>{title}</h1>
    <p>{message}</p>
    <a class="btn" href="{bot_link}">Вернуться в Telegram</a>
    <div class="brand">DocAI — анализ документов</div>
  </div>
</body>
</html>"""


@api_view(['GET', 'POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def robokassa_success(request):
    """Страница возврата покупателя после успешной оплаты (SuccessURL)."""
    data = request.GET.dict() if request.method == 'GET' else request.POST.dict()
    inv_id = (data.get('InvId') or '').strip()

    if not robokassa.verify_success_signature(data):
        logger.warning('Robokassa SuccessURL: подпись не прошла проверку. InvId=%s', inv_id or '—')

    order = RobokassaOrder.objects.filter(inv_id=inv_id).select_related('plan').first() \
        if inv_id.isdigit() else None

    if order and order.status == 'activated':
        title = 'Оплата прошла успешно'
        message = (
            f'Тариф «{order.plan.name}» активирован. '
            'Вернитесь в Telegram — новые лимиты уже доступны.'
        )
        icon, color = '✅', '#16a34a'
    elif order:
        title = 'Оплата обрабатывается'
        message = (
            'Платёж получен, но подтверждение от Robokassa ещё не пришло. '
            'Обычно это занимает до пары минут — вернитесь в Telegram и откройте профиль чуть позже.'
        )
        icon, color = '⏳', '#d97706'
    else:
        title = 'Оплата принята'
        message = 'Вернитесь в Telegram — лимиты обновятся автоматически в течение пары минут.'
        icon, color = '✅', '#16a34a'

    return HttpResponse(_render_status_page(title, message, icon, color),
                        content_type='text/html; charset=utf-8')


@api_view(['GET', 'POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def robokassa_fail(request):
    """Страница возврата покупателя после неуспешной оплаты (FailURL)."""
    data = request.GET.dict() if request.method == 'GET' else request.POST.dict()
    inv_id = (data.get('InvId') or '').strip()

    logger.info('Robokassa FailURL: оплата не завершена. InvId=%s', inv_id or '—')

    html = _render_status_page(
        'Оплата не завершена',
        'Платёж был отменён или не прошёл. Вернитесь в Telegram и попробуйте снова — '
        'можно выбрать другой способ оплаты.',
        '⚠️',
        '#dc2626',
    )
    return HttpResponse(html, content_type='text/html; charset=utf-8')


@api_view(['GET'])
def payment_status(request, inv_id: int):
    """Статус заказа. Бот опрашивает его, чтобы сообщить пользователю об оплате."""
    order = RobokassaOrder.objects.filter(inv_id=inv_id).select_related('plan', 'user').first()
    if not order:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        'inv_id': order.inv_id,
        'status': order.status,
        'plan': order.plan.slug,
        'plan_name': order.plan.name,
        'amount': robokassa.format_sum(order.amount),
        'paid': order.status == 'activated',
        'is_test': order.is_test,
        'tg_id': order.user.tg_id,
        'created_at': order.created_at,
    })


@api_view(['POST'])
def increment_usage(request, tg_id):
    try:
        user = User.objects.get(tg_id=tg_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    user.check_subscription()
    user.reset_if_needed()

    plan_limit = user._get_plan_limit()
    if user.usage_count < plan_limit:
        user.usage_count += 1
        user.save(update_fields=['usage_count'])
    elif user.bonus_analyses > 0:
        user.bonus_analyses = max(0, user.bonus_analyses - 1)
        user.save(update_fields=['bonus_analyses'])

    return Response({
        'usage_count': user.usage_count,
        'remaining': user.get_remaining(),
    })

@api_view(['POST'])
def save_document(request):
    tg_id = request.data.get('tg_id')
    try:
        user = User.objects.get(tg_id=tg_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    doc = Document.objects.create(
        user=user,
        doc_type=request.data.get('doc_type'),
        summary=request.data.get('summary'),
        full_response=request.data.get('full_response'),
        risk_level=request.data.get('risk_level', 'low')
    )
    return Response({'id': doc.id, 'status': 'created'}, status=status.HTTP_201_CREATED)