"""Тесты реферальной программы.

Запуск:
    cd backend
    ..\\venv\\Scripts\\python.exe manage.py test api.tests_referral --settings=config.settings_test
"""

import hashlib
import json
from decimal import Decimal

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from api.models import Plan, PlanPrice, User, ReferralLog


def md5(value: str) -> str:
    return hashlib.md5(value.encode('utf-8')).hexdigest()


class BaseReferralTest(TestCase):
    def setUp(self):
        self.plan = Plan.objects.create(
            slug='personal', name='Personal', analyses_limit=30, is_active=True, order=1,
        )
        PlanPrice.objects.create(plan=self.plan, currency='RUB', amount=Decimal('399.00'))
        self.referrer = User.objects.create(tg_id=111111, username='referrer')

    def auth(self):
        return {'HTTP_X_BOT_API_KEY': settings.BOT_API_KEY}

    def signup(self, tg_id, referrer_id=None):
        payload = {'tg_id': tg_id, 'username': f'user{tg_id}'}
        if referrer_id is not None:
            payload['referrer_id'] = referrer_id
        return self.client.post(
            reverse('user-get-or-create'),
            data=json.dumps(payload),
            content_type='application/json',
            **self.auth(),
        )

    def pay(self, tg_id, amount='399.00'):
        resp = self.client.post(
            reverse('payment-create'),
            data=json.dumps({'tg_id': tg_id, 'plan': 'personal'}),
            content_type='application/json',
            **self.auth(),
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        inv_id = resp.json()['inv_id']
        sig = md5(f'{amount}:{inv_id}:test_pass2:Shp_order={inv_id}')
        webhook = self.client.post(reverse('robokassa-result'), data={
            'OutSum': amount,
            'InvId': str(inv_id),
            'SignatureValue': sig,
            'Shp_order': str(inv_id),
        })
        self.assertEqual(webhook.status_code, 200, webhook.content)
        return inv_id



class AttachReferrerTest(BaseReferralTest):
    def test_new_user_gets_referrer_and_log(self):
        resp = self.signup(222222, referrer_id=111111)
        self.assertEqual(resp.status_code, 200, resp.content)

        friend = User.objects.get(tg_id=222222)
        self.assertEqual(friend.referrer_id, 111111)

        log = ReferralLog.objects.get(referred=friend)
        self.assertEqual(log.referrer, self.referrer)
        self.assertFalse(log.bonus_granted)
        self.assertEqual(log.bonus_amount, 0)

    def test_self_referral_is_ignored(self):
        self.signup(333333, referrer_id=333333)
        user = User.objects.get(tg_id=333333)
        self.assertIsNone(user.referrer_id)
        self.assertFalse(ReferralLog.objects.filter(referred=user).exists())

    def test_unknown_referrer_is_ignored(self):
        self.signup(444444, referrer_id=999999)
        self.assertIsNone(User.objects.get(tg_id=444444).referrer_id)

    def test_invalid_referrer_format_is_ignored(self):
        resp = self.signup(555555, referrer_id='ref_abc')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(User.objects.get(tg_id=555555).referrer_id)

    def test_existing_user_does_not_get_referrer(self):
        """Повторный /start не должен менять реферера."""
        self.signup(666666)
        self.signup(666666, referrer_id=111111)
        self.assertIsNone(User.objects.get(tg_id=666666).referrer_id)
        self.assertEqual(ReferralLog.objects.count(), 0)


class ReferralBonusTest(BaseReferralTest):
    def test_bonus_granted_after_payment(self):
        self.signup(222222, referrer_id=111111)
        self.pay(222222)

        self.referrer.refresh_from_db()
        self.assertEqual(self.referrer.bonus_analyses, 30)

        log = ReferralLog.objects.get(referred__tg_id=222222)
        self.assertTrue(log.bonus_granted)
        self.assertEqual(log.bonus_amount, 30)

    def test_no_bonus_without_referrer(self):
        self.signup(777777)
        self.pay(777777)

        self.referrer.refresh_from_db()
        self.assertEqual(self.referrer.bonus_analyses, 0)
        self.assertEqual(ReferralLog.objects.count(), 0)

    def test_bonus_granted_only_once(self):
        """Повторная оплата того же друга не даёт бонус второй раз."""
        self.signup(222222, referrer_id=111111)
        self.pay(222222)
        self.pay(222222)

        self.referrer.refresh_from_db()
        self.assertEqual(self.referrer.bonus_analyses, 30)

    def test_bonus_not_granted_on_failed_payment(self):
        """Если сумма не совпала — бонус не начисляется."""
        self.signup(222222, referrer_id=111111)
        self.pay(222222, amount='1.00')

        self.referrer.refresh_from_db()
        self.assertEqual(self.referrer.bonus_analyses, 0)
        log = ReferralLog.objects.get(referred__tg_id=222222)
        self.assertFalse(log.bonus_granted)


class ReferralStatsTest(BaseReferralTest):
    def test_stats_counts(self):
        self.signup(222222, referrer_id=111111)
        self.signup(333333, referrer_id=111111)
        self.pay(222222)

        resp = self.client.get(
            reverse('referral-stats', args=[111111]), **self.auth(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data['invited_total'], 2)
        self.assertEqual(data['invited_paid'], 1)
        self.assertEqual(data['bonus_earned'], 30)
        self.assertEqual(data['bonus_balance'], 30)
        self.assertEqual(data['bonus_per_referral'], 30)

    def test_stats_unknown_user(self):
        resp = self.client.get(reverse('referral-stats', args=[999999]), **self.auth())
        self.assertEqual(resp.status_code, 404)

    def test_stats_requires_api_key(self):
        resp = self.client.get(reverse('referral-stats', args=[111111]))
        self.assertIn(resp.status_code, (401, 403))
