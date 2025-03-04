from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.models import F, Func, Value, CharField, Q
from django.db.models.expressions import Window
from django.db.models.functions import RowNumber
from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.core.models import FeatureFlag
from apps.core.reports import (
    check_report_access, BaseChartView, underline_columns, BaseReportDatatableView, FusionChartTypes,
    prepare_stacked_line_chart_result_json,
)
from apps.sensors.models import Fullness
from apps.sensors.reports.shared import collect_sensor_request_context, common_filter_sensor_queryset
from apps.sensors.tables import FullnessTable


@login_required
def report_fullness(request):
    if not check_report_access(request):
        return HttpResponseForbidden()

    context = collect_sensor_request_context(request)
    context.update({
        'table': FullnessTable(),
        'report_name_i18n_key': 'fullness',
        'table_data_url_name': 'reports:sensor:fullness_table_data',
        'chart_data_url_name': 'reports:sensor:fullness_chart_data',
        'chart_type': FusionChartTypes.SCROLL_STACKED_COLUMN.value,
    })
    return render(request, 'sensors/reports/fullness.html', context)


_report_columns = ['sensor.address', 'sensor.serial_number', 'value', 'ctime']


def exclude_moisture_in_request(request):
    return request.GET.get('exclude_moisture', None) == 'true'


class FullnessReportList(BaseReportDatatableView):
    model = Fullness
    columns = _report_columns
    columns_underline = underline_columns(_report_columns)
    column_filter = _report_columns
    order_columns = _report_columns
    datatable_options = {
        'columns': columns
    }

    def filter_queryset(self, qs):
        qs = common_filter_sensor_queryset(qs, self.request.GET, self.get_filter_qs_options())
        exclude_zero_data = self.request.GET.get('exclude_zero_data', None) == 'true'
        if exclude_zero_data:
            qs = qs.exclude(Q(signal_amp__isnull=True) | Q(signal_amp=0))
        if exclude_moisture_in_request(self.request) and \
                self.request.uac.check_feature_enabled(FeatureFlag.MOISTURE_DROP):
            qs = qs.exclude(parsing_metadata_json__contains={'any_measurement_moisture': True})
        qs = qs.order_by('-ctime')
        return qs

    def render_column(self, row, column):
        if column == 'value' and exclude_moisture_in_request(self.request) and \
                not self.request.uac.check_feature_enabled(FeatureFlag.MOISTURE_DROP) and \
                'any_measurement_moisture' in row.parsing_metadata_json:
            return row.parsing_metadata_json['latest_moisture_free_fullness']
        return super().render_column(row, column)


class FullnessReportStackedChart(BaseChartView):
    model = Fullness

    def filter_queryset(self, qs):
        sensor_id = self.request.GET.get('sensor', None)
        single_sensor_selected = sensor_id and sensor_id != ''

        qs = common_filter_sensor_queryset(qs, self.request.GET, self.get_filter_qs_options())
        exclude_zero_data = self.request.GET.get('exclude_zero_data', None) == 'true'
        if exclude_zero_data:
            qs = qs.exclude(Q(signal_amp__isnull=True) | Q(signal_amp=0))
        if exclude_moisture_in_request(self.request) and \
                self.request.uac.check_feature_enabled(FeatureFlag.MOISTURE_DROP):
            qs = qs.exclude(parsing_metadata_json__contains={'any_measurement_moisture': True})

        if single_sensor_selected:
            qs = qs.order_by('ctime').annotate(
                day=Func(
                    F('ctime'),
                    Value('YYYY-MM-DD HH24:MI'),
                    function='to_char',
                    output_field=CharField()
                ),
                fullness=F('value'))
            qs = qs.values('day', 'fullness', 'parsing_metadata_json')
            if exclude_moisture_in_request(self.request) and \
                    not self.request.uac.check_feature_enabled(FeatureFlag.MOISTURE_DROP):
                for item in qs:
                    if 'any_measurement_moisture' in item['parsing_metadata_json']:
                        item['fullness'] = item['parsing_metadata_json']['latest_moisture_free_fullness']
        else:
            day_func = Func(
                F('ctime'),
                Value('YYYY-MM-DD'),
                function='to_char',
                output_field=CharField()
            )
            # We can't filter by window function results in SQL - https://code.djangoproject.com/ticket/30104
            # Filtering & aggregating in Python will involve large memory & network footprint for high volume of data
            # We fall back to minimal raw SQL to keep this scalable
            # Courtesy of this blog article - https://blog.oyam.dev/django-filter-by-window-function/
            sql, params = qs.annotate(
                row_number=Window(
                    expression=RowNumber(),
                    partition_by=[F('sensor'), day_func],
                    order_by=F('ctime').desc()
                ),
                day=day_func,
            ).query.sql_with_params()
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT day, AVG(value) AS fullness
                    FROM ({}) fullness_with_row_numbers
                    WHERE row_number = 1
                    GROUP BY day
                    ORDER BY day""".format(sql),
                    params,
                )
                columns = [col[0] for col in cursor.description]
                qs = [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]
        return qs

    def prepare_result_json(self, qs):
        return prepare_stacked_line_chart_result_json(
            qs,
            [25, 50, 75, 100],
            'fullness',
            {
                "paletteColors": "#1ea51b,#ffe400,#ff7200,#ff0000",
            }
        )
