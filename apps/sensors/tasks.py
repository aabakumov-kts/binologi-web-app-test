from __future__ import absolute_import, unicode_literals

import paho.mqtt.client as mqtt
import random
import re
import time

from celery import shared_task, chain
from celery.utils.log import get_task_logger
from dataclasses import dataclass
from datetime import timedelta
from django_celery_beat import models as django_celery_beat_models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from sentry_sdk import capture_message
from typing import Optional

from apps.core.helpers import get_unknown_city_country, execute_reverse_geocoding
from apps.core.models import Company
from apps.core.report_data_generation import BaseReportDataGenerator, SECONDS_PER_PERIOD
from apps.core.tasks import NotificationPriorities, notification_levels_resolver, create_notification
from apps.sensors.shared import SensorsNotificationTypes, arrange_sensor_config_jobs
from apps.sensors.models import (
    Sensor, SensorData, SimBalance, BatteryLevel, Temperature, Fullness, SensorSettingsProfile, SensorJob, ErrorType,
    Error, CompanySensorsLicense, SensorOnboardRequest,
)
from apps.sensors.utils import build_sensor_connect_schedule, parse_sensor_message_payload


logger = get_task_logger(__name__)


def generate_time_series_record(model, sensor, **kwargs):
    model.objects.filter(sensor=sensor, actual=True).update(actual=False)
    model.objects.create(sensor=sensor, actual=True, **kwargs)


def convert_ranges_to_fullness_percentage(range_to_waste, range_to_bin_bottom):
    range_filled_by_waste = max(range_to_bin_bottom - range_to_waste, 0)
    return (range_filled_by_waste / float(range_to_bin_bottom)) * 100


def update_latest_sensor_job(sensor, job_type, missing_message, job_result):
    latest_job = SensorJob.objects.filter(sensor=sensor, type=job_type, status='').order_by('-ctime').first()
    if latest_job is None:
        logger.warning(missing_message)
    else:
        latest_job.status = SensorJob.SUCCESS_STATUS
        latest_job.result = job_result
        latest_job.mtime = timezone.now()
        latest_job.save()


HARDWARE_ID_REGEX = re.compile(r"sensors/(.+)/.+")
SIM_BALANCE_REGEX = re.compile(r"[+-]?\d+(?:\.\d+)")
PHONE_NUMBER_REGEX = re.compile(r'\d{0,15}')
ICCID_NUMBER_REGEX = re.compile(r'\d{0,20}')

settings_profile_fields_to_job_payload_mapping = {
    'accelerometer_delay': 'a111Delay',
    'accelerometer_sensitivity': 'acelTh',
    'access_point_name': 'nbiot',
    'close_measurement_approximation_profile': 'close_r_s_profile',
    'close_measurement_distance_begin': 'close_r_start',
    'close_measurement_distance_length': 'close_r_len',
    'close_measurement_downsampling': 'close_r_downsampling',
    'close_measurement_gain': 'close_r_gain',
    'close_measurement_noise_samples_number': 'close_r_sweep_bkgd',
    'close_measurement_noise_threshold': 'close_r_threashold',
    'close_measurement_on_flag': 'close_r_meas_on',
    'close_measurement_peaks_merge_distance': 'close_r_peak_merge_lim',
    'close_measurement_peaks_sorting_method': 'close_r_peak_sorting',
    'close_measurement_signal_samples_number': 'close_r_sweep_avr',
    'connection_schedule_start': 'on_time',
    'connection_schedule_stop': 'off_time',
    'current_orientation': 'orient',
    'enabled_flag': 'onFlag',
    'far_measurement_approximation_profile': 'far_r_s_profile',
    'far_measurement_distance_begin': 'far_r_start',
    'far_measurement_distance_length': 'far_r_len',
    'far_measurement_downsampling': 'far_r_downsampling',
    'far_measurement_gain': 'far_r_gain',
    'far_measurement_noise_samples_number': 'far_r_sweep_bkgd',
    'far_measurement_noise_threshold': 'far_r_threashold',
    'far_measurement_on_flag': 'far_r_meas_on',
    'far_measurement_peaks_merge_distance': 'far_r_peak_merge_lim',
    'far_measurement_peaks_sorting_method': 'far_r_peak_sorting',
    'far_measurement_signal_samples_number': 'far_r_sweep_avr',
    'fill_alert_count': 'fillCount',
    'fill_alert_interval': 'fillWakeup',
    'fill_alert_range': 'fillAlert',
    'fire_min_temp': 'tempFire',
    'fire_temp_gradient': 'gradient_temperature',
    'first_turn_on_flag': 'on_init_modem',
    'gps_in_every_connection': 'fGps',
    'gps_timeout': 'tGps',
    'gsm_timeout': 'tGsm',
    'login': 'serverLogin',
    'measurement_interval': 'intConn',
    'measurement_results_number': 'result_r_length',
    'message_send_retries': 'retry',
    'mid_measurement_approximation_profile': 'mid_r_s_profile',
    'mid_measurement_distance_begin': 'mid_r_start',
    'mid_measurement_distance_length': 'mid_r_len',
    'mid_measurement_downsampling': 'mid_r_downsampling',
    'mid_measurement_gain': 'mid_r_gain',
    'mid_measurement_noise_samples_number': 'mid_r_sweep_bkgd',
    'mid_measurement_noise_threshold': 'mid_r_threashold',
    'mid_measurement_on_flag': 'mid_r_meas_on',
    'mid_measurement_peaks_merge_distance': 'mid_r_peak_merge_lim',
    'mid_measurement_peaks_sorting_method': 'mid_r_peak_sorting',
    'mid_measurement_signal_samples_number': 'mid_r_sweep_avr',
    'orientation_threshold': 'orientTh',
    'password': 'serverPassword',
    'server_host': 'serverHost',
    'server_port': 'serverPort',
    'updates_server_path': 'upPath',
    'updates_server_url': 'upSer'
}
settings_profile_fields_to_job_payload_resolver =\
    {v: k for k, v in settings_profile_fields_to_job_payload_mapping.items()}

job_types_to_payload_mapping = {
    SensorJob.UPDATE_CONFIG_JOB_TYPE: lambda job: job.payload,
    SensorJob.FETCH_CONFIG_JOB_TYPE: lambda job: job.payload,
    SensorJob.GET_LOCATION_JOB_TYPE: lambda job: 'e/gps',
    SensorJob.UPDATE_FIRMWARE_JOB_TYPE: lambda job: job.payload,
    SensorJob.CALIBRATE_JOB_TYPE: lambda job: 'e/env',
    SensorJob.ORIENT_JOB_TYPE: lambda job: 'e/orient',
    # TODO: These job types don't work now
    SensorJob.GET_SIM_BALANCE_JOB_TYPE: lambda job: f'g/simBalance`{job.payload}',
    SensorJob.GET_PHONE_NUMBER_JOB_TYPE: lambda job: f'g/phoneNum`{job.payload}',
}

DEFAULT_SENSOR_LOCATION = {
    'lng': 37.573856,
    'lat': 55.751574,
}


@shared_task
def onboard_new_sensor(hardware_id):
    SensorOnboardRequest.objects.create(hardware_identity=hardware_id)


def process_sensor_data_dict(data, sensor, sensor_data_id=None):
    def detect_moisture(measurement_distance_begin_m, measured_range):
        moisture_distance_begin = measurement_distance_begin_m * 1000
        moisture_distance_end = moisture_distance_begin + sensor.container_type.moisture_threshold
        return moisture_distance_begin <= measured_range <= moisture_distance_end

    if 'binFill' in data:
        filling_value = data['binFill']
        try:
            range_to_waste = int(filling_value)
        except ValueError:
            logger.warning(
                f"Sensor data with ID '{sensor_data_id}' contains invalid value for 'binFill': {filling_value}")
        else:
            # Calculate fullness percentage
            max_range_mm = sensor.container_type.get_max_range(sensor.mount_type) * 1000
            min_range_m = sensor.container_type.get_min_range(sensor.mount_type)
            min_range_mm = min_range_m * 1000 if min_range_m else 200
            if range_to_waste > max_range_mm:
                range_filled_by_waste = 0
            elif range_to_waste < min_range_mm:
                range_filled_by_waste = max_range_mm - min_range_mm
            else:
                range_filled_by_waste = max_range_mm - range_to_waste
            if sensor.mount_type in [Sensor.VERTICAL_MOUNT_TYPE, Sensor.DIAGONAL_MOUNT_TYPE]:
                fullness_value = (range_filled_by_waste / float(max_range_mm - min_range_mm)) * 100
            else:
                waste_detected = range_to_waste / float(max_range_mm - min_range_mm) <= 0.5
                fullness_value = 90 if waste_detected else 0
            # Process signal amplitude
            signal_amp = None
            if 'ampltd' in data:
                raw_ampltd = data['ampltd']
                try:
                    signal_amp = int(raw_ampltd)
                except ValueError:
                    logger.warning(
                        f"Sensor data with ID '{sensor_data_id}' contains invalid value for 'ampltd': {raw_ampltd}")
            # Detect moisture
            parsing_metadata = {}
            if sensor.settings_profile.close_measurement_on_flag == 1:
                if detect_moisture(sensor.settings_profile.close_measurement_distance_begin, range_to_waste):
                    parsing_metadata['close_measurement_moisture'] = True
            elif sensor.settings_profile.mid_measurement_on_flag == 1:
                if detect_moisture(sensor.settings_profile.mid_measurement_distance_begin, range_to_waste):
                    parsing_metadata['mid_measurement_moisture'] = True
            elif sensor.settings_profile.far_measurement_on_flag == 1:
                if detect_moisture(sensor.settings_profile.far_measurement_distance_begin, range_to_waste):
                    parsing_metadata['far_measurement_moisture'] = True
            if parsing_metadata:
                parsing_metadata['any_measurement_moisture'] = True
                latest_moisture_free_fullness = Fullness.objects.filter(sensor=sensor).exclude(
                    parsing_metadata_json__contains={'any_measurement_moisture': True}).order_by('-ctime').first()
                parsing_metadata['latest_moisture_free_fullness'] =\
                    latest_moisture_free_fullness.value if latest_moisture_free_fullness else 0
            # Store values
            sensor.fullness = fullness_value
            generate_time_series_record(
                Fullness, sensor, value=fullness_value, signal_amp=signal_amp, parsing_metadata_json=parsing_metadata)
    if 'batV' in data:
        sensor.battery = int(data['batV'])
        generate_time_series_record(BatteryLevel, sensor, level=sensor.battery)
    if 'rFlag' in data:
        error_code = int(data['rFlag'])
        try:
            error_type = ErrorType.objects.get(code=error_code)
        except ErrorType.DoesNotExist:
            if error_code == 0:
                logger.debug(f'Error code {error_code} received, assumed no errors occurred')
            else:
                logger.warning(f"Unrecognized error code '{error_code}' received")
        else:
            generate_time_series_record(Error, sensor, error_type=error_type)
    if 'temp' in data:
        temperature = int(data['temp'])
        sensor.temperature = temperature
        generate_time_series_record(Temperature, sensor, value=temperature)
    if 'ICCID' in data:
        iccid_value_text = data['ICCID']
        if ICCID_NUMBER_REGEX.fullmatch(iccid_value_text):
            sensor.sim_number = iccid_value_text
        else:
            logger.warning(f"Failed to parse ICCID text '{iccid_value_text}'")

    sensor.save()


@shared_task
def parse_sensor_regular_data(sensor_data_id):
    try:
        sensor_data = SensorData.objects.prefetch_related('sensor', 'sensor__container_type').get(pk=sensor_data_id)
    except SensorData.DoesNotExist:
        raise Warning(f"Sensor data with ID '{sensor_data_id}' does not exist")

    data = sensor_data.data_json
    sensor = sensor_data.sensor
    with transaction.atomic():
        # Dropping current actual errors to free room for new ones
        sensor.error_set.filter(actual=True).update(actual=False)
        process_sensor_data_dict(data, sensor, sensor_data.id)

    logger.debug(f'Regular sensor data with ID {sensor_data_id} parsed successfully')

    return sensor.id


@shared_task
def reverse_geocode_sensor_location(sensor_id):
    try:
        sensor = Sensor.objects.prefetch_related('company').get(pk=sensor_id)
    except Sensor.DoesNotExist:
        raise Warning(f"Sensor with ID '{sensor_id}' does not exist")

    unknown_country, unknown_city = get_unknown_city_country()
    country, city, address = execute_reverse_geocoding((sensor.location.y, sensor.location.x), sensor.company.lang)
    if address:
        sensor.address = address
    if country != unknown_country:
        sensor.country = country
    if city != unknown_city:
        sensor.city = city
    sensor.save()


def convert_nmea_value_to_decimal(nmea_value):
    value_parts = nmea_value.split('.')
    degrees = int(value_parts[0][:-2])
    minutes = float(f"{value_parts[0][-2:]}.{value_parts[1]}") / 60
    return degrees + minutes


@shared_task
def parse_sensor_jobs_data(sensor_data_id):
    try:
        sensor_data = SensorData.objects.prefetch_related('sensor', 'sensor__settings_profile').get(pk=sensor_data_id)
    except SensorData.DoesNotExist:
        raise Warning(f"Sensor data with ID '{sensor_data_id}' does not exist")

    data = sensor_data.data_json
    sensor = sensor_data.sensor
    additional_tasks_to_execute = []
    with transaction.atomic():
        if 'gps' in data:
            nmea_value = data['gps']
            nmea_parts = nmea_value.split(',')
            if nmea_value in ['error', 'NoDatagps', 'NoData']:
                logger.warning(f"Sensor data with ID '{sensor_data.id}' contains error for 'gps' value")
            elif not all(map(lambda i: nmea_parts[i], [1, 2, 3, 4])):
                logger.warning(f"Sensor data with ID '{sensor_data.id}' contains empty parts in 'gps' value")
            else:
                lat = convert_nmea_value_to_decimal(nmea_parts[1])
                long = convert_nmea_value_to_decimal(nmea_parts[3])
                if nmea_parts[2] == 'S':
                    lat = -lat
                if nmea_parts[4] == 'W':
                    long = -long
                previous_sensor_location_str = str(sensor.location)
                new_sensor_location_str = f'SRID=4326;POINT ({long} {lat})'
                sensor.location = new_sensor_location_str
                if new_sensor_location_str != previous_sensor_location_str:
                    additional_tasks_to_execute.append((reverse_geocode_sensor_location, [sensor.id]))
                update_latest_sensor_job(
                    sensor,
                    SensorJob.GET_LOCATION_JOB_TYPE,
                    f"Failed to found a GPS location job for the update '{nmea_value}' received",
                    nmea_value,
                )
        if 'simBalance' in data:
            sim_balance_text = data['simBalance']
            if SIM_BALANCE_REGEX.search(sim_balance_text):
                balance = round(float(SIM_BALANCE_REGEX.search(sim_balance_text).group(0)))
                generate_time_series_record(SimBalance, sensor, balance=balance)
            else:
                logger.warning(f"Failed to parse SIM balance text '{sim_balance_text}'")
            update_latest_sensor_job(
                sensor,
                SensorJob.GET_SIM_BALANCE_JOB_TYPE,
                f"Failed to found a SIM balance job for the update '{sim_balance_text}' received",
                sim_balance_text,
            )
        if 'phoneNum' in data:
            phone_value_text = data['phoneNum']
            if PHONE_NUMBER_REGEX.fullmatch(phone_value_text):
                sensor.phone_number = phone_value_text
            else:
                logger.warning(f"Failed to parse phone number text '{phone_value_text}'")
            update_latest_sensor_job(
                sensor,
                SensorJob.GET_PHONE_NUMBER_JOB_TYPE,
                f"Failed to found a phone number job for the update '{phone_value_text}' received",
                phone_value_text,
            )
        if any((config_key in data for config_key in settings_profile_fields_to_job_payload_resolver)):
            update_latest_sensor_job(
                sensor,
                SensorJob.FETCH_CONFIG_JOB_TYPE,
                f"Failed to found a fetch config job for the update stored as sensor data with ID {sensor_data_id}",
                sensor_data.payload,
            )
        sensor.save()

    for task, args in additional_tasks_to_execute:
        task.delay(*args)

    incomplete_jobs = SensorJob.objects.filter(sensor=sensor, status='')
    settings_profile = sensor.settings_profile
    utc_now = timezone.now()
    connections_allowed_to_complete_job = 2
    failed_jobs = 0
    for job in incomplete_jobs:
        if (utc_now - job.ctime).days > connections_allowed_to_complete_job:
            # Quick check: we know that sensor should connect at least once a day
            # This also helps to avoid building up a connection schedule for many days in edge cases
            fail_job = True
        else:
            # Long way: build a connections schedule
            schedule_moments = build_sensor_connect_schedule(
                job.ctime.date(), settings_profile.connection_schedule_start, settings_profile.connection_schedule_stop,
                connections_allowed_to_complete_job, settings_profile.measurement_interval)
            scheduled_connections_count =\
                len([moment for moment in schedule_moments if job.ctime <= moment <= utc_now])
            fail_job = scheduled_connections_count > connections_allowed_to_complete_job
        if fail_job:
            job.status = SensorJob.FAILURE_STATUS
            job.result = f'Failed automatically due to no result after ' \
                         f'{connections_allowed_to_complete_job} connections'
            job.mtime = timezone.now()
            job.save()
            failed_jobs += 1
    if failed_jobs > 0:
        logger.debug(f'{failed_jobs} jobs failed due to no result after '
                     f'{connections_allowed_to_complete_job} connections')

    logger.debug(f'Jobs sensor data with ID {sensor_data_id} parsed successfully')

    return sensor.id


@shared_task
def send_sensor_jobs(sensor_id):
    try:
        sensor = Sensor.objects.get(pk=sensor_id)
    except Sensor.DoesNotExist:
        raise Warning(f"Sensor with ID '{sensor_id}' does not exist")

    incomplete_jobs = SensorJob.objects.filter(sensor=sensor, status='')
    if incomplete_jobs.count() == 0:
        logger.debug(f"There's no incomplete jobs for sensor with ID {sensor_id}")
        return

    encoding_failed_job_ids = []
    connect_rc = None

    def on_connect(client, userdata, flags, rc):
        nonlocal connect_rc
        connect_rc = rc
        if rc != 0:
            client.disconnect()
            return
        topic = f'/sensors/{sensor.hardware_identity}/jobs'
        for job in incomplete_jobs:
            if job.type not in job_types_to_payload_mapping:
                logger.warning(f"There is no mapping of job type {job.type} to message payload")
            else:
                raw_payload = job_types_to_payload_mapping[job.type](job)
                try:
                    ascii_payload = raw_payload.encode('ascii')
                except UnicodeEncodeError:
                    encoding_failed_job_ids.append(job.pk)
                else:
                    mqtt_client.publish(topic, ascii_payload)
        client.disconnect()

    if not settings.DISABLE_SENSOR_JOB_SEND_DELAY:
        time.sleep(10)  # Wait for sensor to subscribe

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    if settings.MQTT_USERNAME and settings.MQTT_PASSWORD:
        mqtt_client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
    mqtt_client.connect(settings.MQTT_BROKER_HOST)
    mqtt_client.loop_forever()
    if connect_rc in [4, 5]:
        raise Warning('Connection to MQTT broker failed due to invalid credentials')
    if connect_rc != 0:
        raise Warning(f"Connection to MQTT broker failed with return code '{connect_rc}'")

    sent_jobs = set([job.id for job in incomplete_jobs]).difference(encoding_failed_job_ids)
    immediately_completed_job_types = [
        SensorJob.UPDATE_CONFIG_JOB_TYPE,
        SensorJob.CALIBRATE_JOB_TYPE,
        SensorJob.ORIENT_JOB_TYPE,
    ]
    SensorJob.objects.filter(
        type__in=immediately_completed_job_types, id__in=sent_jobs).update(
        status=SensorJob.SUCCESS_STATUS, mtime=timezone.now())
    SensorJob.objects.filter(id__in=encoding_failed_job_ids).update(
        status=SensorJob.FAILURE_STATUS, mtime=timezone.now(), result="Failed to encode job payload in ASCII")

    logger.debug(f'Successfully sent jobs for sensor with ID {sensor_id}')


@shared_task
def execute_sensor_data_pipeline(topic, payload):
    hardware_id_search = HARDWARE_ID_REGEX.search(topic)
    if not hardware_id_search:
        raise Warning("Hardware ID is missing in data from sensor")

    hardware_id = hardware_id_search.group(1)
    try:
        sensor = Sensor.objects.get(hardware_identity=hardware_id)
    except Sensor.DoesNotExist:
        try:
            onboard_request = SensorOnboardRequest.objects.get(hardware_identity=hardware_id)
        except SensorOnboardRequest.DoesNotExist:
            onboard_new_sensor.delay(hardware_id)
        else:
            logger.info(f'Received data from sensor with HWID "{hardware_id}" '
                        f'with pending onboarding request {onboard_request.id}, '
                        f'data was discarded')
    else:
        if sensor.disabled:
            logger.debug(f'Sensor with ID {sensor.id} is disabled, message is discarded')
            return
        try:
            json_payload = parse_sensor_message_payload(payload)
        except IndexError:
            if payload == 'Power off':
                logger.debug(f'Received "Power off" debug payload from sensor ID {sensor.id}')
                return
            raise Warning(f"Failed to parse data from sensor (ID {sensor.id}): {payload}")
        else:
            if sensor.company.id != settings.SENSOR_ASSET_HOLDER_COMPANY_ID:
                sensor_license = CompanySensorsLicense.objects.filter(company=sensor.company).order_by('-end').first()
                license_is_valid = sensor_license.is_valid if sensor_license else False
                if not license_is_valid:
                    Sensor.objects.filter(company=sensor.company).update(disabled=True)
                    raise Warning(f"Company {sensor.company.id} has invalid or missing sensors license")
            stored_sensor_data = SensorData.objects.create(
                sensor=sensor, topic=topic, payload=payload, data_json=json_payload)

            chain(parse_sensor_regular_data.s(stored_sensor_data.id), generate_sensor_status_notifications.s()).delay()
            chain(parse_sensor_jobs_data.s(stored_sensor_data.id), send_sensor_jobs.s()).delay()


@dataclass
class ConfigureJobDS:
    pk: Optional[int]
    payload_dict: dict
    payload_length_left: int


@shared_task
def configure_devices(profile_id, changed_fields):
    try:
        settings_profile = SensorSettingsProfile.objects.get(pk=profile_id)
    except SensorSettingsProfile.DoesNotExist:
        raise Warning(f"Sensor settings profile with id '{profile_id}' does not exist")

    profile_sensors_ids = settings_profile.profile_sensors.values_list('id', flat=True)
    if not profile_sensors_ids:
        logger.info(f"Devices using profile with id '{profile_id}' not found")
        return

    any_mapping_missing = any((
        field not in settings_profile_fields_to_job_payload_mapping
        for field in changed_fields
    ))
    if any_mapping_missing:
        fields_with_missing_mappings = [
            field for field in changed_fields
            if field not in settings_profile_fields_to_job_payload_mapping
        ]
        raise Warning(
            f"There are missing mappings for settings profile fields: {', '.join(fields_with_missing_mappings)}")

    arrange_sensor_config_jobs(profile_sensors_ids, settings_profile_fields_to_job_payload_mapping, changed_fields,
                               field_values_source=settings_profile)


@shared_task
def schedule_location_updates(*company_ids):
    excluded_company_ids = []
    if len(company_ids) == 0:
        # This is the default task instance
        full_task_name = f"{schedule_location_updates.__module__}.{schedule_location_updates.__name__}"
        for task in django_celery_beat_models.PeriodicTask.objects.filter(task=full_task_name, enabled=True):
            excluded_company_ids.extend(eval(task.args))
    sensors_qs = Sensor.objects.all()
    if company_ids:
        sensors_qs = sensors_qs.filter(company_id__in=company_ids)
    elif excluded_company_ids:
        sensors_qs = sensors_qs.exclude(company_id__in=excluded_company_ids)
    sensors_qs = sensors_qs.values_list('id', flat=True).order_by('id')
    sensors_count = sensors_qs.count()
    if sensors_count == 0:
        logger.debug("No sensors found to generate location update jobs, skipping")
        return

    page_size = 1000
    offset = 0
    jobs_created = 0
    while offset < sensors_count:
        current_page = sensors_qs[offset:offset + page_size]
        current_page_sensors_with_existing_job = {sensor_id for sensor_id, jobs_count in SensorJob.objects.filter(
            sensor_id__in=current_page, type=SensorJob.GET_LOCATION_JOB_TYPE, status='').annotate(
            jobs_count=Count('id')).values_list('sensor_id', 'jobs_count') if jobs_count > 0}
        current_page_sensors_without_job = {sensor_id for sensor_id in current_page}.difference(
            current_page_sensors_with_existing_job)
        SensorJob.objects.bulk_create([
            SensorJob(sensor_id=sensor_id, type=SensorJob.GET_LOCATION_JOB_TYPE)
            for sensor_id in current_page_sensors_without_job
        ])
        jobs_created += len(current_page_sensors_without_job)
        offset += page_size

    logger.debug(f"Update location jobs were created for {jobs_created} sensors, total {sensors_count} processed")


@shared_task
def withdraw_sensors_usage_balance():
    # This is an unbounded data set but it's probably fine since there won't be too many companies
    for company in Company.objects.filter(sensor__disabled=False).\
            annotate(sensors_count=Count('sensor')).\
            filter(sensors_count__gt=0).\
            exclude(pk=settings.SENSOR_ASSET_HOLDER_COMPANY_ID):
        if company.companysensorslicense_set.count() == 0:
            warn_message = f'Detected company (id {company.id}) without a sensors license'
            logger.warning(warn_message)
            capture_message(warn_message)
            continue
        sensors_license = company.companysensorslicense_set.order_by('-end').first()
        if not sensors_license.is_valid:
            # License is already invalid for some reason, there's no need to withdraw usage balance in this case
            continue
        active_sensors_count = company.sensor_set.filter(disabled=False).count()
        sensors_license.update_balance(-active_sensors_count, comment='Automatic usage balance withdrawal')


class SensorReportDataGenerator(BaseReportDataGenerator):
    def generate_level_detection_fullness_record(self, sensor, last_100_fullness_ctime):
        if sensor.fullness >= 90:
            return 0 if random.random() >= 0.5 else sensor.fullness

        max_daily_fullness_increase = settings.DATA_GEN_FULLNESS_MAX_DAILY_INCREASE
        timedelta_since_last_100_fullness = self.utc_now - last_100_fullness_ctime
        total_days_last_100_fullness =\
            timedelta_since_last_100_fullness.total_seconds() / SECONDS_PER_PERIOD[django_celery_beat_models.DAYS]
        fullness_increases_by_days =\
            [random.random() * max_daily_fullness_increase for _ in range(0, round(total_days_last_100_fullness))]
        total_fullness_increase = sum(fullness_increases_by_days)
        return 90 if total_fullness_increase >= 90 else 0


def generate_report_data_for_sensors(sensors_qs, utc_now, record_generation_interval):
    sensors_count = sensors_qs.count()
    if sensors_count == 0:
        logger.debug("No sensors found to generate report data, skipping")
        return

    error_types = list(ErrorType.objects.values_list('code', flat=True))
    generator = SensorReportDataGenerator(utc_now, record_generation_interval)

    sensors_qs_to_paginate = sensors_qs.order_by('id')
    page_size = 1000
    offset = 0
    while offset < sensors_count:
        current_page = sensors_qs_to_paginate[offset:offset + page_size]
        for sensor in current_page:
            message = dict()

            if sensor.mount_type in [Sensor.VERTICAL_MOUNT_TYPE, Sensor.DIAGONAL_MOUNT_TYPE]:
                fullness, _ = generator.generate_fullness_record(sensor.fullness)
            else:
                last_90_fullness = Fullness.objects.filter(sensor=sensor, value=90).order_by('-ctime').first()
                fullness = generator.generate_level_detection_fullness_record(
                    sensor, last_90_fullness.ctime if last_90_fullness else (utc_now - timedelta(days=30)))
            max_range_mm = sensor.container_type.get_max_range(sensor.mount_type) * 1000
            range_filled_by_waste = (fullness / float(100)) * max_range_mm
            range_to_waste = max_range_mm - range_filled_by_waste
            message['binFill'] = range_to_waste
            # Don't use charge factor here since sensors don't have a solar panel
            message['batV'] = generator.generate_battery_level_record(sensor.battery, use_charge=False)
            message['temp'] = generator.generate_temperature_record()
            error_type = generator.generate_error_record(error_types)
            if error_type:
                message['rFlag'] = error_type

            models_to_update = [Fullness, BatteryLevel, Temperature]
            if error_type:
                models_to_update.append(Error)
            with transaction.atomic():
                # Dropping current actual errors to free room for new ones
                sensor.error_set.filter(actual=True).update(actual=False)
                process_sensor_data_dict(message, sensor)
                for model in models_to_update:
                    model.objects.filter(sensor=sensor, actual=True).update(ctime=utc_now)
            if random.random() > 0.9:
                generate_sensor_status_notifications.delay(sensor.id)
        offset += page_size

        logger.debug("Report data was generated for %s sensors" % sensors_count)


@shared_task
def generate_sensor_status_notifications(sensor_id):
    try:
        sensor = Sensor.objects.select_related('company').get(pk=sensor_id)
    except Sensor.DoesNotExist:
        raise Warning(f"There's no sensor with the PK specified: {sensor_id}")

    recipients = get_user_model().objects.filter(user_to_company__company=sensor.company)
    if recipients.count() == 0:
        logger.debug(f"There's no receivers for sensor {sensor_id}/{sensor.serial_number} notifications")

    def create_sensor_notification(
            notification_type: SensorsNotificationTypes, priority: NotificationPriorities, **kwargs):
        create_notification(
            sensor, recipient=recipients, verb=notification_type.value,
            level=notification_levels_resolver[priority].value, **kwargs)

    sensor_fullness_analysis = (p for ft, p in [
        (100, NotificationPriorities.HIGH),
        (90, NotificationPriorities.MEDIUM),
        (75, NotificationPriorities.LOW),
    ] if sensor.fullness >= ft)
    try:
        notification_priority = next(sensor_fullness_analysis)
    except StopIteration:
        pass
    else:
        create_sensor_notification(SensorsNotificationTypes.SENSOR_FULLNESS_ABOVE_THRESHOLD, notification_priority,
                                   fullness_level=sensor.fullness)

    if sensor.battery <= 30:
        create_sensor_notification(SensorsNotificationTypes.SENSOR_BATTERY_BELOW_THRESHOLD, NotificationPriorities.LOW,
                                   battery_level=sensor.battery)

    sensor_actual_error_type_codes = \
        set(sensor.error_set.filter(actual=True).values_list('error_type__code', flat=True))
    if any(sensor_actual_error_type_codes.intersection([2])):
        create_sensor_notification(SensorsNotificationTypes.SENSOR_FIRE_DETECTED, NotificationPriorities.HIGH)


@shared_task
def query_sensors_configuration(*fields):
    if len(fields) == 0:
        logger.warning("No fields specified, exiting")
        return

    any_mapping_missing = any((field not in settings_profile_fields_to_job_payload_resolver for field in fields))
    if any_mapping_missing:
        fields_with_missing_mappings = [
            field for field in fields
            if field not in settings_profile_fields_to_job_payload_resolver
        ]
        raise Warning(
            f"There are missing mappings for specified fields: {', '.join(fields_with_missing_mappings)}")

    sensors_qs = Sensor.objects.exclude(disabled=True)
    sensors_count = sensors_qs.count()
    if sensors_count == 0:
        logger.debug("No sensors found, exiting")
        return

    sensors_qs_to_paginate = sensors_qs.order_by('id')
    page_size = 1000
    offset = 0
    while offset < sensors_count:
        current_page = sensors_qs_to_paginate[offset:offset + page_size]
        arrange_sensor_config_jobs(
            current_page.values_list('pk', flat=True), {f: f for f in fields}, fields, add_fetch=True)
        offset += page_size
        logger.debug("Configuration query jobs generated for %s sensors" % sensors_count)
