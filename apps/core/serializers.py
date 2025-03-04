from rest_framework import serializers

from apps.core.data import Fullness
from apps.core.models import City, Sectors


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ('id', 'title')


class LocationSerializer(serializers.Serializer):
    x = serializers.FloatField()
    y = serializers.FloatField()


class FullnessSerializer(serializers.Serializer):
    title = serializers.CharField()
    value = serializers.IntegerField()

    def get_attribute(self, instance):
        fullness = Fullness.get_member(instance.fullness)
        fullness.value = instance.fullness
        return fullness


class SectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sectors
        fields = ('id', 'name')
