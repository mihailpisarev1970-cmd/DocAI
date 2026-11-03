from django.contrib import admin
from django.urls import path, include, re_path

from api.health import health
from api.static_serve import static_serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('health/', health, name='health'),

    # Статика админки при DEBUG=False (nginx проксирует /static/ сюда)
    re_path(r'^static/(?P<path>.*)$', static_serve, name='static-serve'),
]
