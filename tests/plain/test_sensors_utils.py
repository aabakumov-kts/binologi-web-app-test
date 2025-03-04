import pytz
import unittest

from datetime import date, datetime, timedelta

from apps.sensors.utils import build_sensor_connect_schedule


class SensorConnectScheduleTests(unittest.TestCase):
    def test_returns_empty_schedule_for_negative_days_number(self):
        # Arrange & act
        schedule = build_sensor_connect_schedule(date.today(), 0, 24, -1, 1)
        # Assert
        self.assertEqual(0, len(schedule))

    def test_returns_empty_schedule_for_zero_days_number(self):
        # Arrange & act
        schedule = build_sensor_connect_schedule(date.today(), 0, 24, 0, 1)
        # Assert
        self.assertEqual(0, len(schedule))

    def test_returns_correct_schedule_for_single_day_and_regular_hours(self):
        # Arrange
        today = date.today()
        # Act
        schedule = build_sensor_connect_schedule(today, 0, 24, 1, 60 * 12)
        # Assert
        self.assertEqual(3, len(schedule))
        self.assertEqual(datetime(today.year, today.month, today.day, tzinfo=pytz.utc), schedule[0])
        self.assertEqual(datetime(today.year, today.month, today.day, 12, tzinfo=pytz.utc), schedule[1])
        self.assertEqual(datetime(today.year, today.month, today.day, tzinfo=pytz.utc) + timedelta(days=1), schedule[2])

    def test_returns_correct_schedule_for_single_day_and_inverse_hours(self):
        # Arrange
        today = date.today()
        # Act
        schedule = build_sensor_connect_schedule(today, 18, 6, 1, 60 * 6)
        # Assert
        self.assertEqual(3, len(schedule))
        self.assertEqual(datetime(today.year, today.month, today.day, 18, tzinfo=pytz.utc), schedule[0])
        self.assertEqual(datetime(today.year, today.month, today.day, tzinfo=pytz.utc) + timedelta(days=1), schedule[1])
        self.assertEqual(
            datetime(today.year, today.month, today.day, 6, tzinfo=pytz.utc) + timedelta(days=1), schedule[2])

    def test_returns_correct_schedule_for_multiple_days(self):
        # Arrange
        today = date.today()
        # Act
        schedule = build_sensor_connect_schedule(today, 6, 7, 3, 60 * 2)
        # Assert
        self.assertEqual(3, len(schedule))
        base_datetime = datetime(today.year, today.month, today.day, 6, tzinfo=pytz.utc)
        self.assertEqual(base_datetime, schedule[0])
        self.assertEqual(base_datetime + timedelta(days=1), schedule[1])
        self.assertEqual(base_datetime + timedelta(days=2), schedule[2])
