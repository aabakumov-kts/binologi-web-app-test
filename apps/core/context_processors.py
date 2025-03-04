from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.urls import resolve
from django.urls.exceptions import Resolver404
from django.utils.translation import ugettext_lazy as _
from rest_framework.authtoken.models import Token

from apps.core.models import FeatureFlag


MODAL_MESSAGE_EXTRA_TAGS = 'modal'


def get_return_to_url(request, param='returnTo'):
    if param not in request.GET:
        return None
    # Trying to resolve to make sure it's our URL
    result = request.GET[param]
    try:
        resolve(result)
    except Resolver404:
        return None
    else:
        return result


# Actual context processors follow

def app_env_name(request):
    return {
        'app_env_name': settings.APP_ENV_NAME,
    }


def feature_flag_model(request):
    return {
        'feature_flag_model': FeatureFlag,
    }


def process_messages(request):
    storage = messages.get_messages(request)
    # Iteration over storage here is important
    # See https://docs.djangoproject.com/en/2.2/ref/contrib/messages/#displaying-messages for details
    result = {}
    alerts = []
    result['alerts'] = alerts
    for message in storage:
        if message.extra_tags == MODAL_MESSAGE_EXTRA_TAGS:
            result['modal_to_display'] = message.message
        else:
            alerts.append(message)
    return result


def return_url(request):
    result = {}
    return_to_url = get_return_to_url(request)
    if return_to_url:
        result['return_to_url'] = return_to_url
    return result


def freshdesk_widget_fields(request):
    result = {}
    if request.user.is_authenticated:
        result['freshdesk_widget_email'] = request.user.email
        subject = _('New support request from user #%(user_id)s') % {'user_id': request.user.id}
        result['freshdesk_widget_subject'] = subject
    return result


def notifications(request):
    result = {}
    if request.user.is_authenticated:
        result['realtime_api_root_url'] = settings.REALTIME_API_ROOT_URL
        user_model = get_user_model()
        try:
            token = request.user.auth_token
        except user_model.auth_token.RelatedObjectDoesNotExist:
            token = Token.objects.create(user=request.user)
        result['realtime_api_auth_token'] = token.key
        # We don't care if there are more than 10 unread notifications here
        unread_notifications_count = len(request.user.notifications.unread().order_by('-timestamp')[:10])
        if unread_notifications_count:
            result['unread_notifications_count'] = str(unread_notifications_count) \
                if unread_notifications_count < 10 else '9+'
    return result
