# coding=utf-8
import csv

from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.contrib.gis import admin
from django.db import transaction
from django.db.models import Count
from django.utils.translation import ugettext_lazy as _, override as current_language_override
from django.urls import path
from django.utils.text import capfirst
from django.shortcuts import redirect, render
from io import StringIO
from datetime import datetime

from apps.core.admin import validate_object_exists, clean_company_username_prefix
from apps.core.models import Country, City, Company, Sectors, WasteType
from app.models import (
    Container, Traffic, Error, ErrorType, Equipment, SimBalance, Pressure, FullnessValues, ContainerType, Route,
    Battery_Level, Temperature, EnergyEfficiencyProfile, EnergyEfficiencyForContainer, MobileAppTranslation,
    CreateDemoSandboxRequest, TrashbinJobModel, SlackEnabledTrashbin, DemoSandboxTranslation, validate_lang,
)
from app.tasks import process_single_demo_sandbox_request, calculate_energy_efficiency


containers_file_header = ['serial', 'phone', 'container_type', 'company', 'country', 'city', 'address', 'sector',
                          'waste_type', 'lat', 'lng', 'master_serial']


def validate_container_file_contents(value):
    records = csv.DictReader(StringIO(value.read().decode('utf-8')), delimiter=',', fieldnames=containers_file_header)
    next(records)  # Skip any header
    serials = []
    master_to_satellites = {}
    for index, line in enumerate(records):
        line_no = index + 2
        serial = line['serial']
        master_serial = line['master_serial']

        if master_serial:
            if not serial:
                raise ValidationError('Serial is missing on line %(line_no)s', params={'line_no': line_no})
        else:
            values_without_master_serial = list(line.values())[:-1]
            any_missing_value = any((v is None or v == '' for v in values_without_master_serial))
            if any_missing_value:
                raise ValidationError('There are missing value(s) on line %(line_no)s', params={'line_no': line_no})

        with current_language_override('en'):
            validate_object_exists(ContainerType, 'title', line['container_type'], line_no)
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
        if master_serial:
            if master_serial not in master_to_satellites:
                master_to_satellites[master_serial] = []
            master_to_satellites[master_serial].append(serial)

    if len(serials) != len(set(serials)):
        raise ValidationError('There are some duplicated serial numbers')

    if not set(serials).issuperset(master_to_satellites.keys()):
        raise ValidationError('There are some master serials which are missing')

    for master_to_check in master_to_satellites.keys():
        if any((master_to_check in satellites for satellites in master_to_satellites.values())):
            raise ValidationError(
                'Master "%(master_to_check)s" is present in satellites', params={'master_to_check': master_to_check})

    if Container.objects.filter(serial_number__in=serials).count() > 0:
        raise ValidationError('There are existing containers with serial numbers specified')


class UploadContainersForm(forms.Form):
    file = forms.FileField(validators=[validate_container_file_contents], required=True)
    password = forms.CharField(label=capfirst(_('password')), max_length=128, widget=forms.PasswordInput, required=True)


@admin.register(Container)
class ContainerAdmin(admin.OSMGeoAdmin):
    openlayers_url = '//openlayers.org/api/2.13/OpenLayers.js'
    change_list_template = "admin_custom/changelist_with_upload_csv.html"

    list_display = (
        'serial_number', 'waste_type', 'company', 'phone_number', 'country', 'is_master', 'sector', 'master_bin',
    )
    list_filter = ('waste_type', 'company', 'country', 'is_master')
    fieldsets = (
        (None, {
            'fields': (
                'serial_number', 'container_type', 'waste_type', 'company', 'country', 'city', 'address',
                'phone_number', 'sector', 'location', 'autogenerate_data',
            )
        }),
        ('Sensors', {
            'classes': ('collapse',),
            'fields': ('fullness', 'battery', 'temperature', 'pressure', 'traffic', 'humidity', 'air_quality'),
        }),
        ('Station settings', {
            'classes': ('collapse',),
            'fields': ('is_master', 'master_bin'),
        }),
        ('Security', {
            'classes': ('collapse',),
            'fields': ('password',),
        }),
    )
    readonly_fields = ('is_master',)

    def get_queryset(self, request):
        queryset = super(ContainerAdmin, self).get_queryset(request)
        return queryset.prefetch_related('country')

    def get_urls(self):
        urls = super().get_urls()
        return [path('import-csv/', self.import_csv), ] + urls

    def import_csv(self, request):
        if request.method == 'POST':
            form = UploadContainersForm(request.POST, request.FILES)
            if form.is_valid():
                bins_password = form.cleaned_data.get('password')
                csv_file = request.FILES['file']
                csv_file.seek(0)
                records = csv.DictReader(
                    StringIO(csv_file.read().decode('utf-8')), delimiter=',', fieldnames=containers_file_header)
                next(records)  # Skip any header
                with current_language_override('en'):
                    satellite_records = []
                    with transaction.atomic():
                        for line in records:
                            master_serial = line['master_serial']
                            if master_serial:
                                satellite_records.append(line)
                                continue
                            master_container = Container()
                            master_container.serial_number = line['serial']
                            master_container.phone_number = line['phone']
                            master_container.container_type = ContainerType.objects.get(title=line['container_type'])
                            master_container.company = Company.objects.get(name=line['company'])
                            master_container.country = Country.objects.get(name=line['country'])
                            master_container.city = City.objects.get(
                                title=line['city'], country=master_container.country)
                            master_container.address = line['address']
                            master_container.sector = Sectors.objects.get(
                                name=line['sector'], company=master_container.company)
                            master_container.waste_type = WasteType.objects.get(title=line['waste_type'])
                            master_container.location = 'SRID=4326;POINT ({} {})'.format(line['lng'], line['lat'])
                            master_container.password = make_password(bins_password)
                            master_container.save()
                        for line in satellite_records:
                            master_serial = line['master_serial']
                            master_bin = Container.objects.get(serial_number=master_serial)
                            satellite_container = Container()
                            satellite_container.serial_number = line['serial']
                            satellite_container.phone_number = line['phone'] or master_bin.phone_number
                            satellite_container.container_type = ContainerType.objects.get(
                                title=line['container_type'] or master_bin.container_type.title)
                            satellite_container.company = Company.objects.get(
                                name=line['company'] or master_bin.company.name)
                            satellite_container.country = Country.objects.get(
                                name=line['country'] or master_bin.country.name)
                            if line['city']:
                                satellite_container.city = City.objects.get(
                                    title=line['city'], country=satellite_container.country)
                            else:
                                satellite_container.city = master_bin.city
                            satellite_container.address = line['address'] or master_bin.address
                            if line['sector']:
                                satellite_container.sector = Sectors.objects.get(
                                    name=line['sector'], company=satellite_container.company)
                            else:
                                satellite_container.sector = master_bin.sector
                            satellite_container.waste_type = WasteType.objects.get(
                                title=line['waste_type'] or master_bin.waste_type.title)
                            if line['lng'] and line['lat']:
                                satellite_container.location = \
                                    'SRID=4326;POINT ({} {})'.format(line['lng'], line['lat'])
                            else:
                                satellite_container.location = master_bin.location
                            satellite_container.master_bin = master_bin
                            satellite_container.is_master = False
                            satellite_container.password = make_password(None)
                            satellite_container.save()
                self.message_user(request, 'Your containers CSV file has been imported')
                return redirect("..")
        else:
            form = UploadContainersForm()
        return render(request, "admin_custom/upload_csv_form.html", {"form": form})

    def save_model(self, request, obj, form, change):
        obj.is_master = obj.master_bin is None
        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        result = super().get_form(request, obj, **kwargs)
        result.base_fields['password'].widget.input_type = 'password'
        result.base_fields['password'].required = False

        def clean_password(self):
            if not self.cleaned_data['password']:
                return make_password(None)
            if 'password' not in self.initial:
                return make_password(self.cleaned_data['password'])
            return self.cleaned_data['password'] \
                if self.cleaned_data['password'] == self.initial['password'] \
                else make_password(self.cleaned_data['password'])

        setattr(result, 'clean_password', clean_password)
        return result


@admin.register(ContainerType)
class ContainerTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'get_errortype_count')

    def get_queryset(self, request):
        queryset = super(EquipmentAdmin, self).get_queryset(request)
        return queryset.annotate(Count('errortype'))

    def get_errortype_count(self, obj):
        return obj.errortype__count


@admin.register(ErrorType)
class ErrorTypeAdmin(admin.ModelAdmin):
    list_display = ('title', 'code', 'equipment', 'description')
    list_filter = ('equipment',)


def simple_validate_file_contents(value):
    _ = value.read()


class UploadContainerDataForm(forms.Form):
    file = forms.FileField(validators=[simple_validate_file_contents], required=True)
    container = forms.ModelChoiceField(queryset=Container.objects.all(), required=True)


class ImportContainerDataFromCsvModelAdminMixin:
    change_list_template = "admin_custom/changelist_with_upload_csv.html"
    default_datetime_format = "%m/%d/%Y %H:%M:%S"

    def get_fieldnames(self):
        raise NotImplementedError()

    def process_record(self, container, record):
        raise NotImplementedError()

    def get_urls(self):
        urls = super().get_urls()
        return [path('import-csv/', self.import_csv), ] + urls

    def import_csv(self, request):
        if request.method == 'POST':
            csv_file = request.FILES['file']
            csv_file.seek(0)
            records = csv.DictReader(
                StringIO(csv_file.read().decode('utf-8')), delimiter=',', fieldnames=self.get_fieldnames())
            container = Container.objects.get(id=request.POST['container'])
            for line in records:
                self.process_record(container, line)
            self.message_user(request, 'Your CSV file has been imported')
            return redirect("..")

        form = UploadContainerDataForm()
        payload = {"form": form}
        return render(request, "admin_custom/upload_csv_form.html", payload)


@admin.register(FullnessValues)
class FullnessValuesAdmin(ImportContainerDataFromCsvModelAdminMixin, admin.ModelAdmin):
    list_display = ('container', 'fullness_value', 'actual')
    list_filter = ('container',)

    def get_fieldnames(self):
        return ['ctime', 'value']

    def process_record(self, container, record):
        fullness = FullnessValues()
        fullness.container = container
        fullness.ctime = datetime.strptime(record['ctime'], self.default_datetime_format)
        fullness.actual = 0
        fullness.fullness_value = record['value']
        fullness.save()


@admin.register(Error)
class ErrorAdmin(ImportContainerDataFromCsvModelAdminMixin, admin.ModelAdmin):
    list_display = ('container', 'get_error_code', 'get_error_equipment', 'get_error_title')

    def save_model(self, request, obj, form, change):
        Error.objects.filter(container__company_id=obj.container.company.id, container_id=obj.container.id).update(
            actual=0)
        obj.save()

    def get_queryset(self, request):
        queryset = super(ErrorAdmin, self).get_queryset(request)
        queryset = queryset.select_related('container', 'error_type')
        queryset = queryset.prefetch_related('error_type__equipment')
        return queryset

    def get_error_code(self, obj):
        return obj.error_type.code

    def get_error_equipment(self, obj):
        return obj.error_type.equipment

    def get_error_title(self, obj):
        return obj.error_type.title

    def get_fieldnames(self):
        return ['ctime', 'actual', 'type_id']

    def process_record(self, container, record):
        error = Error()
        error.container = container
        error.ctime = datetime.strptime(record['ctime'], self.default_datetime_format)
        error.actual = record['actual']
        error.error_type = ErrorType.objects.get(id=record['type_id'])
        error.save()


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('user', 'ctime')


@admin.register(Battery_Level)
class Battery_LevelAdmin(ImportContainerDataFromCsvModelAdminMixin, admin.ModelAdmin):
    list_display = ('container', 'level', 'actual')

    def save_model(self, request, obj, form, change):
        Battery_Level.objects.filter(container_id=obj.container.id).update(actual=0)
        obj.save()

    def get_queryset(self, request):
        queryset = super(Battery_LevelAdmin, self).get_queryset(request)
        queryset = queryset.select_related('container')
        return queryset

    def get_fieldnames(self):
        return ['ctime', 'value']

    def process_record(self, container, record):
        battery_level = Battery_Level()
        battery_level.container = container
        battery_level.ctime = datetime.strptime(record['ctime'], self.default_datetime_format)
        battery_level.actual = 0
        battery_level.level = record['value']
        battery_level.save()


@admin.register(Temperature)
class TemperatureAdmin(ImportContainerDataFromCsvModelAdminMixin, admin.ModelAdmin):
    list_display = ('container', 'temperature_value', 'actual', 'ctime')

    def save_model(self, request, obj, form, change):
        Battery_Level.objects.filter(container__company_id=obj.container.company.id,
                                     container_id=obj.container.id).update(actual=0)
        obj.save()

    def get_queryset(self, request):
        queryset = super(TemperatureAdmin, self).get_queryset(request)
        queryset = queryset.select_related('container')
        return queryset

    def get_fieldnames(self):
        return ['ctime', 'value']

    def process_record(self, container, record):
        temperature = Temperature()
        temperature.container = container
        temperature.ctime = datetime.strptime(record['ctime'], self.default_datetime_format)
        temperature.actual = 0
        temperature.temperature_value = record['value']
        temperature.save()


@admin.register(SimBalance)
class SimBalanceAdmin(ImportContainerDataFromCsvModelAdminMixin, admin.ModelAdmin):
    list_display = ('container', 'balance', 'actual', 'ctime')

    def save_model(self, request, obj, form, change):
        SimBalance.objects.filter(container_id=obj.container.id).update(actual=0)
        obj.save()

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('container')
        return queryset

    def get_fieldnames(self):
        return ['ctime', 'value']

    def process_record(self, container, record):
        balance = SimBalance()
        balance.container = container
        balance.ctime = datetime.strptime(record['ctime'], self.default_datetime_format)
        balance.actual = 0
        balance.balance = record['value']
        balance.save()


@admin.register(Pressure)
class PressureAdmin(ImportContainerDataFromCsvModelAdminMixin, admin.ModelAdmin):
    list_display = ('container', 'pressure_value', 'actual', 'ctime')

    def save_model(self, request, obj, form, change):
        Pressure.objects.filter(container_id=obj.container.id).update(actual=0)
        obj.save()

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('container')
        return queryset

    def get_fieldnames(self):
        return ['ctime', 'value']

    def process_record(self, container, record):
        pressure = Pressure()
        pressure.container = container
        pressure.ctime = datetime.strptime(record['ctime'], self.default_datetime_format)
        pressure.actual = 0
        pressure.pressure_value = record['value']
        pressure.save()


@admin.register(Traffic)
class TrafficAdmin(ImportContainerDataFromCsvModelAdminMixin, admin.ModelAdmin):
    list_display = ('container', 'traffic_value', 'actual', 'ctime')

    def save_model(self, request, obj, form, change):
        Traffic.objects.filter(container_id=obj.container.id).update(actual=0)
        obj.save()

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('container')
        return queryset

    def get_fieldnames(self):
        return ['ctime', 'value']

    def process_record(self, container, record):
        traffic = Traffic()
        traffic.container = container
        traffic.ctime = datetime.strptime(record['ctime'], self.default_datetime_format)
        traffic.actual = 0
        traffic.traffic_value = record['value']
        traffic.save()


@admin.register(EnergyEfficiencyProfile)
class EnergyEfficiencyParamsAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'sleep_period_start', 'sleep_period_stop', 'min_temperature_for_charging', 'battery_capacity',
        'standby_days_stop', 'battery_charge_change_window_days',
    )


def calculate_ef_for_bins(modeladmin, request, queryset):
    for ef_for_bin in queryset:
        calculate_energy_efficiency.delay(ef_for_bin.pk)
    messages.success(request, 'Energy efficiency is scheduled for calculation for bins specified')


calculate_ef_for_bins.short_description = "Calculate EF for selected bins"


@admin.register(EnergyEfficiencyForContainer)
class EnergyEfficiencyForContainerAdmin(admin.ModelAdmin):
    list_display = ('id', 'container', 'profile', 'turn_on')
    readonly_fields = ('ef_last_log', 'turn_on')
    actions = [calculate_ef_for_bins]


@admin.register(MobileAppTranslation)
class MobileAppTranslationAdmin(admin.ModelAdmin):
    list_display = ('id', 'string_name', 'string_text', 'lang')


def execute_cds_requests(modeladmin, request, queryset):
    for cdsr in queryset:
        process_single_demo_sandbox_request.delay(cdsr.pk)
    messages.success(request, 'Requests sent for processing')


execute_cds_requests.short_description = "Execute selected CDS requests"


class CreateDemoSandboxRequestAdminForm(forms.ModelForm):
    username_prefix = forms.CharField(required=False, help_text='Will be autogenerated if left empty')
    lang = forms.ChoiceField(choices=settings.LANGUAGES)

    def clean_username_prefix(self):
        return clean_company_username_prefix(
            self.cleaned_data["username_prefix"], self.cleaned_data.get("company_name"))


@admin.register(CreateDemoSandboxRequest)
class CreateDemoSandboxRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'ctime', 'template_company', 'company_name', 'status', 'progress', 'mtime')
    list_filter = ('status',)
    readonly_fields = ('admin_username', 'admin_password', 'progress')
    actions = [execute_cds_requests]
    form = CreateDemoSandboxRequestAdminForm

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'template_company':
            kwargs['queryset'] = Company.objects.filter(pk__in=settings.DEMO_SANDBOX_TEMPLATE_COMPANY_IDS)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(TrashbinJobModel)
class TrashbinJobModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'trashbin', 'type', 'ctime', 'status')
    list_filter = ('trashbin', 'type', 'status')


@admin.register(SlackEnabledTrashbin)
class SlackEnabledTrashbinAdmin(admin.ModelAdmin):
    list_display = ('id', 'serial_number')


trashbin_translations_file_header = ['serial', 'lang', 'key', 'value']


def validate_trashbin_translations_file_contents(value):
    records = csv.DictReader(
        StringIO(value.read().decode('utf-8')), delimiter=',', fieldnames=trashbin_translations_file_header)
    next(records)  # Skip any header
    uniqueness_checker = set()
    record_count = 0
    for index, line in enumerate(records):
        line_no = index + 2
        serial, lang, key = [line[k] for k in trashbin_translations_file_header[:-1]]
        # Value can be empty in case of a satellite
        any_missing_value = any(v is None or v == '' for v in [serial, lang, key])
        if any_missing_value:
            raise ValidationError('There are missing value(s) on line %(line_no)s', params={'line_no': line_no})

        try:
            Container.objects.get(serial_number=serial)
        except Container.DoesNotExist:
            raise ValidationError(
                'There is no container with serial %(serial)s specified on line %(line_no)s',
                params={'serial': serial, 'line_no': line_no})
        validate_lang(lang)
        try:
            DemoSandboxTranslation.objects.get(
                object_type=DemoSandboxTranslation.CONTAINER_OBJECT_TYPE, object_id=serial, lang=lang, key=key)
        except DemoSandboxTranslation.DoesNotExist:
            pass
        else:
            raise ValidationError(
                'There is an existing translation for serial/lang/key combination on line %(line_no)s',
                params={'line_no': line_no})
        uniqueness_checker.add((serial, lang, key))
        record_count += 1
    if len(uniqueness_checker) < record_count:
        raise ValidationError('There are some duplicates, serial/lang/key combinations must be unique')


class UploadTrashbinTranslationsForm(forms.Form):
    file = forms.FileField(validators=[validate_trashbin_translations_file_contents], required=True)


@admin.register(DemoSandboxTranslation)
class DemoSandboxTrashbinTranslationAdmin(admin.ModelAdmin):
    change_list_template = 'admin_custom/changelist_with_upload_csv.html'
    list_display = ('id', 'object_type', 'object_id', 'lang', 'key', 'value')
    list_filter = ('object_type', 'lang', 'key')

    def get_urls(self):
        urls = super().get_urls()
        return [path('import-csv/', self.import_csv), ] + urls

    def import_csv(self, request):
        if request.method == 'POST':
            form = UploadTrashbinTranslationsForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['file']
                csv_file.seek(0)
                records = csv.DictReader(StringIO(csv_file.read().decode('utf-8')), delimiter=',',
                                         fieldnames=trashbin_translations_file_header)
                next(records)  # Skip any header
                with transaction.atomic():
                    for line in records:
                        serial, lang, key, value = [line[k] for k in trashbin_translations_file_header]
                        DemoSandboxTranslation.objects.create(
                            object_type=DemoSandboxTranslation.CONTAINER_OBJECT_TYPE, object_id=serial, lang=lang,
                            key=key, value=value)
                self.message_user(request, 'Your translations CSV file has been imported')
                return redirect("..")
        else:
            form = UploadTrashbinTranslationsForm()
        return render(request, "admin_custom/upload_csv_form.html", {"form": form})
