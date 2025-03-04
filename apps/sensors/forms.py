from django import forms
from django.utils.translation import ugettext_lazy as _

from apps.core.form_fields import CityDatalistField
from apps.core.models import City, Sectors
from apps.core.widgets import PointInput
from apps.sensors.models import Sensor


# TODO: Remove this indirection when the issue led to it will be resolved
#
# This is exactly the same issue as with ContainerForm
# Check out app/forms.py:159 for details
def get_sensor_form_class():
    class SensorForm(forms.ModelForm):
        city = CityDatalistField(label=_("city_upper"))

        def __init__(self, request, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if not request.uac.is_superadmin:
                self.fields['serial_number'].disabled = True
                self.fields['sim_number'].disabled = True
            if request.uac.has_per_company_access:
                del self.fields['company']
                self.fields['sector'].queryset = Sectors.objects.filter(company=request.uac.company)

        class Meta:
            model = Sensor
            fields = (
                'serial_number', 'sim_number', 'company', 'country', 'city', 'address', 'container_type',
                'waste_type', 'sector', 'location', 'disabled'
            )
            labels = {
                'sim_number': _('SIM/eSIM number / ICCID'),
            }
            help_texts = {
                'sim_number': None,
            }
            widgets = {
                'location': PointInput(),
            }

        def clean_city(self):
            data = self.cleaned_data
            country = data.get('country')
            city = data.get('city')
            if not (country and city):
                return
            city, created = City.objects.get_or_create(country=country, title=city)
            return city
    return SensorForm


class SensorControlSettingsForm(forms.Form):
    connection_schedule_start = forms.IntegerField(
        label=_('Connection schedule start'), min_value=0, max_value=24, required=False,
        widget=forms.NumberInput(attrs={'placeholder': _('0-24 hours with 0 as default')}))
    connection_schedule_stop = forms.IntegerField(
        label=_('Connection schedule stop'), min_value=0, max_value=24, required=False,
        widget=forms.NumberInput(attrs={'placeholder': _('0-24 hours with 24 as default')}))
    measurement_interval = forms.IntegerField(
        label=_('Connection interval'), min_value=5, max_value=1440, required=False,
        widget=forms.NumberInput(attrs={'placeholder': _('5-1440 minutes with 30 as default')}))
    gps_in_every_connection = forms.NullBooleanField(
        label=_('Require GPS position in every connection'), required=False)
    fire_min_temp = forms.IntegerField(
        label=_('Minimal temperature for fire alarm'), min_value=50, max_value=80, required=False,
        widget=forms.NumberInput(attrs={'placeholder': _('50-80 °C with 70 as default')}))
    accelerometer_sensitivity = forms.IntegerField(
        label=_('Accelerometer sensitivity'), min_value=20, max_value=125, required=False,
        widget=forms.NumberInput(attrs={'placeholder': _('20-125 with 50 as default')}))
    close_measurement_on_flag = forms.NullBooleanField(
        label=_('Enable close range measurement mode'), required=False)
    mid_measurement_on_flag = forms.NullBooleanField(
        label=_('Enable mid range measurement mode'), required=False)
    far_measurement_on_flag = forms.NullBooleanField(
        label=_('Enable far range measurement mode'), required=False)
    accelerometer_delay = forms.IntegerField(
        label=_('Delay of accelerometer response'), min_value=0, max_value=300, required=False,
        widget=forms.NumberInput(attrs={'placeholder': _('0-300 seconds 0 as default')}))
