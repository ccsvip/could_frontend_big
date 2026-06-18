import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

django_application = get_asgi_application()


async def application(scope, receive, send):
    if scope.get('type') == 'websocket' and scope.get('path') == '/ws/realtime/':
        from config.realtime import realtime_websocket_application

        await realtime_websocket_application(scope, receive, send)
        return

    await django_application(scope, receive, send)
