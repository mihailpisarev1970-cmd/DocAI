import httpx
from config import BACKEND_URL, BOT_API_KEY

_client = httpx.AsyncClient(
    base_url=BACKEND_URL,
    headers={'X-Bot-Api-Key': BOT_API_KEY},
    timeout=60.0,
)

async def get_or_create_user(
    tg_id: int,
    username: str | None,
    full_name: str | None,
    referrer_id: int | None = None,
) -> dict:
    payload = {'tg_id': tg_id, 'username': username, 'full_name': full_name}
    if referrer_id:
        payload['referrer_id'] = referrer_id
    r = await _client.post('/api/users/get-or-create/', json=payload)
    r.raise_for_status()
    return r.json()

async def get_referral_stats(tg_id: int) -> dict:
    r = await _client.get(f'/api/users/{tg_id}/referrals/')
    r.raise_for_status()
    return r.json()

async def increment_usage(tg_id: int) -> dict:
    r = await _client.post(f'/api/users/{tg_id}/increment-usage/')
    r.raise_for_status()
    return r.json()

async def save_document(tg_id: int, doc_type: str, summary: str, full_response: str) -> dict:
    r = await _client.post('/api/documents/', json={
        'tg_id': tg_id,
        'doc_type': doc_type,
        'summary': summary,
        'full_response': full_response,
        'risk_level': 'low'
    })
    r.raise_for_status()
    return r.json()

async def create_payment(tg_id: int, plan: str) -> dict:
    r = await _client.post('/api/payments/create/', json={
        'tg_id': tg_id, 'plan': plan
    })
    r.raise_for_status()
    return r.json()

async def get_payment_status(inv_id: int) -> dict:
    r = await _client.get(f'/api/payments/{inv_id}/status/')
    r.raise_for_status()
    return r.json()

async def reconcile_payment(inv_id: int) -> dict:
    """Просит бэкенд сверить заказ с Robokassa и активировать при оплате."""
    r = await _client.post(f'/api/payments/{inv_id}/reconcile/')
    r.raise_for_status()
    return r.json()

async def reconcile_all_pending(hours: int = 72) -> dict:
    """Сверяет все pending-заказы за последние N часов."""
    r = await _client.post('/api/payments/reconcile-all/', json={'hours': hours})
    r.raise_for_status()
    return r.json()

async def close():
    await _client.aclose()