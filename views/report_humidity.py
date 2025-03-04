# coding=utf-8
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import HttpResponseForbidden
from django.shortcuts import render

from app.models import Humidity
from app.tables import HumidityTable
from .shared import (
    collect_common_request_context, underline_columns, filter_columns, BaseReportDatatableView,
    COMMON_LINE_CHART_SETTINGS, calculate_line_chart_max_height, BaseChartView, check_report_access,
)


@login_required
def report_humidity(request):
    if not check_report_access(request):
        return HttpResponseForbidden()

    context = collect_common_request_context(request)
    context['humidity_data'] = HumidityTable()
    return render(request, 'reports/humidity.html', context)


_report_columns = ['container.address', 'container.waste_type.title', 'container.serial_number', 'humidity_value',
                   'ctime', 'elapsed']


class HumidityReportList(BaseReportDatatableView):
    model = Humidity
    columns = _report_columns
    columns_underline = underline_columns(_report_columns)
    column_filter = filter_columns(_report_columns, ['elapsed'])
    order_columns = _report_columns
    datatable_options = {
        'columns': columns
    }

    def get_initial_queryset(self):
        qs = super().get_initial_queryset()
        return qs.select_related('container__waste_type')


class HumidityReportStackedChart(BaseChartView):
    model = Humidity

    def filter_queryset(self, qs):
        qs = super(HumidityReportStackedChart, self).filter_queryset(qs)

        qs = qs.extra({'day': "date_trunc('day', app_humidity.ctime)::date"})\
            .values('day').order_by('day').annotate(humidity_avg=Avg('humidity_value'))

        return qs

    def prepare_result_json(self, qs):
        json_data = {'chart': COMMON_LINE_CHART_SETTINGS.copy()}
        y_max = 0

        json_data['categories'] = [{
            "category": []
        }]

        json_data['dataset'] = [{
            "renderas": "Area",
            "data": []
        }]

        for item in qs:
            value = int(item['humidity_avg'])
            json_data['categories'][0]['category'].append({"label": item['day']})
            json_data['dataset'][0]['data'].append({"value": value})
            if value > y_max:
                y_max = value

        json_data['chart'].update({
            "yAxisMaxValue": calculate_line_chart_max_height(y_max),
            "yAxisMinValue": 0,
            "PYAxisMinValue": "0",
            "SYAxisMinValue": "0",
            "yAxisName": "%",
        })

        return json_data
