import math
import re
import operator

from copy import deepcopy
from datetime import datetime, timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.timesince import timesince
from django.utils.translation import ugettext_lazy as _, get_language
from django.views import generic
from django_datatables_view.base_datatable_view import BaseDatatableView
from enum import Enum
from functools import reduce

from apps.core.data import FULLNESS
from apps.core.models import Company, Country, City
from apps.core.utils import split_value_among_segments


def check_report_access(request):
    return request.uac.is_superadmin or request.uac.has_per_company_access


def collect_common_request_context(request):
    if request.uac.is_superadmin:
        companies = Company.objects.all()
    else:
        companies = Company.objects.filter(id=request.uac.company_id)

    cities = []
    countries = []
    if request.uac.is_superadmin:
        countries = Country.objects.order_by('name').values('id', 'name')
    elif request.uac.has_per_company_access:
        countries = Country.objects.filter(container__company=request.uac.company).order_by('name').\
            values('id', 'name').distinct()
        cities = City.objects.filter(container__company=request.uac.company).order_by('title').\
            values('id', 'title').distinct()

    fullness = {
        'name': 'fullness',
        'title': _('fullness'),
        'options': FULLNESS,
    }

    if len(cities) == 0:
        cities = City.objects.order_by('title').values('id', 'title')

    return {
        'companies': companies,
        'countries': countries,
        'cities': cities,
        'fullness': fullness,
    }


_common_filter_default_options = {
    'filter_by_actual': True,
    'time_field_name': 'ctime',
}


def filter_queryset_by_date_range(qs, params_dict, options_dict):
    options = _common_filter_default_options.copy()
    options.update(options_dict)

    date_from = params_dict.get('datetime_from', None)
    date_to = params_dict.get('datetime_to', None)
    date_range = params_dict.get('date_range', 'date_day')
    filter_by_actual, time_field_name, = (options[opt] for opt in ['filter_by_actual', 'time_field_name'])

    now = datetime.now()
    if date_range == 'date_now' and filter_by_actual:
        qs = qs.filter(actual=1, )
    elif date_range == 'date_day':
        filter_kwargs = {'%s__gte' % time_field_name: (now - timedelta(hours=24))}
        qs = qs.filter(**filter_kwargs)
    elif date_range == 'date_month':
        filter_kwargs = {
            '%s__gte' % time_field_name: (now - timedelta(days=30)),
        }
        qs = qs.filter(**filter_kwargs)
    elif date_range == 'date_period':
        period_dates_format = '%Y-%m-%d %H:%M:%S'
        filter_kwargs = {}
        if date_from and date_from != '':
            tz_aware_date_from = timezone.make_aware(datetime.strptime(date_from, period_dates_format))
            filter_kwargs['%s__gte' % time_field_name] = tz_aware_date_from
        if date_to and date_to != '':
            tz_aware_date_to = timezone.make_aware(datetime.strptime(date_to, period_dates_format))
            filter_kwargs['%s__lte' % time_field_name] = tz_aware_date_to
        qs = qs.filter(**filter_kwargs)

    return qs


class BaseChartView(LoginRequiredMixin, generic.View):
    model = None

    def get(self, request):
        qs = self.model.objects.all()
        qs = self.filter_queryset(qs)
        json = self.prepare_result_json(qs)
        return JsonResponse(json)

    def get_filter_qs_options(self):
        return {
            'user_is_admin': self.request.uac.is_superadmin,
            'user_company_id': self.request.uac.company_id,
        }

    def filter_queryset(self, qs):
        raise NotImplementedError()

    def prepare_result_json(self, qs):
        raise NotImplementedError()


COMMON_STACKED_LINE_CHART_SETTINGS = {
    "baseFontSize": 13,
    "caption": "",
    "bgAlpha": "0",
    "borderAlpha": "0",
    "numberPrefix": "",
    "showShadow": "0",
    "enableSmartLabels": "1",
    "startingAngle": "20",
    "showLabels": "1",
    "showLegend": "0",
    "legendShadow": "0",
    "legendBorderAlpha": "0",
    "showPercentValues": "0",
    "showPercentInTooltip": "1",
    "decimals": "0",
    "divlinecolor": "CCCCCC",
    "minorTMNumber": "1",
    "labelDisplay": "ROTATE",
    "slantLabels": "1",
    "majorTMNumber": "1",
    "divLineThickness": "1",
    "divlineDashLen": "1",
    "showCanvasBorder": "0",
    "theme": "fint",
    "showSum": "1",
    "plotBorderAlpha": "0",
    "usePlotGradientColor": "0",
    "plotGradientColor": "0",
    "showValues": "1",
    "showValuesInside": "1",
    "placeValuesInside": "1",
    "valuePadding": "0",
    "chartTopMargin": "50",
    "chartLeftMargin": "50",
    "chartRightMargin": "50",
    "chartBottomMargin": "50",
    "scrollheight": "10",
    "flatScrollBars": "1",
    "scrollShowButtons": "0",
    "scrollColor": "#cccccc",
    "showHoverEffect": "1",
    "placevaluesinside": "0",
    "valueFontSize": "15",
    "valueFontBold": "1",
    "valueFontColor": "#000",
    "numVisiblePlot": "30",
    "showLimits": "0",
    "captionPadding": "100",
    "numDivLines": "10",
    "adjustDiv": "1",
    "rotateYAxisName": "0",
}


def fill_stacked_chart_datasets(value, segments, datasets, clip_peak=True):
    def update_segment_dataset(index, segment_value):
        dataset_value = segment_value if segment_value is not None else ""
        datasets[index]['data'].append({"value": dataset_value})
    split_value_among_segments(value, segments, update_segment_dataset, clip_peak)


def calculate_line_chart_max_height(y_max):
    return round(int(math.ceil((y_max + y_max * 0.10) / 10.0)) * 10)


def prepare_stacked_line_chart_result_json(qs, segments, field_name, options_override=None):
    result = {'chart': COMMON_STACKED_LINE_CHART_SETTINGS.copy()}
    y_max = 0

    result['categories'] = [{
        "category": []
    }]

    result['dataset'] = [
        {
            "seriesname": "",
            "renderas": "Area",
            "showValues": "0",
            "data": []
        } for _ in segments]

    for item in qs:
        value = item[field_name]
        result['categories'][0]['category'].append({"label": item['day']})
        if value:
            fill_stacked_chart_datasets(value, segments, result['dataset'])
            if value > y_max:
                y_max = int(value)
        else:
            for idx, v in enumerate(segments):
                result['dataset'][idx]['data'].append({"value": None})

    result['chart'].update({
        "yAxisMaxValue": calculate_line_chart_max_height(y_max),
        "yAxisMinValue": 0,
        "PYAxisMinValue": 0,
        "SYAxisMinValue": 0,
        "PYAxisMaxValue": "110",
        "SYAxisMaxValue": "110",
        "yAxisName": "%",
    })
    if options_override:
        result['chart'].update(options_override)

    return result


def _reinit_order_columns(column_dict):
    result_columns = {}
    for key, value in column_dict.items():
        if key.startswith('columns['):
            m = re.search(r'columns\[(\d+)\]\[data\]', key)
            if m and m.group(1):
                result_columns[int(m.group(1))] = value

    result_array = []
    for key in sorted(result_columns.keys()):
        result_array.append(result_columns[key])
    return result_array


TIMESINCE_STRINGS = {
    'year': _('%d yr'),
    'month': _('%d mo'),
    'week': _('%d w'),
    'day': _('%d d'),
    'hour': _('%d hr'),
    'minute': _('%d min'),
}


def default_render_column(row, column, fallback=None):
    if column == 'ctime':
        return date_format(timezone.localtime(row.ctime), "SHORT_DATETIME_FORMAT")
    if column == 'elapsed':
        return timesince(row.ctime, time_strings=TIMESINCE_STRINGS)
    return fallback(row, column) if fallback else row[column]


def _merge_items(one, two):
    if isinstance(two, dict):
        result = deepcopy(one)
        for key, value in two.items():
            if key in result and isinstance(result[key], dict):
                result[key] = _merge_items(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result
    return two


class BaseReportDatatableView(LoginRequiredMixin, BaseDatatableView):
    pre_camel_case_notation = False
    max_display_length = 200

    def initialize(self, *args, **kwargs):
        super().initialize(*args, **kwargs)
        self.order_columns = _reinit_order_columns(self.request.GET)

    def render_column(self, row, column):
        return default_render_column(row, column, super().render_column)

    def get_filter_qs_options(self):
        return {
            'user_is_admin': self.request.uac.is_superadmin,
            'user_company_id': self.request.uac.company_id,
        }

    def filter_queryset(self, qs):
        raise NotImplementedError()

    def prepare_results(self, qs):
        json_data = []
        for item in qs:
            row = {}
            for column in self.get_columns():
                if '.' in column:
                    new_column = column.split('.')[0]
                    part_column = column.split('.')
                    del part_column[0]
                    if new_column not in row:
                        row[new_column] = reduce(lambda res, cur: {cur: res}, reversed(part_column),
                                                 self.render_column(item, column))
                    elif row[new_column] is not None:
                        column_value = row[new_column]
                        old_value = column_value.copy()
                        new_value = reduce(lambda res, cur: {cur: res}, reversed(part_column),
                                           self.render_column(item, column))
                        row[new_column] = _merge_items(old_value, new_value)
                else:
                    row[column] = self.render_column(item, column)
            json_data.append(row)
        return json_data


def underline_columns(columns):
    columns_underline = []
    for el in columns:
        columns_underline.append(el.replace('.', '__'))
    return columns_underline


def filter_columns(columns, exclude):
    result = columns[:]
    for i in range(len(result)):
        if result[i] in exclude:
            result[i] = ''
    return result


class FusionChartTypes(Enum):
    PIE = 'pie2d'
    SCROLL_COLUMN = 'scrollColumn2d'
    STACKED_COLUMN = 'stackedcolumn2d'
    SCROLL_STACKED_COLUMN = 'scrollstackedcolumn2d'


def filter_qs_by_fullness(qs, fullness_list, fullness_field_accessor):
    fullness_complex_query = []

    for val in fullness_list:
        fullness_obj = None
        if val == '0':
            fullness_obj = FULLNESS[0]
        elif val == '50':
            fullness_obj = FULLNESS[1]
        elif val == '75':
            fullness_obj = FULLNESS[2]
        elif val == '90':
            fullness_obj = FULLNESS[3]

        if fullness_obj:
            fullness_complex_query.append(
                Q(**{fullness_field_accessor + '__gte': fullness_obj.lower}) &
                Q(**{fullness_field_accessor + '__lte': fullness_obj.upper}))

    if fullness_complex_query:
        qs = qs.filter(reduce(operator.or_, fullness_complex_query))

    return qs


COMMON_PIE_CHART_SETTINGS = {
    "pieRadius": 100,
    "baseFontSize": 13,
    "caption": "",
    "subCaption": "",
    "paletteColors": "#00FF01,#0000FE,#FFF001,#FE0000,#01FEF1,#FE8000,#37C938,#3276D7,#FCF257,#FC5656,#4FFCF3,#FBA853,"
                     "#68FB68,#9696FF,#FBF58E,#FF9D9D,#97FAF5,#FECA96",
    "bgAlpha": "0",
    "borderAlpha": "0",
    "use3DLighting": "0",
    "showShadow": "0",
    "enableSmartLabels": "1",
    "startingAngle": "-25",
    "showLabels": "1",
    "showLegend": "0",
    "legendShadow": "0",
    "legendBorderAlpha": "0",
    "enableMultiSlicing": "1",
    "slicingDistance": "1",
    "showPercentValues": "1",
    "showPercentInTooltip": "1",
    "useDataPlotColorForLabels": "0",
    "decimals": "1",
    "animateClockwise": "1"
}


def prepare_errors_chart_result_json(qs):
    json_data = {'chart': COMMON_PIE_CHART_SETTINGS.copy(), 'data': []}
    for item in qs:
        if item['total'] < 100:
            is_sliced = 1
        else:
            is_sliced = 1
        json_data['data'].append({
            'label': item['error_type__title_' + get_language()],
            'value': item['total'],
            'isSliced': str(is_sliced)
        })
    return json_data


COMMON_LINE_CHART_SETTINGS = {
    "valuePadding": "0",
    "chartTopMargin": "50",
    "chartLeftMargin": "50",
    "chartRightMargin": "50",
    "chartBottomMargin": "50",
    "valueFontBold": "1",
    "scrollheight": "10",
    "flatScrollBars": "1",
    "scrollShowButtons": "0",
    "scrollColor": "#cccccc",
    "showHoverEffect": "1",
    "baseFontSize": 13,
    "caption": "",
    "paletteColors": "#008ee4",
    "bgAlpha": "0",
    "borderAlpha": "0",
    "showShadow": "0",
    "enableSmartLabels": "1",
    "startingAngle": "20",
    "showLegend": "0",
    "legendShadow": "0",
    "legendBorderAlpha": "0",
    "showPercentValues": "1",
    "showPercentInTooltip": "0",
    "decimals": "0",
    "divlinecolor": "CCCCCC",
    "numberPrefix": "",
    "theme": "fint",
    "majorTMNumber": "1",
    "minorTMNumber": "1",
    "labelDisplay": "ROTATE",
    "slantLabels": "1",
    "numDivLines": "10",
    "valueFontSize": "15",
    "numVisiblePlot": "30",
    "adjustDiv": "0",
    "rotateYAxisName": "0",
}


def prepare_temperature_chart_result_json(qs):
    json_data = {'chart': COMMON_LINE_CHART_SETTINGS.copy()}
    json_data['chart'].update({
        "yAxisMaxValue": 40,
        "yAxisName": "℃",
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
        json_data['dataset'][0]['data'].append({"value": int(item['temperature_avg'])})

    return json_data
