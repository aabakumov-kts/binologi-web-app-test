# coding=utf-8
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import HttpResponseForbidden
from django.shortcuts import render

from app.models import Traffic
from app.tables import TrafficTable
from .shared import (
    collect_common_request_context, underline_columns, filter_columns, BaseReportDatatableView,
    COMMON_LINE_CHART_SETTINGS, calculate_line_chart_max_height, BaseChartView, check_report_access,
)


@login_required
def report_traffic(request):
    if not check_report_access(request):
        return HttpResponseForbidden()

    context = collect_common_request_context(request)
    context['traffic_data'] = TrafficTable()
    return render(request, 'reports/traffic.html', context)


_report_columns = ['container.company.name', 'container.country.name', 'container.city.title', 'container.address',
                   'container.waste_type.title', 'container.serial_number', 'container.sector.name', 'traffic_value',
                   'ctime', 'elapsed']


class TrafficReportList(BaseReportDatatableView):
    model = Traffic
    columns = _report_columns
    columns_underline = underline_columns(_report_columns)
    column_filter = filter_columns(_report_columns, ['elapsed'])
    order_columns = _report_columns
    datatable_options = {
        'columns': columns
    }


class TrafficReportStackedChart(BaseChartView):
    model = Traffic

    def filter_queryset(self, qs):
        qs = super(TrafficReportStackedChart, self).filter_queryset(qs)

        qs = qs.extra({'day': "date_trunc('day', app_traffic.ctime)::date"}).values('day').order_by('day').annotate(
            Traffic_avg=Avg('traffic_value'))

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
            value = int(item['Traffic_avg'])
            json_data['categories'][0]['category'].append({"label": item['day']})
            json_data['dataset'][0]['data'].append({"value": value})
            if value > y_max:
                y_max = value

        json_data['chart'].update({
            "yAxisMaxValue": calculate_line_chart_max_height(y_max),
            "yAxisMinValue": 0,
        })

        return json_data
