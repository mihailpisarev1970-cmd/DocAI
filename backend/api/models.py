from datetime import timedelta

from django.db import models
from django.utils import timezone


def _next_month_first(dt):
    return (dt.replace(day=1) + timedelta(days=32)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )


class Plan(models.Model):
    slug = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    analyses_limit = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Лимит анализов',
        help_text='Оставьте пустым для безлимита',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        ordering = ['order']
        verbose_name = 'Тариф'
        verbose_name_plural = 'Тарифы'

    def __str__(self):
        return self.name

    def get_limit(self) -> int:
        return self.analyses_limit if self.analyses_limit is not None else 9999

    def get_price(self, currency: str):
        try:
            return self.prices.get(currency=currency).amount
        except PlanPrice.DoesNotExist:
            return None


class PlanPrice(models.Model):
    CURRENCY_CHOICES = [
        ('STARS', 'Telegram Stars ⭐'),
        ('USD',   'USD $'),
        ('USDT',  'USDT ₮'),
        ('RUB',   'RUB ₽'),
        ('UZS',   'UZS сўм'),
        ('TENGE', 'KZT ₸'),
    ]

    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name='prices',
        verbose_name='Тариф',
    )
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, verbose_name='Валюта')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Сумма')

    class Meta:
        unique_together = ('plan', 'currency')
        verbose_name = 'Цена'
        verbose_name_plural = 'Цены'

    def __str__(self):
        return f'{self.plan.slug} / {self.currency} {self.amount}'


class PaymentMethod(models.Model):
    CURRENCY_CHOICES = [
        ('STARS', 'Telegram Stars ⭐'),
        ('USD',   'USD $'),
        ('USDT',  'USDT ₮'),
        ('RUB',   'RUB ₽'),
        ('UZS',   'UZS сўм'),
        ('TENGE', 'KZT ₸'),
    ]

    slug         = models.CharField(max_length=30, unique=True)
    name         = models.CharField(max_length=150, verbose_name='Название')
    flag         = models.CharField(max_length=10, blank=True, verbose_name='Флаг (эмодзи)')
    currency     = models.CharField(max_length=10, choices=CURRENCY_CHOICES, verbose_name='Валюта')
    instructions = models.TextField(blank=True, verbose_name='Инструкция')
    details      = models.TextField(blank=True, verbose_name='Реквизиты')
    is_active    = models.BooleanField(default=True, verbose_name='Активен')
    order        = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        ordering = ['order']
        verbose_name = 'Метод оплаты'
        verbose_name_plural = 'Методы оплаты'

    def __str__(self):
        return self.name


_FALLBACK_LIMITS = {'free': 3, 'personal': 30, 'business': 9999}


class User(models.Model):
    PLAN_CHOICES = [
        ('free', 'Free'),
        ('personal', 'Personal'),
        ('business', 'Business'),
    ]

    tg_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    full_name = models.CharField(max_length=255, null=True, blank=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    usage_count = models.IntegerField(default=0)
    usage_reset = models.DateTimeField(null=True, blank=True)
    referrer_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    subscription_expires = models.DateTimeField(null=True, blank=True)
    first_analysis_nudge_sent = models.BooleanField(default=False)
    bonus_analyses = models.IntegerField(default=0, verbose_name='Бонусных анализов')

    def _get_plan_limit(self) -> int:
        try:
            return Plan.objects.get(slug=self.plan).get_limit()
        except Plan.DoesNotExist:
            return _FALLBACK_LIMITS.get(self.plan, 3)

    def check_subscription(self):
        if self.plan != 'free' and self.subscription_expires:
            if timezone.now() >= self.subscription_expires:
                self.plan = 'free'
                self.save(update_fields=['plan'])

    def reset_if_needed(self):
        now = timezone.now()
        if self.usage_reset and now >= self.usage_reset:
            self.usage_count = 0
            self.usage_reset = _next_month_first(now)
            self.save(update_fields=['usage_count', 'usage_reset'])

    def get_days_left(self) -> int | None:
        if not self.subscription_expires or self.plan == 'free':
            return None
        delta = self.subscription_expires - timezone.now()
        return max(0, delta.days)

    def get_remaining(self) -> int:
        self.check_subscription()
        self.reset_if_needed()
        plan_remaining = max(0, self._get_plan_limit() - self.usage_count)
        return plan_remaining + self.bonus_analyses

    def __str__(self):
        return f"User {self.tg_id} ({self.plan})"


class ReferralLog(models.Model):
    referrer      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_given')
    referred      = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referral_received')
    bonus_granted = models.BooleanField(default=False, verbose_name='Бонус начислен')
    bonus_amount  = models.IntegerField(default=0, verbose_name='Начислено анализов')
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Реферал'
        verbose_name_plural = 'Рефералы'

    def __str__(self):
        return f'{self.referrer.tg_id} → {self.referred.tg_id}'


class Document(models.Model):
    RISK_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=255, null=True, blank=True)
    summary = models.TextField(null=True, blank=True)
    full_response = models.TextField()
    deadline = models.CharField(max_length=255, null=True, blank=True)
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES, default='low')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Doc {self.id} ({self.user.tg_id})"


class PaymentLog(models.Model):
    user               = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    plan               = models.CharField(max_length=20)
    telegram_charge_id = models.CharField(max_length=255, unique=True)
    stars_amount       = models.IntegerField()
    method_slug        = models.CharField(max_length=30, blank=True, default='stars', verbose_name='Метод')
    amount             = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Сумма')
    currency           = models.CharField(max_length=10, blank=True, verbose_name='Валюта')
    provider_payment_id = models.CharField(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='ID платежа у провайдера',
    )
    created_at         = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.telegram_charge_id[:16]}… ({self.plan})"


class RobokassaOrder(models.Model):
    """Заказ на оплату через Robokassa.

    Создаётся в момент запроса ссылки на оплату и служит единственным
    источником правды при обработке уведомления ResultURL.
    """

    STATUS_CHOICES = [
        ('new',       'Создан'),
        ('pending',   'Ожидает оплаты'),
        ('paid',      'Оплачен'),
        ('activated', 'Подписка активирована'),
        ('failed',    'Ошибка'),
    ]

    inv_id      = models.BigIntegerField(unique=True, db_index=True, verbose_name='Номер счёта (InvId)')
    user        = models.ForeignKey(User, on_delete=models.PROTECT, related_name='robokassa_orders', verbose_name='Пользователь')
    plan        = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='robokassa_orders', verbose_name='Тариф')
    amount      = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Сумма')
    currency    = models.CharField(max_length=10, default='RUB', verbose_name='Валюта')
    is_test     = models.BooleanField(default=False, verbose_name='Тестовый платёж')
    status      = models.CharField(max_length=12, choices=STATUS_CHOICES, default='new', verbose_name='Статус')

    payment_method = models.CharField(max_length=50, blank=True, verbose_name='Способ оплаты')
    fee            = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Комиссия')
    email          = models.CharField(max_length=255, blank=True, verbose_name='Email покупателя')

    failure_reason = models.CharField(max_length=255, blank=True, verbose_name='Причина ошибки')
    created_at     = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    paid_at        = models.DateTimeField(null=True, blank=True, verbose_name='Оплачен')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Заказ Robokassa'
        verbose_name_plural = 'Заказы Robokassa'

    def __str__(self):
        return f'Заказ #{self.inv_id} — {self.plan.slug} — {self.amount} {self.currency} [{self.status}]'


class BotSetting(models.Model):
    key         = models.CharField(max_length=50, unique=True, verbose_name='Ключ')
    value       = models.CharField(max_length=255, blank=True, verbose_name='Значение')
    description = models.CharField(max_length=255, blank=True, verbose_name='Описание')

    class Meta:
        verbose_name = 'Настройка бота'
        verbose_name_plural = 'Настройки бота'

    def __str__(self):
        return f'{self.key} = {self.value or "—"}'


class PendingPayment(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Ожидание'),
        ('approved', 'Подтверждено'),
        ('rejected', 'Отказано'),
    ]

    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pending_payments')
    plan             = models.CharField(max_length=20, verbose_name='Тариф')
    payment_method   = models.ForeignKey(
        PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Метод оплаты',
    )
    admin_message_id = models.BigIntegerField(null=True, blank=True, verbose_name='ID сообщения в группе')
    status           = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='Статус')
    created_at       = models.DateTimeField(auto_now_add=True)
    resolved_at      = models.DateTimeField(null=True, blank=True, verbose_name='Обработан')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Ожидающий платёж'
        verbose_name_plural = 'Ожидающие платежи'

    def __str__(self):
        return f'PendingPayment #{self.id} {self.user.tg_id} → {self.plan} [{self.status}]'