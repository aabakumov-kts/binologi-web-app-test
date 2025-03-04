from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import HttpResponseForbidden
from django.shortcuts import render

from app.models import Battery_Level
from apps.core.reports import (
    check_report_access, BaseChartView, underline_columns, BaseReportDatatableView, FusionChartTypes,
    prepare_stacked_line_chart_result_json,
)
from apps.trashbins.reports.shared import collect_trashbin_request_context, common_filter_trashbin_queryset
from apps.trashbins.tables import BatteryLevelTable


@login_required
def report_battery_level(request):
    if not check_report_access(request):
        return HttpResponseForbidden()

    context = collect_trashbin_request_context(request)
    context.update({
        'table': BatteryLevelTable(),
        'report_name_i18n_key': 'battery_level',
        'table_data_url_name': 'reports:trashbin:battery_level_table_data',
        'chart_data_url_name': 'reports:trashbin:battery_level_chart_data',
        'chart_type': FusionChartTypes.SCROLL_STACKED_COLUMN.value,
    })
    return render(request, 'trashbins/reports/generic.html', context)


_report_columns = ['container.city.title', 'container.address', 'container.waste_type.title', 'container.serial_number',
                   'container.sector.name', 'level', 'ctime']


class BatteryLevelReportList(BaseReportDatatableView):
    model = Battery_Level
    columns = _report_columns
    columns_underline = underline_columns(_report_columns)
    column_filter = _report_columns
    order_columns = _report_columns
    datatable_options = {
        'columns': columns
    }

    def filter_queryset(self, qs):
        qs = common_filter_trashbin_queryset(qs, self.request.GET, self.get_filter_qs_options())
        qs = qs.order_by('-ctime')
        return qs

    def get_initial_queryset(self):
        qs = super().get_initial_queryset()
        return qs.select_related('container__city', 'container__waste_type', 'container__sector')


class BatteryLevelReportStackedChart(BaseChartView):
    model = Battery_Level

    def filter_queryset(self, qs):
        qs = common_filter_trashbin_queryset(qs, self.request.GET, self.get_filter_qs_options())

        qs = qs.extra({'day': "date_trunc('day', app_battery_level.ctime)::date"}) \
            .values('day').annotate(battery_level_avg=Avg('level')).order_by('day')

        return qs

    def prepare_result_json(self, qs):
        segments_part_value = 33.333
        return prepare_stacked_line_chart_result_json(
            qs,
            [segments_part_value, segments_part_value * 2, 100],
            'battery_level_avg',
            {
                "paletteColors": "#ff0000,#ffe400,#1ea51b",
                "yAxisMaxValue": 110,
            }
        )
