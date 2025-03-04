# coding=utf-8
from django import forms
from django.utils.text import capfirst
from django.utils.translation import ugettext_lazy as _
from timezone_field import TimeZoneFormField
from timezone_field.utils import add_gmt_offset_to_choices
import pytz

from apps.core.models import UsersToCompany, Sectors
from apps.core.form_fields import CityDatalistField
from apps.core.helpers import CompanyDeviceProfile
from apps.core.widgets import PointInput
from app.models import Company, User, Container, City, DriverUnavailabilityPeriod
from apps.main.helpers import get_effective_company_device_profile


# First element of each tuple in the array - number of containers
# Second element of each tuple - tuple of max users by roles: SA, OP, DR
TRASHBINS_MAX_USERS_PER_COMPANY_BY_ROLE = [
    (1, (1, 1, 3)),
    (5, (1, 2, 3)),
    (10, (1, 2, 3)),
    (20, (1, 3, 5)),
    (50, (1, 4, 10)),
    (100, (1, 5, 15)),
    (175, (1, 7, 21)),
    (300, (1, 10, 30)),
    (500, (2, 15, 45)),
    (1000, (3, 30, 90)),
]

SENSORS_MAX_USERS_PER_COMPANY_BY_ROLE = [
    (10, (1, 1, 3)),
    (50, (1, 2, 3)),
    (100, (1, 2, 3)),
    (200, (1, 3, 5)),
    (500, (1, 4, 10)),
    (1000, (1, 5, 15)),
    (1750, (1, 7, 21)),
    (3000, (1, 10, 30)),
    (5000, (2, 15, 45)),
    (10000, (3, 30, 90)),
]

ROLE_INDEX_IN_MAX_USERS_BY_ROLE = [
    UsersToCompany.ADMIN_ROLE,
    UsersToCompany.OPERATOR_ROLE,
    UsersToCompany.DRIVER_ROLE,
]

NULLABLE_TIMEZONES = add_gmt_offset_to_choices([
    (pytz.timezone(tz), tz.replace('_', ' ')) for tz in pytz.common_timezones
])
NULLABLE_TIMEZONES.insert(0, (None, capfirst(_('same as company'))))


class UserForm(forms.ModelForm):
    new_password = forms.CharField(
        label=capfirst(_('password')),
        initial='',
        required=False,
        widget=forms.PasswordInput,
    )
    company = forms.ModelChoiceField(
        queryset=Company.objects.all(),
        label=capfirst(_('company')),
        required=True,
    )
    role = forms.ChoiceField(
        choices=UsersToCompany.ROLES,
        initial=UsersToCompany.OPERATOR_ROLE,
        label=capfirst(_('role')),
        required=True,
    )
    timezone = TimeZoneFormField(required=False, label=capfirst(_('timezone')), choices=NULLABLE_TIMEZONES)
    comment = forms.CharField(label=capfirst(_('comment')), initial='', required=False, max_length=150)

    class Meta:
        model = User
        fields = ('username',)
        labels = {
            'username': _('Login'),
        }
        help_texts = {
            'username': None,
        }

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and hasattr(self.instance, 'user_to_company'):
            self.fields['comment'].initial = self.instance.user_to_company.comment

        if request.uac.has_per_company_access:
            companies = Company.objects.filter(pk=request.uac.company_id)
            self.fields['company'].queryset = companies
            self.fields['company'].initial = request.uac.company_id
            self.fields['company'].empty_label = None

            if self.instance and request.user == self.instance:
                self.fields['role'].disabled = True

        if 'company' in self.initial and 'username' in self.initial:
            username = self.initial['username']
            company = self.initial['company']
            username_prefix_defined = company.username_prefix is not None and bool(company.username_prefix.strip())
            username_prefix = company.username_prefix.strip() if username_prefix_defined else None
            if username_prefix is not None and username.startswith(username_prefix):
                self.initial['username'] = username[len(username_prefix):]

        if self.instance.pk is None:
            self.fields['new_password'].required = True

        self.devices_profile = get_effective_company_device_profile(request)

    def clean_company(self):
        company = self.cleaned_data.get('company')
        role = self.cleaned_data.get('role')

        if role != UsersToCompany.ADMIN_ROLE and not company:
            raise forms.ValidationError(_('Choice a company.'))

        return company

    def clean(self):
        cleaned_data = super().clean()

        company = cleaned_data.get('company')
        role = cleaned_data.get('role')
        users_to_company_qs = UsersToCompany.objects.filter(company=company, role=role)
        if self.instance.id is not None:
            users_to_company_qs = users_to_company_qs.exclude(user=self.instance)
        max_users_lookup = TRASHBINS_MAX_USERS_PER_COMPANY_BY_ROLE \
            if self.devices_profile == CompanyDeviceProfile.TRASHBIN else SENSORS_MAX_USERS_PER_COMPANY_BY_ROLE
        total_devices_count = company.container_set.count() \
            if self.devices_profile == CompanyDeviceProfile.TRASHBIN else company.sensor_set.count()
        try:
            max_users_by_role = next(tier[1] for tier in max_users_lookup if tier[0] >= total_devices_count)
        except StopIteration:
            max_users_by_role = max_users_lookup[-1][1]

        total_company_users_in_role = users_to_company_qs.count()
        max_users_per_company_in_role = max_users_by_role[ROLE_INDEX_IN_MAX_USERS_BY_ROLE.index(role)]
        if total_company_users_in_role + 1 > max_users_per_company_in_role:
            raise forms.ValidationError(
                _('Too many users of role per company, limit is %(value)s'),
                params={'value': max_users_per_company_in_role},
            )

        username = cleaned_data.get('username')
        company = cleaned_data.get('company')
        username_prefix_defined = company.username_prefix is not None and bool(company.username_prefix.strip())
        username_prefix = company.username_prefix.strip() if username_prefix_defined else None
        if username_prefix is not None and not username.startswith(username_prefix):
            cleaned_data['username'] = username_prefix + username


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ('name', 'country', 'minsim', 'username_prefix', 'timezone')
        labels = {
            'username_prefix': _('username prefix'),
        }


# TODO: Remove this indirection when the issue led to it will be resolved
#
# There is a bug in smart_selects.form_fields.GroupedModelSelect._get_choices
# It results in fetching of options eagerly rather than lazily
# Because of that Django couldn't start in case app_sectors table isn't present in DB
#
# Last release of django-smart-selects was on 26 Feb 2018 with >30 open issues on GitHub
# Hence this unlikely to be resolved if submitted as issue, PR could work better
# We can establish a fork, fix the issue, switch to fork and submit a PR
# Whenever PR will be accepted we can switch back to main repo and delete our fork
def get_container_form_class():
    class ContainerForm(forms.ModelForm):
        city = CityDatalistField(label=_("city_upper"))

        def __init__(self, request, *args, **kwargs):
            super(ContainerForm, self).__init__(*args, **kwargs)

            if not request.uac.is_superadmin:
                self.fields['serial_number'].disabled = True

            if request.uac.has_per_company_access:
                del self.fields['company']
                self.fields['sector'].queryset = Sectors.objects.filter(company=request.uac.company)

            if self.instance and not self.instance.is_master:
                del self.fields['location']

        class Meta:
            model = Container
            fields = (
                'serial_number', 'phone_number', 'container_type', 'company', 'country', 'city', 'address', 'sector',
                'waste_type', 'location',
            )
            widgets = {
                'location': PointInput(),
            }

        def clean_city(self):
            data = self.cleaned_data
            country = data.get('country')
            city = data.get('city')
            if not (country and city):
                return
            city, created = City.objects.get_or_create(
                country=country,
                title=city,
            )
            return city
    return ContainerForm


class SectorForm(forms.ModelForm):
    class Meta:
        model = Sectors
        fields = ('name', 'company')

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if request.uac.has_per_company_access:
            companies = Company.objects.filter(pk=request.uac.company_id)
            self.fields['company'].queryset = companies
            self.fields['company'].initial = request.uac.company_id
            self.fields['company'].empty_label = None


class CityForm(forms.ModelForm):
    class Meta:
        model = City
        fields = ('country', 'title')


class DriverUnavailabilityPeriodForm(forms.ModelForm):
    class Meta:
        model = DriverUnavailabilityPeriod
        fields = '__all__'
        widgets = {
            'driver': forms.HiddenInput(),
            'begin': forms.DateInput(attrs={'class': 'date-picker'}),
            'end': forms.DateInput(attrs={'class': 'date-picker'}),
        }
