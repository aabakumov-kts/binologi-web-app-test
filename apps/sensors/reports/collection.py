from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, F, IntegerField, Case, When, Value
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils.translation import get_language

from apps.core.reports import (
    check_report_access, BaseChartView, underline_columns, BaseReportDatatableView, filter_columns,
    COMMON_PIE_CHART_SETTINGS,
)
from app.models import RoutePoints, ROUTE_POINT_STATUS_COLLECTED
from apps.sensors.reports.shared import collect_sensor_request_context, common_filter_sensor_queryset
from apps.sensors.tables import CollectionTable


@login_required
def report_collection(request):
    if not check_report_access(request):
        return HttpResponseForbidden()

    context = collect_sensor_request_context(request)
    context.update({
        'table': CollectionTable(),
    })
    return render(request, 'sensors/reports/collection.html', context)


_report_columns = ['fullness_color', 'collections_count', 'volume', 'weight']


class CollectionReportList(BaseReportDatatableView):
    model = RoutePoints
    columns = _report_columns
    columns_underline = underline_columns(_report_columns)
    column_filter = filter_columns(_report_columns, ['fullness_color', 'collections_count'])
    order_columns = _report_columns
    datatable_options = {
        'columns': columns
    }

    def render_column(self, row, column):
        if column == 'fullness_color':
            if row[column] == 0:
                return '0-50%'
            if row[column] == 1:
                return '50-75%'
            if row[column] == 2:
                return '75-90%'
            if row[column] == 3:
                return '90-100%'
        return row[column]

    def get_filter_qs_options(self):
        result = super().get_filter_qs_options()
        result['filter_by_actual'] = False
        return result

    def get_initial_queryset(self):
        qs = super().get_initial_queryset()
        return qs.filter(sensor__isnull=False, status=ROUTE_POINT_STATUS_COLLECTED)

    def filter_queryset(self, qs):
        qs = common_filter_sensor_queryset(qs, self.request.GET, self.get_filter_qs_options())

        volume_expr = (F('fullness') / 100.0) * (F('sensor__container_type__volume') * 1000)

        qs = qs.annotate(
            fullness_color=Case(
                When(fullness__lt=50, then=Value(0)),
                When(fullness__lt=75, then=Value(1)),
                When(fullness__lt=90, then=Value(2)),
                When(fullness__gte=90, then=Value(3)),
                output_field=IntegerField(),
            ),
        ).values('fullness_color').order_by('fullness_color').annotate(
            collections_count=Count('id'),
            volume=Sum(volume_expr, output_field=IntegerField()),
            weight=Sum(volume_expr * F('sensor__waste_type__density'), output_field=IntegerField()),
        )

        return qs


class CollectionReportWasteTypesPieChart(BaseChartView):
    model = RoutePoints

    def get_filter_qs_options(self):
        result = super().get_filter_qs_options()
        result['filter_by_actual'] = False
        return result

    def filter_queryset(self, qs):
        qs = qs.filter(sensor__isnull=False)
        qs = common_filter_sensor_queryset(qs, self.request.GET, self.get_filter_qs_options())
        qs = qs.order_by()
        return qs.values('sensor__waste_type__title_' + get_language()).annotate(collections_count=Count('id'))

    def prepare_result_json(self, qs):
        json_data = {'chart': COMMON_PIE_CHART_SETTINGS.copy(), 'data': []}
        for item in qs:
            json_data['data'].append(
                {'label': item['sensor__waste_type__title_' + get_language()], 'value': item['collections_count']})
        return json_data


class CollectionReportSectorsPieChart(BaseChartView):
    model = RoutePoints

    def get_filter_qs_options(self):
        result = super().get_filter_qs_options()
        result['filter_by_actual'] = False
        return result

    def filter_queryset(self, qs):
        qs = qs.filter(sensor__isnull=False)
        qs = common_filter_sensor_queryset(qs, self.request.GET, self.get_filter_qs_options())
        qs = qs.order_by()
        return qs.values('sensor__sector__name').annotate(collections_count=Count('id'))

    def prepare_result_json(self, qs):
        json_data = {'chart': COMMON_PIE_CHART_SETTINGS.copy(), 'data': []}
        for item in qs:
            json_data['data'].append({'label': item['sensor__sector__name'], 'value': item['collections_count']})
        return json_data
