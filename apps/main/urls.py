from django.urls import path

from apps.core.middleware import license_check_exempt
from apps.main.views import (
    home_login, view_login, view_logout, view_main, view_efficiency_monitor, view_switch_device_profile,
    RegisterCompanyFormView,
)


app_name = 'main'

urlpatterns = [
    path('', home_login, name='home'),
    path('login/', view_login, name='login'),
    path('logout/', license_check_exempt(view_logout), name='logout'),
    path('main/', view_main, name='map'),
    path('tools/efficiency-monitor/', view_efficiency_monitor, name='efficiency-monitor'),
    path('switch-device-profile/', view_switch_device_profile, name='switch-device-profile'),
    path('register-company/', RegisterCompanyFormView.as_view(), name='register-company'),
]
