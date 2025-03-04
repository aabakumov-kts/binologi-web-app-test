from dataclasses import dataclass
from django.utils.translation import ugettext as _
from enum import Enum
from typing import Optional

from apps.core.utils import (
    notification_subject_generators, notification_message_generators, notification_link_generators,
)
from apps.sensors.models import SensorJob, Sensor
from apps.sensors.utils import parse_sensor_message_payload, serialize_sensor_message_payload


class SensorsNotificationTypes(Enum):
    SENSOR_FULLNESS_ABOVE_THRESHOLD = 'SENSOR_FULLNESS_ABOVE_THRESHOLD'
    SENSOR_BATTERY_BELOW_THRESHOLD = 'SENSOR_BATTERY_BELOW_THRESHOLD'
    SENSOR_FIRE_DETECTED = 'SENSOR_FIRE_DETECTED'


def register_notification_generators():
    from apps.core.helpers import CompanyDeviceProfile

    def primary_subject_generator(n):
        return _('Sensor %(serial_number)s') % {'serial_number': n.actor.serial_number}

    def primary_link_generator(n):
        return f'/main/?device_profile={CompanyDeviceProfile.SENSOR.value}&lat={n.actor.location.y}' \
               f'&lng={n.actor.location.x}'

    for nt in [
        SensorsNotificationTypes.SENSOR_FULLNESS_ABOVE_THRESHOLD,
        SensorsNotificationTypes.SENSOR_BATTERY_BELOW_THRESHOLD,
        SensorsNotificationTypes.SENSOR_FIRE_DETECTED,
    ]:
        notification_subject_generators[nt.value] = primary_subject_generator
        notification_link_generators[nt.value] = primary_link_generator

    notification_message_generators[SensorsNotificationTypes.SENSOR_FULLNESS_ABOVE_THRESHOLD.value] = \
        lambda n: _('Sensor fullness is %(fullness)s percent') % {'fullness': n.data['fullness_level']}
    notification_message_generators[SensorsNotificationTypes.SENSOR_BATTERY_BELOW_THRESHOLD.value] = \
        lambda n: _('Sensor battery level is %(battery)s percent') % {'battery': n.data['battery_level']}
    notification_message_generators[SensorsNotificationTypes.SENSOR_FIRE_DETECTED.value] = \
        lambda n: _('Fire and/or high temperature detected')


@dataclass
class ConfigureJobDS:
    pk: Optional[int]
    payload_dict: dict
    payload_length_left: int


def arrange_sensor_config_jobs(sensor_ids, field_mapping, fields, add_fetch=False, field_values_source=None):
    if not add_fetch and field_values_source is None:
        return  # Nothing to do

    payload_max_length = next(f.max_length for f in SensorJob._meta.get_fields() if f.name == 'payload')

    def serialized_field_length(field_name, field_value):
        return len(field_name) + len(field_value) + 2  # backtick + colon

    for sensor_id in sensor_ids:
        existing_jobs = [
            ConfigureJobDS(job.pk, parse_sensor_message_payload(job.payload), payload_max_length - len(job.payload))
            for job in SensorJob.objects.filter(
                sensor_id=sensor_id, type=SensorJob.UPDATE_CONFIG_JOB_TYPE, status='').order_by('-ctime')
        ]
        new_jobs = []

        def process_jobs_for_field(payload_key, existing_job_with_key_handler, payload_diff, new_value):
            # Try to look up existing job with this field
            try:
                existing_job = next(job for job in existing_jobs if payload_key in job.payload_dict)
            except StopIteration:
                existing_job = None

            if existing_job and existing_job_with_key_handler(existing_job):
                return

            # Try to look up existing job with enough payload length left
            try:
                existing_job = next(job for job in existing_jobs if job.payload_length_left + payload_diff >= 0)
            except StopIteration:
                existing_job = None

            if existing_job:
                existing_job.payload_dict[payload_key] = new_value
                existing_job.payload_length_left += payload_diff
            else:
                # Create new job if there's no room in existing jobs
                if len(new_jobs) == 0:
                    new_jobs.append(ConfigureJobDS(None, dict(), payload_max_length))
                current_job = new_jobs[-1]
                if current_job.payload_length_left + payload_diff < 0:
                    new_jobs.append(ConfigureJobDS(None, dict(), payload_max_length))
                    current_job = new_jobs[-1]
                current_job.payload_dict[payload_key] = new_value
                current_job.payload_length_left += payload_diff

        for field in fields:
            if field_values_source is not None:
                set_field_payload_key = f's/{field_mapping[field]}'
                new_value_str = str(field_values_source[field] if isinstance(field_values_source, dict)
                                    else getattr(field_values_source, field))

                def update_value_in_existing_job_with_key(existing_job):
                    current_value_str = existing_job.payload_dict[set_field_payload_key]
                    payload_diff = len(current_value_str) - len(new_value_str)
                    if existing_job.payload_length_left + payload_diff < 0:
                        del existing_job.payload_dict[set_field_payload_key]
                        existing_job.payload_length_left +=\
                            serialized_field_length(set_field_payload_key, current_value_str)
                        return False
                    existing_job.payload_dict[set_field_payload_key] = new_value_str
                    existing_job.payload_length_left += payload_diff
                    return True

                process_jobs_for_field(
                    set_field_payload_key,
                    update_value_in_existing_job_with_key,
                    -serialized_field_length(set_field_payload_key, new_value_str),
                    new_value_str,
                )

            if add_fetch:
                process_jobs_for_field(
                    f'g/{field_mapping[field]}',
                    lambda _: True,
                    -(len(f'g/{field_mapping[field]}') + 1),  # backtick
                    None
                )

        for job in existing_jobs:
            updated_payload = serialize_sensor_message_payload(job.payload_dict)
            updated_rows = SensorJob.objects.filter(pk=job.pk, status='').update(payload=updated_payload)
            if updated_rows == 0:  # This means job was already processed
                new_jobs.append(ConfigureJobDS(None, job.payload_dict, job.payload_length_left))

        for job in new_jobs:
            job_payload_str = serialize_sensor_message_payload(job.payload_dict)
            SensorJob.objects.create(
                sensor_id=sensor_id, type=SensorJob.UPDATE_CONFIG_JOB_TYPE, payload=job_payload_str)


def get_sensors_qs_for_request(request):
    if request.uac.is_superadmin:
        # TODO: This is an unbounded data set
        return Sensor.objects.all()
    if request.uac.has_per_company_access:
        return Sensor.objects.filter(company=request.uac.company)
    return Sensor.objects.none()
