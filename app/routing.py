from django.conf import settings
from django.conf.urls import url
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.generic.http import AsyncHttpConsumer

from app import consumers


class BasicHttpConsumer(AsyncHttpConsumer):
    async def handle(self, body):
        await self.send_response(501, b"HTTP handling not implemented here", headers=[
            (b"Content-Type", b"text/plain"),
        ])


websocket_urlpatterns = [
    url(r'^ws/mobile-api/(?P<token>.+)$', consumers.MobileApiConsumer),
    url(r'^ws/notifications/(?P<token>.+)$', consumers.NotificationsWebsocketConsumer),
]

http_stub_urlpatterns = [
    url(r'^', BasicHttpConsumer),
]

application_mapping = {
    'websocket': AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
}

if not settings.DEBUG:
    application_mapping['http'] = URLRouter(http_stub_urlpatterns)

application = ProtocolTypeRouter(application_mapping)
