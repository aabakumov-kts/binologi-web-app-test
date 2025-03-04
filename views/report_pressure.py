# coding=utf-8
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils.translation import ugettext_lazy as _

from app.models import Pressure
from app.tables import PressureTable
from .shared import (
    collect_common_request_context, underline_columns, filter_columns, BaseReportDatatableView,
    COMMON_LINE_CHART_SETTINGS, BaseChartView, check_report_access,
)


@login_required
def report_pressure(request):
    if not check_report_access(request):
        return HttpResponseForbidden()

    context = collect_common_request_context(request)
    context['pressure_data'] = PressureTable()
    return render(request, 'reports/pressure.html', context)


_report_columns = ['container.company.name', 'container.country.name', 'container.city.title', 'container.address',
                   'container.waste_type.title', 'container.serial_number', 'container.sector.name', 'pressure_value',
                   'ctime', 'elapsed']


class PressureReportList(BaseReportDatatableView):
    model = Pressure
    columns = _report_columns
    columns_underline = underline_columns(_report_columns)
    column_filter = filter_columns(_report_columns, ['elapsed'])
    order_columns = _report_columns
    datatable_options = {
        'columns': columns
    }

    def get_initial_queryset(self):
        qs = super().get_initial_queryset()
        return qs.select_related(
            'container__company', 'container__country', 'container__city', 'container__waste_type', 'container__sector')


class PressureReportStackedChart(BaseChartView):
    model = Pressure

    def filter_queryset(self, qs):
        qs = super(PressureReportStackedChart, self).filter_queryset(qs)

        qs = qs.extra({'day': "date_trunc('day', app_pressure.ctime)::date"})\
            .values('day').order_by('day').annotate(Pressure_avg=Avg('pressure_value'))

        return qs

    def prepare_result_json(self, qs):
        json_data = {'chart': COMMON_LINE_CHART_SETTINGS.copy()}
        json_data['chart'].update({
            "yAxisMaxValue": 780,
            "yAxisMinValue": "700",
            "PYAxisMinValue": "700",
            "SYAxisMinValue": "700",
            "yAxisName": _('pressure_units'),
        })

        json_data['categories'] = [{
            "category": []
        }]

        json_data['dataset'] = [{
            "renderas": "Area",
            "data": []
        }]

        for item in qs:
            json_data['categories'][0]['category'].append({"label": item['day']})
            json_data['dataset'][0]['data'].append({"value": int(item['Pressure_avg'])})

        return json_data
