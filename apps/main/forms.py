from django import forms
from django.utils.translation import ugettext_lazy as _


class RegisterCompanyForm(forms.Form):
    company_name = forms.CharField(max_length=128, label=_('company_name'))
    contact_email = forms.EmailField(label=_('contact_email'))
    license_key = forms.CharField(max_length=20, label=_('license_key'))


class ExtendLicenseForm(forms.Form):
    license_key = forms.CharField(max_length=20, label=_('license_key'))
