import json as py_json
import math
import mimetypes
import os
import pandas as pd
import ujson as json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from datetime import datetime, date
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordChangeView
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q, Count, F
from django.http import Http404, HttpResponseForbidden, JsonResponse, HttpResponseBadRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.text import capfirst
from django.utils.timesince import timesince
from django.utils.translation import ugettext_lazy as _
from django.views import generic
from django.views.generic.edit import FormView
from fbprophet import Prophet
from notifications.models import Notification
from pathlib import Path
from table.views import FeedDataView

from apps.core.context_processors import MODAL_MESSAGE_EXTRA_TAGS, get_return_to_url
from apps.core.data import FULLNESS
from apps.core.forms import UserTimezoneChangeForm, NotificationsSettingsForm
from apps.core.middleware import license_check_exempt
from apps.core.models import FeatureFlag, UsersToCompany, Sectors
from apps.core.reports import prepare_stacked_line_chart_result_json, FusionChartTypes, TIMESINCE_STRINGS
from apps.core.tables import NotificationTable
from apps.core.tasks import NotificationLevels
from apps.core.utils import notification_message_generators, notification_link_generators
from app.models import (
    Route, RoutePoints, Routes, RoutesDrivers, ROUTE_STATUS_ABORTED_BY_OPERATOR, FINISHED_ROUTE_STATUSES,
)
from app.helpers import send_push
from app.redis_client import RedisClient
from app.utils import convert_web_app_route_points, validate_route_points


base_dir = os.path.dirname(os.path.abspath(__file__))

LOW_BATTERY_LEVEL_ICON_DATA_URL = Path(os.path.join(base_dir, 'assets', 'low_battery_level_icon_data_url')).read_text()
BIN_ON_ROUTE_ICON_DATA_URL = Path(os.path.join(base_dir, 'assets', 'bin_on_route_icon_data_url')).read_text()
WARNING_ICON_DATA_URL = Path(os.path.join(base_dir, 'assets', 'warning_icon_data_url')).read_text()

RESPONSIVE_BODY_CLASS = 'responsive-page'


def ensure_object_access_or_404(request, object_company):
    if request.uac.is_superadmin:
        return
    if request.uac.has_per_company_access and object_company == request.uac.company:
        return
    raise Http404()


class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'core/account/change_password.html'

    def dispatch(self, *args, **kwargs):
        if not self.request.uac.check_feature_enabled(FeatureFlag.CHANGE_PASSWORD):
            return HttpResponseForbidden()
        return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'passwordChanged', MODAL_MESSAGE_EXTRA_TAGS)
        return super().form_valid(form)

    def get_success_url(self):
        return_to_url = get_return_to_url(self.request)
        return return_to_url if return_to_url else reverse('main:map')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['body_class'] = RESPONSIVE_BODY_CLASS
        return context


class TimezoneChangeView(generic.edit.FormView):
    form_class = UserTimezoneChangeForm
    template_name = 'core/account/change_timezone.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.uac.has_per_company_access:
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'timezoneChanged', MODAL_MESSAGE_EXTRA_TAGS)
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.request.user.user_to_company
        return kwargs

    def get_context_data(self, **kwargs):
        kwargs = super().get_context_data(**kwargs)
        company_tz = self.request.uac.company.timezone
        kwargs['company_timezone'] = str(company_tz)
        kwargs['utc_offset'] = datetime.now(company_tz).strftime('%z')
        return kwargs

    def get_success_url(self):
        return_to_url = get_return_to_url(self.request)
        return return_to_url if return_to_url else reverse('main:map')


TOP_LEVEL_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'top_level_static',
)


def create_top_level_static_view(file_name):
    file_contents = Path(os.path.join(TOP_LEVEL_STATIC_DIR, file_name)).read_bytes()
    mime_type, _ = mimetypes.guess_type(file_name)

    @license_check_exempt
    def serve_file_view(request):
        return HttpResponse(file_contents, content_type=mime_type)

    return serve_file_view


def send_route(route):
    new_route_command = json.dumps({
        'action': 'new_route',
        'created': route.ctime.isoformat(),
        'id': route.id,
        'points': route.route_json,
    })
    driver_id = route.user_id
    redis = RedisClient()
    redis.set_route_to_send(driver_id, new_route_command)
    async_to_sync(get_channel_layer().group_send)(
        settings.MOBILE_API_CONSUMERS_GROUP_NAME,
        {
            'type': 'new_route',
            'driver_id': driver_id,
            'command': new_route_command,
        }
    )
    if not redis.is_driver_online(driver_id):
        send_push(driver_id, settings.NEW_ROUTE_PUSH_MESSAGE_CODE)


class BaseCreateRouteView(LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        if not (request.uac.is_superadmin or (request.uac.has_per_company_access and request.uac.company)):
            raise Http404()

        request_company = request.uac.company

        drivers = User.objects.filter(user_to_company__role=UsersToCompany.DRIVER_ROLE)
        if request_company:
            drivers = drivers.filter(user_to_company__company=request_company)
        total_drivers_count = drivers.count()
        now = date.today()
        availability_inclusion_expr = Q(driverunavailabilityperiod__begin__lte=now) & Q(
            driverunavailabilityperiod__end__gte=now)
        drivers = drivers.filter(~availability_inclusion_expr).annotate(
            active_routes_count=Count('route', filter=Q(route__status=None) | Q(route__status__in=[0, 1])),
            comment=F('user_to_company__comment'),
        ).values('id', 'username', 'comment', 'active_routes_count')

        sectors = Sectors.objects.values('id', 'name')
        if request_company:
            sectors = sectors.filter(company=request_company)

        context = {
            'fullness': FULLNESS,
            'error_types': self.get_error_types(),
            'sectors_list': sectors,
            'sectors_json': py_json.dumps(list(sectors), cls=DjangoJSONEncoder),
            'drivers_json': py_json.dumps(list(drivers), cls=DjangoJSONEncoder),
            'total_drivers_count': total_drivers_count,
        }
        context.update(self.get_render_context())
        return render(request, 'routes/create.html', context)

    def post(self, request, *args, **kwargs):
        try:
            req_payload = py_json.loads(request.body)
        except py_json.decoder.JSONDecodeError:
            return HttpResponseBadRequest('JSON body is missing or invalid.')
        if 'data' not in req_payload or len(req_payload['data']) == 0:
            return HttpResponseBadRequest('Routes data is missing.')
        if not all('id' in route and 'points' in route for route in req_payload['data']):
            return HttpResponseBadRequest('One or more routes data is incomplete.')
        company = request.uac.company if request.uac.has_per_company_access else None
        if company is None and request.uac.is_superadmin:
            company = UsersToCompany.objects.get(
                user_id=req_payload['data'][0]['id'], role=UsersToCompany.DRIVER_ROLE).company
        drivers_ids = set(route['id'] for route in req_payload['data'])
        if len(drivers_ids) != UsersToCompany.objects.filter(company=company, user_id__in=drivers_ids).count():
            return HttpResponseBadRequest('One or more drivers specified are invalid.')
        if any(not validate_route_points(route['points']) for route in req_payload['data']):
            return HttpResponseBadRequest('One or more routes have invalid points data.')

        base_route = None
        for route_data in req_payload['data']:
            driver_id = route_data['id']
            if base_route is None:
                base_route = Routes.objects.create(company=company)
            points = convert_web_app_route_points(route_data['points'], settings.DEFAULT_CONTAINER_VOLUME)
            if points:
                RoutesDrivers.finish_routes(driver_id)
                RoutePoints.close_route_points(driver_id, ROUTE_STATUS_ABORTED_BY_OPERATOR)
                Routes.close_parent_routes_if_possible(driver_id)

                unfinished_routes_status_filter = ~Q(status__in=FINISHED_ROUTE_STATUSES) | Q(status__isnull=True)
                Route.objects.filter(unfinished_routes_status_filter, user_id=driver_id). \
                    update(status=ROUTE_STATUS_ABORTED_BY_OPERATOR)

                route = Route.objects.create(user_id=driver_id, route_json=points, parent_route=base_route)
                for point in points:
                    route_point_attribs = {
                        'user_id': driver_id,
                        'parent_route': base_route,
                        'route': route,
                        'fullness': point['fullness'],
                        'volume': point['volume'],
                    }
                    route_point_attribs.update(self.get_route_point_attributes(point))
                    RoutePoints.objects.create(**route_point_attribs)
                send_route(route)
        # TODO: Fix this interaction model
        # Overall AJAX POST + manual redirect doesn't fit current post back approach
        # Could be kept with some tweaks for the future SPA, though
        resp_payload = {}
        return_to_url = get_return_to_url(request)
        if return_to_url:
            resp_payload['returnToUrl'] = return_to_url
            messages.success(request, 'routeAdded', MODAL_MESSAGE_EXTRA_TAGS)
        else:
            alert_text = '{} {}'.format(
                capfirst(_('route_added_modal_title')), capfirst(_('route_added_modal_description')))
            messages.success(request, alert_text)
        return JsonResponse(resp_payload)

    def get_error_types(self):
        raise NotImplementedError()

    def get_route_point_attributes(self, json_point):
        return {}

    def get_render_context(self):
        return {}


def switch_language(request, lang):
    available_langs = [t[0] for t in settings.LANGUAGES]
    next_url = request.GET.get('next', None)
    response = redirect(next_url if next_url else '/')
    if lang in available_langs:
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang)
    return response


class BaseFullnessForecastView(LoginRequiredMixin, generic.TemplateView):
    ERROR_MESSAGE_CONTEXT_KEY = 'error_message'
    FULLNESS_RANGE_LATEST_CONTEXT_KEY = 'fullness_range_latest'
    FULLNESS_RANGES_COLLECTION_CONTEXT_KEY = 'fullness_ranges_collection'

    dataframe_datetime_format = '%Y-%m-%d %H:%M:%S'
    graph_date_format = '%Y-%m-%d'

    template_name = 'core/fullness_forecast.html'

    def render_to_response(self, context, **response_kwargs):
        if not self.request.uac.check_feature_enabled(FeatureFlag.FULLNESS_FORECAST):
            return HttpResponseForbidden()

        if self.ERROR_MESSAGE_CONTEXT_KEY in context:
            return super().render_to_response(context, **response_kwargs)

        forecasts = []
        for collection_range in context[self.FULLNESS_RANGES_COLLECTION_CONTEXT_KEY]:
            forecast = self._get_forecast(collection_range)
            if forecast is not None:
                forecasts.append(forecast)
        if len(forecasts) == 0:
            context[self.ERROR_MESSAGE_CONTEXT_KEY] = _("Forecast for this SmartCity Bin can't created at the moment")
            return super().render_to_response(context, **response_kwargs)

        last_fullness_value = context[self.FULLNESS_RANGE_LATEST_CONTEXT_KEY][-1]
        last_fullness_in_forecast = last_fullness_value['value'] + 100
        days_to_fullness_100 = []
        for forecast in forecasts:
            first_val_above_200_idx = forecast['trend'].ge(200).idxmax()
            first_val_above_last_fullness_idx = forecast['trend'].ge(last_fullness_in_forecast).idxmax()
            days_to_fullness_100.append(first_val_above_200_idx - first_val_above_last_fullness_idx)
        average_days_to_fullness_100 = round(sum(days_to_fullness_100) / len(days_to_fullness_100))
        forecast_to_use = forecasts[days_to_fullness_100.index(max(days_to_fullness_100))]

        def add_item_to_forecast_fullness_range(index):
            forecast_fullness_range.append({
                'day': forecast_to_use['ds'][index].date().strftime(self.graph_date_format),
                'value': min(forecast_to_use['trend'][index] - 100, 100),
            })

        first_val_above_200_idx = forecast_to_use['trend'].ge(200).idxmax()
        first_val_above_last_fullness_idx = forecast_to_use['trend'].ge(last_fullness_in_forecast).idxmax()
        forecast_fullness_range = []
        if average_days_to_fullness_100 <= 15:
            idx = first_val_above_last_fullness_idx
            while idx <= first_val_above_200_idx:
                add_item_to_forecast_fullness_range(idx)
                idx += 1
        else:
            idx = first_val_above_last_fullness_idx
            while idx < first_val_above_last_fullness_idx + 7:
                add_item_to_forecast_fullness_range(idx)
                idx += 1
            forecast_fullness_range.append({'day': '...', 'value': None})
            idx = first_val_above_200_idx - 6
            while idx <= first_val_above_200_idx:
                add_item_to_forecast_fullness_range(idx)
                idx += 1

        def prepare_json_source(fullness_range):
            return prepare_stacked_line_chart_result_json(
                fullness_range,
                [25, 50, 75, 100],
                'value',
                {"paletteColors": "#1ea51b,#ffe400,#ff7200,#ff0000"},
            )

        latest_json_source = prepare_json_source(context[self.FULLNESS_RANGE_LATEST_CONTEXT_KEY])
        forecast_json_source = prepare_json_source(forecast_fullness_range)
        max_height = max(latest_json_source['chart']["yAxisMaxValue"], forecast_json_source['chart']["yAxisMaxValue"])
        latest_json_source['chart']["yAxisMaxValue"] = max_height
        forecast_json_source['chart']["yAxisMaxValue"] = max_height

        first_val_above_190_idx = forecast_to_use['trend'].ge(190).idxmax()
        first_val_above_175_idx = forecast_to_use['trend'].ge(175).idxmax()

        context.update({
            'latest_json_source': latest_json_source,
            'forecast_json_source': forecast_json_source,
            'chart_type': FusionChartTypes.SCROLL_STACKED_COLUMN.value,
            'optimal_pickup_start_date':
                forecast_to_use['ds'][first_val_above_190_idx].date().strftime(self.graph_date_format),
            'near_optimal_pickup_start_date':
                forecast_to_use['ds'][first_val_above_175_idx].date().strftime(self.graph_date_format),
        })
        return super().render_to_response(context, **response_kwargs)

    def _get_forecast(self, collection_range):
        range_td = datetime.strptime(collection_range[-1]['ds'], self.dataframe_datetime_format) - \
                   datetime.strptime(collection_range[0]['ds'], self.dataframe_datetime_format)
        range_days = math.ceil(range_td.total_seconds() / 86400)
        df = pd.DataFrame(collection_range)
        m = Prophet()
        m.fit(df)
        future = m.make_future_dataframe(periods=range_days * 5)
        forecast = m.predict(future)
        if 'trend' not in forecast:
            # There's no trend in prediction
            return None
        first_val_above_200_idx = forecast['trend'].ge(200).idxmax()
        if forecast['trend'][first_val_above_200_idx] <= 200:
            # Index is incorrect
            return None
        return forecast


priority_display_name_text_resolver = {
    NotificationLevels.ERROR.value: _('High'),
    NotificationLevels.WARNING.value: _('Medium'),
    NotificationLevels.INFO.value: _('Low'),
}

priority_display_name_color_resolver = {
    NotificationLevels.ERROR.value: "red",
    NotificationLevels.WARNING.value: "orange",
    NotificationLevels.INFO.value: "green",
}


class NotificationsFeedDataView(LoginRequiredMixin, FeedDataView):
    token = NotificationTable.token

    def get_queryset(self):
        return self.request.user.notifications.unread()

    def convert_queryset_to_values_list(self, queryset):
        def render_column(col, obj):
            if col.field == 'level' and obj.level in priority_display_name_text_resolver and \
                    obj.level in priority_display_name_color_resolver:
                return f"<span style=\"color: {priority_display_name_color_resolver[obj.level]}\">" \
                       f"{priority_display_name_text_resolver[obj.level]}</span>"
            if col.field == 'elapsed':
                return timesince(obj.timestamp, time_strings=TIMESINCE_STRINGS)
            rendered_value = col.render(obj)
            if col.field == 'verb' and rendered_value in notification_message_generators:
                return notification_message_generators[rendered_value](obj)
            return rendered_value

        return [
            [render_column(col, obj) for col in self.columns]
            for obj in queryset
        ]


class NotificationsListView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'core/notifications/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['notifications_table'] = NotificationTable()
        context['body_class'] = RESPONSIVE_BODY_CLASS
        return context


class FollowNotificationView(LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        notification = get_object_or_404(Notification, pk=kwargs.get('pk'))
        notification.unread = False
        notification.save()
        redirect_url = notification_link_generators[notification.verb](notification) \
            if notification.verb in notification_link_generators else '/'
        return redirect(redirect_url)


class MarkAllNotificationsReadView(LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        request.user.notifications.mark_all_as_read()
        messages.success(request, 'allNotificationsRead', MODAL_MESSAGE_EXTRA_TAGS)
        return redirect('/')


class NotificationsSettingsFormView(LoginRequiredMixin, FormView):
    template_name = 'core/notifications/settings.html'
    form_class = NotificationsSettingsForm

    def get_context_data(self, **kwargs):
        kwargs['body_class'] = RESPONSIVE_BODY_CLASS
        kwargs['onesignal_app_id'] = settings.ONESIGNAL_APP_ID
        return super().get_context_data(**kwargs)

    def get_initial(self):
        result = super().get_initial()
        if self.request.user.email:
            result['email'] = self.request.user.email
        return result

    def form_valid(self, form):
        email = form.cleaned_data.get('email')
        self.request.user.email = email
        self.request.user.save()
        messages.success(self.request, _('Notifications settings saved successfully'))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('notifications_list')
