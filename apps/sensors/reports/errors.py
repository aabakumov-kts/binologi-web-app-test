from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils.translation import get_language

from apps.core.reports import (
    check_report_access, BaseChartView, underline_columns, BaseReportDatatableView, FusionChartTypes,
    prepare_errors_chart_result_json,
)
from apps.sensors.models import Error
from apps.sensors.reports.shared import collect_sensor_request_context, common_filter_sensor_queryset
from apps.sensors.tables import ErrorTable


@login_required
def report_errors(request):
    if not check_report_access(request):
        return HttpResponseForbidden()

    context = collect_sensor_request_context(request)
    context.update({
        'table': ErrorTable(),
        'report_name_i18n_key': 'errors',
        'table_data_url_name': 'reports:sensor:errors_table_data',
        'chart_data_url_name': 'reports:sensor:errors_chart_data',
        'chart_type': FusionChartTypes.PIE.value,
    })
    return render(request, 'sensors/reports/generic.html', context)


_report_columns = ['sensor.address', 'sensor.serial_number', 'error_type.title', 'ctime']


def filter_error_qs_by_ids(qs, error_list):
    return qs.filter(error_type_id__in=error_list)


class ErrorsReportList(BaseReportDatatableView):
    model = Error
    columns = _report_columns
    columns_underline = underline_columns(_report_columns)
    column_filter = _report_columns
    order_columns = _report_columns
    datatable_options = {
        'columns': columns
    }

    def get_filter_qs_options(self):
        result = super().get_filter_qs_options()
        result['filter_qs_by_errors'] = filter_error_qs_by_ids
        return result

    def filter_queryset(self, qs):
        qs = common_filter_sensor_queryset(qs, self.request.GET, self.get_filter_qs_options())
        qs = qs.order_by('-ctime')
        return qs

    def get_initial_queryset(self):
        qs = super().get_initial_queryset()
        return qs.select_related('error_type')


class ErrorsReportPieChart(BaseChartView):
    model = Error

    def get_filter_qs_options(self):
        result = super(ErrorsReportPieChart, self).get_filter_qs_options()
        result['filter_qs_by_errors'] = filter_error_qs_by_ids
        return result

    def filter_queryset(self, qs):
        qs = common_filter_sensor_queryset(qs, self.request.GET, self.get_filter_qs_options())
        value_key = 'error_type__title_' + get_language()
        return qs.values(value_key).annotate(total=Count('error_type')).order_by('total')

    def prepare_result_json(self, qs):
        return prepare_errors_chart_result_json(qs)
