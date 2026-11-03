"""Тесты сверки «потерянных» платежей.

Запуск:
    cd backend
    ..\\venv\\Scripts\\python.exe manage.py test api.tests_reconcile --settings=config.settings_test
"""

import hashlib
import json
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from api.models import Plan, PlanPrice, User, RobokassaOrder, PaymentLog
from api.payment_checker import RobokassaCheckError
from api import views


def md5(value: str) -> str:
    return hashlib.md5(value.encode('utf-8')).hexdigest()


class BaseReconcileTest(TestCase):
    def setUp(self):
        self.plan = Plan.objects.create(
            slug='personal', name='Personal', analyses_limit=30, is_active=True, order=1,
        )
        PlanPrice.objects.create(plan=self.plan, currency='RUB', amount=Decimal('399.00'))
        self.user = User.objects.create(tg_id=238583074, username='owner')

    def auth(self):
        return {'HTTP_X_BOT_API_KEY': settings.BOT_API_KEY}

    def make_order(self, status='pending', inv_id=900500):
        return RobokassaOrder.objects.create(
            inv_id=inv_id, user=self.user, plan=self.plan,
            amount=Decimal('399.00'), currency='RUB',
            is_test=False, status=status,
        )


class ReconcileSingleTest(BaseReconcileTest):
    def _post(self, inv_id):
        return self.client.post(reverse('payment-reconcile', args=[inv_id]), **self.auth())

    @patch('api.views.reconcile_pending_order')
    def test_activated_result(self, mock_reconcile):
        order = self.make_order()
        mock_reconcile.return_value = {'status': 'activated', 'paid': True, 'message': 'OK'}

        resp = self._post(order.inv_id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'activated')
        mock_reconcile.assert_called_once()

    @patch('api.views.reconcile_pending_order')
    def test_not_paid_result(self, mock_reconcile):
        order = self.make_order()
        mock_reconcile.return_value = {
            'status': 'not_paid', 'paid': False,
            'message': 'Оплата не завершена', 'state_code': '5',
        }

        resp = self._post(order.inv_id)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['paid'])

    def test_unknown_order_returns_404(self):
        resp = self._post(123456789)
        self.assertEqual(resp.status_code, 404)

    def test_requires_api_key(self):
        order = self.make_order()
        resp = self.client.post(reverse('payment-reconcile', args=[order.inv_id]))
        self.assertIn(resp.status_code, (401, 403))


class ReconcileAllTest(BaseReconcileTest):
    @patch('api.views.reconcile_pending_order')
    def test_reconcile_all(self, mock_reconcile):
        self.make_order(inv_id=900501)
        self.make_order(inv_id=900502)
        mock_reconcile.return_value = {'status': 'not_paid', 'paid': False, 'message': 'нет'}

        resp = self.client.post(
            reverse('payment-reconcile-all'),
            data=json.dumps({'hours': 72}),
            content_type='application/json',
            **self.auth(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['checked'], 2)
        self.assertEqual(data['activated'], 0)

    @patch('api.views.reconcile_pending_order')
    def test_activated_orders_skipped(self, mock_reconcile):
        self.make_order(inv_id=900503, status='activated')
        self.make_order(inv_id=900504, status='pending')
        mock_reconcile.return_value = {'status': 'not_paid', 'paid': False, 'message': 'нет'}

        resp = self.client.post(
            reverse('payment-reconcile-all'),
            data=json.dumps({'hours': 72}),
            content_type='application/json',
            **self.auth(),
        )
        self.assertEqual(resp.json()['checked'], 1)
