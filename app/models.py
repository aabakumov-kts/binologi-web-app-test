import datetime
import binascii
import os

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.text import capfirst
from django.utils.translation import ugettext_lazy as _
from django.db.models import Q, Count
from smart_selects.db_fields import GroupedForeignKey

from apps.core.models import Company, Country, City, Sectors, WasteType, validate_lang
from apps.sensors.models import Sensor


class Container(models.Model):
    serial_number = models.CharField(
        max_length=200,
        verbose_name=_('serial number'),
        unique=True,
    )
    phone_number = models.CharField(
        verbose_name=_('phone number'),
        max_length=40,
    )
    container_type = models.ForeignKey(
        to='app.ContainerType',
        verbose_name=_('container type'),
        on_delete=models.PROTECT,
    )
    is_master = models.BooleanField(
        verbose_name=_('is master'),
        default=True,
    )
    company = models.ForeignKey(
        Company,
        verbose_name=_('company'),
        on_delete=models.CASCADE,
    )
    country = models.ForeignKey(
        verbose_name=_('country'),
        to=Country,
        on_delete=models.SET_NULL,
        null=True,
    )
    city = models.ForeignKey(
        verbose_name=_('city'),
        to=City,
        on_delete=models.SET_NULL,
        null=True,
    )
    address = models.CharField(
        verbose_name=_('address'),
        max_length=256,
        null=True,
    )
    sector = GroupedForeignKey(Sectors, 'company', verbose_name=_('sector'), on_delete=models.PROTECT)
    waste_type = models.ForeignKey(WasteType, verbose_name=_('waste type'), on_delete=models.PROTECT)
    location = models.PointField(
        verbose_name=_('location'),
        default='SRID=4326;POINT (37.6198482461064785 55.7535037511883829)',
    )
    fullness = models.IntegerField(
        verbose_name=_('fullness'),
        help_text=_('in percents (%)'),
        null=True,
        default=0,
    )
    battery = models.IntegerField(
        verbose_name=_('battery charge'),
        help_text=_('in percents (%)'),
        default=0,
    )
    temperature = models.IntegerField(
        verbose_name=_('temperature'),
        help_text=_('in celsius (C)'),
        default=0,
    )
    pressure = models.IntegerField(
        verbose_name=_('pressure'),
        help_text=_('in milimeters (mm)'),
        default=0,
    )
    traffic = models.IntegerField(default=0)
    humidity = models.IntegerField(
        verbose_name=_('humidity'),
        help_text=_('in percents (%)'),
        default=0,
    )
    air_quality = models.IntegerField(
        verbose_name=_('air_quality'),
        default=0,
    )
    max_volume = models.IntegerField(default=settings.DEFAULT_CONTAINER_VOLUME)
    ctime = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('create time'),
    )
    data_mtime = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('update time'),
    )
    autogenerate_data = models.BooleanField(default=False)
    master_bin = models.ForeignKey('self', models.SET_NULL, blank=True, null=True, related_name='satellites')
    password = models.CharField(_('password'), max_length=128)

    def __str__(self):
        return self.serial_number

    def latitude(self):
        return self.location.y

    def longitude(self):
        return self.location.x

    @property
    def current_fullness_volume(self):
        return (self.fullness / 100.0) * self.max_volume

    def save(self, *args, **kwargs):
        if self.is_master:
            self.satellites.update(location=self.location)
        elif self.master_bin:
            self.location = self.master_bin.location
        super().save(*args, **kwargs)


class ContainerType(models.Model):
    title = models.CharField(
        max_length=50,
        verbose_name=_('title')
    )
    description = models.CharField(max_length=150, null=True, blank=True)

    def __str__(self):
        return self.title


class Equipment(models.Model):
    title = models.CharField(
        max_length=32,
        verbose_name=_('title'),
    )

    def __str__(self):
        return self.title


class ErrorType(models.Model):
    equipment = models.ForeignKey(Equipment, null=True, on_delete=models.PROTECT)
    code = models.CharField(max_length=8)
    title = models.CharField(max_length=256)
    description = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ('code',)

    def __str__(self):
        return self.title


class Error(models.Model):
    container = models.ForeignKey(
        to=Container,
        verbose_name=_('container'),
        related_name='errors',
        on_delete=models.CASCADE,
    )
    error_type = models.ForeignKey(
        to=ErrorType,
        verbose_name=_('error type'),
        on_delete=models.CASCADE,
    )
    ctime = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('error create time'),
    )
    actual = models.IntegerField(
        default=1,
        verbose_name=_('actual data'),
    )

    class Meta:
        ordering = ('ctime',)

    def __str__(self):
        return '%s %s %s' % (self.container, self.error_type, self.ctime)

    @property
    def container_company_name(self):
        return self.container.company.name

    @property
    def container_country_name(self):
        return self.container.country.name

    @property
    def container_city_title(self):
        return self.container.city.title

    @property
    def container_address(self):
        return self.container.address

    @property
    def container_waste_type_title(self):
        return self.container.waste_type.title

    @property
    def container_serial_number(self):
        return self.container.serial_number

    @property
    def container_sector_name(self):
        return self.container.sector.name

    @property
    def error_type_title(self):
        return self.error_type.title


class Routes(models.Model):
    start_time = models.DateTimeField(default=timezone.now)
    finish_time = models.DateTimeField(null=True, default=None)
    company = models.ForeignKey(
        Company,
        verbose_name=_('company'),
        blank=True,
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return str(self.id)

    @staticmethod
    def close_parent_routes_if_possible(user_id):
        routes_drivers_filter = Q(routesdrivers__finish_time__isnull=True) & ~Q(routesdrivers__driver_id=user_id)
        Routes.objects.filter(finish_time__isnull=True, parent_route__user_id=user_id).\
            annotate(unfinished_other_drivers=Count('routesdrivers__pk', filter=routes_drivers_filter)).\
            filter(unfinished_other_drivers=0).\
            update(finish_time=datetime.datetime.now())


ROUTE_STATUS_STARTED_BY_USER = 0
ROUTE_STATUS_MOVING_HOME = 1
ROUTE_STATUS_COMPLETE_BY_USER = 2
ROUTE_STATUS_ABORTED_BY_OPERATOR = 3
ROUTE_STATUS_ABORTED_BY_USER = 4


ROUTE_STATUSES = {
    None: _('new'),
    ROUTE_STATUS_STARTED_BY_USER: _('started'),
    ROUTE_STATUS_MOVING_HOME: _('moving home'),
    ROUTE_STATUS_COMPLETE_BY_USER: _('completed'),
    ROUTE_STATUS_ABORTED_BY_OPERATOR: _('aborted by operator'),
    ROUTE_STATUS_ABORTED_BY_USER: _('aborted by driver'),
}


FINISHED_ROUTE_STATUSES = [
    ROUTE_STATUS_COMPLETE_BY_USER, ROUTE_STATUS_ABORTED_BY_OPERATOR, ROUTE_STATUS_ABORTED_BY_USER,
]


class Route(models.Model):
    user = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        verbose_name=_('user'),
        on_delete=models.CASCADE,
    )
    route_json = JSONField(
        verbose_name=_('route'),
    )
    ctime = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('created at'),
    )
    parent_route = models.ForeignKey(Routes, related_name='parent_route', on_delete=models.CASCADE)
    status = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ('-ctime',)

    def __str__(self):
        return "{} #{}".format(_('route').capitalize(), self.pk)

    @property
    def route_points_count(self):
        return len(self.routes_route.all())

    @property
    def humanized_status(self):
        return (ROUTE_STATUSES[self.status] if self.status in ROUTE_STATUSES else _('unknown')).capitalize()

    @property
    def route_driver(self):
        # This will return None if the set is empty
        return self.routesdrivers_set.first()

    @property
    def is_finished(self):
        return self.status in FINISHED_ROUTE_STATUSES

    @property
    def is_new(self):
        return self.status is None


ROUTE_POINT_STATUS_NOT_COLLECTED = 0
ROUTE_POINT_STATUS_COLLECTED = 1
ROUTE_POINT_STATUS_ERROR = 2


ROUTE_POINT_STATUSES = {
    ROUTE_POINT_STATUS_NOT_COLLECTED: _('not collected'),
    ROUTE_POINT_STATUS_COLLECTED: _('collected'),
    ROUTE_POINT_STATUS_ERROR: _('collection issue'),
    3: _('aborted by operator'),
    4: _('aborted by driver'),
}


class RoutePoints(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    container = models.ForeignKey(
        to=Container,
        verbose_name=_('container'),
        related_name='routepoints',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    sensor = models.ForeignKey(
        to=Sensor,
        verbose_name=_('sensor'),
        related_name='routepoints',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    ctime = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('created at'),
    )
    mtime = models.DateTimeField(default=None, null=True)
    parent_route = models.ForeignKey(Routes, related_name='routes_parent_route', on_delete=models.CASCADE)
    route = models.ForeignKey(Route, related_name='routes_route', on_delete=models.CASCADE)

    comment = models.CharField(max_length=500)
    status = models.IntegerField(default=0)
    fullness = models.IntegerField(default=None, null=True)
    volume = models.IntegerField(default=settings.DEFAULT_CONTAINER_VOLUME, null=True)

    class Meta:
        ordering = ('-ctime',)
        constraints = [
            models.CheckConstraint(
                check=Q(container__isnull=False) | Q(sensor__isnull=False),
                name='either_container_or_sensor_specified',
            )
        ]

    def __str__(self):
        serial_candidates_gen = (serial for serial in [
            self.container.serial_number if self.container else None,
            self.sensor.serial_number if self.sensor else None,
            'N/A',
        ] if serial is not None)
        return "{} - {} #{}".format(next(serial_candidates_gen), _('route').capitalize(), self.route.pk)

    @property
    def humanized_status(self):
        return (ROUTE_POINT_STATUSES[self.status] if self.status in ROUTE_POINT_STATUSES else _('unknown')).capitalize()

    @staticmethod
    def close_route_points(driver_id, close_status, route_id=None):
        qs = RoutePoints.objects.filter(user_id=driver_id, mtime__isnull=True)
        if route_id is not None:
            qs = qs.filter(route_id=route_id)
        qs.update(mtime=datetime.datetime.now(), status=close_status)

    def clean(self):
        super().clean()
        if self.container is None and self.sensor is None:
            raise ValidationError('Either container or sensor should be specified')


class RoutesDrivers(models.Model):
    base_route = models.ForeignKey(Routes, on_delete=models.CASCADE)
    route = models.ForeignKey(Route, default=None, on_delete=models.CASCADE)
    driver = models.ForeignKey(
        to=User,
        default=None,
        verbose_name=_('driver'),
        related_name='driver',
        on_delete=models.CASCADE,
    )
    is_active = models.NullBooleanField(default=True)
    start_time = models.DateTimeField(null=True, default=None)
    finish_time = models.DateTimeField(null=True, default=None)
    track = models.IntegerField(default=0, null=True)
    track_full = models.IntegerField(default=0, null=True)
    company = models.ForeignKey(
        Company,
        verbose_name=_('company'),
        blank=True,
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return str(self.id)

    @staticmethod
    def finish_routes(driver_id, route_id=None):
        qs = RoutesDrivers.objects.filter(driver_id=driver_id, finish_time__isnull=True)
        if route_id is not None:
            qs = qs.filter(route_id=route_id)
        qs.update(finish_time=datetime.datetime.now(), is_active=False)


class FullnessValues(models.Model):
    container = models.ForeignKey(
        to=Container,
        verbose_name=_('container'),
        related_name='fullness_table',
        on_delete=models.CASCADE,
    )
    ctime = models.DateTimeField(default=timezone.now)
    fullness_value = models.IntegerField(default=0)
    location = models.PointField(
        verbose_name=_('location'),
        default='SRID=4326;POINT (37.6198482461064785 55.7535037511883829)',
    )
    actual = models.IntegerField(
        default=1,
        verbose_name=_('actual data'),
    )

    class Meta:
        db_table = 'app_fullness'


class FullnessStats(models.Model):
    container = models.ForeignKey(
        to=Container,
        verbose_name=_('container'),
        related_name='fullness_stats_table',
        on_delete=models.CASCADE,
    )
    start_time = models.DateTimeField(default=timezone.now)
    collection_time = models.DateTimeField(null=True, blank=True)
    fullness_before_press = models.IntegerField(default=0)
    fullness_after_press = models.IntegerField(default=0)
    actual = models.IntegerField(
        default=1,
        verbose_name=_('actual data'),
    )

    class Meta:
        db_table = 'app_container_stats'


class Collection(models.Model):
    container = models.ForeignKey(
        to=Container,
        verbose_name=_('container'),
        on_delete=models.CASCADE,
    )
    ctime = models.DateTimeField(default=timezone.now)
    fullness = models.IntegerField(default=0)
    fullness_before_press = models.IntegerField(default=0, null=True, blank=True)
    location = models.PointField(
        verbose_name=_('location'),
        default='SRID=4326;POINT (37.6198482461064785 55.7535037511883829)',
    )
    driver = models.ForeignKey(
        to=User,
        verbose_name=_('driver'),
        on_delete=models.CASCADE,
        null=True,
    )
    route_point = models.ForeignKey(
        to=RoutePoints,
        null=True,
        on_delete=models.CASCADE,
    )


class Battery_Level(models.Model):
    container = models.ForeignKey(
        to=Container,
        verbose_name=_('container'),
        on_delete=models.CASCADE,
    )
    ctime = models.DateTimeField(default=timezone.now)
    level = models.IntegerField(default=0)
    volts = models.FloatField(default=0)
    actual = models.IntegerField(
        default=1,
        verbose_name=_('actual data'),
    )


class Traffic(models.Model):
    container = models.ForeignKey(
        to=Container,
        verbose_name=_('container'),
        related_name='traffic_table',
        on_delete=models.CASCADE,
    )
    ctime = models.DateTimeField(default=timezone.now)
    traffic_value = models.IntegerField(default=0)
    location = models.PointField(
        verbose_name=_('location'),
        default='SRID=4326;POINT (37.6198482461064785 55.7535037511883829)',
    )
    actual = models.IntegerField(
        default=1,
        verbose_name=_('actual data'),
    )


class Pressure(models.Model):
    container = models.ForeignKey(
        to=Container,
        verbose_name=_('container'),
        related_name='pressure_table',
        on_delete=models.CASCADE,
    )
    ctime = models.DateTimeField(default=timezone.now)
    pressure_value = models.IntegerField(default=0)
    location = models.PointField(
        verbose_name=_('location'),
        default='SRID=4326;POINT (37.6198482461064785 55.7535037511883829)',
    )
    actual = models.IntegerField(
        default=1,
        verbose_name=_('actual data'),
    )


class Temperature(models.Model):
    container = models.ForeignKey(
        to=Container,
        verbose_name=_('container'),
        related_name='temperature_table',
        on_delete=models.CASCADE,
    )
    ctime = models.DateTimeField(default=timezone.now)
    temperature_value = models.IntegerField(default=0)
    location = models.PointField(
        verbose_name=_('location'),
        default='SRID=4326;POINT (37.6198482461064785 55.7535037511883829)',
    )
    actual = models.IntegerField(
        default=1,
        verbose_name=_('actual data'),
    )

    class Meta:
        ordering = ('ctime',)

    def __str__(self):
        return '%s %s %s' % (self.container, self.temperature_value, self.ctime)


class SimBalance(models.Model):
    container = models.ForeignKey(
        to=Container,
        verbose_name=_('container'),
        related_name='sim_balance_table',
        on_delete=models.CASCADE,
    )
    ctime = models.DateTimeField(default=timezone.now)
    balance = models.IntegerField(default=0)
    actual = models.IntegerField(
        default=1,
        verbose_name=_('actual data'),
    )

    class Meta:
        ordering = ('ctime',)

    def __str__(self):
        return '%s %s %s' % (self.container, self.balance, self.ctime)


class Location(models.Model):
    container = models.ForeignKey(
        to=Container,
        verbose_name=_('container'),
        related_name='location_table',
        on_delete=models.CASCADE,
    )
    ctime = models.DateTimeField(default=timezone.now)
    location = models.PointField(
        verbose_name=_('location'),
        default='SRID=4326;POINT (37.6198482461064785 55.7535037511883829)',
    )
    actual = models.IntegerField(
        default=1,
        verbose_name=_('actual data'),
    )

    class Meta:
        ordering = ('ctime',)

    def __str__(self):
        return '%s %s %s' % (self.container, self.location, self.ctime)


class Humidity(models.Model):
    container = models.ForeignKey(
        to=Container,
        verbose_name=_('container'),
        related_name='humidity_table',
        on_delete=models.CASCADE,
    )
    ctime = models.DateTimeField(default=timezone.now)
    humidity_value = models.IntegerField(default=0)
    location = models.PointField(
        verbose_name=_('location'),
        default='SRID=4326;POINT (37.6198482461064785 55.7535037511883829)',
    )
    actual = models.IntegerField(
        default=1,
        verbose_name=_('actual data'),
    )


class AirQuality(models.Model):
    container = models.ForeignKey(
        to=Container,
        verbose_name=_('container'),
        related_name='air_quality_table',
        on_delete=models.CASCADE,
    )
    ctime = models.DateTimeField(default=timezone.now)
    air_quality_value = models.IntegerField(default=0)
    location = models.PointField(
        verbose_name=_('location'),
        default='SRID=4326;POINT (37.6198482461064785 55.7535037511883829)',
    )
    actual = models.IntegerField(
        default=1,
        verbose_name=_('actual data'),
    )


class EnergyEfficiencyProfile(models.Model):
    """Energy efficiency profile is a set of settings for a particular case: device and/or environment conditions.

    Less obvious attributes description as follows:
        battery_min_voltage                Battery voltage which corresponds to zero capacity left, V.
        battery_max_voltage                Battery voltage which corresponds to maximum capacity left, V.
        battery_capacity                   Battery maximum capacity, A * h.
        battery_nominal_voltage            Battery nominal voltage used to convert capacity to energy i.e. V * A * h.
        discharge_per_standby_day          Battery discharge per standby day, W * h.
        battery_charge_change_window_days  Time window in days which begin & end used to find out capacity difference.
        discharge_per_press                Battery discharge per pressing, W * h.
    """
    name = models.CharField(max_length=128, verbose_name=_('title'))

    sleep_period_start = models.TimeField(default=datetime.time(19, 00))
    sleep_period_stop = models.TimeField(default=datetime.time(8, 00))

    min_temperature_for_charging = models.SmallIntegerField(default=-10)

    battery_min_voltage = models.FloatField(validators=[MinValueValidator(0)], default=0)
    battery_max_voltage = models.FloatField(validators=[MinValueValidator(0)], default=0)
    battery_capacity = models.FloatField(validators=[MinValueValidator(0)], default=0)
    battery_nominal_voltage = models.FloatField(validators=[MinValueValidator(0)], default=0)

    standby_days_stop = models.PositiveSmallIntegerField(validators=[MinValueValidator(0)], default=10)
    discharge_per_standby_day = models.FloatField(validators=[MinValueValidator(0)], default=0)

    battery_charge_change_window_days = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)], default=5)
    discharge_per_press = models.FloatField(validators=[MinValueValidator(0)], default=0)

    def __str__(self):
        return 'EEP {} - {}'.format(self.id, self.name)


class EnergyEfficiencyForContainer(models.Model):
    container = models.OneToOneField(
        to=Container,
        verbose_name=_('container'),
        related_name='energy_efficiency',
        on_delete=models.CASCADE,
    )
    profile = models.ForeignKey(EnergyEfficiencyProfile, related_name='containers', on_delete=models.CASCADE)
    ef_last_log = models.TextField(null=True, blank=True)
    turn_on = models.BooleanField(default=True)

    class Meta:
        unique_together = ['container', 'profile']

    def __str__(self):
        return 'EEFC {}: {} for {}'.format(self.id, self.profile, self.container)


class DriverUnavailabilityPeriod(models.Model):
    driver = models.ForeignKey(to=settings.AUTH_USER_MODEL, verbose_name=_('driver'), on_delete=models.CASCADE)
    begin = models.DateField(verbose_name=_('period begin'))
    end = models.DateField(verbose_name=_('period end'))
    reason = models.CharField(verbose_name=_('reason'), max_length=256)

    def __str__(self):
        return '{} - {} / {} - {}'.format(
            self.driver.username, self.begin.isoformat(), self.end.isoformat(), self.reason)

    def clean(self):
        if self.begin > self.end:
            raise ValidationError(_('Begin of the period should be earlier than its end.'))

    @staticmethod
    def any_period_active_now(driver):
        now = datetime.date.today()
        return len(DriverUnavailabilityPeriod.objects.filter(driver=driver, begin__lte=now, end__gte=now)) > 0


class MobileAppTranslation(models.Model):
    string_name = models.CharField(max_length=100, default='', null=True, blank=True)
    string_text = models.CharField(max_length=500, default='', null=True, blank=True)
    lang = models.CharField(max_length=20, default='', null=True, blank=True)


class MobileAppUserLanguage(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_('user'))
    lang = models.CharField(max_length=20, default='', null=True, blank=True)


class ContainerAuthToken(models.Model):
    key = models.CharField("Key", max_length=40, primary_key=True)
    container = models.OneToOneField(
        Container, related_name='auth_token', on_delete=models.CASCADE, verbose_name=_("container"))
    created = models.DateTimeField(capfirst(_("created at")), auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = binascii.hexlify(os.urandom(20)).decode()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.key


class CreateDemoSandboxRequest(models.Model):
    STATUS_NEW = 0
    STATUS_SUCCESS = 1
    STATUS_FAILED = 2
    STATUS_IN_PROGRESS = 3
    STATUSES = (
        (STATUS_NEW, 'New'),
        (STATUS_SUCCESS, 'Succeed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_IN_PROGRESS, 'In progress'),
    )
    # Status fields
    status = models.IntegerField(default=STATUS_NEW, choices=STATUSES)
    ctime = models.DateTimeField(default=timezone.now, verbose_name=_('created at'))
    mtime = models.DateTimeField(blank=True, null=True)
    progress = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    # Request fields
    template_company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True)
    company_name = models.CharField(max_length=128)
    username_prefix = models.CharField(max_length=80, validators=[UnicodeUsernameValidator()])
    lang = models.CharField(max_length=20, default='en', validators=[validate_lang])
    # Result fields
    admin_username = models.CharField(_('username'), max_length=150, blank=True, null=True)
    admin_password = models.CharField(_('password'), max_length=128, blank=True, null=True)


class TrashbinData(models.Model):
    trashbin = models.ForeignKey(Container, on_delete=models.CASCADE)
    data_json = JSONField()
    ctime = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ('-ctime',)

    def __str__(self):
        return "%s" % self.pk


class TrashbinJobModel(models.Model):
    PRESS_CONTROL_JOB_TYPE = 'PRESS_CONTROL'
    DOWNLOAD_FIRMWARE_JOB_TYPE = 'DOWNLOAD_FIRMWARE'
    DOWNLOAD_AD_JOB_TYPE = 'DOWNLOAD_AD'
    CONNECT_TO_VPN_JOB_TYPE = 'CONNECT_TO_VPN'
    UPDATE_CONFIG_JOB_TYPE = 'UPDATE_CONFIG'

    JOB_TYPE_CHOICES = (
        (PRESS_CONTROL_JOB_TYPE, 'Press Control'),
        (DOWNLOAD_FIRMWARE_JOB_TYPE, 'Download Firmware'),
        (DOWNLOAD_AD_JOB_TYPE, 'Download Advertising'),
        (CONNECT_TO_VPN_JOB_TYPE, 'Connect to VPN'),
        (UPDATE_CONFIG_JOB_TYPE, 'Update Configuration'),
    )

    SUCCESS_STATUS = 'SUCCESS'
    FAILURE_STATUS = 'FAILURE'

    JOB_STATUS_CHOICES = (
        (SUCCESS_STATUS, 'Successful job'),
        (FAILURE_STATUS, 'Failed job'),
    )

    trashbin = models.ForeignKey(Container, on_delete=models.CASCADE)
    ctime = models.DateTimeField(default=timezone.now)
    mtime = models.DateTimeField(default=None, null=True, blank=True)
    type = models.CharField(
        max_length=32,
        choices=JOB_TYPE_CHOICES,
        blank=True,
    )
    payload = JSONField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=JOB_STATUS_CHOICES,
        blank=True,
    )
    execution_description = models.TextField(blank=True)

    class Meta:
        ordering = ('-ctime',)
        db_table = "api_jobs"

    def __str__(self):
        return "%s" % self.pk


class SlackEnabledTrashbin(models.Model):
    serial_number = models.CharField(max_length=200, unique=True)


class DemoSandboxTranslation(models.Model):
    CONTAINER_OBJECT_TYPE = 'CONTAINER'
    SECTOR_OBJECT_TYPE = 'SECTOR'
    SENSOR_OBJECT_TYPE = 'SENSOR'

    OBJECT_TYPE_CHOICES = (
        (CONTAINER_OBJECT_TYPE, 'Container'),
        (SECTOR_OBJECT_TYPE, 'Sector'),
        (SENSOR_OBJECT_TYPE, 'Sensor'),
    )

    object_type = models.CharField(max_length=32, choices=OBJECT_TYPE_CHOICES)
    object_id = models.CharField(max_length=200)
    lang = models.CharField(max_length=20)
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=500)

    class Meta:
        unique_together = ['object_type', 'object_id', 'lang', 'key']
