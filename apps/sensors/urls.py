from django.urls import path

from apps.sensors.views import (
    SensorsListView, SensorsDataView, SensorUpdateView, SensorMapCard, SensorControlMainView,
    sensor_control_request_gps, sensor_control_request_calibrate, sensor_control_request_orient,
)


app_name = 'sensors'

urlpatterns = [
    path('', SensorsListView.as_view(), name='list'),
    path('data/', SensorsDataView.as_view(), name='data'),
    path('<int:pk>/update/', SensorUpdateView.as_view(), name='update'),
    path('<int:pk>/map-card/', SensorMapCard.as_view(), name='map-card'),
    path('<int:pk>/control-main/', SensorControlMainView.as_view(), name='control-main'),
    path('<int:pk>/control-gps/', sensor_control_request_gps, name='control-gps'),
    path('<int:pk>/control-calibrate/', sensor_control_request_calibrate, name='control-calibrate'),
    path('<int:pk>/control-orient/', sensor_control_request_orient, name='control-orient'),
]
