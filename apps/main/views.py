import boto3
import ujson as json

from datetime import datetime, timedelta
from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Func, Min, Max, ExpressionWrapper, FloatField, Count, Exists, OuterRef, Q
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import translation
from django.utils.formats import date_format
from django.utils.translation import ugettext_lazy as _, get_language
from django.views.generic.edit import FormView
from django.views.decorators.http import require_GET, require_POST
from slugify import slugify

from apps.core.context_processors import get_return_to_url, MODAL_MESSAGE_EXTRA_TAGS
from apps.core.data import FULLNESS
from apps.core.helpers import CompanyDeviceProfile
from apps.core.middleware import license_check_exempt
from apps.core.models import FeatureFlag, Sectors, WasteType, Company, UsersToCompany
from apps.core.views import (
    LOW_BATTERY_LEVEL_ICON_DATA_URL, RESPONSIVE_BODY_CLASS, BIN_ON_ROUTE_ICON_DATA_URL, WARNING_ICON_DATA_URL,
)
from app.models import ErrorType as TrashbinErrorType, Container, Error as TrashbinError, Collection
from apps.sensors.models import (
    Sensor, ErrorType as SensorErrorType, Error as SensorError, CompanySensorsLicense, SensorsLicenseKey,
)
from apps.main.forms import RegisterCompanyForm, ExtendLicenseForm
from apps.main.helpers import get_effective_company_device_profile
from apps.main.middleware import check_license_is_valid, get_license


@require_GET
def home_login(request):
    if request.user.is_authenticated:
        return_to_url = get_return_to_url(request, 'next')
        return HttpResponseRedirect(return_to_url or '/main/')

    render_context = {
        'bad_login': bool(request.GET.get('bad_login', '')),
        'body_class': RESPONSIVE_BODY_CLASS,
    }
    return render(request, "main/home_login.html", render_context)


@require_POST
def view_login(request):
    username = request.POST.get('email', '').strip()
    password = request.POST.get('password', '').strip()
    user = authenticate(username=username, password=password)
    user_has_web_app_access = False
    if user is not None:
        user_has_company_access = hasattr(user, 'user_to_company')
        user_has_web_app_access = user.is_superuser or user_has_company_access
    if user_has_web_app_access:
        login(request, user)
        request.session[translation.LANGUAGE_SESSION_KEY] = get_language()
        return_to_url = get_return_to_url(request, 'next')
        return HttpResponseRedirect(return_to_url or '/main/')
    else:
        lang_arg_part = f"lang={request.GET.get('lang')}&" if request.GET.get('lang') else ''
        return HttpResponseRedirect(f'/?{lang_arg_part}bad_login=1')


@require_POST
@login_required
def view_logout(request):
    logout(request)
    # Explicitly drop session once again to avoid persisting selected language, see django.contrib.auth.logout impl
    request.session.flush()
    return HttpResponseRedirect('/')


_DEFAULT_MAP_POSITIONING = {
    'center': {
        'lng': 37.573856,
        'lat': 55.751574,
    },
    'zoom': 9,
}


def calculate_efficiency_monitor_values(containers_qs):
    effective_collection_fullness = 80
    bin_fullness_threshold = 80
    collections_analysis_weeks = 4
    utc_now = datetime.utcnow()
    current_week_start = utc_now - timedelta(weeks=1)
    previous_week_start = utc_now - timedelta(weeks=2)
    total_trashbins_count = containers_qs.count()
    collections_analysis_start = utc_now - timedelta(weeks=collections_analysis_weeks)

    def calculate_percentage(value, total):
        return round((value / total) * 100, 2) if value and total else 0

    def calculate_collection_efficiency(start, end):
        week_collections = Collection.objects.filter(container__in=containers_qs, ctime__gt=start, ctime__lte=end)
        effective_week_collections = week_collections.filter(fullness__gte=effective_collection_fullness).count()
        total_week_collections = week_collections.count()
        return calculate_percentage(effective_week_collections, total_week_collections) \
            if total_week_collections > 0 else None

    trashbins_with_collection = containers_qs.filter(
        collection__ctime__gt=collections_analysis_start, collection__ctime__lte=utc_now).annotate(
        collections_count=Count('collection')).filter(collections_count__gt=0).count()
    current_week_effectiveness = calculate_collection_efficiency(current_week_start, utc_now)

    result = {
        'current_week_effectiveness': current_week_effectiveness,
        'filled_bins_count': containers_qs.filter(fullness__gte=bin_fullness_threshold).count(),
        'bins_without_collection_count': total_trashbins_count - trashbins_with_collection,
        'bins_with_errors_count': containers_qs.filter(errors__actual=1).count(),
    }
    if current_week_effectiveness:
        previous_week_effectiveness = calculate_collection_efficiency(previous_week_start, current_week_start) or 0
        result['effectiveness_diff'] = round(current_week_effectiveness - previous_week_effectiveness, 2)
    for field_to_get_percentage in ['filled_bins', 'bins_without_collection', 'bins_with_errors']:
        value = result[field_to_get_percentage + '_count']
        result[field_to_get_percentage + '_percent'] = calculate_percentage(value, total_trashbins_count)
    return result


def _get_devices_queryset(request, model):
    if not (request.uac.is_superadmin or (request.uac.has_per_company_access and request.uac.company)):
        devices_queryset = model.objects.none()
    else:
        devices_queryset = model.objects.all()
        if request.uac.company:
            devices_queryset = devices_queryset.filter(company=request.uac.company)
    return devices_queryset


@require_GET
@login_required
def view_main(request):
    try:
        device_profile = CompanyDeviceProfile(request.GET.get('device_profile', ''))
    except ValueError:
        pass
    else:
        request.session['device_profile_override'] = device_profile.value

    device_profile = get_effective_company_device_profile(request)
    devices_queryset = _get_devices_queryset(
        request, Sensor if device_profile == CompanyDeviceProfile.SENSOR else Container)

    open_device_type_qp = request.GET.get('openDeviceType', '')
    open_device_id_qp = request.GET.get('openDeviceId', '')
    valid_device_types = ['sensor', 'bin']
    open_device_qp_correct = open_device_type_qp and open_device_id_qp and open_device_type_qp in valid_device_types
    device_to_open = None
    if open_device_qp_correct:
        device_model = Container if open_device_type_qp == 'bin' else Sensor
        device_to_open = device_model.objects.filter(pk=open_device_id_qp).first()

    lat_query_param = request.GET.get('lat', '')
    lng_query_param = request.GET.get('lng', '')

    if device_to_open:
        map_positioning = {
            'center': {
                'lng': float(device_to_open.location.x),
                'lat': float(device_to_open.location.y),
            },
            'zoom': 15,
            'override': True,
        }
    elif lat_query_param and lng_query_param:
        map_positioning = {
            'center': {
                'lng': float(lng_query_param),
                'lat': float(lat_query_param),
            },
            'zoom': 15,
            'override': True,
        }
    elif devices_queryset.count() > 0:
        containers_bounds = devices_queryset.annotate(
            lng=ExpressionWrapper(Func('location', function='ST_X'), output_field=FloatField()),
            lat=ExpressionWrapper(Func('location', function='ST_Y'), output_field=FloatField())) \
            .aggregate(lng_min=Min('lng'), lng_max=Max('lng'), lat_min=Min('lat'), lat_max=Max('lat'))
        map_positioning = {
            'center': {
                'lng': containers_bounds['lng_min'] + (
                            (containers_bounds['lng_max'] - containers_bounds['lng_min']) / 2),
                'lat': containers_bounds['lat_min'] + (
                            (containers_bounds['lat_max'] - containers_bounds['lat_min']) / 2),
            },
            'bounds': {
                'lngMin': containers_bounds['lng_min'],
                'lngMax': containers_bounds['lng_max'],
                'latMin': containers_bounds['lat_min'],
                'latMax': containers_bounds['lat_max'],
            },
        }
    else:
        map_positioning = _DEFAULT_MAP_POSITIONING

    context = {
        'maps_api_key': settings.GOOGLE_MAPS_API_KEY,
        'map_positioning': json.dumps(map_positioning),
        'low_battery_level_icon_url': LOW_BATTERY_LEVEL_ICON_DATA_URL,
        'bin_on_route_icon_url': BIN_ON_ROUTE_ICON_DATA_URL,
        'warning_icon_url': WARNING_ICON_DATA_URL,
    }

    if device_to_open:
        context['open_device_info'] = json.dumps({
            'type': open_device_type_qp,
            'pk': open_device_id_qp,
        })

    if request.uac.is_driver:
        context['body_class'] = f'map-page {RESPONSIVE_BODY_CLASS}'
        context['onesignal_app_id'] = settings.ONESIGNAL_APP_ID
        return render(request, 'main/map_driver.html', context)

    context.update({
        'efficiency_monitor_enabled':
            device_profile == CompanyDeviceProfile.TRASHBIN and
            request.uac.check_feature_enabled(FeatureFlag.EFFICIENCY_MONITOR),
        'body_class': 'map-page',
    })

    sectors_queryset = Sectors.objects.annotate(
        containers_count=Count('container'), sensors_count=Count('sensor')).filter(
        Q(containers_count__gt=0) | Q(sensors_count__gt=0)).order_by('pk')
    if request.uac.company:
        sectors_queryset = sectors_queryset.filter(company=request.uac.company)
    sectors_filter_enabled = not request.uac.is_superadmin and len(sectors_queryset) > 1

    context.update({
        'filters': {
            'waste_type': {
                'name': 'waste_type',
                'title': _('waste type'),
                'options': WasteType.objects.all(),
            },
            'fullness': {
                'name': 'fullness',
                'title': _('fullness'),
                'options': reversed(FULLNESS),
            },
            'sector': {
                'enabled': sectors_filter_enabled,
                'options': sectors_queryset.values('pk', 'name')[:10] if sectors_filter_enabled else [],
            },
        },
    })

    if device_profile == CompanyDeviceProfile.SENSOR:
        errors_queryset = SensorError.objects.filter(error_type=OuterRef('pk'), actual=True)
        if request.uac.company:
            errors_queryset = errors_queryset.filter(sensor__company=request.uac.company)
        error_type_queryset = SensorErrorType.objects.annotate(
            actual_error_exists=Exists(errors_queryset)).filter(actual_error_exists=True)
        error_type_filter_enabled = error_type_queryset.count() > 0

        context['filters']['error_type'] = {
            'name': 'error_type',
            'title': _('error type'),
            'enabled': error_type_filter_enabled,
            'options': error_type_queryset if error_type_filter_enabled else [],
        }
    else:
        errors_queryset = TrashbinError.objects.filter(error_type=OuterRef('pk'), actual=1)
        if request.uac.company:
            errors_queryset = errors_queryset.filter(container__company=request.uac.company)
        error_type_queryset = TrashbinErrorType.objects.annotate(
            actual_error_exists=Exists(errors_queryset)).filter(actual_error_exists=True).select_related('equipment')
        error_type_filter_enabled = len(error_type_queryset) > 1

        context['filters'].update({
            'error_type': {
                'name': 'error_type',
                'title': _('error type'),
                'enabled': error_type_filter_enabled,
                'options': error_type_queryset.order_by('equipment__id'),
            },
        })

    return render(request, 'main/map.html', context)


@require_GET
@login_required
def settings_index(request):
    device_profile = get_effective_company_device_profile(request)
    if device_profile == CompanyDeviceProfile.SENSOR:
        return redirect(reverse('sensors:list'))
    return redirect(reverse('containers:list'))


@require_GET
@login_required
def view_efficiency_monitor(request):
    if not request.uac.check_feature_enabled(FeatureFlag.EFFICIENCY_MONITOR):
        return HttpResponseForbidden()
    containers_queryset = _get_devices_queryset(request, Container)
    return render(request, 'main/efficiency_monitor/index.html',
                  calculate_efficiency_monitor_values(containers_queryset))


@license_check_exempt
@require_POST
@login_required
def view_switch_device_profile(request):
    try:
        device_profile = CompanyDeviceProfile(request.POST.get('profile', ''))
    except ValueError:
        raise SuspiciousOperation('Profile parameter not provided')
    request.session['device_profile_override'] = device_profile.value
    return HttpResponseRedirect('/')


class RegisterCompanyFormView(FormView):
    template_name = 'main/register_company.html'
    form_class = RegisterCompanyForm

    def get_context_data(self, **kwargs):
        kwargs['body_class'] = RESPONSIVE_BODY_CLASS
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        license_key = form.cleaned_data.get('license_key')
        try:
            slk = SensorsLicenseKey.objects.get(key=license_key)
        except SensorsLicenseKey.DoesNotExist:
            form.add_error(
                'license_key',
                _('No such license key. Please double check the input or contact our support service.'))
            return super().form_invalid(form)
        else:
            if slk.used:
                form.add_error(
                    'license_key',
                    _('License key was already used. Please double check the input or contact our support service.'))
                return super().form_invalid(form)

        contact_email = form.cleaned_data.get('contact_email')
        company_name = form.cleaned_data.get('company_name')
        with transaction.atomic():
            try:
                new_company = Company.objects.create(
                    name=company_name, username_prefix=slugify(company_name) + '-', lang=get_language())
            except IntegrityError:
                form.add_error(
                    'company_name',
                    _('This company name is already taken. Please try another or contact our support service.'))
                return super().form_invalid(form)

            slk.create_license(new_company)
            user_model = get_user_model()
            admin_user = user_model.objects.create(username=new_company.username_prefix + 'admin', email=contact_email)
            random_password = get_user_model().objects.make_random_password()
            admin_user.set_password(random_password)
            admin_user.save()
            admin_user.user_to_company = UsersToCompany()
            admin_user.user_to_company.company = new_company
            admin_user.user_to_company.role = UsersToCompany.ADMIN_ROLE
            admin_user.user_to_company.save()
            admin_username, admin_password = admin_user.username, random_password

        ses_client = boto3.client('ses')
        ses_client.send_templated_email(
            Source=settings.DEFAULT_FROM_EMAIL,
            Destination={
                'ToAddresses': [
                    contact_email,
                ],
            },
            Template=str(_('register-company-ses-template-name')),  # Enforcing str here to bypass type validation
            TemplateData=json.dumps({
                'company_name': company_name,
                'web_app_url': f'{settings.WEB_APP_ROOT_URL}/?lang={get_language()}',
                'login': admin_username,
                'password': admin_password,
            })
        )

        login(self.request, admin_user)
        self.request.session[translation.LANGUAGE_SESSION_KEY] = get_language()
        return super().form_valid(form)

    def get_success_url(self):
        next_url = get_return_to_url(self.request, 'next')
        return next_url if next_url else '/'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('/')

        return super().get(request, *args, **kwargs)


@license_check_exempt
@login_required
def invalid_license_view(request):
    license_is_valid = check_license_is_valid(request)
    if license_is_valid:
        return redirect('/')
    return render(request, 'main/invalid_license.html')


@license_check_exempt
@require_GET
@login_required
def account_info_view(request):
    context = {}
    if request.uac.has_per_company_access:
        context['company_name'] = request.uac.company.name
        device_license = get_license(request)
        if device_license:
            context['license_info'] = {
                'start': date_format(device_license.begin, "SHORT_DATE_FORMAT"),
                'end': date_format(device_license.end, "SHORT_DATE_FORMAT"),
                'invalid': not device_license.is_valid
            }
            if isinstance(device_license, CompanySensorsLicense):
                context['license_info']['usage_balance'] = device_license.usage_balance
                if request.uac.is_administrator:
                    context['extend_license_form'] = ExtendLicenseForm()
    return render(request, "main/account/info.html", context)


@license_check_exempt
@require_POST
@login_required
def extend_license_view(request):
    extending_successful = False
    if request.uac.has_per_company_access:
        device_license = get_license(request)
        if device_license and isinstance(device_license, CompanySensorsLicense):
            form = ExtendLicenseForm(data=request.POST)
            if form.is_valid():
                license_key = form.cleaned_data.get('license_key')
                try:
                    slk = SensorsLicenseKey.objects.get(key=license_key)
                except SensorsLicenseKey.DoesNotExist:
                    slk = None
                if slk and not slk.used:
                    slk.extend_license(device_license, request.user)
                    extending_successful = True
                    messages.success(request, 'licenseExtendedSuccess', MODAL_MESSAGE_EXTRA_TAGS)
    if not extending_successful:
        messages.warning(request, 'licenseExtensionFailure', MODAL_MESSAGE_EXTRA_TAGS)
    return HttpResponseRedirect(reverse('main:map'))
