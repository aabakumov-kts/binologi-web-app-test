from django.urls import path

from apps.core.middleware import license_check_exempt
from apps.core.views import CustomPasswordChangeView, TimezoneChangeView


account_urlpatterns = ([
    path('change-password/', license_check_exempt(CustomPasswordChangeView.as_view()), name='change_password'),
    path('change-timezone/', license_check_exempt(TimezoneChangeView.as_view()), name='change_timezone'),
], 'account')
