import pytz

from datetime import datetime, timedelta


def _build_schedule_datetime(date, hour):
    return datetime(date.year, date.month, date.day, tzinfo=pytz.utc) + timedelta(days=1) if hour == 24 \
        else datetime(date.year, date.month, date.day, hour, tzinfo=pytz.utc)


def build_sensor_connect_schedule(schedule_start_date, start_hour, stop_hour, days_to_build_schedule_for, interval):
    schedule_start = _build_schedule_datetime(schedule_start_date, start_hour)
    schedule_end = _build_schedule_datetime(schedule_start_date, stop_hour)
    if schedule_end < schedule_start:
        schedule_end += timedelta(days=1)
    schedule_moments = []
    while days_to_build_schedule_for > 0:
        current_moment = schedule_start
        while current_moment <= schedule_end:
            schedule_moments.append(current_moment)
            current_moment += timedelta(seconds=interval * 60)
        schedule_start += timedelta(days=1)
        schedule_end += timedelta(days=1)
        days_to_build_schedule_for -= 1
    return schedule_moments


def parse_sensor_message_payload(payload_str):
    kv_pairs = (ln.split(':') for ln in payload_str.split('`'))
    return {k: vals[0] if len(vals) > 0 else None for [k, *vals] in kv_pairs}


def serialize_sensor_message_payload(payload_dict):
    return '`'.join([f'{key}:{value}' if value else key for key, value in payload_dict.items()])
