"""Отдача статики в продакшене без whitenoise и без DEBUG=True.

Django при DEBUG=False сам статику не отдаёт. Здесь мы делаем это вручную:
URL /static/<path> читает файл из STATIC_ROOT. Файлы маленькие и неизменные,
поэтому это нормально для админки.

В nginx запросы к /static/ проксируются на gunicorn, который попадает сюда.
"""
import mimetypes
import os
import posixpath

from django.conf import settings
from django.http import FileResponse, Http404


def static_serve(request, path):
    """Безопасно отдаёт файл из STATIC_ROOT по относительному пути."""
    normalized = posixpath.normpath(path).lstrip('/')

    # Защита от выхода за пределы STATIC_ROOT (../)
    if normalized.startswith('..') or os.path.isabs(normalized):
        raise Http404('Недопустимый путь')

    static_root = str(settings.STATIC_ROOT)
    full_path = os.path.join(static_root, normalized)

    # Дополнительная проверка, что путь внутри STATIC_ROOT
    if not os.path.abspath(full_path).startswith(os.path.abspath(static_root)):
        raise Http404('Недопустимый путь')

    if not os.path.isfile(full_path):
        raise Http404(f'Файл не найден: {normalized}')

    content_type, _ = mimetypes.guess_type(full_path)
    response = FileResponse(open(full_path, 'rb'), content_type=content_type or 'application/octet-stream')
    response['Cache-Control'] = 'public, max-age=2592000'
    return response
