import math
import random

from datetime import timedelta
from django.conf import settings
from django_celery_beat import models as django_celery_beat_models


SECONDS_PER_PERIOD = {
    django_celery_beat_models.DAYS: 86400,         # 60 seconds per minute * 60 minutes per hour * 24 hours per day
    django_celery_beat_models.HOURS: 3600,         # 60 seconds per minute * 60 minutes per hour
    django_celery_beat_models.MINUTES: 60,         # 60 seconds per minute
    django_celery_beat_models.SECONDS: 1,
    django_celery_beat_models.MICROSECONDS: 1e-6,  # 0.000001 seconds per microsecond
}


class BaseReportDataGenerator:
    def __init__(self, utc_now, record_generation_interval):
        self.utc_now = utc_now
        self.record_generation_interval = record_generation_interval
        self.record_daily_time_slice =\
            SECONDS_PER_PERIOD[django_celery_beat_models.DAYS] / float(record_generation_interval)

    def calculate_time_of_day_factor(self):
        seconds_per_day = SECONDS_PER_PERIOD[django_celery_beat_models.DAYS]
        time_of_day_delta = self.utc_now - self.utc_now.replace(hour=0, minute=0, second=0, microsecond=0)
        cos_value = math.cos(((time_of_day_delta.total_seconds() / seconds_per_day) * 2 - 1) * math.pi)
        return (cos_value + 1) / float(2)

    def generate_time_sample(self, utc_now=None):
        interval_start = (utc_now or self.utc_now) - timedelta(seconds=self.record_generation_interval)
        return interval_start + timedelta(seconds=random.randint(0, self.record_generation_interval))

    def generate_temperature_record(self):
        min_temperature, max_temperature, randomization_delta = \
            settings.DATA_GEN_TEMPERATURE_MIN, settings.DATA_GEN_TEMPERATURE_MAX, \
            settings.DATA_GEN_TEMPERATURE_RANDOM_DELTA

        time_of_day_factor = self.calculate_time_of_day_factor()
        randomization_factor = random.randint(-randomization_delta, randomization_delta)
        temperature = min_temperature + (max_temperature - min_temperature) * time_of_day_factor + randomization_factor
        return round(temperature)

    def generate_battery_level_record(self, current_battery_level, use_charge=True):
        max_daily_battery_discharge, max_daily_battery_charge = \
            settings.DATA_GEN_BATTERY_MAX_DAILY_DISCHARGE, settings.DATA_GEN_BATTERY_MAX_DAILY_CHARGE

        charge_battery = current_battery_level < 10 and random.random() >= 0.5
        if charge_battery:
            battery_level = current_battery_level + 90
        else:
            max_battery_charge_per_record = max_daily_battery_charge / self.record_daily_time_slice
            max_battery_discharge_per_record = max_daily_battery_discharge / self.record_daily_time_slice
            time_of_day_factor = self.calculate_time_of_day_factor()
            battery_level = min(max(round(
                current_battery_level - random.random() * max_battery_discharge_per_record +
                (random.random() * max_battery_charge_per_record * time_of_day_factor if use_charge else 0)
            ), 0), 100)

        return battery_level

    def generate_fullness_record(self, current_fullness):
        max_daily_fullness_increase = settings.DATA_GEN_FULLNESS_MAX_DAILY_INCREASE

        decrease_fullness = current_fullness > 90 and random.random() >= 0.5
        if decrease_fullness:
            fullness = current_fullness - 90
        else:
            max_increase_per_record = max_daily_fullness_increase / self.record_daily_time_slice
            fullness = min(round(current_fullness + random.random() * max_increase_per_record), 100)

        return fullness, decrease_fullness

    def generate_error_record(self, error_types):
        error_probability = settings.DATA_GEN_ERROR_PROBABILITY

        error_occured = random.random() < (error_probability / float(100))
        if not error_occured:
            return None

        error_type_index = random.randint(0, len(error_types) - 1)
        return error_types[error_type_index]


def get_record_generation_interval(task_name):
    try:
        current_periodic_task = django_celery_beat_models.PeriodicTask.objects.filter(
            task=task_name, enabled=True, interval__isnull=False).get()
    except django_celery_beat_models.PeriodicTask.DoesNotExist:
        raise Warning(f"Failed to found scheduled PeriodicTask '{task_name}' for current execution")
    return current_periodic_task.interval.every * SECONDS_PER_PERIOD[current_periodic_task.interval.period]
