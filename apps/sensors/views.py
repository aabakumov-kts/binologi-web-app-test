import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponseBadRequest, JsonResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, UpdateView, DetailView, View
from table.views import FeedDataView

from apps.core.data import Fullness, get_battery_card_class
from apps.core.models import WasteType
from apps.core.views import (
    ensure_object_access_or_404, LOW_BATTERY_LEVEL_ICON_DATA_URL, BaseCreateRouteView, RESPONSIVE_BODY_CLASS,
    BIN_ON_ROUTE_ICON_DATA_URL,
)
from apps.sensors.forms import get_sensor_form_class, SensorControlSettingsForm
from apps.sensors.models import Sensor, ErrorType, ContainerType, SensorJob, SensorData
from apps.sensors.shared import arrange_sensor_config_jobs, get_sensors_qs_for_request
from apps.sensors.tables import SensorTable
from app.models import ROUTE_POINT_STATUS_NOT_COLLECTED


class SensorsListView(LoginRequiredMixin, TemplateView):
    template_name = 'sensors/list.html'

    def get_context_data(self, **kwargs):
        if not (self.request.uac.is_superadmin or self.request.uac.has_per_company_access):
            raise Http404()
        context = super().get_context_data(**kwargs)
        context['sensors_table'] = SensorTable()
        return context


class SensorsDataView(LoginRequiredMixin, FeedDataView):
    token = SensorTable.token

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.uac.is_superadmin:
            return queryset
        elif self.request.uac.has_per_company_access:
            return queryset.filter(company=self.request.uac.company)
        raise Http404()


class SensorUpdateView(LoginRequiredMixin, UpdateView):
    model = Sensor
    template_name = 'sensors/form.html'

    def form_valid(self, form):
        sensor = form.save(commit=False)
        if self.request.uac.has_per_company_access:
            sensor.company = self.request.uac.company
        sensor.save()
        messages.success(self.request,
                         _('Sensor "%(serial)s" updated successfully') % {'serial': sensor.serial_number})
        return redirect('sensors:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(request=self.request)
        return kwargs

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        ensure_object_access_or_404(self.request, obj.company)
        return obj

    def get_form_class(self):
        return get_sensor_form_class()


class SensorMapCard(DetailView):
    model = Sensor
    template_name = 'sensors/map_card.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        ensure_object_access_or_404(self.request, obj.company)
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('sensor')
        context['low_battery_level_icon_url'] = LOW_BATTERY_LEVEL_ICON_DATA_URL
        context['bin_on_route_icon_url'] = BIN_ON_ROUTE_ICON_DATA_URL
        context['low_battery_level'] = self.object.battery <= settings.LOW_BATTERY_STATUS_ICON_LEVEL_THRESHOLD
        context['any_active_routes'] = self.object.routepoints.filter(status=ROUTE_POINT_STATUS_NOT_COLLECTED)
        context['fullness_card_class'] = Fullness.get_card_class(self.object.fullness)
        context['battery_card_class'] = get_battery_card_class(self.object.battery)
        if self.request.uac.is_driver:
            context['shortened_version'] = True
        else:
            sensors = [{'id': self.object.pk, 'serial_number': self.object.serial_number}]
            base_qs = get_sensors_qs_for_request(self.request)
            base_qs = base_qs.exclude(pk=self.object.pk).exclude(disabled=True).\
                order_by('pk').values('id', 'serial_number')
            sensors.extend(base_qs)
            base_url = reverse('main:map')
            context['sensors_nav_links'] = [
                (f"{base_url}?openDeviceType=sensor&openDeviceId={s['id']}", s['serial_number']) for s in sensors]
        return context


class CreateRouteView(BaseCreateRouteView):
    def get_error_types(self):
        return ErrorType.objects.order_by('id').values('id', 'title')

    def get_route_point_attributes(self, json_point):
        return {
            'sensor_id': json_point['id'],
        }

    def get_render_context(self):
        waste_types = list(WasteType.objects.values())
        return {
            'fetch_sensors': True,
            'points_templates_prefix': 'sensors',
            'waste_types': waste_types,
        }


class OnboardSensorView(View):
    def get(self, request, serial, *args, **kwargs):
        render_context = {
            'body_class': RESPONSIVE_BODY_CLASS,
            'company_name': None,
            'container_types': [],
            'mount_types': [],
            'return_url': request.path,
            'sensor_already_registered': False,
            'sensor_available': False,
            'sensor_serial': serial,
            'user_authenticated': request.user.is_authenticated,
            'waste_types': [],
        }
        response = None
        if not request.user.is_authenticated:
            response = render(request, 'sensors/onboard_sensor.html', render_context)
        elif not (request.uac.has_per_company_access and request.uac.company):
            response = redirect('/')  # There's no way for super admins to onboard a sensor
        if response:
            return response

        render_context['company_name'] = request.uac.company.name
        try:
            sensor = Sensor.objects.filter(serial_number=serial).get()
        except Sensor.DoesNotExist:
            pass
        else:
            render_context['sensor_available'] = sensor.company_id == settings.SENSOR_ASSET_HOLDER_COMPANY_ID
            render_context['sensor_already_registered'] = sensor.company_id == request.uac.company.id
        if render_context['sensor_available']:
            render_context['container_types'] = list(ContainerType.objects.values())
            render_context['mount_types'] = [
                {'id': Sensor.HORIZONTAL_MOUNT_TYPE, 'title': _('At the side')},
                {'id': Sensor.VERTICAL_MOUNT_TYPE, 'title': _('On the cap')},
                # TODO: Add diagonal mount type when it'll be available
                # {'id': Sensor.DIAGONAL_MOUNT_TYPE, 'title': _('Diagonally')},
            ]
            render_context['waste_types'] = list(WasteType.objects.values())
        return render(request, 'sensors/onboard_sensor.html', render_context)

    def post(self, request, serial, *args, **kwargs):
        if not request.user.is_authenticated or not (request.uac.has_per_company_access and request.uac.company):
            return HttpResponseForbidden('Authenticated users with company access are allowed')

        try:
            payload = json.loads(request.body)
        except json.decoder.JSONDecodeError:
            return HttpResponseBadRequest('JSON body is missing or invalid.')

        try:
            sensor = Sensor.objects.filter(
                company_id=settings.SENSOR_ASSET_HOLDER_COMPANY_ID, serial_number=serial).get()
        except Sensor.DoesNotExist:
            return HttpResponseBadRequest(f'Failed to find sensor with serial number {serial}.')

        try:
            container_type = ContainerType.objects.filter(
                pk=payload['container_type'] if 'container_type' in payload else None).get()
        except ContainerType.DoesNotExist:
            return HttpResponseBadRequest('Container type is missing or invalid.')

        try:
            waste_type = WasteType.objects.filter(pk=payload['waste_type'] if 'waste_type' in payload else None).get()
        except WasteType.DoesNotExist:
            return HttpResponseBadRequest('Waste type is missing or invalid.')

        if 'mount_type' not in payload or payload['mount_type'] not in map(lambda x: x[0], Sensor.MOUNT_TYPES):
            return HttpResponseBadRequest('Mount type is missing or invalid.')

        with transaction.atomic():
            sensor.container_type = container_type
            sensor.company = request.uac.company
            sensor.sector = request.uac.company.sectors_set.first()
            sensor.waste_type = waste_type
            sensor.mount_type = payload['mount_type']
            sensor.save()

            latest_unfinished_get_location_job = SensorJob.objects.filter(
                sensor=sensor, type=SensorJob.GET_LOCATION_JOB_TYPE, status='').order_by('-ctime').first()
            if latest_unfinished_get_location_job is None:
                SensorJob.objects.create(sensor=sensor, type=SensorJob.GET_LOCATION_JOB_TYPE)

            # TODO: Restore this when MQTT broker will support DB-based auth
            # VerneMQ supports that but we have to figure out why sensor fails to communicate with it
            # There seems to be such feature in Mosquitto but not out of the box, i.e. requires further research

            # auth_creds = SensorsAuthCredentials.objects.get(company=request.uac.company)
            # update_auth_job_payload = {
            #     's/serverLogin': auth_creds.username,
            #     's/serverPassword': auth_creds.password,
            # }
            # SensorJob.objects.create(
            #     sensor=sensor, type=SensorJob.UPDATE_CONFIG_JOB_TYPE,
            #     payload=serialize_sensor_message_payload(update_auth_job_payload))

        return JsonResponse({})


sensor_control_settings_form_fields_to_job_payload_mapping = {
    'accelerometer_delay': 'a111Delay',
    'accelerometer_sensitivity': 'acelTh',
    'close_measurement_on_flag': 'close_r_meas_on',
    'connection_schedule_start': 'on_time',
    'connection_schedule_stop': 'off_time',
    'far_measurement_on_flag': 'far_r_meas_on',
    'fire_min_temp': 'tempFire',
    'gps_in_every_connection': 'fGps',
    'measurement_interval': 'intConn',
    'mid_measurement_on_flag': 'mid_r_meas_on',
}


class SensorControlMainView(DetailView):
    model = Sensor
    template_name = 'sensors/control_main.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        ensure_object_access_or_404(self.request, obj.company)
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['gps_status_info'] = self._get_job_status_info(SensorJob.GET_LOCATION_JOB_TYPE)
        context['gps_form_url'] = reverse('sensors:control-gps', args=(self.object.pk,))

        context['calibration_status_info'] = self._get_job_status_info(SensorJob.CALIBRATE_JOB_TYPE)
        context['calibration_form_url'] = reverse('sensors:control-calibrate', args=(self.object.pk,))

        context['orient_status_info'] = self._get_job_status_info(SensorJob.ORIENT_JOB_TYPE)
        context['orient_form_url'] = reverse('sensors:control-orient', args=(self.object.pk,))

        settings_form = kwargs['posted_form'] if 'posted_form' in kwargs else SensorControlSettingsForm()
        for field_name, form_field in settings_form.fields.items():
            field_mapping = sensor_control_settings_form_fields_to_job_payload_mapping[field_name]
            data_with_field = SensorData.objects.filter(
                sensor=self.object, payload__contains=field_mapping).order_by('-ctime').first()
            if data_with_field:
                form_field.help_text =\
                    _("The latest value of this setting is \"%(field_value)s\" received at %(timestamp)s") % {
                        'field_value': data_with_field.data_json[field_mapping],
                        'timestamp': data_with_field.ctime.strftime('%Y-%m-%d %H:%M:%S'),
                    }
            else:
                form_field.help_text = _("We don't know the latest value of this setting")
        context['settings_form'] = settings_form

        sensors = [{'id': self.object.pk, 'serial_number': self.object.serial_number}]
        base_qs = get_sensors_qs_for_request(self.request)
        base_qs = base_qs.exclude(pk=self.object.pk).exclude(disabled=True).order_by('pk').values('id', 'serial_number')
        sensors.extend(base_qs)
        context['sensors_nav_links'] = [
            (reverse('sensors:control-main', args=(s['id'],)), s['serial_number']) for s in sensors]

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        settings_form = SensorControlSettingsForm(data=request.POST)
        if settings_form.is_valid():
            any_field_sent = False
            changed_fields = []
            field_values_source = {}
            for field_name, field_value in settings_form.cleaned_data.items():
                if field_value is None:
                    continue
                changed_fields.append(field_name)
                field_values_source[field_name] =\
                    (1 if field_value else 0) if isinstance(field_value, bool) else field_value
                any_field_sent = True
            if any_field_sent:
                arrange_sensor_config_jobs([self.object.pk], sensor_control_settings_form_fields_to_job_payload_mapping,
                                           changed_fields, add_fetch=True, field_values_source=field_values_source)
                messages.success(request, _('Successfully sent a settings request'))
            return redirect('sensors:control-main', pk=self.object.pk)
        context = self.get_context_data(object=self.object, posted_form=settings_form)
        return self.render_to_response(context)

    def _get_job_status_info(self, job_type):
        status_info = {
            'job_finished': False,
        }
        latest_finished_job = SensorJob.objects.filter(sensor=self.object, type=job_type).\
            exclude(status='').order_by('-mtime').first()
        if latest_finished_job:
            status_info.update({
                'job_finished': True,
                'job_successful': latest_finished_job.status == SensorJob.SUCCESS_STATUS,
                'job_timestamp': latest_finished_job.mtime or _('unknown'),
            })
        return status_info


def _sensor_control_request_generic(request, pk, job_type, request_type):
    existing_job = SensorJob.objects.filter(sensor_id=pk, type=job_type, status='').order_by('-ctime').first()
    if existing_job:
        messages.warning(
            request, _("There's an in-flight %(request_type)s request already") % {'request_type': request_type})
    else:
        SensorJob.objects.create(sensor_id=pk, type=job_type)
        messages.success(
            request, _('Successfully created a %(request_type)s request') % {'request_type': request_type})
    return redirect('sensors:control-main', pk=pk)


@require_POST
@login_required
def sensor_control_request_gps(request, pk):
    return _sensor_control_request_generic(request, pk, SensorJob.GET_LOCATION_JOB_TYPE, _('GPS position'))


@require_POST
@login_required
def sensor_control_request_calibrate(request, pk):
    return _sensor_control_request_generic(request, pk, SensorJob.CALIBRATE_JOB_TYPE, _('calibration'))


@require_POST
@login_required
def sensor_control_request_orient(request, pk):
    return _sensor_control_request_generic(request, pk, SensorJob.ORIENT_JOB_TYPE, _('orientation'))
