from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.core.reports import (
    check_report_access, BaseChartView, underline_columns, BaseReportDatatableView, FusionChartTypes,
    prepare_temperature_chart_result_json,
)
from apps.sensors.models import Temperature
from apps.sensors.reports.shared import collect_sensor_request_context, common_filter_sensor_queryset
from apps.sensors.tables import TemperatureTable


@login_required
def report_temperature(request):
    if not check_report_access(request):
        return HttpResponseForbidden()

    context = collect_sensor_request_context(request)
    context.update({
        'table': TemperatureTable(),
        'report_name_i18n_key': 'temperature',
        'table_data_url_name': 'reports:sensor:temperature_table_data',
        'chart_data_url_name': 'reports:sensor:temperature_chart_data',
        'chart_type': FusionChartTypes.SCROLL_COLUMN.value,
    })
    return render(request, 'sensors/reports/generic.html', context)


_report_columns = ['sensor.address', 'sensor.serial_number', 'value', 'ctime']


class TemperatureReportList(BaseReportDatatableView):
    model = Temperature
    columns = _report_columns
    columns_underline = underline_columns(_report_columns)
    column_filter = _report_columns
    order_columns = _report_columns
    datatable_options = {
        'columns': columns
    }

    def filter_queryset(self, qs):
        qs = common_filter_sensor_queryset(qs, self.request.GET, self.get_filter_qs_options())
        qs = qs.order_by('-ctime')
        return qs


class TemperatureReportStackedChart(BaseChartView):
    model = Temperature

    def filter_queryset(self, qs):
        qs = common_filter_sensor_queryset(qs, self.request.GET, self.get_filter_qs_options())

        qs = qs.extra({'day': "date_trunc('day', sensors_temperature.ctime)::date"}).values('day').order_by('day')\
            .annotate(temperature_avg=Avg('value'))

        return qs

    def prepare_result_json(self, qs):
        return prepare_temperature_chart_result_json(qs)
