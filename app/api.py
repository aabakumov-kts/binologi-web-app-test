import boto3
import logging
import operator
import ujson as json

from botocore.client import Config
from django.db.models import Q, Count, Exists, OuterRef, Case, When, Value, BooleanField
from rest_framework.generics import ListAPIView, GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import ValidationError
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from functools import reduce
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from django.db import transaction

from apps.core.data import FULLNESS
from apps.core.helpers import filter_queryset_by_bounds, filter_queryset_by_fullness
from apps.core.models import City, Country
from app.helpers import validate_user_license
from app.models import (
    Container, MobileAppUserLanguage, MobileAppTranslation, ROUTE_POINT_STATUS_NOT_COLLECTED,
    RoutePoints, ContainerAuthToken, TrashbinJobModel, TrashbinData, EnergyEfficiencyForContainer, Error,
)
from app.tasks import notify_about_trashbin_message, calculate_energy_efficiency
from apps.trashbins.models import CompanyTrashbinsLicense
from apps.trashbins.trashbin_data_parsing import is_trashbin_data_with_satellites, parse_trashbin_data_packet
from apps.trashbins.tasks import generate_trashbin_status_notifications
from app.serializers import (
    ContainerSerializer, CitySerializer, ApiAuthTokenSerializer, MobileAppTranslationSerializer,
)
from app.authentication import token_is_expired
from app.permissions import IsContainerAuthenticated


logger = logging.getLogger('app_main')


class ContainerListAPIView(GenericAPIView):
    serializer_class = ContainerSerializer

    def get(self, request):
        containers_queryset = self.filter_queryset(self.get_queryset())
        satellites_ids = list(containers_queryset.filter(is_master=False).values('id', 'master_bin_id'))
        master_ids = list(containers_queryset.filter(satellites_count__gt=0).values_list('id', flat=True))
        all_master_ids = list(set(master_ids + [p['master_bin_id'] for p in satellites_ids]))
        all_stations = Container.objects.filter(id__in=all_master_ids).prefetch_related('satellites')
        result_stations = []
        for station in all_stations:
            # Usage of station.satellites.all() is important here to actually hit the cache set up with prefetch_related
            station_satellites = [satellite.id for satellite in station.satellites.all()]
            result_station = {
                'location': {'x': station.location.x, 'y': station.location.y},
                'master': station.id,
                'satellites': station_satellites,
            }
            result_stations.append(result_station)

        serializer = self.get_serializer(containers_queryset, many=True)
        return Response({'containers': serializer.data, 'stations': result_stations})

    def get_queryset(self):
        if not (self.request.uac.is_superadmin or (
                self.request.uac.has_per_company_access and self.request.uac.company)):
            base_qs = Container.objects.none()
        else:
            base_qs = Container.objects.select_related('city', 'sector')
        not_collected_route_points = RoutePoints.objects.filter(
            container=OuterRef('pk'), status=ROUTE_POINT_STATUS_NOT_COLLECTED)
        active_errors = Error.objects.filter(container=OuterRef('pk'), actual=1)
        return base_qs.annotate(
            satellites_count=Count('satellites'),
            any_active_routes=Exists(not_collected_route_points),
            low_battery_level=Case(
                When(
                    Q(battery__lte=settings.LOW_BATTERY_STATUS_ICON_LEVEL_THRESHOLD) & Q(is_master=True),
                    then=Value(True)),
                default=Value(False),
                output_field=BooleanField()),
            any_active_errors=Exists(active_errors))

    def filter_queryset(self, queryset):
        if self.request.uac.company:
            queryset = queryset.filter(company=self.request.uac.company)

        params = self.request.query_params

        # fullness complex query ( AND ) OR ( AND ) OR ...
        fullness_list = [x for x in FULLNESS if x.title in params.getlist('fullness', [])]
        queryset = filter_queryset_by_fullness(queryset, fullness_list)

        # filter by waste type
        waste_type = params.getlist('waste_type', [])
        if waste_type:
            queryset = queryset.filter(waste_type__in=waste_type, )

        # filter by error types
        complex_query = []
        error_type = params.getlist('error_type', [])
        if error_type:
            complex_query.append(Q(errors__error_type__in=error_type,) &
                                 Q(errors__actual=1))
            queryset = queryset.filter(reduce(operator.and_, complex_query))

        sector = params.getlist('sector', [])
        if sector:
            queryset = queryset.filter(sector__in=sector)

        serials = params.getlist('serial', [])
        if serials:
            queryset = queryset.filter(serial_number__in=serials)

        bounds = [self.request.query_params.get(k) for k in ['north', 'west', 'south', 'east']]
        return filter_queryset_by_bounds(queryset, bounds)


class CitiesListAPIView(ListAPIView):
    serializer_class = CitySerializer

    def get_queryset(self):
        country_id = self.kwargs.get('pk')
        countries = Country.objects.filter(pk=country_id)
        if not countries.exists():
            return City.objects.none()
        queryset = City.objects.filter(country__in=countries, title__isnull=False)
        return queryset


class GenericObtainAuthToken(APIView):
    throttle_classes = ()
    permission_classes = ()
    parser_classes = (FormParser, MultiPartParser, JSONParser,)

    def post(self, request):
        try:
            username = request.data['username']
            password = request.data['password']
            serializer = ApiAuthTokenSerializer(data={'username': username, 'password': password})
            try:
                serializer.is_valid(raise_exception=True)
            except ValidationError:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.warning('Error in %s (%s)' % (str(e), type(e)))
            return Response({'detail': 'Authentication failed'}, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data['user']
        # DRF auth happens in the view layer hence UserAccessControlMiddleware can't check the subscription
        validation_result = validate_user_license(user)
        if validation_result is not None and not validation_result:
            return Response({'detail': 'Subscription is expired or otherwise invalid'},
                            status=status.HTTP_403_FORBIDDEN)

        token, created = Token.objects.get_or_create(user=user)
        self.before_response_hook(request, user)
        return Response({'token': token.key}, status=status.HTTP_200_OK)

    def before_response_hook(self, request, user):
        pass


class MobileApiObtainAuthToken(GenericObtainAuthToken):
    def before_response_hook(self, request, user):
        if 'locale' not in request.data:
            return
        locale = request.data['locale'].lower()
        try:
            user_lang = MobileAppUserLanguage.objects.get(user=user)
            user_lang.lang = locale
            user_lang.save()
        except MobileAppUserLanguage.DoesNotExist:
            MobileAppUserLanguage.objects.create(user=user, lang=locale)


class UserProfile(APIView):
    def get(self, request):
        user = request.user
        # DRF auth happens in the view layer hence UserAccessControlMiddleware can't check the subscription
        validation_result = validate_user_license(user)
        if validation_result is not None and not validation_result:
            return Response({'detail': 'Subscription is expired or otherwise invalid'},
                            status=status.HTTP_403_FORBIDDEN)

        return Response({
            'username': user.username,
        })


class MobileAppTranslationView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        if 'lang' in request.data or 'lang' in request.GET:
            lang = None
            if 'lang' in request.data:
                lang = request.data['lang']
            elif 'lang' in request.GET:
                lang = request.GET['lang']

            try:
                langstrings = MobileAppTranslation.objects.filter(lang=lang).order_by("id")
            except Exception as e:
                logger.error('%s (%s)' % (str(e), type(e)))
                return Response({}, status=status.HTTP_400_BAD_REQUEST)

            serializer = MobileAppTranslationSerializer(langstrings, many=True)
        else:
            return Response({}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data)


@api_view(['POST'])
@permission_classes((AllowAny,))
def get_trashbin_auth_token(request):
    if 'serial' not in request.data or 'password' not in request.data:
        return Response({'error': ["Auth credentials are not provided"]}, status=status.HTTP_401_UNAUTHORIZED)

    serial, password = request.data['serial'], request.data['password']
    try:
        container = Container.objects.get(serial_number=serial)
    except Container.DoesNotExist:
        container = None
    else:
        def password_setter(raw_password):
            container.password = make_password(raw_password)
            container.save(update_fields=['password'])
        if not check_password(password, container.password, password_setter):
            container = None
    if container is not None:
        try:
            token = ContainerAuthToken.objects.get(container=container)
        except ContainerAuthToken.DoesNotExist:
            token = ContainerAuthToken.objects.create(container=container)
        if token_is_expired(token):
            token.delete()
            token = ContainerAuthToken.objects.create(container=container)
        return Response({'token': token.key, 'user_id': token.container_id}, status=status.HTTP_200_OK)
    else:
        return Response({'error': ["Auth credentials provided are invalid"]}, status=status.HTTP_401_UNAUTHORIZED)


MAX_DATA_BODY_LENGTH = 1024 * 1024  # 1 MB
MAX_DATA_RECORDS_COUNT = 10000


def check_company_license(trashbin):
    trashbin_license = CompanyTrashbinsLicense.objects.filter(company=trashbin.company).order_by('-end').first()
    license_is_valid = trashbin_license.is_valid if trashbin_license else False
    if not license_is_valid:
        logger.warning(f"Company {trashbin.company.id} has invalid or missing trashbins license")
        return Response(
            {'error': ['Company license is missing or invalid.']},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


class TrashbinDataView(APIView):
    permission_classes = (IsContainerAuthenticated,)

    def post(self, request):
        if len(request.body) > MAX_DATA_BODY_LENGTH:
            return Response({'error': ['Request body length cannot exceed 1 MB']},
                            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        try:
            data = request.body
            logger.debug('Got raw trashbin data: %s' % (repr(data)))
            json_data = json.loads(data)
        except Exception as e:
            logger.warning('%s (%s)' % (str(e), type(e)), exc_info=True)
            error_message = str(e) if settings.DEBUG else 'Body parsing failed'
            return Response({'error': [error_message]}, status=status.HTTP_400_BAD_REQUEST)

        mandatory_fields = ['version', 'serial', 'data']
        for field in mandatory_fields:
            if field not in json_data:
                return Response(
                    {'error': [f"Mandatory '{field}' field is missing"]}, status=status.HTTP_400_BAD_REQUEST)

        json_serial = str(json_data['serial'])
        if request.user.serial_number != json_serial:
            return Response(
                {'error': ['Providing packets for different user is forbidden.']},
                status=status.HTTP_403_FORBIDDEN,
            )

        satellite_data_records_count = \
            sum([len(satellite_msg['data']) for satellite_msg in json_data['bins']]) \
            if is_trashbin_data_with_satellites(json_data) else 0
        total_data_records_count = len(json_data['data']) + satellite_data_records_count
        if total_data_records_count > MAX_DATA_RECORDS_COUNT:
            return Response(
                {'error': ['Records count in a packet cannot exceed 10,000.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            trashbin = Container.objects.get(serial_number=json_serial)
        except Container.DoesNotExist:
            return Response(
                {'error': [f'Failed to find trashbin with serial "{json_serial}".']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        license_check_response = check_company_license(trashbin)
        if license_check_response:
            return license_check_response

        try:
            with transaction.atomic():
                trashbin_data = TrashbinData.objects.create(trashbin=request.user, data_json=json_data)
                parse_trashbin_data_packet(json_data, trashbin.id)
            notify_about_trashbin_message.delay(trashbin_data.id)
            generate_trashbin_status_notifications.delay(trashbin.id)
            return Response({}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception('%s (%s)' % (str(e), type(e)))
            error_message = str(e) if settings.DEBUG else 'Registering of a packet failed'
            return Response({'error': [error_message]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


valid_job_statuses = [s for p in [(t[0], t[0].lower(),) for t in TrashbinJobModel.JOB_STATUS_CHOICES] for s in p]


class TrashbinJobsView(APIView):
    permission_classes = (IsContainerAuthenticated,)

    def post(self, request):
        data = request.body
        logger.debug('Got jobs data: %s' % (repr(data)))

        license_check_response = check_company_license(request.user)
        if license_check_response:
            return license_check_response

        try:
            json_data = json.loads(data)
            if 'jobs' in json_data:
                for job in json_data['jobs']:
                    job_id, job_status, description = \
                        job['id'], job['status'], job['description'] if 'description' in job else ''
                    if job_status not in valid_job_statuses:
                        raise ValueError('Job status %s is not valid' % (job_status,))
                    TrashbinJobModel.objects.filter(trashbin=request.user, id=job_id) \
                        .update(status=job_status.upper(), execution_description=description, mtime=timezone.now())
        except Exception as e:
            logger.exception('%s (%s)' % (str(e), type(e)))
            error_message = str(e) if settings.DEBUG else 'unknown'
            return Response({'error': [error_message]}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_200_OK)

    def get(self, request):
        license_check_response = check_company_license(request.user)
        if license_check_response:
            return license_check_response

        try:
            ef_for_current_bin = EnergyEfficiencyForContainer.objects.get(container=request.user)
        except EnergyEfficiencyForContainer.DoesNotExist:
            logger.debug(f"Energy efficiency isn't set up for current bin with id {request.user.pk}")
            ef_for_current_bin = None
        if ef_for_current_bin:
            try:
                calculate_energy_efficiency(ef_for_current_bin.pk)
            except Exception:
                logger.exception(f'Failed to calculate EF for a bin with id {request.user.pk}')

        jobs_qs = TrashbinJobModel.objects.filter(trashbin=request.user, status='')
        result = [self._process_job(j) for j in jobs_qs]
        return Response({'jobs': result}, status=status.HTTP_200_OK)

    def _process_job(self, job):
        if job.type == TrashbinJobModel.DOWNLOAD_FIRMWARE_JOB_TYPE and 's3_key' in job.payload:
            signed_url = self._get_signed_url(settings.FIRMWARE_S3_BUCKET_NAME, job.payload['s3_key'])
            job.payload.pop('s3_key')
            job.payload['url'] = signed_url
        if job.type == TrashbinJobModel.CONNECT_TO_VPN_JOB_TYPE and 'config_s3_key' in job.payload:
            signed_url = self._get_signed_url(settings.VPN_CONFIGS_S3_BUCKET_NAME, job.payload['config_s3_key'])
            job.payload.pop('config_s3_key')
            job.payload['config_url'] = signed_url
        return {'id': job.id, 'type': job.type, 'payload': job.payload}

    def _get_signed_url(self, bucket_name, key):
        # Caching S3 client for the lifetime of the view
        if getattr(self, 's3_client', None) is None:
            self.s3_client = boto3.client(
                's3',
                config=Config(s3={'addressing_style': 'path'}, signature_version='s3v4'))
        s3_client = self.s3_client
        return s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': bucket_name,
                'Key': key
            },
            ExpiresIn=settings.S3_SIGNED_URL_EXPIRATION,
        )
