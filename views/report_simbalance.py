# coding=utf-8
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from app.models import SimBalance
from app.tables import SimBalanceTable
from .shared import (
    collect_common_request_context, underline_columns, filter_columns, BaseReportDatatableView, check_report_access,
)


@login_required
def report_simbalance(request):
    if not check_report_access(request):
        return HttpResponseForbidden()

    context = collect_common_request_context(request)
    context['simbalance_data'] = SimBalanceTable()
    return render(request, 'reports/sim.html', context)


_report_columns = ['container.company.name', 'container.country.name', 'container.city.title', 'container.address',
                   'container.waste_type.title', 'container.serial_number', 'container.sector.name', 'balance',
                   'ctime', 'elapsed', 'container.phone_number']


class SimBalanceReportList(BaseReportDatatableView):
    model = SimBalance
    columns = _report_columns
    columns_underline = underline_columns(_report_columns)
    column_filter = filter_columns(_report_columns, ['elapsed'])
    order_columns = _report_columns
    datatable_options = {
        'columns': columns
    }

    def filter_queryset(self, qs):
        qs = super(SimBalanceReportList, self).filter_queryset(qs)

        balance_from = self.request.GET.get('balance_from', None)
        balance_to = self.request.GET.get('balance_to', None)
        if balance_from and balance_from != '':
            qs = qs.filter(balance__gte=balance_from)
        if balance_to and balance_to != '':
            qs = qs.filter(balance__lte=balance_to)

        return qs

    def get_initial_queryset(self):
        qs = super().get_initial_queryset()
        return qs.select_related(
            'container__company', 'container__country', 'container__city', 'container__waste_type', 'container__sector')
