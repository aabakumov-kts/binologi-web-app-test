from django import forms

from apps.core.models import City
from apps.core.widgets import CityWidget


class CityDatalistField(forms.CharField):
    widget = CityWidget

    def prepare_value(self, value):
        if isinstance(value, City):
            return value.title
        if isinstance(value, int):
            city = City.objects.get(pk=value)
            return city.title
        return value
