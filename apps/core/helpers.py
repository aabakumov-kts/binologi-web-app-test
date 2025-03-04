import logging
import math
import operator
import random
import requests

from django.conf import settings
from django.contrib.gis.gdal import Envelope
from django.db.models import Q
from django.utils.translation import override as current_language_override
from enum import Enum
from functools import reduce

from apps.core.models import City, Country


logger = logging.getLogger('app_main')


def filter_queryset_by_bounds(queryset, bounds):
    any_bound_missing = any(b is None for b in bounds)
    if any_bound_missing:
        return queryset

    float_bounds = [float(b) for b in bounds]
    any_bound_is_nan = any(math.isnan(b) for b in float_bounds)
    if any_bound_is_nan:
        return queryset

    north, west, south, east = float_bounds
    min_y, max_y = (south, north,) if south < north else (north, south,)
    min_x, max_x = (east, west,) if east < west else (west, east,)
    bounds = Envelope(min_x, min_y, max_x, max_y)
    return queryset.filter(location__intersects=bounds.wkt)


def filter_queryset_by_fullness(queryset, fullness_list):
    complex_query = []
    for item in fullness_list:
        complex_query.append(Q(fullness__lte=item.upper) &
                             Q(fullness__gte=item.lower))
    if complex_query:
        queryset = queryset.filter(reduce(operator.or_, complex_query))
    return queryset


def get_unknown_city_country():
    with current_language_override('en'):
        unknown_city = City.objects.prefetch_related('country').get(title='Unknown')
    return unknown_city.country, unknown_city


def _check_reverse_geocoding_result(res):
    if 'address_components' not in res:
        return False
    street_address_present = any((comp for comp in res['address_components'] if 'street_number' in comp['types']))
    city_present = any((comp for comp in res['address_components'] if 'locality' in comp['types']))
    country_present = any((comp for comp in res['address_components'] if 'country' in comp['types']))
    return street_address_present and city_present and country_present


def execute_reverse_geocoding(lat_lng, lang):
    if not any((lng for lng, _ in settings.LANGUAGES if lng == lang)):
        raise ValueError(f'Unsupported language specified: {lang}')

    response = requests.get(
        'https://maps.googleapis.com/maps/api/geocode/json',
        params={
            'latlng': f'{lat_lng[0]},{lat_lng[1]}',
            'key': settings.GOOGLE_MAPS_API_KEY,
            'result_type': 'street_address',
            'language': lang,
        },
    ).json()
    resp_status = response['status']
    unknown_country, unknown_city = get_unknown_city_country()
    fallback_result = unknown_country, unknown_city, ''
    if resp_status != 'OK':
        error_message = response['error_message'] if 'error_message' in response else 'No error message provided'
        logger.warning(f'Reverse geocoding request failed with status {resp_status}: {error_message}')
        return fallback_result

    valid_result = next((res for res in response['results'] if _check_reverse_geocoding_result(res)), None)
    if valid_result is None:
        return fallback_result

    country_addr_component = next((comp for comp in valid_result['address_components'] if 'country' in comp['types']))
    city_addr_component = next((comp for comp in valid_result['address_components'] if 'locality' in comp['types']))
    with current_language_override(lang):
        city = City.objects.filter(title__icontains=city_addr_component['long_name']).first()
        country = Country.objects.filter(name__icontains=country_addr_component['long_name']).first()
    return country or unknown_country, city or unknown_city, valid_result['formatted_address']


class CompanyDeviceProfile(Enum):
    TRASHBIN = 'trashbin'
    SENSOR = 'sensor'


def format_random_location(center):
    return 'SRID=4326;POINT ({} {})'.format(
        center['lng'] + (random.random() - 0.5),
        center['lat'] + (random.random() - 0.5),
    )
