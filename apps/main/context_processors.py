from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from apps.core.helpers import CompanyDeviceProfile
from apps.main.helpers import get_raw_company_device_profile, get_effective_company_device_profile


def company_device_profile(request):
    """Device profile means which device types company owns"""
    result = {}
    any_trashbin, any_sensor = get_raw_company_device_profile(request)
    result['all_device_types_company'] = any_trashbin and any_sensor
    device_profile = get_effective_company_device_profile(request)
    result['is_trashbin_company'] = device_profile == CompanyDeviceProfile.TRASHBIN
    result['is_sensor_company'] = device_profile == CompanyDeviceProfile.SENSOR
    return result


def feedback_survey(request):
    result = {}
    survey_enabled = False
    if settings.DEMO_FEEDBACK_SURVEY_ENABLED:
        company_name = request.uac.company.name if request.uac.has_per_company_access and request.uac.company else None
        if company_name:
            feedback_form_url = _('Feedback survey form url with "%(company_name)s" param') \
                                % {'company_name': company_name}
            # If translated feedback URL starts with # it's a marker that it's an invalid URL
            if not feedback_form_url.startswith('#'):
                survey_enabled = True
                result['feedback_survey_form_url'] = feedback_form_url
    result['feedback_survey_enabled'] = survey_enabled
    return result
