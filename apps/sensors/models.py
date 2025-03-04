import logging
import re
import uuid

from datetime import date, timedelta
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.db import connection, transaction
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from sentry_sdk import capture_message
from smart_selects.db_fields import GroupedForeignKey

from apps.core.helpers import get_unknown_city_country, format_random_location
from apps.core.models import Country, City, Company, Sectors, WasteType


logger = logging.getLogger('app_main')


class SensorSettingsProfile(models.Model):
    name = models.CharField(max_length=128, blank=True)

    first_turn_on_flag = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1)], help_text='on_init_modem')
    enabled_flag = models.IntegerField(
        default=1, validators=[MinValueValidator(0), MaxValueValidator(1)], help_text='onFlag')

    connection_schedule_start = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(24)], help_text='on_time')
    connection_schedule_stop = models.IntegerField(
        default=24, validators=[MinValueValidator(0), MaxValueValidator(24)], help_text='off_time')
    measurement_interval = models.IntegerField(
        default=30, validators=[MinValueValidator(5), MaxValueValidator(1440)], help_text='intConn')
    gsm_timeout = models.IntegerField(
        default=30, validators=[MinValueValidator(20), MaxValueValidator(600)], help_text='tGsm')
    gps_timeout = models.IntegerField(
        default=180, validators=[MinValueValidator(0), MaxValueValidator(300)], help_text='tGps')
    gps_in_every_connection = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1)], help_text='fGps')
    message_send_retries = models.IntegerField(
        default=20, validators=[MinValueValidator(1), MaxValueValidator(300)], help_text='retry')

    fire_min_temp = models.IntegerField(
        default=70, validators=[MinValueValidator(50), MaxValueValidator(80)], help_text='tempFire')
    fire_temp_gradient = models.IntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(20)], help_text='gradient_temperature')

    orientation_threshold = models.IntegerField(
        default=10, validators=[MinValueValidator(0), MaxValueValidator(125)], help_text='orientTh')
    current_orientation = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(6)], help_text='orient')
    accelerometer_sensitivity = models.IntegerField(
        default=50, validators=[MinValueValidator(20), MaxValueValidator(125)], help_text='acelTh')
    accelerometer_delay = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(300)], help_text='a111Delay')

    access_point_name = models.CharField(default=r'"IP","iot"', max_length=64, help_text='nbiot')
    server_host = models.CharField(max_length=64, help_text='serverHost')
    server_port = models.IntegerField(
        default=1883, validators=[MinValueValidator(0), MaxValueValidator(65535)], help_text='serverPort')
    login = models.CharField(max_length=32, help_text='serverLogin')
    password = models.CharField(max_length=32, help_text='serverPassword')
    updates_server_url = models.CharField(default='http://downloads.binology.com', max_length=64, help_text='upSer')
    updates_server_path = models.CharField(default='/firmware-updates/bfnew.bin', max_length=64, help_text='upPath')

    fill_alert_interval = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1440)], help_text='fillWakeup')
    fill_alert_range = models.IntegerField(
        default=200, validators=[MinValueValidator(20), MaxValueValidator(3500)], help_text='fillAlert')
    fill_alert_count = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(10)], help_text='fillCount')

    measurement_results_number = models.IntegerField(
        default=1, validators=[MinValueValidator(0), MaxValueValidator(10)], help_text='result_r_length')

    close_measurement_distance_begin = models.FloatField(
        default=0.06, validators=[MinValueValidator(-0.11), MaxValueValidator(0.11)], help_text='close_r_start')
    close_measurement_distance_length = models.FloatField(
        default=0.46, validators=[MinValueValidator(0), MaxValueValidator(0.46)], help_text='close_r_len')
    close_measurement_gain = models.FloatField(
        default=0.5, validators=[MinValueValidator(0), MaxValueValidator(1)], help_text='close_r_gain')
    close_measurement_approximation_profile = models.IntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(5)], help_text='close_r_s_profile')
    close_measurement_noise_threshold = models.FloatField(
        default=0.25, validators=[MinValueValidator(0.01), MaxValueValidator(0.99)], help_text='close_r_threashold')
    close_measurement_peaks_merge_distance = models.FloatField(
        default=0.005, validators=[MinValueValidator(0.001), MaxValueValidator(0.46)],
        help_text='close_r_peak_merge_lim')
    close_measurement_peaks_sorting_method = models.IntegerField(
        default=1, validators=[MinValueValidator(0), MaxValueValidator(3)], help_text='close_r_peak_sorting')
    close_measurement_downsampling = models.IntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(4)], help_text='close_r_downsampling')
    close_measurement_signal_samples_number = models.IntegerField(
        default=10, validators=[MinValueValidator(5), MaxValueValidator(50)], help_text='close_r_sweep_avr')
    close_measurement_noise_samples_number = models.IntegerField(
        default=30, validators=[MinValueValidator(10), MaxValueValidator(100)], help_text='close_r_sweep_bkgd')
    close_measurement_on_flag = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1)], help_text='close_r_meas_on')

    mid_measurement_distance_begin = models.FloatField(
        default=0.2, validators=[MinValueValidator(0.05), MaxValueValidator(2)], help_text='mid_r_start')
    mid_measurement_distance_length = models.FloatField(
        default=1.25, validators=[MinValueValidator(0.1), MaxValueValidator(1.25)], help_text='mid_r_len')
    mid_measurement_gain = models.FloatField(
        default=0.7, validators=[MinValueValidator(0), MaxValueValidator(1)], help_text='mid_r_gain')
    mid_measurement_approximation_profile = models.IntegerField(
        default=2, validators=[MinValueValidator(2), MaxValueValidator(5)], help_text='mid_r_s_profile')
    mid_measurement_noise_threshold = models.FloatField(
        default=0.25, validators=[MinValueValidator(0.01), MaxValueValidator(0.99)], help_text='mid_r_threashold')
    mid_measurement_peaks_merge_distance = models.FloatField(
        default=0.01, validators=[MinValueValidator(0.001), MaxValueValidator(0.5)], help_text='mid_r_peak_merge_lim')
    mid_measurement_peaks_sorting_method = models.IntegerField(
        default=1, validators=[MinValueValidator(0), MaxValueValidator(3)], help_text='mid_r_peak_sorting')
    mid_measurement_downsampling = models.IntegerField(
        default=2, validators=[MinValueValidator(2), MaxValueValidator(4)], help_text='mid_r_downsampling')
    mid_measurement_signal_samples_number = models.IntegerField(
        default=10, validators=[MinValueValidator(5), MaxValueValidator(50)], help_text='mid_r_sweep_avr')
    mid_measurement_noise_samples_number = models.IntegerField(
        default=30, validators=[MinValueValidator(10), MaxValueValidator(100)], help_text='mid_r_sweep_bkgd')
    mid_measurement_on_flag = models.IntegerField(
        default=1, validators=[MinValueValidator(0), MaxValueValidator(1)], help_text='mid_r_meas_on')

    far_measurement_distance_begin = models.FloatField(
        default=0.2, validators=[MinValueValidator(0.05), MaxValueValidator(4.5)], help_text='far_r_start')
    far_measurement_distance_length = models.FloatField(
        default=2.5, validators=[MinValueValidator(0.1), MaxValueValidator(2.5)], help_text='far_r_len')
    far_measurement_gain = models.FloatField(
        default=0.7, validators=[MinValueValidator(0), MaxValueValidator(1)], help_text='far_r_gain')
    far_measurement_approximation_profile = models.IntegerField(
        default=4, validators=[MinValueValidator(2), MaxValueValidator(5)], help_text='far_r_s_profile')
    far_measurement_noise_threshold = models.FloatField(
        default=0.25, validators=[MinValueValidator(0.01), MaxValueValidator(0.99)], help_text='far_r_threashold')
    far_measurement_peaks_merge_distance = models.FloatField(
        default=0.05, validators=[MinValueValidator(0.001), MaxValueValidator(0.5)], help_text='far_r_peak_merge_lim')
    far_measurement_peaks_sorting_method = models.IntegerField(
        default=1, validators=[MinValueValidator(0), MaxValueValidator(3)], help_text='far_r_peak_sorting')
    far_measurement_downsampling = models.IntegerField(
        default=2, validators=[MinValueValidator(2), MaxValueValidator(4)], help_text='far_r_downsampling')
    far_measurement_signal_samples_number = models.IntegerField(
        default=10, validators=[MinValueValidator(5), MaxValueValidator(50)], help_text='far_r_sweep_avr')
    far_measurement_noise_samples_number = models.IntegerField(
        default=30, validators=[MinValueValidator(10), MaxValueValidator(100)], help_text='far_r_sweep_bkgd')
    far_measurement_on_flag = models.IntegerField(
        default=1, validators=[MinValueValidator(0), MaxValueValidator(1)], help_text='far_r_meas_on')

    def clean(self):
        connection_interval_hours = self.connection_schedule_stop - self.connection_schedule_start + (
            24 if self.connection_schedule_stop < self.connection_schedule_start else 0)
        if connection_interval_hours <= 0:
            raise ValidationError('Actual connection interval is zero or negative.')
        if self.measurement_interval > connection_interval_hours * 60:
            raise ValidationError("Measurement interval configured is too high - it won't happen even once a day.")
        downsampling_values = [
            self.close_measurement_downsampling, self.mid_measurement_downsampling, self.far_measurement_downsampling]
        if any(val == 3 for val in downsampling_values):
            raise ValidationError("Downsampling values can't be equal to 3")

    def __str__(self):
        return f"{self.pk} - {self.name or 'No name'}"


class ContainerType(models.Model):
    volume = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(100)])  # m3
    description = models.CharField(max_length=200, blank=True)
    horizontal_mount_max_range = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(10)], null=True)  # m
    vertical_mount_max_range = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(10)], null=True)  # m
    diagonal_mount_max_range = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(10)], null=True)  # m
    vertical_mount_min_range = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(10)], blank=True, null=True)  # m
    moisture_threshold = models.IntegerField(default=20)  # mm

    def __str__(self):
        return self.description

    def get_max_range(self, mount_type):
        mount_types_to_sizes = {
            Sensor.HORIZONTAL_MOUNT_TYPE: self.horizontal_mount_max_range,
            Sensor.VERTICAL_MOUNT_TYPE: self.vertical_mount_max_range,
            Sensor.DIAGONAL_MOUNT_TYPE: self.diagonal_mount_max_range,
        }
        if mount_type in mount_types_to_sizes:
            return mount_types_to_sizes[mount_type]
        raise ValueError(f'Mount type {mount_type} is not supported')

    def get_min_range(self, mount_type):
        return self.vertical_mount_min_range if mount_type == Sensor.VERTICAL_MOUNT_TYPE else None


NUMBERS_ONLY_REGEX = re.compile(r'\d+')
NUMBERS_ONLY_HELP_TEXT = 'Only numbers allowed'


class Sensor(models.Model):
    HORIZONTAL_MOUNT_TYPE = 'HORIZONTAL'
    VERTICAL_MOUNT_TYPE = 'VERTICAL'
    DIAGONAL_MOUNT_TYPE = 'DIAGONAL'

    MOUNT_TYPES = (
        (HORIZONTAL_MOUNT_TYPE, 'Horizontal'),
        (VERTICAL_MOUNT_TYPE, 'Vertical'),
        (DIAGONAL_MOUNT_TYPE, 'Diagonal'),
    )

    ctime = models.DateTimeField(default=timezone.now, verbose_name=_('create time'))
    mtime = models.DateTimeField(default=timezone.now, verbose_name=_('update time'))

    company = models.ForeignKey(Company, verbose_name=_('company'), on_delete=models.CASCADE)

    location = models.PointField(
        verbose_name=_('location'), default='SRID=4326;POINT (37.6198482461064785 55.7535037511883829)')
    country = models.ForeignKey(Country, verbose_name=_('country'), on_delete=models.SET_NULL, null=True)
    city = models.ForeignKey(City, verbose_name=_('city'), on_delete=models.SET_NULL, null=True)
    address = models.CharField(verbose_name=_('address'), max_length=256, null=True)
    sector = GroupedForeignKey(Sectors, 'company', verbose_name=_('sector'), on_delete=models.PROTECT)
    waste_type = models.ForeignKey(WasteType, verbose_name=_('waste type'), on_delete=models.PROTECT)

    serial_number = models.CharField(max_length=200, verbose_name=_('serial number'), unique=True)
    phone_number = models.CharField(max_length=15, verbose_name=_('phone number'), blank=True,
                                    validators=[RegexValidator(NUMBERS_ONLY_REGEX)], help_text=NUMBERS_ONLY_HELP_TEXT)
    hardware_identity = models.CharField(max_length=50, unique=True)

    fullness = models.IntegerField(default=0, help_text=_('in percents (%)'), verbose_name=_('fullness'))
    battery = models.IntegerField(default=0, help_text=_('in percents (%)'), verbose_name=_('battery charge'))
    temperature = models.IntegerField(default=0, help_text=_('in celsius (C)'), verbose_name=_('temperature'))

    settings_profile = models.ForeignKey(
        to=SensorSettingsProfile, related_name='profile_sensors', on_delete=models.PROTECT)
    container_type = models.ForeignKey(ContainerType, related_name='container_type_sensors',
                                       verbose_name=_('container type'), on_delete=models.PROTECT)
    autogenerate_data = models.BooleanField(default=False)
    mount_type = models.CharField(max_length=16, choices=MOUNT_TYPES, default=HORIZONTAL_MOUNT_TYPE)
    disabled = models.BooleanField(default=False, verbose_name=_('disabled'))

    sim_number = models.CharField(max_length=20, blank=True, validators=[RegexValidator(NUMBERS_ONLY_REGEX)],
                                  help_text=NUMBERS_ONLY_HELP_TEXT)
    account_number = models.CharField(max_length=12, blank=True)

    class Meta:
        ordering = ['serial_number']

    def __str__(self):
        return self.serial_number


class SensorData(models.Model):
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE)
    ctime = models.DateTimeField(default=timezone.now)
    topic = models.CharField(max_length=1024)
    payload = models.CharField(max_length=1024)
    data_json = JSONField()

    class Meta:
        ordering = ('-ctime',)


class SimBalance(models.Model):
    sensor = models.ForeignKey(Sensor, verbose_name=_('sensor'), on_delete=models.CASCADE)
    ctime = models.DateTimeField(default=timezone.now)
    balance = models.IntegerField(default=0)
    actual = models.BooleanField(default=False, verbose_name=_('actual data'))

    class Meta:
        verbose_name = _('sim balance')
        verbose_name_plural = _('sim balance')
        ordering = ('ctime',)

    def __str__(self):
        return '%s %s %s' % (self.sensor, self.balance, self.ctime)


class BatteryLevel(models.Model):
    sensor = models.ForeignKey(Sensor, verbose_name=_('sensor'), on_delete=models.CASCADE)
    ctime = models.DateTimeField(default=timezone.now)
    level = models.IntegerField(default=0)
    volts = models.FloatField(default=0)
    actual = models.BooleanField(default=False, verbose_name=_('actual data'))


class Temperature(models.Model):
    sensor = models.ForeignKey(
        Sensor, verbose_name=_('sensor'), related_name='temperature_table', on_delete=models.CASCADE)
    ctime = models.DateTimeField(default=timezone.now)
    value = models.IntegerField(default=0)
    actual = models.BooleanField(default=False, verbose_name=_('actual data'))

    class Meta:
        verbose_name = _('temperature')
        verbose_name_plural = _('temperature')
        ordering = ('ctime',)

    def __str__(self):
        return '%s %s %s' % (self.sensor, self.value, self.ctime)


class ErrorType(models.Model):
    code = models.IntegerField(verbose_name=_('code error'), unique=True)
    title = models.CharField(max_length=256, verbose_name=_('title'))

    class Meta:
        verbose_name = _('error type')
        verbose_name_plural = _('error types')
        ordering = ('code',)

    def __str__(self):
        return self.title


class Error(models.Model):
    sensor = models.ForeignKey(Sensor, verbose_name=_('sensor'), on_delete=models.CASCADE)
    error_type = models.ForeignKey(ErrorType, verbose_name=_('error type'), on_delete=models.CASCADE)
    ctime = models.DateTimeField(default=timezone.now)
    actual = models.BooleanField(default=False, verbose_name=_('actual data'))

    class Meta:
        verbose_name = _('error')
        verbose_name_plural = _('errors')
        ordering = ('ctime',)

    def __str__(self):
        return '%s %s %s' % (self.sensor, self.error_type, self.ctime)


class Fullness(models.Model):
    sensor = models.ForeignKey(
        Sensor, verbose_name=_('sensor'), related_name='fullness_table', on_delete=models.CASCADE)
    ctime = models.DateTimeField(default=timezone.now)
    value = models.IntegerField(default=0)
    actual = models.BooleanField(default=False, verbose_name=_('actual data'))
    signal_amp = models.IntegerField(null=True, blank=True)
    parsing_metadata_json = JSONField(default=dict)


class SensorJob(models.Model):
    UPDATE_CONFIG_JOB_TYPE = 'UPDATE_CONFIG'
    FETCH_CONFIG_JOB_TYPE = 'FETCH_CONFIG'
    GET_LOCATION_JOB_TYPE = 'GET_LOCATION'
    UPDATE_FIRMWARE_JOB_TYPE = 'UPDATE_FIRMWARE'
    CALIBRATE_JOB_TYPE = 'CALIBRATE'
    ORIENT_JOB_TYPE = 'ORIENT'
    # TODO: Clarify what's with these job types
    GET_SIM_BALANCE_JOB_TYPE = 'GET_SIM_BALANCE'
    GET_PHONE_NUMBER_JOB_TYPE = 'GET_PHONE_NUMBER'

    JOB_TYPE_CHOICES = (
        (UPDATE_CONFIG_JOB_TYPE, 'Update Configuration'),
        (FETCH_CONFIG_JOB_TYPE, 'Fetch Configuration'),
        (GET_LOCATION_JOB_TYPE, 'Determine GPS location'),
        (UPDATE_FIRMWARE_JOB_TYPE, 'Update firmware'),
        (GET_SIM_BALANCE_JOB_TYPE, 'Determine SIM balance'),
        (GET_PHONE_NUMBER_JOB_TYPE, 'Determine phone number'),
        (CALIBRATE_JOB_TYPE, 'Calibrate sensor'),
        (ORIENT_JOB_TYPE, 'Orient sensor'),
    )

    SUCCESS_STATUS = 'SUCCESS'
    FAILURE_STATUS = 'FAILURE'

    JOB_STATUS_CHOICES = (
        (SUCCESS_STATUS, 'Successful job'),
        (FAILURE_STATUS, 'Failed job'),
    )

    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE)
    ctime = models.DateTimeField(default=timezone.now)
    mtime = models.DateTimeField(default=None, null=True, blank=True)
    type = models.CharField(max_length=32, choices=JOB_TYPE_CHOICES)
    # Payload length limit is aligned with device capabilities
    payload = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=16, choices=JOB_STATUS_CHOICES, blank=True)
    result = models.CharField(max_length=1024, blank=True)


class VerneMQAuthAcl(models.Model):
    DEFAULT_MOUNTPOINT = ''
    DEFAULT_CLIENT_ID = '*'
    DEFAULT_ACL = [{'pattern': '#'}]

    mountpoint = models.CharField(max_length=10)
    client_id = models.CharField(max_length=128)
    username = models.CharField(max_length=128)
    password = models.CharField(max_length=128)
    publish_acl = JSONField()
    subscribe_acl = JSONField()

    class Meta:
        db_table = 'vmq_auth_acl'
        unique_together = ('mountpoint', 'client_id', 'username')

    @staticmethod
    def hash_password(password):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto';")
            if cursor.fetchone() is None:
                warn_message = 'Current database is missing "pgcrypto" extension'
                logger.warning(warn_message)
                capture_message(warn_message)
                return None
            else:
                cursor.execute("SELECT crypt(%s, gen_salt('bf'));", [password])
                return cursor.fetchone()[0]


class SensorsAuthCredentials(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, unique=True)
    username = models.CharField(max_length=32, unique=True)
    password = models.CharField(max_length=32)


class CompanySensorsLicense(models.Model):
    company = models.ForeignKey(Company, verbose_name=_('company'), on_delete=models.CASCADE)
    begin = models.DateField(verbose_name=_('period begin'), default=date.today)
    end = models.DateField(verbose_name=_('period end'))
    usage_balance = models.IntegerField()
    description = models.CharField(max_length=256, blank=True)

    @property
    def is_valid(self):
        return self.begin <= date.today() <= self.end and self.usage_balance >= 0

    def update_balance(self, amount, actor=None, comment=''):
        op = LicenseBalanceTransactionLog.WITHDRAW_OP if amount < 0 else LicenseBalanceTransactionLog.DEPOSIT_OP
        with transaction.atomic():
            LicenseBalanceTransactionLog.objects.create(
                license=self, actor=actor, operation=op, amount=abs(amount), comment=comment)
            self.usage_balance += amount
            self.save()


class LicenseBalanceTransactionLog(models.Model):
    WITHDRAW_OP = 'WITHDRAW'
    DEPOSIT_OP = 'DEPOSIT'
    EFFICIENCY_MONITOR = 'EFFICIENCY_MONITOR'

    OP_CHOICES = [
        (WITHDRAW_OP, 'Withdraw'),
        (DEPOSIT_OP, 'Deposit'),
    ]

    license = models.ForeignKey(CompanySensorsLicense, on_delete=models.CASCADE, related_name='transaction_log')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_('user'), related_name='+', null=True)
    ctime = models.DateTimeField(default=timezone.now, verbose_name=_('create time'))
    operation = models.CharField(max_length=16, choices=OP_CHOICES)
    amount = models.IntegerField()
    comment = models.CharField(max_length=128, blank=True)

    @property
    def operation_amount(self):
        return f"{'-' if self.operation == self.WITHDRAW_OP else '+'}{self.amount}"


class SensorsLicenseKey(models.Model):
    key = models.CharField(max_length=20, unique=True)
    period_days = models.IntegerField(validators=[MinValueValidator(1)])
    devices_count = models.IntegerField(validators=[MinValueValidator(1)])
    ctime = models.DateTimeField(default=timezone.now, verbose_name=_('created at'))
    mtime = models.DateTimeField(blank=True, null=True)
    used = models.BooleanField(default=False)

    @property
    def usage_balance_top_up_amount(self):
        return self.period_days * self.devices_count

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = str(uuid.uuid4())[4:][:-13].upper()
        self.mtime = timezone.now()
        super().save(*args, **kwargs)

    def create_license(self, company):
        if self.used:
            raise ValueError('This license key is already used')

        with transaction.atomic():
            self.used = True
            self.save()
            end = date.today() + timedelta(days=self.period_days)
            description = f'License created for license key {self.key}: ' \
                          f'{self.devices_count} devices for {self.period_days} days'
            return CompanySensorsLicense.objects.create(
                company=company, end=end, usage_balance=self.usage_balance_top_up_amount, description=description)

    def extend_license(self, sensors_license, actor=None):
        if self.used:
            raise ValueError('This license key is already used')

        with transaction.atomic():
            self.used = True
            self.save()
            sensors_license.end = sensors_license.end + timedelta(days=self.period_days)
            sensors_license.update_balance(
                self.usage_balance_top_up_amount, actor=actor, comment=f'License extended by license key {self.key}')


DEFAULT_SENSOR_LOCATION = {
    'lng': 37.573856,
    'lat': 55.751574,
}


class SensorOnboardRequest(models.Model):
    FRONT_INSTALL_TYPE = 'FRONT'
    REAR_INSTALL_TYPE = 'REAR'

    INSTALL_TYPE_CHOICES = (
        (FRONT_INSTALL_TYPE, 'Front'),
        (REAR_INSTALL_TYPE, 'Rear'),
    )

    # TODO: Uncomment more choices when it'll make sense
    NETWORK_TYPE_2G = '2G'
    NETWORK_TYPE_NB_IOT = 'NB_IOT'
    # NETWORK_TYPE_LORAWAN = 'LORAWAN'

    NETWORK_TYPE_CHOICES = (
        (NETWORK_TYPE_2G, '2G'),
        (NETWORK_TYPE_NB_IOT, 'NB-IoT'),
        # (NETWORK_TYPE_LORAWAN, 'LoRaWAN'),
    )

    install_types_to_sn = {
        FRONT_INSTALL_TYPE: 'F',
        REAR_INSTALL_TYPE: 'R',
    }

    network_types_to_sn = {
        NETWORK_TYPE_2G: '2G',
        NETWORK_TYPE_NB_IOT: 'NB',
        # NETWORK_TYPE_LORAWAN: 'LW',
    }

    hardware_identity = models.CharField(max_length=50, unique=True)
    install_type = models.CharField(max_length=16, choices=INSTALL_TYPE_CHOICES, blank=True)
    network_type = models.CharField(max_length=16, choices=NETWORK_TYPE_CHOICES, blank=True)
    ctime = models.DateTimeField(default=timezone.now)
    mtime = models.DateTimeField(default=None, null=True, blank=True)
    is_closed = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.install_type and self.network_type:
            with transaction.atomic():
                self._create_sensor_record()
                self.is_closed = True
                self.mtime = timezone.now()
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def clean(self):
        if not self.install_type or not self.network_type:
            return

        try:
            Sensor.objects.get(hardware_identity=self.hardware_identity)
        except Sensor.DoesNotExist:
            pass
        else:
            raise ValidationError(f"There's an existing sensor with hardware ID {self.hardware_identity}")

    def _create_sensor_record(self):
        if settings.SENSOR_ASSET_HOLDER_COMPANY_ID is None:
            raise Exception("Sensor asset holder company ID is unset")

        try:
            asset_holder_company = Company.objects.get(pk=settings.SENSOR_ASSET_HOLDER_COMPANY_ID)
        except Company.DoesNotExist:
            raise Exception(f"Sensor asset holder company with ID {settings.SENSOR_ASSET_HOLDER_COMPANY_ID} not found")

        unknown_country, unknown_city = get_unknown_city_country()
        sensor = Sensor()
        sensor.settings_profile = SensorSettingsProfile.objects.first()
        sensor.serial_number = str(uuid.uuid4())  # To just ensure there won't be collisions
        sensor.hardware_identity = self.hardware_identity
        sensor.phone_number = ''
        sensor.container_type = ContainerType.objects.first()
        sensor.company = asset_holder_company
        sensor.country = unknown_country
        sensor.city = unknown_city
        sensor.address = '-'
        sensor.sector = Sectors.objects.filter(company=asset_holder_company).first()
        sensor.waste_type = WasteType.objects.first()
        sensor.location = format_random_location(DEFAULT_SENSOR_LOCATION)
        sensor.save()
        manufacturer_code = '0'
        sensor.serial_number = f"BWS{self.install_types_to_sn[self.install_type]}" \
                               f"{self.network_types_to_sn[self.network_type]}-" \
                               f"{manufacturer_code}{str(date.today().year)[2:]}{sensor.id:05d}"
        sensor.save()
