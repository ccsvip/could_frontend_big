import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

django_application = get_asgi_application()


async def application(scope, receive, send):
    if scope.get('type') == 'websocket' and scope.get('path') == '/ws/device-runtime/status/':
        from apps.devices.websocket import device_status_websocket_application

        await device_status_websocket_application(scope, receive, send)
        return
    if scope.get('type') == 'websocket' and scope.get('path') == '/ws/devices/events/':
        from apps.devices.realtime import device_events_websocket_application

        await device_events_websocket_application(scope, receive, send)
        return

    await django_application(scope, receive, send)
