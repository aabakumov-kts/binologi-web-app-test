from django.conf import settings
from django.db.models import Case, When, Value, BooleanField, OuterRef, Exists, Subquery
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from apps.core.data import FULLNESS
from apps.core.helpers import filter_queryset_by_bounds, filter_queryset_by_fullness
from apps.sensors.models import Sensor, Fullness as SensorFullness
from apps.sensors.serializers import SensorSerializer
from app.models import RoutePoints, ROUTE_POINT_STATUS_NOT_COLLECTED


class SensorListAPIView(GenericAPIView):
    serializer_class = SensorSerializer

    def get(self, request):
        sensors_queryset = self.filter_queryset(self.get_queryset()).distinct()
        serializer = self.get_serializer(sensors_queryset, many=True)
        return Response({'sensors': serializer.data})

    def get_queryset(self):
        if not (self.request.uac.is_superadmin or (
                self.request.uac.has_per_company_access and self.request.uac.company)):
            return Sensor.objects.none()
        not_collected_route_points = RoutePoints.objects.filter(
            sensor=OuterRef('pk'), status=ROUTE_POINT_STATUS_NOT_COLLECTED)
        latest_data_timestamp = SensorFullness.objects.filter(sensor=OuterRef('pk'), actual=True)
        return Sensor.objects.select_related('city').filter(disabled=False).annotate(
            any_active_routes=Exists(not_collected_route_points),
            low_battery_level=Case(
                When(battery__lte=settings.LOW_BATTERY_STATUS_ICON_LEVEL_THRESHOLD, then=Value(True)),
                default=Value(False),
                output_field=BooleanField()),
            latest_data_timestamp=Subquery(latest_data_timestamp.values('ctime')[:1]))

    def filter_queryset(self, queryset):
        if self.request.uac.company:
            queryset = queryset.filter(company=self.request.uac.company)

        params = self.request.query_params

        # fullness complex query ( AND ) OR ( AND ) OR ...
        fullness_list = [x for x in FULLNESS if x.title in params.getlist('fullness', [])]
        queryset = filter_queryset_by_fullness(queryset, fullness_list)

        waste_type = params.getlist('waste_type', [])
        if waste_type:
            queryset = queryset.filter(waste_type__in=waste_type, )

        error_type = params.getlist('error_type', [])
        if error_type:
            error_list = [int(er) for er in error_type]
            queryset = queryset.filter(error__error_type__in=error_list, error__actual=True)

        sector = params.getlist('sector', [])
        if sector:
            queryset = queryset.filter(sector__in=sector)

        serials = params.getlist('serial', [])
        if serials:
            queryset = queryset.filter(serial_number__in=serials)

        bounds = [self.request.query_params.get(k) for k in ['north', 'west', 'south', 'east']]
        return filter_queryset_by_bounds(queryset, bounds)
