from __future__ import absolute_import, unicode_literals

import binascii
import ujson as json
import os
import pytz
import random
import requests
import threading
import urllib

from celery import shared_task
from celery.utils.log import get_task_logger
from datetime import datetime, timedelta, date
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from functools import partial

from apps.core.models import UsersToCompany, Sectors, Company
from apps.core.report_data_generation import BaseReportDataGenerator, get_record_generation_interval
from app.models import (
    Container, ErrorType, FullnessValues, Battery_Level, SimBalance, EnergyEfficiencyForContainer,
    CreateDemoSandboxRequest, TrashbinJobModel, SlackEnabledTrashbin, TrashbinData, DemoSandboxTranslation,
    FullnessStats,
)
from apps.trashbins.models import CompanyTrashbinsLicense
from apps.trashbins.tasks import generate_trashbin_status_notifications
from apps.trashbins.trashbin_data_parsing import parse_trashbin_data_packet
from apps.sensors.models import Sensor, CompanySensorsLicense
from apps.sensors.tasks import generate_report_data_for_sensors


logger = get_task_logger(__name__)


class ContainerReportDataGenerator(BaseReportDataGenerator):
    def generate_temperature_record(self):
        temperature = super().generate_temperature_record()
        timestamp = self.generate_time_sample()
        return {'ctime': timestamp.isoformat(), 'sensorTemperature': temperature}

    def generate_battery_level_record(self, current_battery_level, use_charge=True):
        battery_level = super().generate_battery_level_record(current_battery_level)
        max_voltage, min_voltage = settings.ACCUM_MAX_VOLTAGE, settings.ACCUM_MIN_VOLTAGE
        voltage_diff = max_voltage - min_voltage
        battery_voltage = min_voltage + voltage_diff * (battery_level / float(100))
        timestamp = self.generate_time_sample()
        return {'ctime': timestamp.isoformat(), 'batteryVoltage': battery_voltage}

    def generate_fullness_record(self, current_fullness):
        fullness, decrease_fullness = super().generate_fullness_record(current_fullness)
        timestamp = self.generate_time_sample()
        return {'ctime': timestamp.isoformat(), 'binFilling': fullness}, decrease_fullness

    def generate_pressure_record(self):
        min_pressure, max_pressure = settings.DATA_GEN_PRESSURE_MIN, settings.DATA_GEN_PRESSURE_MAX

        pressure = random.randint(min_pressure, max_pressure)
        timestamp = self.generate_time_sample()
        return {'ctime': timestamp.isoformat(), 'sensorPressure': pressure}

    def generate_sim_balance_record(self, current_balance):
        sim_balance_top_up, max_daily_balance_withdraw = \
            settings.DATA_GEN_SIM_BALANCE_TOP_UP_AMOUNT, settings.DATA_GEN_SIM_BALANCE_MAX_DAILY_WITHDRAW

        top_up_balance = current_balance < 30 and random.random() >= 0.5
        if top_up_balance:
            balance = current_balance + sim_balance_top_up
        else:
            max_balance_withdraw_per_record = max_daily_balance_withdraw / self.record_daily_time_slice
            balance = max(round(current_balance - random.random() * max_balance_withdraw_per_record), 0)

        timestamp = self.generate_time_sample()
        return {'ctime': timestamp.isoformat(), 'simBalance': '%s rub' % float(balance)}

    def generate_error_record(self, error_types):
        error_type = super().generate_error_record(error_types)
        if not error_type:
            return None

        timestamp = self.generate_time_sample()
        return {'ctime': timestamp.isoformat(), 'Error': str(error_type)}

    def generate_humidity_record(self):
        min_humidity, max_humidity = settings.DATA_GEN_HUMIDITY_MIN, settings.DATA_GEN_HUMIDITY_MAX

        humidity = random.randint(min_humidity, max_humidity)
        timestamp = self.generate_time_sample()
        return {'ctime': timestamp.isoformat(), 'sensorHumidity': humidity}

    def generate_air_quality_record(self):
        min_air_quality, max_air_quality = settings.DATA_GEN_AIR_QUALITY_MIN, settings.DATA_GEN_AIR_QUALITY_MAX

        air_quality = random.randint(min_air_quality, max_air_quality)
        timestamp = self.generate_time_sample()
        return {'ctime': timestamp.isoformat(), 'sensorAirQuality': air_quality}


def get_container_current_stat(model, container_id, stat_field):
    try:
        actual_instance = model.objects.filter(container=container_id, actual=1).first()
    except model.DoesNotExist:
        actual_instance = model.objects.filter(container=container_id).order_by('-ctime').first()
    return 0 if actual_instance is None else getattr(actual_instance, stat_field)


def generate_report_data_for_bins(bins_qs, utc_now, record_generation_interval):
    bins_count = bins_qs.count()
    if bins_count == 0:
        logger.debug("No containers found to generate report data, skipping")
        return

    error_types = list(ErrorType.objects.values_list('code', flat=True))
    generator = ContainerReportDataGenerator(utc_now, record_generation_interval)

    bins_qs_to_paginate = bins_qs.\
        values_list('id', 'serial_number', 'is_master', 'master_bin_id', 'master_bin__serial_number').order_by('id')
    page_size = 1000
    offset = 0
    while offset < bins_count:
        current_page = bins_qs_to_paginate[offset:offset + page_size]
        for container_id, serial_number, is_master, master_bin_id, master_serial in current_page:
            message = dict()

            message['ctime'] = utc_now.isoformat()
            message['autogenerated'] = True
            data_array = []
            message['data'] = data_array
            message['version'] = '1.0-multi'

            current_fullness = get_container_current_stat(FullnessValues, container_id, 'fullness_value')
            fullness_record, fullness_decreased = generator.generate_fullness_record(current_fullness)

            if is_master:
                message['serial'] = serial_number
                data_array.append(fullness_record)

                current_battery_level = get_container_current_stat(Battery_Level, container_id, 'level')
                current_sim_balance = get_container_current_stat(SimBalance, container_id, 'balance')

                if fullness_decreased:
                    # We want to make sure collection was prior to new decreased fullness
                    timestamp = generator.generate_time_sample(utc_now - timedelta(seconds=record_generation_interval))
                    data_array.append({'ctime': timestamp.isoformat(), 'trashReceiver_switchCounter_binFilling': 1})
                    fullness_stats = FullnessStats.objects.filter(container=container_id, actual=1).first()
                    if not fullness_stats:
                        fullness_stats = FullnessStats.objects.create(start_time=timestamp, container_id=container_id)
                    fullness_stats.fullness_before_press = current_fullness + 100
                    fullness_stats.fullness_after_press = current_fullness
                    fullness_stats.save()

                data_array.append(generator.generate_temperature_record())
                data_array.append(generator.generate_pressure_record())
                data_array.append(generator.generate_battery_level_record(current_battery_level))
                # Traffic report was disabled since its absolutely fake at the moment
                # data_array.append(generator.generate_traffic_record())
                data_array.append(generator.generate_sim_balance_record(current_sim_balance))
                data_array.append(generator.generate_humidity_record())
                data_array.append(generator.generate_air_quality_record())

                error_record = generator.generate_error_record(error_types)
                if error_record:
                    data_array.append(error_record)
            elif not master_serial:
                raise Warning(f"Master bin serial is missing for satellite {serial_number}/{container_id}")
            else:
                message['serial'] = master_serial
                bins_array = []
                message['bins'] = bins_array
                satellite_data_array = []
                satellite_item = {'serial': serial_number, 'data': satellite_data_array}
                bins_array.append(satellite_item)
                satellite_data_array.append(fullness_record)

            with transaction.atomic():
                parse_trashbin_data_packet(message, container_id if is_master else master_bin_id)
            if random.random() > 0.9:
                generate_trashbin_status_notifications.delay(container_id)
        offset += page_size

    logger.debug("Report data was generated for %s containers" % bins_count)


class EnergyEfficiencyLog:
    def __init__(self):
        self.messages = []

    def log_message(self, msg):
        self.messages.append(msg)

    def log_variables(self, **kwargs):
        for k, v in kwargs.items():
            self.messages.append('{} = {}'.format(k, str(v)))

    def get_log_str(self):
        return '\n'.join([str(m) for m in self.messages])


def get_battery_charge_by_voltage(min_voltage, max_voltage, capacity, voltage):
    return capacity * max(min((voltage - min_voltage) / (max_voltage - min_voltage), 1.0), 0.0)


class EnergyEfficiencyCalculator:
    def __init__(self, log):
        self.logger = log

    def calculate_for_container(self, container, current_battery_level, previous_battery_level):
        self.logger.log_variables(
            SLEEP_PERIOD_START=container['sleep_period_start'],
            SLEEP_PERIOD_STOP=container['sleep_period_stop'],
            MIN_TEMPERATURE_FOR_CHARGING=container['min_temperature_for_charging'],
            BATTERY_MIN_VOLTAGE=container['battery_min_voltage'],
            BATTERY_MAX_VOLTAGE=container['battery_max_voltage'],
            BATTERY_CAPACITY=container['battery_capacity'],
            BATTERY_NOMINAL_VOLTAGE=container['battery_nominal_voltage'],
            STANDBY_DAYS_STOP=container['standby_days_stop'],
            DISCHARGE_PER_STANDBY_DAY=container['discharge_per_standby_day'],
            BATTERY_CHARGE_CHANGE_WINDOW_DAYS=container['battery_charge_change_window_days'],
            DISCHARGE_PER_PRESS=container['discharge_per_press'],
        )

        timestamp = datetime.utcnow()
        current_time = timestamp.time()
        if not current_battery_level or not previous_battery_level:
            self.logger.log_message('BATTERY LEVEL DATA MISSING, USING MAX')
            init_battery_level = lambda l: container['battery_max_voltage'] if not l else l  # noqa: E731
            current_battery_level = init_battery_level(current_battery_level)
            previous_battery_level = init_battery_level(previous_battery_level)

        self.logger.log_variables(
            RUN_TIMESTAMP=timestamp.isoformat(),
            CURRENT_TIME=current_time,
            CURRENT_TEMP=container['temperature'],
            CURRENT_BATTERY_LEVEL=current_battery_level,
            PREVIOUS_BATTERY_LEVEL=previous_battery_level,
        )

        enough_battery_charge_threshold = container['battery_min_voltage'] + (container['battery_max_voltage'] -
                                                                              container['battery_min_voltage']) * 0.5
        if current_battery_level >= enough_battery_charge_threshold:
            self.logger.log_message('CURRENT BATTERY LEVEL IS ABOVE THRESHOLD')
            turn_on_press = True
        else:
            battery_charge_calculator = partial(
                get_battery_charge_by_voltage, container['battery_min_voltage'], container['battery_max_voltage'],
                container['battery_capacity'])
            nominal_voltage = container['battery_nominal_voltage']
            current_battery_energy_capacity = battery_charge_calculator(current_battery_level) * nominal_voltage
            previous_battery_energy_capacity = battery_charge_calculator(previous_battery_level) * nominal_voltage

            self.logger.log_variables(
                CURRENT_BATTERY_ENERGY_CAPACITY=current_battery_energy_capacity,
                PREVIOUS_BATTERY_ENERGY_CAPACITY=previous_battery_energy_capacity,
            )

            can_press_by_temp = container['temperature'] >= container['min_temperature_for_charging']
            can_press_by_current_time = container['sleep_period_stop'] < current_time < container['sleep_period_start']
            standby_days = current_battery_energy_capacity / container['discharge_per_standby_day']
            is_enough_standby_days = standby_days > container['standby_days_stop']
            press_count_by_charge_diff = \
                (current_battery_energy_capacity - previous_battery_energy_capacity) / container['discharge_per_press']
            turn_on_press = bool(
                can_press_by_temp * can_press_by_current_time * is_enough_standby_days *
                bool(press_count_by_charge_diff >= 1))

            self.logger.log_variables(
                CAN_PRESS_BY_TEMP=can_press_by_temp,
                CAN_PRESS_BY_CURRENT_TIME=can_press_by_current_time,
                STANDBY_DAYS=standby_days,
                IS_ENOUGH_STANDBY_DAYS=is_enough_standby_days,
                PRESS_COUNT_BY_CHARGE_DIFF=press_count_by_charge_diff,
            )
        self.logger.log_message('PRESS IS TURNED {}'.format('ON' if turn_on_press else 'OFF'))

        return turn_on_press


@shared_task
def calculate_energy_efficiency(ef_for_bin_id):
    try:
        ef_for_bin = EnergyEfficiencyForContainer.objects.select_related('container', 'profile').get(pk=ef_for_bin_id)
    except EnergyEfficiencyForContainer.DoesNotExist:
        raise Warning(f"EF for bin with id {ef_for_bin_id} doesn't exist")

    container_fields = ['id', 'serial_number', 'temperature']
    profile_fields = [
        'sleep_period_start', 'sleep_period_stop',
        'min_temperature_for_charging', 'battery_min_voltage', 'battery_max_voltage', 'battery_capacity',
        'battery_nominal_voltage', 'standby_days_stop', 'discharge_per_standby_day',
        'battery_charge_change_window_days', 'discharge_per_press',
    ]
    container = {}
    container.update({f: getattr(ef_for_bin.container, f) for f in container_fields})
    container.update({f: getattr(ef_for_bin.profile, f) for f in profile_fields})
    calc_logger = EnergyEfficiencyLog()
    calculator = EnergyEfficiencyCalculator(calc_logger)
    utc_now = datetime.utcnow()
    battery_charge_change_window_start = utc_now - timedelta(days=container['battery_charge_change_window_days'])
    battery_level_qs = Battery_Level.objects\
        .filter(container_id=container['id'], ctime__lt=utc_now, ctime__gt=battery_charge_change_window_start)\
        .order_by('-ctime')
    previous_battery_level = battery_level_qs.last().volts if len(battery_level_qs) > 0 else None
    current_battery_level = battery_level_qs.first().volts if len(battery_level_qs) > 1 else previous_battery_level
    turn_on_press = calculator.calculate_for_container(container, current_battery_level, previous_battery_level)

    # Persist data in DB
    ef_for_bin.ef_last_log = calc_logger.get_log_str()
    ef_for_bin.turn_on = turn_on_press
    ef_for_bin.save()

    # Create a job for the trashbin
    create_new_task = True
    latest_task = TrashbinJobModel.objects.filter(
        trashbin_id=container['id'], type=TrashbinJobModel.PRESS_CONTROL_JOB_TYPE, status__in=['', 'SUCCESS']
    ).order_by('-ctime').first()
    if latest_task is not None:
        press_turned_on_in_latest_task = latest_task.payload['turn_on']
        create_new_task = press_turned_on_in_latest_task != turn_on_press
    if create_new_task:
        TrashbinJobModel.objects.create(trashbin_id=container['id'], type=TrashbinJobModel.PRESS_CONTROL_JOB_TYPE,
                                        payload={'turn_on': turn_on_press})


def clone_model_instance(instance, **kwargs):
    instance.pk = None
    for key, value in kwargs.items():
        setattr(instance, key, value)
    instance.save()
    return instance


class TimerHolder:
    def __init__(self):
        self._timer = None

    def update(self, timer):
        self._timer = timer

    def cancel(self):
        self._timer.cancel()


def start_interval_execution(interval, func):
    th = TimerHolder()

    def wrapped_callable():
        func()
        t = threading.Timer(interval, wrapped_callable)
        th.update(t)
        t.start()

    wrapped_callable()
    return th


def create_demo_sandbox(request: CreateDemoSandboxRequest):
    request.status = CreateDemoSandboxRequest.STATUS_IN_PROGRESS

    total_bins = Container.objects.filter(company=request.template_company).count()
    total_sensors = Sensor.objects.filter(company=request.template_company).count()
    logger.debug(f'Template company "{request.template_company}"/{request.template_company.pk} '
                 f'has {total_bins} bins & {total_sensors} sensors')

    total_report_records = settings.DEMO_DATA_GEN_DAYS * (total_bins + total_sensors)
    before_devices_ops = 5
    after_devices_ops = 5
    total_ops = total_bins + total_report_records + before_devices_ops + after_devices_ops
    completed_ops = 0

    def progress_updater():
        request.progress = round(max(min(completed_ops / total_ops, 1), 0) * 100)
        request.mtime = timezone.now()
        request.save()

    timer_holder = start_interval_execution(60, progress_updater)  # Updates every minute

    try:
        # Wrap new sandbox company creation in a transaction
        with transaction.atomic():
            company = clone_model_instance(
                Company.objects.get(pk=request.template_company.pk), name=request.company_name,
                username_prefix=request.username_prefix, lang=request.lang)

            raw_sectors_translations = DemoSandboxTranslation.objects.filter(
                object_type=DemoSandboxTranslation.SECTOR_OBJECT_TYPE, lang=request.lang, key='name')
            logger.debug(
                f"Found {len(raw_sectors_translations)} sector name translation(s) for language '{request.lang}'.")
            sectors_translations_dict = {trans.object_id: trans.value for trans in raw_sectors_translations}
            sectors_mapping = {}
            for sector in Sectors.objects.filter(company=request.template_company):
                old_sector_pk = sector.pk
                effective_name = sectors_translations_dict[sector.name] \
                    if sector.name in sectors_translations_dict else sector.name
                new_sector = clone_model_instance(sector, name=effective_name, company=company)
                sectors_mapping[old_sector_pk] = new_sector
            # Removing sector created by default
            Sectors.objects.filter(company=company).exclude(
                pk__in=[sector.pk for sector in sectors_mapping.values()]).delete()
            # Create company licenses
            demo_license_lifespan = 100  # days
            licenses_end_day = date.today() + timedelta(days=demo_license_lifespan)
            if total_bins > 0:
                CompanyTrashbinsLicense.objects.create(company=company, end=licenses_end_day)
            if total_sensors > 0:
                usage_balance = total_sensors * demo_license_lifespan
                CompanySensorsLicense.objects.create(company=company, end=licenses_end_day, usage_balance=usage_balance)

            completed_ops += before_devices_ops

            unique_suffix = binascii.hexlify(os.urandom(4)).decode('utf-8')
            devices_ctime = timezone.now()
            master_bins_mapping = {}

            raw_bins_address_translations = DemoSandboxTranslation.objects.filter(
                object_type=DemoSandboxTranslation.CONTAINER_OBJECT_TYPE, lang=request.lang, key='address')
            logger.debug(
                f"Found {len(raw_bins_address_translations)} trashbin address translation(s) "
                f"for language '{request.lang}'.")
            bins_address_translations_dict = {trans.object_id: trans.value for trans in raw_bins_address_translations}

            for master_bin in Container.objects.filter(company=request.template_company, is_master=True):
                old_bin_pk = master_bin.pk
                effective_address = bins_address_translations_dict[master_bin.serial_number]\
                    if master_bin.serial_number in bins_address_translations_dict\
                    else master_bin.address
                new_master_bin = clone_model_instance(
                    master_bin, serial_number=f'{master_bin.serial_number}-{unique_suffix}', company=company,
                    sector=sectors_mapping[master_bin.sector.pk], ctime=devices_ctime, autogenerate_data=True,
                    address=effective_address)
                master_bins_mapping[old_bin_pk] = new_master_bin
                completed_ops += 1

            for sat_bin in Container.objects.filter(company=request.template_company, is_master=False):
                old_master_bin_pk = sat_bin.master_bin_id
                effective_address = sat_bin.address
                if sat_bin.serial_number in bins_address_translations_dict:
                    effective_address = bins_address_translations_dict[sat_bin.serial_number]\
                        if bins_address_translations_dict[sat_bin.serial_number] != ''\
                        else master_bins_mapping[old_master_bin_pk].address
                new_sat_bin = clone_model_instance(
                    sat_bin, serial_number=f'{sat_bin.serial_number}-{unique_suffix}', company=company,
                    sector=sectors_mapping[sat_bin.sector.pk], ctime=devices_ctime, autogenerate_data=True,
                    master_bin=None, address=effective_address)
                master_bins_mapping[old_master_bin_pk].satellites.add(new_sat_bin)
                completed_ops += 1

            raw_sensors_address_translations = DemoSandboxTranslation.objects.filter(
                object_type=DemoSandboxTranslation.SENSOR_OBJECT_TYPE, lang=request.lang, key='address')
            logger.debug(
                f"Found {len(raw_sensors_address_translations)} sensor address translation(s) "
                f"for language '{request.lang}'.")
            sensors_address_translations_dict =\
                {trans.object_id: trans.value for trans in raw_sensors_address_translations}

            for sensor in Sensor.objects.filter(company=request.template_company):
                effective_address = sensors_address_translations_dict[sensor.serial_number] \
                    if sensor.serial_number in sensors_address_translations_dict \
                    else sensor.address
                clone_model_instance(
                    sensor, serial_number=f'{sensor.serial_number}-{unique_suffix}', company=company,
                    sector=sectors_mapping[sensor.sector.pk], ctime=devices_ctime, autogenerate_data=True,
                    address=effective_address, hardware_identity=f'{sensor.hardware_identity}-{unique_suffix}')
                completed_ops += 1

            user_model = get_user_model()
            users_to_create = [
                ('admin', get_user_model().objects.make_random_password(), UsersToCompany.ADMIN_ROLE),
                ('driver', None, UsersToCompany.DRIVER_ROLE),
            ]
            for username, pwd, role in users_to_create:
                new_user = user_model.objects.create(username=request.username_prefix + username)
                new_user.set_password(pwd)
                new_user.save()
                new_user.user_to_company = UsersToCompany()
                new_user.user_to_company.company = company
                new_user.user_to_company.role = role
                new_user.user_to_company.save()
            admin_username, admin_password = request.username_prefix + users_to_create[0][0], users_to_create[0][1]

            completed_ops += after_devices_ops

        # Generate report data without a long upper level transaction to increase scalability
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        days_to_generate_range = range(settings.DEMO_DATA_GEN_DAYS)
        # TODO: Replace hardcoded string with name generated from __module__ & __name__
        record_generation_interval = get_record_generation_interval('apps.main.tasks.generate_report_data')

        for day in reversed(days_to_generate_range):
            day_timestamp = utc_now - timedelta(days=day)
            generate_report_data_for_bins(
                Container.objects.filter(company=company), day_timestamp, record_generation_interval)
            completed_ops += total_bins
            generate_report_data_for_sensors(
                Sensor.objects.filter(company=company), day_timestamp, record_generation_interval)
            completed_ops += total_sensors

    except Exception:
        logger.exception(f"Processing of demo sandbox request with ID '{request.pk}' failed.")
        request.status = CreateDemoSandboxRequest.STATUS_FAILED
    else:
        request.admin_username = admin_username
        request.admin_password = admin_password
        request.progress = 100
        request.status = CreateDemoSandboxRequest.STATUS_SUCCESS

    timer_holder.cancel()
    request.mtime = timezone.now()
    request.save()


@shared_task
def process_all_demo_sandbox_requests():
    for new_request in CreateDemoSandboxRequest.objects.filter(status=CreateDemoSandboxRequest.STATUS_NEW):
        create_demo_sandbox(new_request)


@shared_task
def process_single_demo_sandbox_request(request_id):
    request = CreateDemoSandboxRequest.objects.get(pk=request_id)
    if request.status != CreateDemoSandboxRequest.STATUS_NEW:
        raise Warning(f"Can't process demo sandbox request with ID '{request.pk}' "
                      f"since it's either already processed or now in progress.")

    create_demo_sandbox(request)


@shared_task
def notify_about_trashbin_message(trashbin_data_id):
    if not settings.TRASHBIN_NOTIFICATIONS_ENABLED:
        logger.debug("Trashbin notifications are disabled")
        return

    trashbin_data = TrashbinData.objects.select_related('trashbin').get(pk=trashbin_data_id)
    serial = trashbin_data.trashbin.serial_number
    if settings.TRASHBIN_NOTIFICATIONS_SEND_ALL:
        send_current_message = 'autogenerated' not in trashbin_data.data_json
    else:
        try:
            SlackEnabledTrashbin.objects.get(serial_number=serial)
        except SlackEnabledTrashbin.DoesNotExist:
            send_current_message = False
        else:
            send_current_message = True

    if not send_current_message:
        logger.debug(f"Notification from '{serial}' muted")
        return

    notification_message = "Message from '%s'\n\n" % (serial,) + \
                           json.dumps(trashbin_data.data_json, sort_keys=True, indent=4)
    query_string = urllib.parse.urlencode(
        {'chat_id': settings.TRASHBIN_NOTIFICATIONS_TG_BOT_CHAT_ID, 'text': notification_message})
    tg_bot_request_url = 'https://api.telegram.org/bot{API_TOKEN}/sendMessage?{QUERY}'.\
        format(API_TOKEN=settings.TRASHBIN_NOTIFICATIONS_TG_BOT_API_KEY, QUERY=query_string)
    requests.get(tg_bot_request_url)
