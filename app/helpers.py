import logging

from django.db.models import Q
from push_notifications.models import GCMDevice
from django.conf import settings

from app.models import MobileAppUserLanguage, MobileAppTranslation
from apps.sensors.models import CompanySensorsLicense
from apps.trashbins.models import CompanyTrashbinsLicense


logger = logging.getLogger('app_main')


def any_routes_in_progress(driver):
    return len(driver.route_set.filter(Q(status=None) | Q(status__in=[0, 1]))) > 0


def send_push(user_id, message_code):
    message = settings.DEFAULT_MESSAGES_BY_CODES[message_code]

    try:
        user_lang = MobileAppUserLanguage.objects.get(user_id=user_id)
    except MobileAppUserLanguage.DoesNotExist:
        user_lang = None

    if user_lang is not None:
        try:
            localized_message = MobileAppTranslation.objects.get(string_name=message_code, lang=user_lang.lang)
            message = localized_message.string_text
        except MobileAppTranslation.DoesNotExist:
            pass

    try:
        device = GCMDevice.objects.get(user_id=user_id)
        device.send_message(message)
    except GCMDevice.DoesNotExist:
        logger.warning(f'FCMDevice for user with ID "{user_id}" does not exist')


def validate_user_license(user):
    if not hasattr(user, 'user_to_company'):
        return None

    trashbins_license = CompanyTrashbinsLicense.objects.filter(
        company=user.user_to_company.company).order_by('-end').first()
    sensors_license = CompanySensorsLicense.objects.filter(
        company=user.user_to_company.company).order_by('-end').first()
    trashbins_license_is_valid = trashbins_license.is_valid if trashbins_license else False
    sensors_license_is_valid = sensors_license.is_valid if sensors_license else False
    return trashbins_license_is_valid or sensors_license_is_valid
