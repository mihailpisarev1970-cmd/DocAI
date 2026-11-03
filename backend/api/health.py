from django.http import JsonResponse
from .models import RobokassaOrder


def health(request):
    """Healthcheck для Docker: контейнер жив, БД доступна."""
    try:
        orders = RobokassaOrder.objects.count()
        return JsonResponse({
            'status': 'ok',
            'service': 'DocAI',
            'database': 'ok',
            'orders': orders,
        })
    except Exception as exc:
        return JsonResponse({
            'status': 'error',
            'error': str(exc)[:200],
        }, status=503)
