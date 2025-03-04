from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, F, IntegerField, Case, When, Value, Q
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils.translation import get_language

from app.models import Collection, Error
from apps.core.reports import (
    check_report_access, BaseChartView, underline_columns, BaseReportDatatableView, filter_columns,
    COMMON_PIE_CHART_SETTINGS,
)
from apps.trashbins.reports.shared import collect_trashbin_request_context, common_filter_trashbin_queryset
from apps.trashbins.tables import CollectionTable


@login_required
def report_collection(request):
    if not check_report_access(request):
        return HttpResponseForbidden()

    context = collect_trashbin_request_context(request)
    context.update({
        'table': CollectionTable(),
    })
    return render(request, 'trashbins/reports/collection.html', context)


_report_columns = ['fullness_color', 'collections_count', 'volume_before_pressed', 'volume_after_pressed', 'weight']


class CollectionReportList(BaseReportDatatableView):
    model = Collection
    columns = _report_columns
    columns_underline = underline_columns(_report_columns)
    column_filter = filter_columns(_report_columns, ['fullness_color', 'collections_count'])
    order_columns = _report_columns
    datatable_options = {
        'columns': columns
    }

    def render_column(self, row, column):
        if column == 'fullness_color':
            if row[column] == 0:
                return '0-50%'
            if row[column] == 1:
                return '50-75%'
            if row[column] == 2:
                return '75-90%'
            if row[column] == 3:
                return '90-100%'
        return row[column]

    def get_filter_qs_options(self):
        result = super().get_filter_qs_options()
        result['filter_by_actual'] = False
        return result

    def filter_queryset(self, qs):
        qs = common_filter_trashbin_queryset(qs, self.request.GET, self.get_filter_qs_options())

        volume_before_pressed_expr = (F('fullness_before_press') / 100.0) * F('container__max_volume')

        qs = qs.annotate(
            fullness_color=Case(
                When(fullness__lt=50, then=Value(0)),
                When(fullness__lt=75, then=Value(1)),
                When(fullness__lt=90, then=Value(2)),
                When(fullness__gte=90, then=Value(3)),
                output_field=IntegerField(),
            ),
        ).values('fullness_color').order_by('fullness_color').annotate(
            collections_count=Count('id'),
            volume_after_pressed=Sum((F('fullness') / 100.0) * F('container__max_volume')),
            volume_before_pressed=Sum(volume_before_pressed_expr),
            weight=Sum(volume_before_pressed_expr * F('container__waste_type__density'), output_field=IntegerField()),
        )

        return qs


class CollectionReportErrorsPieChart(BaseChartView):
    model = Collection

    def get_filter_qs_options(self):
        result = super().get_filter_qs_options()
        result['filter_by_actual'] = False
        return result

    def filter_queryset(self, qs):
        qs = common_filter_trashbin_queryset(qs, self.request.GET, self.get_filter_qs_options())
        qs = qs.filter(container__errors__id__isnull=False).distinct('container__errors__id').order_by(
            'container__errors__id').values('container__errors__id')
        return Error.objects.filter(id__in=qs).values('error_type__title_' + get_language()).annotate(
            total=Count('error_type')).order_by('total')

    def prepare_result_json(self, qs):
        json_data = {'chart': COMMON_PIE_CHART_SETTINGS.copy(), 'data': []}
        for item in qs:
            json_data['data'].append({'label': item['error_type__title_' + get_language()], 'value': item['total']})
        return json_data


class CollectionReportFullnessPieChart(BaseChartView):
    model = Collection

    def get_filter_qs_options(self):
        result = super().get_filter_qs_options()
        result['filter_by_actual'] = False
        return result

    def filter_queryset(self, qs):
        qs = common_filter_trashbin_queryset(qs, self.request.GET, self.get_filter_qs_options())
        return qs.aggregate(
            fullness_green_sum=Count('pk', filter=Q(fullness__lt=50)),
            fullness_yellow_sum=Count('pk', filter=(Q(fullness__gte=50) & Q(fullness__lt=75))),
            fullness_orange_sum=Count('pk', filter=(Q(fullness__gte=75) & Q(fullness__lt=90))),
            fullness_red_sum=Count('pk', filter=Q(fullness__gte=90)),
        )

    def prepare_result_json(self, qs):
        json_data = {'chart': COMMON_PIE_CHART_SETTINGS.copy(), 'data': []}
        if qs['fullness_green_sum'] > 0:
            json_data['data'].append({'label': '0-49%', 'value': qs['fullness_green_sum'], 'color': '#1ea51b'})
        if qs['fullness_yellow_sum'] > 0:
            json_data['data'].append({'label': '50-74%', 'value': qs['fullness_yellow_sum'], 'color': '#ffe400'})
        if qs['fullness_orange_sum'] > 0:
            json_data['data'].append({'label': '75-89%', 'value': qs['fullness_orange_sum'], 'color': '#ff7200'})
        if qs['fullness_red_sum'] > 0:
            json_data['data'].append({'label': '90%+', 'value': qs['fullness_red_sum'], 'color': '#ff0000'})
        return json_data


class CollectionReportTypesPieChart(BaseChartView):
    model = Collection

    def get_filter_qs_options(self):
        result = super().get_filter_qs_options()
        result['filter_by_actual'] = False
        return result

    def filter_queryset(self, qs):
        qs = common_filter_trashbin_queryset(qs, self.request.GET, self.get_filter_qs_options())
        qs = qs.order_by()
        return qs.values('container__waste_type__title_' + get_language()).annotate(containers_count=Count('id'))

    def prepare_result_json(self, qs):
        json_data = {'chart': COMMON_PIE_CHART_SETTINGS.copy(), 'data': []}
        for item in qs:
            json_data['data'].append(
                {'label': item['container__waste_type__title_' + get_language()], 'value': item['containers_count']})
        return json_data


class CollectionReportSectorsPieChart(BaseChartView):
    model = Collection

    def get_filter_qs_options(self):
        result = super().get_filter_qs_options()
        result['filter_by_actual'] = False
        return result

    def filter_queryset(self, qs):
        qs = common_filter_trashbin_queryset(qs, self.request.GET, self.get_filter_qs_options())
        qs = qs.order_by()
        return qs.values('container__sector__name').annotate(containers_count=Count('id'))

    def prepare_result_json(self, qs):
        json_data = {'chart': COMMON_PIE_CHART_SETTINGS.copy(), 'data': []}
        for item in qs:
            json_data['data'].append({'label': item['container__sector__name'], 'value': item['containers_count']})
        return json_data
