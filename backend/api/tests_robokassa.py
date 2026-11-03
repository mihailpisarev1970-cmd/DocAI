"""Тесты интеграции с Robokassa.

Запуск:
    cd backend
    ..\\venv\\Scripts\\python.exe manage.py test api.tests_robokassa -v 2 --settings=config.settings_test
"""

import hashlib
import json
import urllib.parse
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from api import robokassa
from api.models import Plan, PlanPrice, User, PaymentLog, RobokassaOrder


def md5(value: str) -> str:
    return hashlib.md5(value.encode('utf-8')).hexdigest()


class BaseRobokassaTest(TestCase):
    def setUp(self):
        self.plan = Plan.objects.create(
            slug='personal', name='Personal', analyses_limit=30, is_active=True, order=1,
        )
        PlanPrice.objects.create(plan=self.plan, currency='RUB', amount=Decimal('399.00'))
        self.user = User.objects.create(tg_id=123456, username='tester', full_name='Test User')


class SignatureTest(BaseRobokassaTest):
    def test_format_sum_always_two_decimals(self):
        self.assertEqual(robokassa.format_sum(399), '399.00')
        self.assertEqual(robokassa.format_sum(Decimal('1490')), '1490.00')
        self.assertEqual(robokassa.format_sum(Decimal('399.5')), '399.50')

    def test_payment_url_contains_signature_and_encoded_description(self):
        url = robokassa.build_payment_url(
            inv_id=555, amount=Decimal('399.00'), description='Подписка DocAI «Personal»',
            shp={'Shp_order': 555},
        )
        self.assertIn('MerchantLogin=test_shop', url)
        self.assertIn('OutSum=399.00', url)
        self.assertIn('InvId=555', url)
        self.assertIn('IsTest=1', url)
        self.assertIn('Culture=ru', url)
        # Кириллица должна быть URL-кодирована, а не вставлена как есть.
        self.assertNotIn('Подписка DocAI', url)
        self.assertIn('%D0%9F%D0%BE%D0%B4%D0%BF%D0%B8%D1%81%D0%BA%D0%B0', url)
        self.assertIn('Shp_order=555', url)

        expected_sig = md5('test_shop:399.00:555:test_pass1:Shp_order=555')
        self.assertIn(f'SignatureValue={expected_sig}', url)

    def test_result_signature_valid(self):
        base = '399.00:777:test_pass2:Shp_order=777'
        data = {
            'OutSum': '399.00',
            'InvId': '777',
            'SignatureValue': md5(base).upper(),
            'Shp_order': '777',
        }
        self.assertTrue(robokassa.verify_result_signature(data))

    def test_result_signature_invalid(self):
        data = {
            'OutSum': '1.00',
            'InvId': '777',
            'SignatureValue': md5('399.00:777:test_pass2:Shp_order=777'),
            'Shp_order': '777',
        }
        self.assertFalse(robokassa.verify_result_signature(data))

    def test_result_signature_supports_six_decimals(self):
        """В боевом режиме OutSum приходит с шестью знаками после запятой."""
        out_sum = '399.000000'
        base = f'{out_sum}:777:test_pass2:Shp_order=777'
        data = {
            'OutSum': out_sum,
            'InvId': '777',
            'SignatureValue': md5(base),
            'Shp_order': '777',
        }
        self.assertTrue(robokassa.verify_result_signature(data))

    def test_shp_parameters_must_be_sorted(self):
        """Подпись считается от Shp_* в алфавитном порядке."""
        base = '100.00:1:test_pass2:Shp_a=1:Shp_b=2'
        data = {
            'OutSum': '100.00', 'InvId': '1',
            'SignatureValue': md5(base),
            'Shp_b': '2', 'Shp_a': '1',
        }
        self.assertTrue(robokassa.verify_result_signature(data))



class ReceiptTest(BaseRobokassaTest):
    def test_build_receipt_structure(self):
        receipt = robokassa.build_receipt('Подписка DocAI «Personal»', 399, tax='none')
        data = json.loads(receipt)

        self.assertIn('items', data)
        item = data['items'][0]
        self.assertEqual(item['tax'], 'none')
        self.assertEqual(item['quantity'], 1)
        self.assertEqual(item['sum'], 399.0)
        self.assertEqual(item['cost'], 399.0)
        self.assertEqual(item['payment_method'], 'full_payment')
        self.assertEqual(item['payment_object'], 'service')

    def test_receipt_has_no_spaces(self):
        """Пробелы в JSON ломают подпись Robokassa."""
        receipt = robokassa.build_receipt('Тест', 100, tax='none')
        self.assertNotIn(' ', receipt)

    def test_receipt_name_truncated_to_128(self):
        long_name = 'А' * 200
        receipt = robokassa.build_receipt(long_name, 100)
        data = json.loads(receipt)
        self.assertLessEqual(len(data['items'][0]['name']), 128)

    def test_payment_url_with_receipt_includes_it_in_signature(self):
        receipt = robokassa.build_receipt('Тест', 399, tax='none')
        url = robokassa.build_payment_url(
            inv_id=777, amount=399, description='Тест', receipt=receipt,
        )
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)

        self.assertIn('Receipt', qs)
        self.assertEqual(qs['Receipt'][0], receipt)

        expected = md5(f'test_shop:399.00:777:{receipt}:test_pass1')
        self.assertEqual(qs['SignatureValue'][0], expected)

    def test_payment_url_without_receipt(self):
        url = robokassa.build_payment_url(inv_id=777, amount=399, description='Тест')
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)

        self.assertNotIn('Receipt', qs)
        expected = md5('test_shop:399.00:777:test_pass1')
        self.assertEqual(qs['SignatureValue'][0], expected)

    def _auth(self):
        from django.conf import settings
        return {'HTTP_X_BOT_API_KEY': settings.BOT_API_KEY}

    def test_create_payment_returns_url_and_creates_order(self):
        response = self.client.post(
            reverse('payment-create'),
            data={'tg_id': 123456, 'plan': 'personal'},
            content_type='application/json',
            **self._auth(),
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()

        self.assertIn('confirmation_url', data)
        self.assertEqual(data['amount'], '399.00')
        self.assertGreater(data['inv_id'], 0)

        order = RobokassaOrder.objects.get(inv_id=data['inv_id'])
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.amount, Decimal('399.00'))
        self.assertEqual(order.user.tg_id, 123456)
        self.assertEqual(order.plan.slug, 'personal')
        self.assertTrue(order.is_test)

    def test_two_orders_get_different_inv_ids(self):
        """Проверка исправленного бага с int(time.time())."""
        ids = set()
        for _ in range(3):
            response = self.client.post(
                reverse('payment-create'),
                data={'tg_id': 123456, 'plan': 'personal'},
                content_type='application/json',
                **self._auth(),
            )
            self.assertEqual(response.status_code, 200)
            ids.add(response.json()['inv_id'])
        self.assertEqual(len(ids), 3, 'InvId должны быть уникальными')

    def test_unknown_plan_returns_404(self):
        response = self.client.post(
            reverse('payment-create'),
            data={'tg_id': 123456, 'plan': 'nope'},
            content_type='application/json',
            **self._auth(),
        )
        self.assertEqual(response.status_code, 404)

    def test_plan_without_rub_price_returns_400(self):
        plan = Plan.objects.create(slug='usd_only', name='USD', analyses_limit=10, is_active=True)
        PlanPrice.objects.create(plan=plan, currency='USD', amount=Decimal('5.00'))
        response = self.client.post(
            reverse('payment-create'),
            data={'tg_id': 123456, 'plan': 'usd_only'},
            content_type='application/json',
            **self._auth(),
        )
        self.assertEqual(response.status_code, 400)

    def test_requires_api_key(self):
        response = self.client.post(
            reverse('payment-create'),
            data={'tg_id': 123456, 'plan': 'personal'},
            content_type='application/json',
        )
        self.assertIn(response.status_code, (401, 403))



class ResultWebhookTest(BaseRobokassaTest):
    def _make_order(self, amount=Decimal('399.00')):
        return RobokassaOrder.objects.create(
            inv_id=900001,
            user=self.user,
            plan=self.plan,
            amount=amount,
            currency='RUB',
            is_test=True,
            status='pending',
        )

    def _signed_payload(self, inv_id, out_sum):
        base = f'{out_sum}:{inv_id}:test_pass2:Shp_order={inv_id}'
        return {
            'OutSum': out_sum,
            'InvId': str(inv_id),
            'SignatureValue': md5(base),
            'Shp_order': str(inv_id),
        }

    def test_successful_payment_activates_subscription(self):
        order = self._make_order()
        payload = self._signed_payload(order.inv_id, '399.00')

        response = self.client.post(reverse('robokassa-result'), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), f'OK{order.inv_id}')

        order.refresh_from_db()
        self.user.refresh_from_db()

        self.assertEqual(order.status, 'activated')
        self.assertIsNotNone(order.paid_at)
        self.assertEqual(self.user.plan, 'personal')
        self.assertEqual(self.user.usage_count, 0)
        self.assertIsNotNone(self.user.usage_reset)
        self.assertIsNotNone(self.user.subscription_expires)
        self.assertGreater(self.user.subscription_expires, timezone.now())
        self.assertTrue(PaymentLog.objects.filter(
            user=self.user, provider_payment_id=str(order.inv_id),
        ).exists())

    def test_bad_signature_is_rejected(self):
        order = self._make_order()
        payload = self._signed_payload(order.inv_id, '399.00')
        payload['SignatureValue'] = 'deadbeef' * 4

        response = self.client.post(reverse('robokassa-result'), data=payload)
        self.assertEqual(response.status_code, 400)

        order.refresh_from_db()
        self.assertEqual(order.status, 'pending')
        self.user.refresh_from_db()
        self.assertEqual(self.user.plan, 'free')

    def test_amount_mismatch_does_not_activate(self):
        """Нельзя оплатить 1 рубль и получить тариф за 399 рублей."""
        order = self._make_order()
        payload = self._signed_payload(order.inv_id, '1.00')

        response = self.client.post(reverse('robokassa-result'), data=payload)
        self.assertEqual(response.status_code, 200)

        order.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(order.status, 'failed')
        self.assertEqual(self.user.plan, 'free')

    def test_repeated_notification_is_idempotent(self):
        """Повторный ResultURL не должен начислять дни второй раз."""
        order = self._make_order()
        payload = self._signed_payload(order.inv_id, '399.00')

        self.client.post(reverse('robokassa-result'), data=payload)
        self.user.refresh_from_db()
        first_expires = self.user.subscription_expires

        response = self.client.post(reverse('robokassa-result'), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), f'OK{order.inv_id}')

        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription_expires, first_expires)
        self.assertEqual(PaymentLog.objects.filter(user=self.user).count(), 1)

    def test_unknown_order_returns_error(self):
        payload = self._signed_payload(555555, '399.00')
        response = self.client.post(reverse('robokassa-result'), data=payload)
        self.assertEqual(response.status_code, 400)

    def test_order_blocked_after_amount_mismatch_needs_manual_review(self):
        """После расхождения суммы заказ не активируется автоматически."""
        order = self._make_order()
        # 1. Приходит уведомление с заниженной суммой.
        self.client.post(reverse('robokassa-result'),
                         data=self._signed_payload(order.inv_id, '1.00'))
        order.refresh_from_db()
        self.assertEqual(order.status, 'failed')

        # 2. Повторное уведомление уже с верной суммой не активирует заказ.
        response = self.client.post(reverse('robokassa-result'),
                                    data=self._signed_payload(order.inv_id, '399.00'))
        self.assertEqual(response.status_code, 200)

        order.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(order.status, 'failed')
        self.assertEqual(self.user.plan, 'free')
