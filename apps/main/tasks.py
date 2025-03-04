import pytz

from celery import shared_task
from celery.utils.log import get_task_logger
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from sentry_sdk import capture_message

from apps.core.models import Company
from apps.core.report_data_generation import get_record_generation_interval
from app.models import Container
from app.tasks import generate_report_data_for_bins
from apps.sensors.models import Sensor
from apps.sensors.tasks import generate_report_data_for_sensors


logger = get_task_logger(__name__)


@shared_task
def remove_all_company_data(company_id):
    with transaction.atomic():
        Container.objects.filter(company_id=company_id).delete()
        Sensor.objects.filter(company_id=company_id).delete()
        get_user_model().objects.filter(user_to_company__company_id=company_id).delete()
        Company.objects.filter(pk=company_id).delete()


def should_remove_data_for_license(company, licenses_set_attr_name):
    devices_license = getattr(company, licenses_set_attr_name).order_by('-end').first()
    if devices_license is None:
        warn_message = f'Detected company (id {company.id}) without a license ({licenses_set_attr_name})'
        logger.warning(warn_message)
        capture_message(warn_message)
        return None
    if not devices_license.is_valid:
        grace_period_end = devices_license.end + timedelta(days=settings.LICENSE_DATA_REMOVAL_GRACE_PERIOD_DAYS)
        return grace_period_end < datetime.utcnow().date()
    return False


@shared_task
def remove_obsolete_company_data():
    total_companies = 0
    companies_with_data_removed = 0
    companies_deleted = 0
    # This is an unbounded data set but it's probably fine since there won't be too many companies
    for company in Company.objects.prefetch_related('companytrashbinslicense_set', 'companysensorslicense_set').all():
        device_types = [
            (Container, 'companytrashbinslicense_set'),
            (Sensor, 'companysensorslicense_set'),
        ]
        should_remove_data_by_license = {
            Container: False,
            Sensor: False,
        }
        for device_model, licenses_set_attr_name in device_types:
            devices_license = getattr(company, licenses_set_attr_name).order_by('-end').first()
            if devices_license is None:
                if device_model.objects.filter(company=company).count() > 0:
                    warn_message = f'Detected company (id {company.id}) with devices ' \
                                   f'({device_model.__name__}) but no license'
                    logger.warning(warn_message)
                    capture_message(warn_message)
                continue
            if not devices_license.is_valid:
                grace_period_end = devices_license.end + timedelta(
                    days=settings.LICENSE_DATA_REMOVAL_GRACE_PERIOD_DAYS)
                should_remove_data_by_license[device_model] = grace_period_end < datetime.utcnow().date()
        total_companies += 1
        if any(should_remove_data_by_license.values()):
            with transaction.atomic():
                for device_model, should_remove_data in should_remove_data_by_license.items():
                    if should_remove_data:
                        device_model.objects.filter(company=company).delete()
            companies_with_data_removed += 1
        if settings.REMOVE_COMPANIES_WITHOUT_DEVICES and \
                all(map(lambda t: t[0].objects.filter(company=company).count() == 0, device_types)):
            with transaction.atomic():
                get_user_model().objects.filter(user_to_company__company=company).delete()
                company.delete()
            companies_deleted += 1

    report_message = f"Processed {total_companies} companies, cleaned up data for " \
                     f"{companies_with_data_removed} past due subscriptions"
    if settings.REMOVE_COMPANIES_WITHOUT_DEVICES:
        report_message += f", removed {companies_deleted} companies without devices"
    logger.debug(report_message)


@shared_task
def generate_report_data():
    task_name = f"{generate_report_data.__module__}.{generate_report_data.__name__}"
    record_generation_interval = get_record_generation_interval(task_name)
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    generate_report_data_for_bins(Container.objects.filter(autogenerate_data=True), utc_now, record_generation_interval)
    generate_report_data_for_sensors(Sensor.objects.filter(autogenerate_data=True), utc_now, record_generation_interval)
