import pytz

from django.conf import settings
from datetime import datetime, timedelta
from rest_framework.authentication import get_authorization_header, BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from app.models import ContainerAuthToken


def token_is_expired(token):
    utc_now = datetime.utcnow()
    utc_now = utc_now.replace(tzinfo=pytz.utc)
    return token.created < (utc_now - timedelta(minutes=settings.TOKEN_EXPIRATION_MINUTES))


class ExpiringContainerTokenAuthentication(BaseAuthentication):
    keyword = 'ContainerToken'

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None

        if len(auth) == 1:
            msg = 'Invalid token header. No credentials provided.'
            raise AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = 'Invalid token header. Token string should not contain spaces.'
            raise AuthenticationFailed(msg)

        try:
            token = auth[1].decode()
        except UnicodeError:
            msg = 'Invalid token header. Token string should not contain invalid characters.'
            raise AuthenticationFailed(msg)

        try:
            token = ContainerAuthToken.objects.select_related('container').get(key=token)
        except ContainerAuthToken.DoesNotExist:
            raise AuthenticationFailed('Invalid token.')

        # There is no is_active flag for a container.
        # To make container unable to auth just set unusable password for it.

        if token_is_expired(token):
            token.delete()
            raise AuthenticationFailed('Token has expired')

        return token.container, token

    def authenticate_header(self, request):
        return self.keyword
