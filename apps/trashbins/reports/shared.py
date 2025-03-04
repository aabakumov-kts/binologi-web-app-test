from django.db.models import Q

from apps.core.models import Sectors, WasteType
from apps.core.reports import collect_common_request_context, filter_queryset_by_date_range, filter_qs_by_fullness
from app.models import ContainerType, Container, ErrorType, Equipment, Error


def collect_trashbin_request_context(request):
    result = collect_common_request_context(request)

    container_types = ContainerType.objects.values('id', 'title')

    if request.uac.is_superadmin:
        sectors = Sectors.objects.values('id', 'name')
    else:
        sectors = Sectors.objects.filter(company_id=request.uac.company_id).values('id', 'name')

    containers = []
    if request.uac.is_superadmin:
        # TODO: This is an unbounded data set
        containers = Container.objects.values('id', 'serial_number')
    elif request.uac.has_per_company_access:
        sectors = Sectors.objects.filter(company=request.uac.company).values('id', 'name')
        containers = Container.objects.filter(company=request.uac.company).values('id', 'serial_number')

    waste_types = WasteType.objects.values('id', 'title', 'code')
    error_types = ErrorType.objects.values('id', 'title', 'equipment__title', 'equipment__id')
    equipment = Equipment.objects.values('id', 'title')

    result.update({
        'containers': containers,
        'waste_types': waste_types,
        'error_types': error_types,
        'container_types': container_types,
        'sectors': sectors,
        'equipment': equipment,
    })
    return result


_common_filter_default_options = {
    'filter_by_actual': True,
    'user_is_admin': False,
    'user_company_id': None,
    'filter_qs_by_errors': None,
    'time_field_name': 'ctime',
}


def _default_filter_qs_by_errors(qs, error_list):
    error_containers = Error.objects.filter(
        error_type_id__in=error_list, actual=1).values_list('container_id', flat=True)
    return qs.filter(container_id__in=error_containers)


def common_filter_trashbin_queryset(qs, params_dict, options_dict):
    options = _common_filter_default_options.copy()
    options.update(options_dict)

    def get_options(*args):
        return (options[opt] for opt in args)

    user_is_admin, user_company_id, = get_options('user_is_admin', 'user_company_id')

    company = params_dict.get('company', None)
    container = params_dict.get('container', None)
    country = params_dict.get('country', None)
    city = params_dict.get('city', None)
    waste_type = params_dict.get('waste_type', None)
    fullness = params_dict.get('fullness', None)
    sector = params_dict.get('sector', None)
    container_type = params_dict.get('container_type', None)
    q_search = params_dict.get('q_search', None)

    if company and company != '' and user_is_admin:
        qs = qs.filter(container__company__id=company)
    elif not user_is_admin:
        qs = qs.filter(container__company__id=user_company_id)

    if container and container != '':
        qs = qs.filter(container_id=container)

    if country and country != '':
        qs = qs.filter(container__country__id=country)

    if city and city != '':
        qs = qs.filter(container__city__id=city)

    if waste_type and waste_type != '':
        qs = qs.filter(container__waste_type=waste_type)

    if fullness:
        fullness_list = fullness.split(',')
        qs = filter_qs_by_fullness(qs, fullness_list, 'container__fullness')

    if sector and sector != '':
        qs = qs.filter(container__sector__id=sector)

    if container_type and container_type != '':
        qs = qs.filter(container__container_type=container_type)

    if q_search:
        q_search_query = (Q(container__serial_number__icontains=q_search) |
                          Q(container__address__icontains=q_search) |
                          Q(container__phone_number__icontains=q_search))
        qs = qs.filter(q_search_query)

    errors = params_dict.get('errors', None)
    if errors and errors != '':
        error_list = [int(er) for er in errors.split(',') if er]
        if len(error_list):
            filter_qs_by_errors, = get_options('filter_qs_by_errors')
            if filter_qs_by_errors is not None:
                qs = filter_qs_by_errors(qs, error_list)
            else:
                qs = _default_filter_qs_by_errors(qs, error_list)

    qs = filter_queryset_by_date_range(qs, params_dict, options_dict)

    return qs
