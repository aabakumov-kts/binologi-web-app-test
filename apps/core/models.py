from django.conf import settings
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils.translation import ugettext_lazy as _
from timezone_field import TimeZoneField


def validate_lang(value):
    if all(code != value for code, _ in settings.LANGUAGES):
        raise ValidationError(
            'There is no such language (%(lang)s), supported languages are: %(langs_list)s',
            params={'lang': value, 'langs_list': ', '.join((code for code, _ in settings.LANGUAGES))})


class Country(models.Model):
    name = models.CharField(
        max_length=128,
        verbose_name=_('title')
    )

    class Meta:
        verbose_name = _('country')
        verbose_name_plural = _('country')

    def __str__(self):
        return self.name


class City(models.Model):
    country = models.ForeignKey(
        to=Country,
        verbose_name=_('country'),
        on_delete=models.CASCADE,
    )
    title = models.CharField(
        verbose_name=_('title'),
        max_length=128,
    )

    class Meta:
        verbose_name = _('city')
        verbose_name_plural = _('cities')
        unique_together = ('country', 'title')
        ordering = ('title',)

    def __str__(self):
        return self.title


class Company(models.Model):
    name = models.CharField(
        max_length=128,
        verbose_name=_('title')
    )
    country = models.ForeignKey(
        to=Country,
        verbose_name=_('country'),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    minsim = models.IntegerField(
        verbose_name=_('minimal SIM balance'),
        default=0
    )
    username_prefix = models.CharField(
        max_length=80,
        null=True,
        blank=True,
        unique=True,
        validators=[UnicodeUsernameValidator()],
    )
    timezone = TimeZoneField(default='UTC', display_GMT_offset=True, verbose_name=_('timezone'))
    lang = models.CharField(max_length=20, default='en', validators=[validate_lang])

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('company')
        verbose_name_plural = _('companies')


class UsersToCompany(models.Model):
    ADMIN_ROLE = 'SA'
    OPERATOR_ROLE = 'OP'
    DRIVER_ROLE = 'DR'
    ROLES = (
        (ADMIN_ROLE, _('administrator')),
        (OPERATOR_ROLE, _('operator')),
        (DRIVER_ROLE, _('driver')),
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_('user'),
        related_name='user_to_company',
    )
    company = models.ForeignKey(
        Company,
        verbose_name=_('company'),
        on_delete=models.CASCADE,
    )
    role = models.CharField(
        verbose_name=_('role'),
        max_length=2,
        choices=ROLES,
        db_index=True,
    )
    timezone = TimeZoneField(null=True, blank=True, display_GMT_offset=True, verbose_name=_('timezone'))
    comment = models.CharField(_('comment'), max_length=150, blank=True)

    def __str__(self):
        return '%s (%s) %s' % (self.user, self.company, self.role)

    def is_driver(self):
        return self.role == UsersToCompany.DRIVER_ROLE

    def is_operator(self):
        return self.role == UsersToCompany.OPERATOR_ROLE

    def is_administrator(self):
        return self.role == UsersToCompany.ADMIN_ROLE


class FeatureFlag(models.Model):
    AIR_QUALITY = 'AIR_QUALITY'
    CHANGE_PASSWORD = 'CHANGE_PASSWORD'
    EFFICIENCY_MONITOR = 'EFFICIENCY_MONITOR'
    FULLNESS_FORECAST = 'FULLNESS_FORECAST'
    MOISTURE_DROP = 'MOISTURE_DROP'

    FEATURE_CHOICES = [
        (AIR_QUALITY, 'Air quality'),
        (CHANGE_PASSWORD, 'Change password'),
        (EFFICIENCY_MONITOR, 'Efficiency monitor'),
        (FULLNESS_FORECAST, 'Fullness forecast'),
        (MOISTURE_DROP, 'Drop moisture')
    ]

    FEATURE_DEFAULTS = {
        AIR_QUALITY: True,
        CHANGE_PASSWORD: True,
        EFFICIENCY_MONITOR: False,
        FULLNESS_FORECAST: False,
        MOISTURE_DROP: False,
    }

    feature = models.CharField(max_length=128, choices=FEATURE_CHOICES)
    company = models.ForeignKey(Company, related_name='features', on_delete=models.CASCADE)
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ('feature', 'company')

    def __str__(self):
        return '{} - {} - {}'.format(self.feature, self.company, self.enabled)


class Sectors(models.Model):
    name = models.CharField(max_length=200, verbose_name=_('title'))
    company = models.ForeignKey(Company, verbose_name=_('company'), null=True, on_delete=models.CASCADE)

    class Meta:
        verbose_name = _('sector')
        verbose_name_plural = _('sector')

    def __str__(self):
        return self.name

    @property
    def is_last_for_company(self):
        return len(self.company.sectors_set.all()) <= 1


class WasteType(models.Model):
    title = models.CharField(
        max_length=200,
        verbose_name=_('title')
    )
    code = models.CharField(
        max_length=8,
        db_index=True,
        verbose_name=_('waste code'),
        null=True,
    )
    # kg/liter
    density = models.FloatField(
        validators=[MinValueValidator(0.0)],
    )

    class Meta:
        verbose_name = _('waste type')
        verbose_name_plural = _('waste types')

    def __str__(self):
        return self.title
