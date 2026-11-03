from django.contrib import admin, messages
from .models import (
    User, Plan, PlanPrice, PaymentMethod, Document,
    PaymentLog, BotSetting, PendingPayment, ReferralLog, RobokassaOrder,
)

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'analyses_limit', 'is_active')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('tg_id', 'username', 'plan', 'usage_count', 'subscription_expires')
    search_fields = ('tg_id', 'username')
    list_filter = ('plan',)

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'doc_type', 'risk_level', 'created_at')

@admin.register(RobokassaOrder)
class RobokassaOrderAdmin(admin.ModelAdmin):
    list_display = (
        'inv_id', 'user', 'plan', 'amount', 'currency',
        'status', 'is_test', 'payment_method', 'created_at', 'paid_at',
    )
    list_filter = ('status', 'is_test', 'plan', 'currency')
    search_fields = ('inv_id', 'user__tg_id', 'user__username', 'email')
    readonly_fields = ('inv_id', 'created_at', 'paid_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    actions = ['reconcile_with_robokassa']

    fieldsets = (
        ('Заказ', {
            'fields': ('inv_id', 'user', 'plan', 'amount', 'currency', 'is_test'),
        }),
        ('Статус оплаты', {
            'fields': ('status', 'payment_method', 'fee', 'email', 'paid_at', 'failure_reason'),
        }),
        ('Служебное', {
            'fields': ('created_at',),
        }),
    )

    @admin.action(description='🔄 Проверить оплату в Robokassa (активировать найденные)')
    def reconcile_with_robokassa(self, request, queryset):
        from .views import reconcile_pending_order

        activated = 0
        not_paid = 0
        errors = 0
        details = []

        for order in queryset.filter(status='pending'):
            res = reconcile_pending_order(order)
            st = res.get('status')
            if st == 'activated':
                activated += 1
                details.append(f'✅ #{order.inv_id} — активирован')
            elif st == 'not_paid':
                not_paid += 1
                details.append(f'⏳ #{order.inv_id} — {res.get("message")}')
            else:
                errors += 1
                details.append(f'⚠️ #{order.inv_id} — {res.get("message")}')

        skipped = queryset.exclude(status='pending').count()
        summary = (
            f'Проверено pending: {queryset.filter(status="pending").count()}. '
            f'Активировано: {activated}. Не оплачено: {not_paid}. Ошибок: {errors}.'
        )
        if skipped:
            summary += f' Пропущено (уже обработаны): {skipped}.'

        self.message_user(request, ' '.join([summary] + details), level=messages.INFO)


@admin.register(ReferralLog)
class ReferralLogAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'referrer', 'referred', 'bonus_granted', 'bonus_amount', 'created_at',
    )
    list_filter = ('bonus_granted', 'created_at')
    search_fields = (
        'referrer__tg_id', 'referrer__username',
        'referred__tg_id', 'referred__username',
    )
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    fieldsets = (
        ('Связь', {'fields': ('referrer', 'referred')}),
        ('Бонус', {'fields': ('bonus_granted', 'bonus_amount')}),
        ('Служебное', {'fields': ('created_at',)}),
    )


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'currency', 'is_active')

@admin.register(BotSetting)
class BotSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description')

admin.site.register(PlanPrice)
admin.site.register(PaymentLog)
admin.site.register(PendingPayment)