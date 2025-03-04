import math

from rest_framework import serializers

from apps.core.serializers import CitySerializer, LocationSerializer, FullnessSerializer, SectorSerializer
from apps.sensors.models import Sensor


class TimestampField(serializers.Field):
    def to_representation(self, value):
        return math.floor(value.timestamp())


class SensorFullnessSerializer(FullnessSerializer):
    latest_data_timestamp = TimestampField()

    def get_attribute(self, instance):
        base_result = super().get_attribute(instance)
        base_result.latest_data_timestamp = instance.latest_data_timestamp
        return base_result


class SensorSerializer(serializers.ModelSerializer):
    city = CitySerializer()
    fullness = SensorFullnessSerializer()
    location = LocationSerializer()
    low_battery_level = serializers.BooleanField(read_only=True)
    any_active_routes = serializers.BooleanField(read_only=True)
    sector = SectorSerializer()
    current_fullness_volume = serializers.SerializerMethodField()

    class Meta:
        model = Sensor
        fields = (
            'id', 'serial_number', 'address', 'city', 'sector', 'fullness', 'location', 'battery', 'temperature',
            'low_battery_level', 'any_active_routes', 'current_fullness_volume', 'mount_type',
        )

    def get_current_fullness_volume(self, obj):
        container_type_max_volume_in_liters = obj.container_type.volume * 1000
        return (obj.fullness / 100.0) * container_type_max_volume_in_liters
