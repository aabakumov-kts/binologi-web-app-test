# coding=utf-8
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.core.models import FeatureFlag
from app.models import AirQuality
from app.tables import AirQualityTable
from .shared import (
    collect_common_request_context, underline_columns, filter_columns, BaseReportDatatableView,
    COMMON_STACKED_LINE_CHART_SETTINGS, calculate_line_chart_max_height, BaseChartView, check_report_access,
    fill_stacked_chart_datasets,
)


@login_required
def report_air_quality(request):
    if not check_report_access(request) or not request.uac.check_feature_enabled(FeatureFlag.AIR_QUALITY):
        return HttpResponseForbidden()

    context = collect_common_request_context(request)
    context['air_quality_data'] = AirQualityTable()
    return render(request, 'reports/air_quality.html', context)


_report_columns = ['container.address', 'container.waste_type.title', 'container.serial_number', 'air_quality_value',
                   'ctime', 'elapsed']


class AirQualityReportList(BaseReportDatatableView):
    model = AirQuality
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


class AirQualityReportStackedChart(BaseChartView):
    model = AirQuality

    def filter_queryset(self, qs):
        qs = super(AirQualityReportStackedChart, self).filter_queryset(qs)

        qs = qs.extra({'day': "date_trunc('day', app_airquality.ctime)::date"})\
            .values('day').order_by('day').annotate(air_quality_avg=Avg('air_quality_value'))

        return qs

    def prepare_result_json(self, qs):
        json_data = {'chart': COMMON_STACKED_LINE_CHART_SETTINGS.copy()}
        y_max = 0

        json_data['categories'] = [{
            "category": []
        }]

        json_data['dataset'] = [
            {
                "seriesname": "",
                "renderas": "Area",
                "showValues": "0",
                "data": []
            } for _ in range(0, 6)]

        segments = [51, 101, 151, 201, 301, 500]
        for item in qs:
            value = item['air_quality_avg']
            json_data['categories'][0]['category'].append({"label": item['day']})
            fill_stacked_chart_datasets(value, segments, json_data['dataset'], clip_peak=False)
            if value > y_max:
                y_max = int(value)

        json_data['chart'].update({
            "paletteColors": "#00af50,#e6d122,#ff9642,#fd3d3d,#7d649e,#262626",
            "yAxisMaxValue": calculate_line_chart_max_height(y_max),
            "yAxisMinValue": 0,
            "PYAxisMinValue": 0,
            "SYAxisMinValue": 0,
            "PYAxisMaxValue": "550",
            "SYAxisMaxValue": "550",
            "yAxisName": "AQI",
        })

        return json_data
