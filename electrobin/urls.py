from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib.gis import admin
from django.shortcuts import redirect
from django.urls import reverse_lazy, path
from os import listdir

from apps.sensors.api import SensorListAPIView
from app.api import (
    ContainerListAPIView, CitiesListAPIView, MobileApiObtainAuthToken, UserProfile, MobileAppTranslationView,
    get_trashbin_auth_token, TrashbinDataView, TrashbinJobsView, GenericObtainAuthToken,
)
from apps.core.helpers import CompanyDeviceProfile
from apps.core.urls import account_urlpatterns
from apps.core.views import (
    create_top_level_static_view, TOP_LEVEL_STATIC_DIR, NotificationsFeedDataView, NotificationsListView,
    FollowNotificationView, MarkAllNotificationsReadView, NotificationsSettingsFormView, switch_language,
)
from app.views import (
    CityList, CityCreate, CityUpdate, CityDelete, CityDataView,
    CompanyList, CompanyCreate, CompaniesDataView, CompanyUpdate, CompanyDelete, CompanyUserList,
    UserList, UserCreate, UsersDataView, UserDelete, UserUpdate,
    ContainerList, ContainerCreate, ContainersDataView, ContainerMapCard, ContainerDelete, ContainerUpdate,
    ContainerDetail,
    SectorList, SectorCreate, SectorsDataView, SectorUpdate, SectorDelete,
    RoutesList, RoutesDataView, RouteAbort, RouteDetail, RouteResend,
    DriversList, DriversDataView, DriverDetail,
    DriverUnavailabilityPeriodCreate, DriverUnavailabilityPeriodUpdate, DriverUnavailabilityPeriodDelete,
)
from apps.sensors.views import (
    SensorsListView, SensorsDataView, SensorUpdateView, SensorMapCard, CreateRouteView as SensorCreateRouteView,
    OnboardSensorView,
)
from apps.trashbins.views import CreateRouteView as TrashbinCreateRouteView, TrashbinFullnessForecastView
from apps.main.helpers import get_effective_company_device_profile
from apps.main.views import settings_index, invalid_license_view, account_info_view, extend_license_view
from views.report_simbalance import report_simbalance, SimBalanceReportList
# from views.report_traffic import *
from views.report_pressure import report_pressure, PressureReportList, PressureReportStackedChart
from views.report_humidity import report_humidity, HumidityReportList, HumidityReportStackedChart
from views.report_air_quality import report_air_quality, AirQualityReportList, AirQualityReportStackedChart

from apps.trashbins.reports.fullness import (
    report_fullness as trashbin_report_fullness,
    FullnessReportList as TrashbinFullnessReportList,
    FullnessReportStackedChart as TrashbinFullnessReportStackedChart,
)
from apps.trashbins.reports.battery_level import (
    report_battery_level as trashbin_report_battery_level,
    BatteryLevelReportList as TrashbinBatteryLevelReportList,
    BatteryLevelReportStackedChart as TrashbinBatteryLevelReportStackedChart,
)
from apps.trashbins.reports.errors import (
    report_errors as trashbin_report_errors,
    ErrorsReportList as TrashbinErrorsReportList,
    ErrorsReportPieChart as TrashbinErrorsReportPieChart,
)
from apps.trashbins.reports.temperature import (
    report_temperature as trashbin_report_temperature,
    TemperatureReportList as TrashbinTemperatureReportList,
    TemperatureReportStackedChart as TrashbinTemperatureReportStackedChart,
)
from apps.trashbins.reports.collection import (
    report_collection as trashbin_report_collection,
    CollectionReportList as TrashbinCollectionReportList,
    CollectionReportErrorsPieChart as TrashbinCollectionReportErrorsPieChart,
    CollectionReportFullnessPieChart as TrashbinCollectionReportFullnessPieChart,
    CollectionReportTypesPieChart as TrashbinCollectionReportWasteTypesPieChart,
    CollectionReportSectorsPieChart as TrashbinCollectionReportSectorsPieChart,
)

from apps.sensors.reports.fullness import (
    report_fullness as sensor_report_fullness,
    FullnessReportList as SensorFullnessReportList,
    FullnessReportStackedChart as SensorFullnessReportStackedChart,
)
from apps.sensors.reports.battery_level import (
    report_battery_level as sensor_report_battery_level,
    BatteryLevelReportList as SensorBatteryLevelReportList,
    BatteryLevelReportStackedChart as SensorBatteryLevelReportStackedChart,
)
from apps.sensors.reports.errors import (
    report_errors as sensor_report_errors,
    ErrorsReportList as SensorErrorsReportList,
    ErrorsReportPieChart as SensorErrorsReportPieChart,
)
from apps.sensors.reports.temperature import (
    report_temperature as sensor_report_temperature,
    TemperatureReportList as SensorTemperatureReportList,
    TemperatureReportStackedChart as SensorTemperatureReportStackedChart,
)
from apps.sensors.reports.collection import (
    report_collection as sensor_report_collection,
    CollectionReportList as SensorCollectionReportList,
    CollectionReportWasteTypesPieChart as SensorCollectionReportWasteTypesPieChart,
    CollectionReportSectorsPieChart as SensorCollectionReportSectorsPieChart,
)

from apps.main.reports.track import report_track, TrackReportList


api_urlpatterns = [
    url(r'^containers/$', ContainerListAPIView.as_view()),
    url(r'^cities/(?P<pk>\d+)/$', CitiesListAPIView.as_view()),
    url(r'^mobile/auth-token/', MobileApiObtainAuthToken.as_view()),
    url(r'^mobile/profile/$', UserProfile.as_view()),
    url(r'^mobile/language/$', MobileAppTranslationView.as_view()),
    url(r'^trashbin/get-token/', get_trashbin_auth_token),
    url(r'^trashbin/data/', TrashbinDataView.as_view()),
    url(r'^trashbin/jobs/', TrashbinJobsView.as_view()),
    url(r'^sensors/$', SensorListAPIView.as_view()),
    url(r'^get-auth-token/', GenericObtainAuthToken.as_view(), name='api-get-token'),
    url(r'^$', lambda r: redirect(reverse_lazy('api-get-token')), name='api-root'),
]

cities_urlpatterns = ([
    url(r'^$', CityList.as_view(), name='list'),
    url(r'^create/$', CityCreate.as_view(), name='create'),
    url(r'^data/$', CityDataView.as_view(), name='data'),
    url(r'^(?P<pk>\d+)/update/$', CityUpdate.as_view(), name='update'),
    url(r'^(?P<pk>\d+)/delete/$', CityDelete.as_view(), name='delete'),
], 'cities')

company_urlpatterns = ([
    url(r'^$', CompanyList.as_view(), name='list'),
    url(r'^add/$', CompanyCreate.as_view(), name='add'),
    url(r'^data/$', CompaniesDataView.as_view(), name='data'),
    url(r'(?P<pk>\d+)/delete/$', CompanyDelete.as_view(), name='delete'),
    url(r'(?P<pk>\d+)/update/$', CompanyUpdate.as_view(), name='update'),
    url(r'(?P<pk>\d+)/users/$', CompanyUserList.as_view(), name='users'),
], 'companies')

user_urlpatterns = ([
    url(r'^$', UserList.as_view(), name='list'),
    url(r'^create/$', UserCreate.as_view(), name='create'),
    url(r'^data/$', UsersDataView.as_view(), name='data'),
    url(r'^(?P<pk>\d+)/delete/$', UserDelete.as_view(), name='delete'),
    url(r'^(?P<pk>\d+)/update/$', UserUpdate.as_view(), name='update'),
], 'users')

container_urlpatterns = ([
    url(r'^$', ContainerList.as_view(), name='list'),
    url(r'^create/$', ContainerCreate.as_view(), name='create'),
    url(r'^data/$', ContainersDataView.as_view(), name='data'),
    url(r'^map/$', ContainerListAPIView.as_view(), name='map'),
    url(r'^(?P<pk>\d+)/$', ContainerDetail.as_view(), name='detail'),
    url(r'^(?P<pk>\d+)/map-card/$', ContainerMapCard.as_view(), name='map-card'),
    url(r'^(?P<pk>\d+)/delete/$', ContainerDelete.as_view(), name='delete'),
    url(r'^(?P<pk>\d+)/update/$', ContainerUpdate.as_view(), name='update'),
], 'containers')

sector_urlpatterns = ([
    url(r'^$', SectorList.as_view(), name='list'),
    url(r'^create/$', SectorCreate.as_view(), name='create'),
    url(r'^data/$', SectorsDataView.as_view(), name='data'),
    url(r'^(?P<pk>\d+)/update/$', SectorUpdate.as_view(), name='update'),
    url(r'^(?P<pk>\d+)/delete/$', SectorDelete.as_view(), name='delete'),
], 'sectors')

trashbin_reports_urlpatterns = ([
    path('fullness/', trashbin_report_fullness, name='fullness'),
    path('fullness/table-data/', TrashbinFullnessReportList.as_view(), name='fullness_table_data'),
    path('fullness/chart-data/', TrashbinFullnessReportStackedChart.as_view(), name='fullness_chart_data'),

    path('battery-level/', trashbin_report_battery_level, name='battery_level'),
    path('battery-level/table-data/', TrashbinBatteryLevelReportList.as_view(), name='battery_level_table_data'),
    path('battery-level/chart-data/', TrashbinBatteryLevelReportStackedChart.as_view(),
         name='battery_level_chart_data'),

    path('errors/', trashbin_report_errors, name='errors'),
    path('errors/table-data/', TrashbinErrorsReportList.as_view(), name='errors_table_data'),
    path('errors/chart-data/', TrashbinErrorsReportPieChart.as_view(), name='errors_chart_data'),

    path('temperature/', trashbin_report_temperature, name='temperature'),
    path('temperature/table-data/', TrashbinTemperatureReportList.as_view(), name='temperature_table_data'),
    path('temperature/chart-data/', TrashbinTemperatureReportStackedChart.as_view(), name='temperature_chart_data'),

    path('collection/', trashbin_report_collection, name='collection'),
    path('collection/table-data/', TrashbinCollectionReportList.as_view(), name='collection_table_data'),
    path('collection/chart-data/errors/', TrashbinCollectionReportErrorsPieChart.as_view(),
         name='collection_chart_data_errors'),
    path('collection/chart-data/fullness/', TrashbinCollectionReportFullnessPieChart.as_view(),
         name='collection_chart_data_fullness'),
    path('collection/chart-data/waste-types/', TrashbinCollectionReportWasteTypesPieChart.as_view(),
         name='collection_chart_data_waste_types'),
    path('collection/chart-data/sectors/', TrashbinCollectionReportSectorsPieChart.as_view(),
         name='collection_chart_data_sectors'),
], 'trashbin')

sensor_reports_urlpatterns = ([
    path('fullness/', sensor_report_fullness, name='fullness'),
    path('fullness_data/', SensorFullnessReportList.as_view(), name='fullness_table_data'),
    path('fullness_data_stacked_chart/', SensorFullnessReportStackedChart.as_view(), name='fullness_chart_data'),

    path('battery_level/', sensor_report_battery_level, name='battery_level'),
    path('battery_level_data/', SensorBatteryLevelReportList.as_view(), name='battery_level_table_data'),
    path('battery_level_stacked_chart/', SensorBatteryLevelReportStackedChart.as_view(),
         name='battery_level_chart_data'),

    path('errors/', sensor_report_errors, name='errors'),
    path('errors/table-data/', SensorErrorsReportList.as_view(), name='errors_table_data'),
    path('errors/chart-data/', SensorErrorsReportPieChart.as_view(), name='errors_chart_data'),

    path('temperature/', sensor_report_temperature, name='temperature'),
    path('temperature/table-data/', SensorTemperatureReportList.as_view(), name='temperature_table_data'),
    path('temperature/chart-data/', SensorTemperatureReportStackedChart.as_view(), name='temperature_chart_data'),

    path('collection/', sensor_report_collection, name='collection'),
    path('collection/table-data/', SensorCollectionReportList.as_view(), name='collection_table_data'),
    path('collection/chart-data/waste-types/', SensorCollectionReportWasteTypesPieChart.as_view(),
         name='collection_chart_data_waste_types'),
    path('collection/chart-data/sectors/', SensorCollectionReportSectorsPieChart.as_view(),
         name='collection_chart_data_sectors'),
], 'sensor')


common_reports_urlpatterns = ([
    path('track/', report_track, name='track'),
    path('track/table-data/', TrackReportList.as_view(), name='track_table_data'),
], 'common')


def reports_index(request):
    device_profile = get_effective_company_device_profile(request)
    if device_profile == CompanyDeviceProfile.SENSOR:
        return redirect('reports:sensor:fullness')
    return redirect('reports:trashbin:fullness')


reports_urlpatterns = ([
    url(r'^$', reports_index, name='index'),

    # Traffic report was disabled since its absolutely fake at the moment
    # url(r'^traffic/$', report_traffic, name='traffic'),
    # url(r'^traffic_data/$',TrafficReportList.as_view(), name='trafficdata'),
    # url(r'^traffic_data_stacked_chart/$', TrafficReportStackedChart.as_view(), name='trafficdata_chart'),

    url(r'^pressure/$', report_pressure, name='pressure'),
    url(r'^pressure_data/$', PressureReportList.as_view(), name='pressuredata'),
    url(r'^pressure_data_stacked_chart/$', PressureReportStackedChart.as_view(), name='pressuredata_chart'),

    url(r'^sim/$', report_simbalance, name='sim'),
    url(r'^simbalance_data/$', SimBalanceReportList.as_view(), name='simbalancedata'),

    url(r'^humidity/$', report_humidity, name='humidity'),
    url(r'^humidity_table_data/$', HumidityReportList.as_view(), name='humidity_table_data'),
    url(r'^humidity_line_chart_data/$', HumidityReportStackedChart.as_view(), name='humidity_chart_data'),

    url(r'^air_quality/$', report_air_quality, name='air_quality'),
    url(r'^air_quality_table_data/$', AirQualityReportList.as_view(), name='air_quality_table_data'),
    url(r'^air_quality_line_chart_data/$', AirQualityReportStackedChart.as_view(), name='air_quality_chart_data'),

    path('trashbin/', include(trashbin_reports_urlpatterns)),
    path('sensor/', include(sensor_reports_urlpatterns)),
    path('common/', include(common_reports_urlpatterns)),
], 'reports')


def route_create_index(request):
    device_profile = get_effective_company_device_profile(request)
    if device_profile == CompanyDeviceProfile.SENSOR:
        return SensorCreateRouteView.as_view()(request)
    return TrashbinCreateRouteView.as_view()(request)


routes_urlpatterns = ([
    url(r'^$', lambda r: redirect(reverse_lazy('routes:create')), name='index'),
    url(r'^create/$', route_create_index, name='create'),
    url(r'^list/$', RoutesList.as_view(), name='list'),
    url(r'^data/$', RoutesDataView.as_view(), name='data'),
    url(r'^(?P<pk>\d+)/abort/$', RouteAbort.as_view(), name='abort'),
    url(r'^(?P<pk>\d+)/detail/$', RouteDetail.as_view(), name='detail'),
    url(r'^(?P<pk>\d+)/resend/$', RouteResend.as_view(), name='resend'),
], 'routes')

route_drivers_urlpatterns = ([
    url(r'^list/$', DriversList.as_view(), name='list'),
    url(r'^data/$', DriversDataView.as_view(), name='data'),
    url(r'^(?P<pk>\d+)/detail/$', DriverDetail.as_view(), name='detail'),
    url(r'^(?P<pk>\d+)/unavailability-period/create/$', DriverUnavailabilityPeriodCreate.as_view(),
        name='create_unavailability_period'),
    url(r'unavailability-period/(?P<pk>\d+)/update/$', DriverUnavailabilityPeriodUpdate.as_view(),
        name='update_unavailability_period'),
    url(r'unavailability-period/(?P<pk>\d+)/delete/$', DriverUnavailabilityPeriodDelete.as_view(),
        name='delete_unavailability_period'),
], 'drivers')

sensors_settings_urlpatterns = ([
    path('', SensorsListView.as_view(), name='list'),
    path('data/', SensorsDataView.as_view(), name='data'),
    path('<int:pk>/update/', SensorUpdateView.as_view(), name='update'),
    path('<int:pk>/map-card/', SensorMapCard.as_view(), name='map-card'),
], 'sensors')

fullness_forecasts_urlpatterns = ([
    path('trashbin/<int:pk>/', TrashbinFullnessForecastView.as_view(), name='trashbin'),
], 'fullness-forecast')

top_level_static_urlpatterns = []
for file_name in listdir(TOP_LEVEL_STATIC_DIR):
    top_level_static_urlpatterns.append(url(r'^' + file_name, create_top_level_static_view(file_name)))

main_urlconfig = [
    url(r'^api/', include(api_urlpatterns)),
    url(r'^settings/$', settings_index, name='settings_index'),
    # Компании
    url(r'^settings/companies/', include(company_urlpatterns)),
    # Пользователи
    url(r'^settings/users/', include(user_urlpatterns)),
    # Контейнеры
    url(r'^settings/containers/', include(container_urlpatterns)),
    # Секторы
    url(r'^settings/sectors/', include(sector_urlpatterns)),
    # Города
    url(r'^settings/cities/', include(cities_urlpatterns)),
    # Маршруты
    url(r'^routes/', include(routes_urlpatterns)),
    url(r'^drivers/', include(route_drivers_urlpatterns)),
    # Отчеты
    url(r'^reports/', include(reports_urlpatterns)),
    # Админка
    url(r'^admin/', admin.site.urls),
    # Аккаунт
    url(r'^account/info/', account_info_view, name='account-info'),
    url(r'^account/extend-license/', extend_license_view, name='extend-license'),
    url(r'^account/', include(account_urlpatterns)),
    url(r'^invalid-license$', invalid_license_view, name='invalid-license'),
    # Sensors app urls
    url(r'^settings/sensors/', include('apps.sensors.urls')),
    path('onboard-sensor/<str:serial>/', OnboardSensorView.as_view(), name='onboard-sensor'),
    # Forecasts
    path('fullness-forecast/', include(fullness_forecasts_urlpatterns)),
    # Notifications
    path('notifications/', NotificationsListView.as_view(), name='notifications_list'),
    path('notifications/data/', NotificationsFeedDataView.as_view(), name='notifications_table_data'),
    path('notifications/mark-all-read/', MarkAllNotificationsReadView.as_view(), name='notifications_mark_all_read'),
    path('notifications/settings/', NotificationsSettingsFormView.as_view(), name='notifications_settings'),
    path('notifications/<int:pk>/follow/', FollowNotificationView.as_view(), name='notifications_follow'),
    # Switch language
    path('switch-lang/<str:lang>/', switch_language, name='switch_language'),
    # Main app urls
    path('', include('apps.main.urls')),
]

urlpatterns = main_urlconfig + top_level_static_urlpatterns + \
              static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
