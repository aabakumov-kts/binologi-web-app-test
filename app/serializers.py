from django.contrib.auth.models import User
from rest_framework import serializers
from django.utils.text import capfirst
from django.utils.translation import ugettext_lazy as _

from apps.core.serializers import CitySerializer, LocationSerializer, FullnessSerializer, SectorSerializer
from app.models import Container, MobileAppTranslation


class ContainerSerializer(serializers.ModelSerializer):
    city = CitySerializer()
    sector = SectorSerializer()
    fullness = FullnessSerializer()
    location = LocationSerializer()
    satellites_count = serializers.IntegerField(read_only=True)
    current_fullness_volume = serializers.FloatField(read_only=True)
    any_active_routes = serializers.BooleanField(read_only=True)
    low_battery_level = serializers.BooleanField(read_only=True)
    any_active_errors = serializers.BooleanField(read_only=True)

    class Meta:
        model = Container
        fields = (
            'id', 'serial_number', 'is_master', 'address', 'current_fullness_volume', 'city', 'sector', 'fullness',
            'location', 'satellites_count', 'battery', 'temperature', 'air_quality', 'any_active_routes',
            'low_battery_level', 'any_active_errors',
        )


class ApiAuthTokenSerializer(serializers.Serializer):
    username = serializers.CharField(label=capfirst(_("username")))
    password = serializers.CharField(label=capfirst(_("password")), style={'input_type': 'password'})

    def authenticate(self, username=None, password=None, **kwargs):
        user_model = User
        if username is None:
            username = kwargs.get(user_model.USERNAME_FIELD)
        try:
            user = user_model.objects.get(username=username)
        except user_model.DoesNotExist:
            return None
        return user if user.check_password(password) else None

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            user = self.authenticate(username=username, password=password)

            if user:
                if not user.is_active:
                    msg = 'User account is disabled.'
                    raise serializers.ValidationError(msg)
            else:
                msg = 'Unable to log in with provided credentials.'
                raise serializers.ValidationError(msg)
        else:
            msg = 'Must include "username" and "password".'
            raise serializers.ValidationError(msg)

        attrs['user'] = user
        return attrs


class MobileAppTranslationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MobileAppTranslation
        fields = ('lang', 'string_name', 'string_text')
