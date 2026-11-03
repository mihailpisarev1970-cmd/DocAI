"""Сверка pending-заказов с Robokassa через XML-интерфейс OpStateExt.

Документация: https://docs.robokassa.ru/ru/xml-interfaces

Подпись (Signature) для OpStateExt:
    md5(f'{MerchantLogin}:{InvoiceID}:{Пароль#2}')
Рядом с ним существует OpState с параметром SignatureValue и другим форматом —
на всякий случай пробуем оба.

Коды State.Code:
    5   — инициализирована, ещё не оплачена
    10  — отменена, деньги не получены
    20  — HOLD
    50  — деньги получены, идёт зачисление
    60  — отказ в зачислении
    80  — приостановлено
    100 — платёж проведён успешно
"""

import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from django.conf import settings

from . import robokassa

logger = logging.getLogger(__name__)

BASE_URL = 'https://auth.robokassa.ru/Merchant/WebService/Service.asmx'
NS = '{http://merchant.roboxchange.com/WebService/}'

# Коды состояния, при которых платёж считаем успешным
PAID_STATE_CODES = {'100'}


class RobokassaCheckError(Exception):
    """Не удалось получить статус операции из Robokassa."""


def _fetch(method: str, inv_id: int, param_name: str, signature: str) -> str:
    query = urllib.parse.urlencode({
        'MerchantLogin': settings.ROBOKASSA_LOGIN,
        'InvoiceID': inv_id,
        param_name: signature,
    })
    url = f'{BASE_URL}/{method}?{query}'
    logger.debug('Запрос к Robokassa: %s %s', method, url)

    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=15) as resp:
            return resp.read().decode('utf-8', 'replace')
    except Exception as exc:
        raise RobokassaCheckError(f'Ошибка запроса к Robokassa: {exc}') from exc


def _parse(xml_text: str) -> dict:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RobokassaCheckError(f'Некорректный XML от Robokassa: {exc}') from exc

    def text(path: str) -> str | None:
        node = root.find(path)
        return node.text.strip() if node is not None and node.text else None

    return {
        'code': text(f'.//{NS}Result/{NS}Code') or text('.//Result/Code'),
        'description': text(f'.//{NS}Result/{NS}Description') or text('.//Result/Description'),
        'state': text(f'.//{NS}State/{NS}Code') or text('.//State/Code'),
        'out_sum': text(f'.//{NS}Info/{NS}OutSum') or text('.//Info/OutSum'),
        'inc_sum': text(f'.//{NS}Info/{NS}IncSum') or text('.//Info/IncSum'),
        'payment_method': (
            text(f'.//{NS}Info/{NS}PaymentMethod/{NS}Description')
            or text('.//Info/PaymentMethod/Description')
        ),
        'state_date': text(f'.//{NS}State/{NS}StateDate') or text('.//State/StateDate'),
    }


def _signatures(inv_id: int):
    """Возможные варианты подписи: (param_name, signature)."""
    login = settings.ROBOKASSA_LOGIN
    pass2 = robokassa.password2()
    pass1 = robokassa.password1()

    raw = f'{login}:{inv_id}:{pass2}'
    return [
        ('Signature', robokassa.sign(raw)),
        ('SignatureValue', robokassa.sign(raw)),
        ('SignatureValue', robokassa.sign(f'{login}:{inv_id}:{pass1}')),
    ]


def get_operation_state(inv_id: int) -> dict:
    """Возвращает состояние операции из Robokassa.

    Пробует OpStateExt и OpState с разными вариантами подписи,
    пока какой-нибудь не вернёт Code=0.
    """
    last_error = None

    for method in ('OpStateExt', 'OpState'):
        for param_name, signature in _signatures(inv_id):
            try:
                xml_text = _fetch(method, inv_id, param_name, signature)
                data = _parse(xml_text)
            except RobokassaCheckError as exc:
                last_error = exc
                continue

            code = data.get('code')
            if code == '0':
                data['method'] = method
                return data

            # Code=1 — неверная подпись, пробуем следующий вариант.
            # Code=3 — операция не найдена: дальше пробовать бессмысленно.
            if code == '3':
                raise RobokassaCheckError(
                    f'Операция {inv_id} не найдена в Robokassa'
                )
            last_error = RobokassaCheckError(
                f'{data.get("description") or "ошибка"} (Code={code})'
            )

    raise RobokassaCheckError(str(last_error) if last_error else 'Не удалось получить статус')


def is_paid(state_data: dict) -> bool:
    """Оплачена ли операция по данным Robokassa."""
    return str(state_data.get('state')) in PAID_STATE_CODES
