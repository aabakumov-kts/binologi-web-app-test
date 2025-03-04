from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpResponseForbidden
from django.shortcuts import render

from app.models import FullnessValues
from apps.core.reports import (
    check_report_access, BaseChartView, underline_columns, BaseReportDatatableView, FusionChartTypes,
    prepare_stacked_line_chart_result_json,
)
from apps.trashbins.reports.shared import collect_trashbin_request_context, common_filter_trashbin_queryset
from apps.trashbins.tables import FullnessTable


@login_required
def report_fullness(request):
    if not check_report_access(request):
        return HttpResponseForbidden()

    context = collect_trashbin_request_context(request)
    context.update({
        'table': FullnessTable(),
        'report_name_i18n_key': 'fullness',
        'table_data_url_name': 'reports:trashbin:fullness_table_data',
        'chart_data_url_name': 'reports:trashbin:fullness_chart_data',
        'chart_type': FusionChartTypes.SCROLL_STACKED_COLUMN.value,
    })
    return render(request, 'trashbins/reports/generic.html', context)


_report_columns = ['container.address', 'container.waste_type.title', 'container.serial_number',
                   'container.sector.name', 'fullness_value', 'ctime']


class FullnessReportList(BaseReportDatatableView):
    model = FullnessValues
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
        return qs.select_related('container__waste_type', 'container__sector')


class FullnessReportStackedChart(BaseChartView):
    model = FullnessValues

    def filter_queryset(self, qs):
        qs = common_filter_trashbin_queryset(qs, self.request.GET, self.get_filter_qs_options())

        qs = qs.extra({'day': "date_trunc('day', app_fullness.ctime)::date"}). \
            values('day').order_by('day').annotate(fullness_max=Max('fullness_value'))

        return qs

    def prepare_result_json(self, qs):
        return prepare_stacked_line_chart_result_json(
            qs,
            [25, 50, 75, 100],
            'fullness_max',
            {
                "paletteColors": "#1ea51b,#ffe400,#ff7200,#ff0000",
            }
        )
