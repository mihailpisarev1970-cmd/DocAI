"""Утилиты интеграции с Robokassa.

Документация:
  * Интерфейс оплаты:             https://docs.robokassa.ru/ru/pay-interface
  * Уведомления и переадресация:  https://docs.robokassa.ru/ru/notifications-and-redirects
  * Тестовый режим:               https://docs.robokassa.ru/ru/testing-mode
"""

import hashlib
import hmac
import logging
import urllib.parse
from decimal import Decimal

from django.conf import settings

logger = logging.getLogger(__name__)

PAYMENT_URL = 'https://auth.robokassa.ru/Merchant/Index.aspx'

# Алгоритмы, которые можно выбрать в технических настройках магазина.
_HASH_ALGORITHMS = {
    'MD5': hashlib.md5,
    'SHA1': hashlib.sha1,
    'SHA256': hashlib.sha256,
    'SHA512': hashlib.sha512,
}


class RobokassaError(Exception):
    """Ошибка конфигурации или проверки данных Robokassa."""


def format_sum(amount) -> str:
    """Сумма строго с двумя знаками после запятой (требование Robokassa)."""
    return f'{Decimal(amount):.2f}'


def _algorithm():
    name = (getattr(settings, 'ROBOKASSA_HASH_ALGORITHM', 'MD5') or 'MD5').upper()
    try:
        return _HASH_ALGORITHMS[name]
    except KeyError:
        raise RobokassaError(f'Неподдерживаемый алгоритм хеша: {name}')


def sign(base: str) -> str:
    """Считает контрольную сумму строки выбранным алгоритмом."""
    return _algorithm()(base.encode('utf-8')).hexdigest()


def _shp_part(shp: dict | None) -> str:
    """Пользовательские параметры в том виде, в котором они входят в подпись.

    Robokassa требует передавать Shp_* строго в алфавитном порядке по имени
    параметра, иначе подпись не сойдётся.
    """
    if not shp:
        return ''
    pairs = ':'.join(f'{key}={value}' for key, value in sorted(shp.items()))
    return ':' + pairs


def is_configured() -> bool:
    """Проверяет, что в настройках заданы логин и пароли (а не заглушки)."""
    placeholders = {'', 'ваш_логин_магазина', 'ваш_пароль_1', 'ваш_пароль_2'}
    login = (getattr(settings, 'ROBOKASSA_LOGIN', '') or '').strip()
    pass1 = (getattr(settings, 'ROBOKASSA_PASSWORD1', '') or '').strip()
    pass2 = (getattr(settings, 'ROBOKASSA_PASSWORD2', '') or '').strip()
    return login not in placeholders and pass1 not in placeholders and pass2 not in placeholders


def password1() -> str:
    """Пароль №1 — для формирования подписи платежа и Success/Fail URL."""
    if getattr(settings, 'ROBOKASSA_USE_TEST_PASSWORDS', False):
        test_pass1 = (getattr(settings, 'ROBOKASSA_TEST_PASSWORD1', '') or '').strip()
        if test_pass1:
            return test_pass1
    return settings.ROBOKASSA_PASSWORD1


def password2() -> str:
    """Пароль №2 — для проверки подписи уведомления ResultURL."""
    if getattr(settings, 'ROBOKASSA_USE_TEST_PASSWORDS', False):
        test_pass2 = (getattr(settings, 'ROBOKASSA_TEST_PASSWORD2', '') or '').strip()
        if test_pass2:
            return test_pass2
    return settings.ROBOKASSA_PASSWORD2


def build_receipt(description: str, amount, tax: str = 'none') -> str:
    """Формирует JSON чека для онлайн-кассы (ФЗ-54).

    tax:
        'none'  — без НДС (УСН, патент)
        'vat0'  — НДС 0%
        'vat10' — НДС 10%
        'vat20' — НДС 20%
        'vat110' / 'vat120' — расчётные ставки

    Возвращает компактную JSON-строку без пробелов: Robokassa принимает её
    как есть, а пробелы ломают подпись.
    """
    import json

    cost = float(format_sum(amount))
    receipt = {
        'items': [
            {
                'name': description[:128],          # не длиннее 128 символов
                'quantity': 1,
                'sum': cost,
                'cost': cost,
                'tax': tax,
                'payment_method': 'full_payment',
                'payment_object': 'service',
            }
        ]
    }
    return json.dumps(receipt, ensure_ascii=False, separators=(',', ':'))


def build_payment_url(
    inv_id: int,
    amount,
    description: str,
    shp: dict | None = None,
    email: str = '',
    success_url: str = '',
    fail_url: str = '',
    is_test: bool | None = None,
    receipt: str = '',
) -> str:
    """Формирует ссылку на страницу оплаты Robokassa.

    Подпись (Пароль №1):
        MerchantLogin:OutSum:InvId:Пароль#1[:Shp_*]           — без чека
        MerchantLogin:OutSum:InvId:Receipt:Пароль#1[:Shp_*]   — с чеком ФЗ-54
    """
    if not is_configured():
        raise RobokassaError(
            'Robokassa не настроена: заполните ROBOKASSA_LOGIN, '
            'ROBOKASSA_PASSWORD1 и ROBOKASSA_PASSWORD2 в backend/.env'
        )

    login = settings.ROBOKASSA_LOGIN
    out_sum = format_sum(amount)
    use_test = settings.ROBOKASSA_TEST_MODE if is_test is None else is_test

    params = {
        'MerchantLogin': login,
        'OutSum': out_sum,
        'InvId': str(inv_id),
        'Description': description,
        'Culture': 'ru',
        'Encoding': 'utf-8',
    }

    if use_test:
        params['IsTest'] = '1'
    if email:
        params['Email'] = email

    shp_part = _shp_part(shp)

    # ВАЖНО: SuccessUrl2/FailUrl2 в запросе НЕ передаём.
    # Robokassa ожидает эти адреса в личном кабинете (Технические настройки),
    # а при передаче в запросе вместе с Shp_ возвращает ошибку 29
    # «Оплата счетов недоступна». Адреса уже настроены в ЛК.
    if receipt:
        # По документации Receipt входит в подпись сразу после InvId.
        signature_base = f'{login}:{out_sum}:{inv_id}:{receipt}:{password1()}'
        params['Receipt'] = receipt
    else:
        signature_base = f'{login}:{out_sum}:{inv_id}:{password1()}'

    params['SignatureValue'] = sign(signature_base + shp_part)

    if shp:
        params.update(shp)

    return f'{PAYMENT_URL}?{urllib.parse.urlencode(params)}'


def _extract_shp(data: dict) -> dict:
    return {
        key: value
        for key, value in data.items()
        if key.lower().startswith('shp_')
    }


def verify_result_signature(data: dict) -> bool:
    """Проверяет подпись уведомления ResultURL (Пароль №2).

    База подписи: OutSum:InvId:Пароль#2[:Shp_*]
    В боевом режиме OutSum приходит с шестью знаками после запятой,
    в тестовом — с двумя, поэтому проверяем оба варианта записи суммы.
    """
    out_sum = data.get('OutSum', '')
    inv_id = data.get('InvId', '')
    signature = data.get('SignatureValue', '')

    if not out_sum or not inv_id or not signature:
        return False

    shp_part = _shp_part(_extract_shp(data))

    # Вариант 1 — сумма ровно в том виде, в каком пришла от Robokassa.
    expected = sign(f'{out_sum}:{inv_id}:{password2()}{shp_part}')
    if hmac.compare_digest(expected.upper(), signature.upper()):
        return True

    # Вариант 2 — сумма, нормализованная до двух знаков после запятой.
    try:
        normalized = format_sum(out_sum)
    except Exception:
        return False

    expected_norm = sign(f'{normalized}:{inv_id}:{password2()}{shp_part}')
    return hmac.compare_digest(expected_norm.upper(), signature.upper())


def verify_success_signature(data: dict) -> bool:
    """Проверяет подпись возврата на SuccessURL (Пароль №1).

    База подписи: OutSum:InvId:Пароль#1[:Shp_*]
    """
    out_sum = data.get('OutSum', '')
    inv_id = data.get('InvId', '')
    signature = data.get('SignatureValue', '')

    if not out_sum or not inv_id or not signature:
        return False

    base = f'{out_sum}:{inv_id}:{password1()}' + _shp_part(_extract_shp(data))
    expected = sign(base)
    return hmac.compare_digest(expected.upper(), signature.upper())

    return settings.ROBOKASSA_PASSWORD2
