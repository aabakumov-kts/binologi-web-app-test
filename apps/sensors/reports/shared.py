from django.db.models import Q

from apps.core.models import WasteType, Sectors
from apps.core.reports import collect_common_request_context, filter_queryset_by_date_range, filter_qs_by_fullness
from apps.sensors.models import ErrorType, Error
from apps.sensors.shared import get_sensors_qs_for_request


def collect_sensor_request_context(request):
    result = collect_common_request_context(request)

    if request.uac.is_superadmin:
        sectors = Sectors.objects.values('id', 'name')
    else:
        sectors = Sectors.objects.filter(company_id=request.uac.company_id).values('id', 'name')

    sensors = get_sensors_qs_for_request(request).values('id', 'serial_number')
    waste_types = WasteType.objects.values('id', 'title', 'code')
    error_types = ErrorType.objects.values('id', 'title')

    result.update({
        'sensors': sensors,
        'waste_types': waste_types,
        'error_types': error_types,
        'sectors': sectors,
    })
    return result


_common_filter_default_options = {
    'filter_by_actual': True,
    'user_is_admin': False,
    'user_company_id': None,
    'filter_qs_by_errors': None,
    'time_field_name': 'ctime',
}


def common_filter_sensor_queryset(qs, params_dict, options_dict):
    options = _common_filter_default_options.copy()
    options.update(options_dict)

    def get_options(*args):
        return (options[opt] for opt in args)

    user_is_admin, user_company_id, = get_options('user_is_admin', 'user_company_id')

    company = params_dict.get('company', None)
    sensor = params_dict.get('sensor', None)
    country = params_dict.get('country', None)
    city = params_dict.get('city', None)
    waste_type = params_dict.get('waste_type', None)
    fullness = params_dict.get('fullness', None)
    sector = params_dict.get('sector', None)
    q_search = params_dict.get('q_search', None)

    if company and company != '' and user_is_admin:
        qs = qs.filter(sensor__company__id=company)
    elif not user_is_admin:
        qs = qs.filter(sensor__company__id=user_company_id)

    if sensor and sensor != '':
        qs = qs.filter(sensor_id=sensor)

    if country and country != '':
        qs = qs.filter(sensor__country__id=country)

    if city and city != '':
        qs = qs.filter(sensor__city__id=city)

    if waste_type and waste_type != '':
        qs = qs.filter(sensor__waste_type=waste_type)

    if fullness:
        fullness_list = fullness.split(',')
        qs = filter_qs_by_fullness(qs, fullness_list, 'sensor__fullness')

    if sector and sector != '':
        qs = qs.filter(sensor__sector__id=sector)

    if q_search:
        q_search_query = (Q(sensor__serial_number__icontains=q_search) |
                          Q(sensor__address__icontains=q_search) |
                          Q(sensor__phone_number__icontains=q_search))
        qs = qs.filter(q_search_query)

    errors = params_dict.get('errors', None)
    if errors and errors != '':
        error_list = [int(er) for er in errors.split(',') if er]
        if len(error_list):
            error_containers = Error.objects.filter(
                error_type_id__in=error_list, actual=True).values_list('sensor_id', flat=True)
            qs = qs.filter(sensor_id__in=error_containers)

    qs = filter_queryset_by_date_range(qs, params_dict, options_dict)

    return qs
