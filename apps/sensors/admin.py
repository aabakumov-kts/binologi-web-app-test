import csv
import pytz

from datetime import datetime, timedelta
from django import forms
from django.contrib import messages
from django.contrib.gis import admin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html
from django.utils.text import capfirst
from django.utils.translation import ugettext_lazy as _, override as current_language_override
from io import StringIO

from apps.core.admin import validate_object_exists, ok_status_icon_markup, fail_status_icon_markup
from apps.core.models import WasteType, Company, Sectors, Country, City
from apps.sensors.models import (
    SensorSettingsProfile, Sensor, ContainerType, SensorJob, SensorData, CompanySensorsLicense,
    LicenseBalanceTransactionLog, SensorsLicenseKey, SensorOnboardRequest,
)


sensors_file_header = ['serial', 'hardware_identity', 'container_type', 'company', 'country', 'city', 'address',
                       'sector', 'waste_type', 'lat', 'lng']


def validate_sensor_file_contents(value):
    records = csv.DictReader(StringIO(value.read().decode('utf-8')), delimiter=',', fieldnames=sensors_file_header)
    next(records)  # Skip any header
    serials = []
    for index, line in enumerate(records):
        line_no = index + 2
        any_missing_value = any((v is None or v == '' for v in list(line.values())))
        if any_missing_value:
            raise ValidationError('There are missing value(s) on line %(line_no)s', params={'line_no': line_no})

        serial = line['serial']

        with current_language_override('en'):
            validate_object_exists(ContainerType, 'volume', line['container_type'], line_no)
            validate_object_exists(WasteType, 'title', line['waste_type'], line_no)

            company = validate_object_exists(Company, 'name', line['company'], line_no)
            if company:
                validate_object_exists(Sectors, 'name', line['sector'], line_no, company=company)

            country = validate_object_exists(Country, 'name', line['country'], line_no)
            if country:
                validate_object_exists(City, 'title', line['city'], line_no, country=country)

        if line['lat']:
            try:
                float(line['lat'])
            except ValueError:
                raise ValidationError('Latitude value of "%(lat)s" is incorrect', params={'lat': line['lat']})

        if line['lng']:
            try:
                float(line['lng'])
            except ValueError:
                raise ValidationError('Longitude value of "%(lng)s" is incorrect', params={'lng': line['lng']})

        serials.append(serial)

    if len(serials) != len(set(serials)):
        raise ValidationError('There are some duplicated serial numbers')

    if Sensor.objects.filter(serial_number__in=serials).count() > 0:
        raise ValidationError('There are existing sensors with serial numbers specified')


class UploadSensorsForm(forms.Form):
    file = forms.FileField(validators=[validate_sensor_file_contents], required=True)
    settings_profile = forms.ModelChoiceField(SensorSettingsProfile.objects.all(), required=True)


def enable_sensors_action(modeladmin, request, queryset):
    queryset.update(disabled=False)
    messages.success(request, 'Selected sensors enabled')


enable_sensors_action.short_description = "Enable selected sensors"


def disable_sensors_action(modeladmin, request, queryset):
    queryset.update(disabled=True)
    messages.success(request, 'Selected sensors disabled')


disable_sensors_action.short_description = "Disable selected sensors"


def sensor_enabled_column(obj):
    return not obj.disabled


sensor_enabled_column.short_description = 'Enabled'
sensor_enabled_column.boolean = True


@admin.register(Sensor)
class SensorAdmin(admin.OSMGeoAdmin):
    openlayers_url = '//openlayers.org/api/2.13/OpenLayers.js'
    change_list_template = "admin_custom/changelist_with_upload_csv.html"
    list_display = (
        'pk', 'serial_number', 'hardware_identity', 'fullness', 'settings_profile', 'container_type', 'company',
        sensor_enabled_column,
    )
    list_filter = ('settings_profile', 'container_type', 'company')
    fieldsets = (
        (None, {
            'fields': (
                'serial_number', 'company', 'settings_profile', 'location', 'country', 'city', 'address', 'sector',
                'container_type', 'waste_type', 'autogenerate_data', 'mount_type',
            )
        }),
        ('Identifiers', {
            'classes': ('collapse',),
            'fields': ('hardware_identity', 'phone_number', 'sim_number', 'account_number'),
        }),
        (capfirst(_('sensors')), {
            'classes': ('collapse',),
            'fields': ('fullness', 'battery', 'temperature'),
        }),
    )
    actions = [enable_sensors_action, disable_sensors_action]

    def get_urls(self):
        urls = super().get_urls()
        return [path('import-csv/', self.import_csv), ] + urls

    def import_csv(self, request):
        if request.method == 'POST':
            form = UploadSensorsForm(request.POST, request.FILES)
            if form.is_valid():
                settings_profile = form.cleaned_data.get('settings_profile')
                csv_file = request.FILES['file']
                csv_file.seek(0)
                records = csv.DictReader(
                    StringIO(csv_file.read().decode('utf-8')), delimiter=',', fieldnames=sensors_file_header)
                next(records)  # Skip any header
                with current_language_override('en'), transaction.atomic():
                    for line in records:
                        sensor = Sensor()
                        sensor.settings_profile = settings_profile
                        sensor.serial_number = line['serial']
                        sensor.hardware_identity = line['hardware_identity']
                        sensor.container_type = ContainerType.objects.get(volume=line['container_type'])
                        sensor.company = Company.objects.get(name=line['company'])
                        sensor.country = Country.objects.get(name=line['country'])
                        sensor.city = City.objects.get(title=line['city'], country=sensor.country)
                        sensor.address = line['address']
                        sensor.sector = Sectors.objects.get(name=line['sector'], company=sensor.company)
                        sensor.waste_type = WasteType.objects.get(title=line['waste_type'])
                        sensor.location = 'SRID=4326;POINT ({} {})'.format(line['lng'], line['lat'])
                        sensor.save()
                self.message_user(request, 'Your sensors CSV file has been imported')
                return redirect("..")
        else:
            form = UploadSensorsForm()
        return render(request, "admin_custom/upload_csv_form.html", {"form": form})


@admin.register(SensorSettingsProfile)
class SensorSettingsProfileAdmin(admin.ModelAdmin):
    list_display = ('pk', 'name', 'connection_schedule_start', 'connection_schedule_stop', 'measurement_interval',
                    'fire_min_temp', 'server_host')


@admin.register(ContainerType)
class ContainerTypeAdmin(admin.ModelAdmin):
    list_display = ('pk', 'volume', 'description')


class SensorJobForm(forms.ModelForm):
    payload = forms.CharField(widget=forms.Textarea, required=False)
    result = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = SensorJob
        exclude = ('pk',)


@admin.register(SensorJob)
class SensorJobAdmin(admin.ModelAdmin):
    form = SensorJobForm
    list_display = ('id', 'sensor', 'type', 'ctime', 'status', 'payload', 'result')
    list_filter = ('sensor', 'type', 'status')


@admin.register(SensorData)
class SensorDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'sensor', 'ctime', 'topic', 'payload')
    list_filter = ('sensor',)


class LicenseBalanceTransactionLogInline(admin.TabularInline):
    model = LicenseBalanceTransactionLog
    fields = ['ctime', 'operation_amount', 'comment', 'actor']
    readonly_fields = ['ctime', 'operation_amount', 'comment', 'actor']
    ordering = ['-ctime']
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CompanySensorsLicense)
class CompanySensorsLicenseAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'begin', 'end', 'usage_balance')


@admin.register(SensorsLicenseKey)
class SensorsLicenseKeyAdmin(admin.ModelAdmin):
    list_display = ('key', 'period_days', 'devices_count', 'ctime', 'mtime', 'used')
    readonly_fields = ('key', 'used')

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (not obj.used if obj else True)


@admin.register(SensorOnboardRequest)
class SensorOnboardRequestAdmin(admin.ModelAdmin):
    list_display = ('hardware_identity', 'ctime', 'is_closed')
    ordering = ('-ctime', 'is_closed')
    readonly_fields = ('hardware_identity', 'is_closed', 'ctime', 'mtime')

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (not obj.is_closed if obj else True)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (not obj.is_closed if obj else True)


class SensorPilot(Sensor):
    @property
    def overall_status(self):
        now = datetime.utcnow()
        now = now.replace(tzinfo=pytz.utc)
        latest_data_timestamp = self.latest_data_timestamp
        data_ok = self.latest_data_timestamp + timedelta(hours=24) > now if latest_data_timestamp else False
        gps_ok = self.get_location_status(now)
        no_errors = self.error_set.filter(actual=True).count() == 0
        overall_status_ok = data_ok and gps_ok and no_errors
        return format_html(ok_status_icon_markup if overall_status_ok else fail_status_icon_markup)

    @property
    def latest_data_timestamp(self):
        latest_data = SensorData.objects.filter(sensor=self).order_by('-ctime').first()
        return None if latest_data is None else latest_data.ctime

    @property
    def location_status(self):
        status_ok = self.get_location_status()
        return format_html(ok_status_icon_markup if status_ok else fail_status_icon_markup)

    class Meta:
        proxy = True

    def get_location_status(self, now=None):
        if now is None:
            now = datetime.utcnow()
            now = now.replace(tzinfo=pytz.utc)
        day_ago = now - timedelta(hours=24)
        return SensorJob.objects.\
            filter(sensor=self, type=SensorJob.GET_LOCATION_JOB_TYPE, mtime__gte=day_ago,
                   status=SensorJob.SUCCESS_STATUS).\
            count() > 0


@admin.register(SensorPilot)
class SensorPilotAdmin(admin.ModelAdmin):
    list_display = (
        'serial_number', 'company', 'overall_status', 'latest_data_timestamp', 'location_status', 'fullness', 'battery',
        'temperature', 'address',
    )
    list_filter = ('company',)
    list_display_links = None

    def has_view_permission(self, request, obj=None):
        return obj is None

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
