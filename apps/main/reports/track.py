from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import F, Count, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.core.models import Company, UsersToCompany
from app.models import RoutesDrivers
from apps.core.reports import (
    check_report_access, underline_columns, BaseReportDatatableView, default_render_column,
    filter_queryset_by_date_range,
)
from apps.main.tables import TrackTable


@login_required
def report_track(request):
    if not check_report_access(request):
        return HttpResponseForbidden()

    drivers_qs = User.objects.filter(user_to_company__role=UsersToCompany.DRIVER_ROLE)
    if request.uac.is_superadmin:
        companies = Company.objects.all()
    else:
        companies = Company.objects.filter(id=request.uac.company_id)
        drivers_qs = drivers_qs.filter(user_to_company__company=request.uac.company_id)

    drivers_qs = drivers_qs.annotate(comment=F('user_to_company__comment')).values('id', 'username', 'comment')

    context = {
        'companies': companies,
        'drivers': drivers_qs,
        'table': TrackTable(),
    }
    return render(request, 'main/reports/track.html', context)


_report_columns = ['driver__username', 'comment', 'containers_count', 'track_full']


class TrackReportList(BaseReportDatatableView):
    model = RoutesDrivers
    columns = _report_columns
    columns_underline = underline_columns(_report_columns)
    column_filter = _report_columns
    order_columns = _report_columns
    datatable_options = {
        'columns': columns
    }

    def get_initial_queryset(self):
        qs = super().get_initial_queryset()
        return qs.select_related('driver')

    def render_column(self, row, column):
        return default_render_column(row, column)

    def filter_queryset(self, qs):
        options = self.get_filter_qs_options()
        user_is_admin, user_company_id, = (options[opt] for opt in ['user_is_admin', 'user_company_id'])
        company = self.request.GET.get('company', None)
        driver = self.request.GET.get('driver', None)

        if company and company != '' and user_is_admin:
            qs = qs.filter(company__id=company)
        elif not user_is_admin:
            qs = qs.filter(company__id=user_company_id)

        if driver:
            qs = qs.filter(driver_id=driver)

        qs = filter_queryset_by_date_range(
            qs, self.request.GET, {'filter_by_actual': False, 'time_field_name': 'finish_time'})

        qs = qs.annotate(comment=F('driver__user_to_company__comment')).values('driver__username', 'comment').\
            order_by('driver__username', 'comment').\
            annotate(containers_count=Count('id'), track_full=Sum('track_full'))

        return qs
