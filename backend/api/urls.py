from django.urls import path
from . import views

urlpatterns = [
    # --- Пользователи ---
    path('users/get-or-create/', views.get_or_create_user, name='user-get-or-create'),
    path('users/<int:tg_id>/increment-usage/', views.increment_usage, name='increment-usage'),
    path('users/<int:tg_id>/referrals/', views.referral_stats, name='referral-stats'),

    # --- Контент ---
    path('plans/', views.get_plans, name='plans'),
    path('documents/', views.save_document, name='save-document'),

    # --- Robokassa ---
    path('payments/create/', views.create_payment, name='payment-create'),
    path('payments/robokassa/result/', views.robokassa_result, name='robokassa-result'),
    path('payments/robokassa/success/', views.robokassa_success, name='robokassa-success'),
    path('payments/robokassa/fail/', views.robokassa_fail, name='robokassa-fail'),
    path('payments/<int:inv_id>/status/', views.payment_status, name='payment-status'),

    # --- Сверка «потерянных» платежей ---
    path('payments/<int:inv_id>/reconcile/', views.reconcile_payment, name='payment-reconcile'),
    path('payments/reconcile-all/', views.reconcile_all_pending, name='payment-reconcile-all'),
]
