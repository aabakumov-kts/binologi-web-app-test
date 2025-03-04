from django import forms
from django.utils.text import capfirst
from django.utils.translation import ugettext_lazy as _

from apps.core.models import UsersToCompany


class UserTimezoneChangeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        empty_choice = self.fields['timezone'].widget.choices[0]
        self.fields['timezone'].widget.choices[0] = (empty_choice[0], capfirst(_('same as company')))

    class Meta:
        model = UsersToCompany
        fields = ('timezone',)


class NotificationsSettingsForm(forms.Form):
    email = forms.EmailField(
        label=_('Email'), help_text=_('If specified you will receive email notifications at this box.'), required=False)
