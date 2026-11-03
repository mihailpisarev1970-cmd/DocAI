from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
import hmac

class BotApiKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        key = request.META.get('HTTP_X_BOT_API_KEY')
        expected = getattr(settings, 'BOT_API_KEY', '')
        
        # Сравниваем ключи безопасным способом (защита от timing-атак)
        if not expected or not key or not hmac.compare_digest(key, expected):
            raise AuthenticationFailed({'error': 'Invalid API key'})
        
        return (None, key)