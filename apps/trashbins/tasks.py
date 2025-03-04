from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model

from apps.core.models import Company
from apps.core.tasks import NotificationPriorities, notification_levels_resolver, create_notification
from apps.trashbins.shared import TrashbinsNotificationTypes

from app.models import Container


logger = get_task_logger(__name__)


@shared_task
def disable_report_data_generation():
    total_companies = 0
    companies_with_disabled_generation = 0
    # This is an unbounded data set but it's probably fine since there won't be too many companies
    for company in Company.objects.prefetch_related('companytrashbinslicense_set').all():
        trashbins_license = company.companytrashbinslicense_set.order_by('-end').first()
        if trashbins_license is None or not trashbins_license.is_valid:
            bins_qs = Container.objects.filter(company=company, autogenerate_data=True)
            if bins_qs.count() > 0:
                bins_qs.update(autogenerate_data=False)
                companies_with_disabled_generation += 1
        total_companies += 1
    logger.debug(f"Processed {total_companies} companies, disabled report data generation for "
                 f"{companies_with_disabled_generation} expired subscriptions")


@shared_task
def generate_trashbin_status_notifications(trashbin_id):
    try:
        trashbin = Container.objects.select_related('company').prefetch_related('satellites').get(pk=trashbin_id)
    except Container.DoesNotExist:
        raise Warning(f"There's no trashbin with the PK specified: {trashbin_id}")

    recipients = get_user_model().objects.filter(user_to_company__company=trashbin.company)
    if recipients.count() == 0:
        logger.debug(f"There's no receivers for trashbin {trashbin_id}/{trashbin.serial_number} notifications")

    def create_trashbin_notification(notification_type: TrashbinsNotificationTypes,
                                     priority: NotificationPriorities, trashbin_override=None, **kwargs):
        create_notification(
            trashbin_override or trashbin, recipient=recipients, verb=notification_type.value,
            level=notification_levels_resolver[priority].value, **kwargs)

    def find_full_trashbin(bin_to_check, fullness_threshold):
        if bin_to_check.fullness >= fullness_threshold:
            return bin_to_check
        if not bin_to_check.is_master:
            return None
        try:
            full_satellite = next(
                (satellite for satellite in trashbin.satellites.all() if satellite.fullness >= fullness_threshold))
        except StopIteration:
            return None
        return full_satellite

    bins_fullness_analysis = ((find_full_trashbin(trashbin, ft), p) for ft, p in [
        (100, NotificationPriorities.HIGH),
        (90, NotificationPriorities.MEDIUM),
        (75, NotificationPriorities.LOW),
    ] if find_full_trashbin(trashbin, ft) is not None)
    try:
        full_bin, notification_priority = next(bins_fullness_analysis)
    except StopIteration:
        full_bin, notification_priority = None, None
    if full_bin:
        create_trashbin_notification(
            TrashbinsNotificationTypes.TRASHBIN_FULLNESS_ABOVE_THRESHOLD, notification_priority,
            trashbin_override=full_bin, fullness_level=full_bin.fullness)

    if trashbin.battery <= 30:
        create_trashbin_notification(TrashbinsNotificationTypes.TRASHBIN_BATTERY_BELOW_THRESHOLD,
                                     NotificationPriorities.LOW, battery_level=trashbin.battery)

    trashbin_actual_error_type_codes = set(trashbin.errors.filter(actual=1).values_list('error_type__code', flat=True))
    if any(trashbin_actual_error_type_codes.intersection(['8', '9'])):
        create_trashbin_notification(TrashbinsNotificationTypes.TRASHBIN_FIRE_DETECTED, NotificationPriorities.HIGH)
    elif any(trashbin_actual_error_type_codes.intersection(['24'])):
        create_trashbin_notification(
            TrashbinsNotificationTypes.TRASHBIN_VANDALISM_DETECTED, NotificationPriorities.HIGH)
    elif any(trashbin_actual_error_type_codes.intersection(['6'])):
        create_trashbin_notification(
            TrashbinsNotificationTypes.TRASHBIN_TRASH_RECEIVER_BLOCKED, NotificationPriorities.HIGH)
    elif any(trashbin_actual_error_type_codes.intersection(['1', '2', '3', '4', '5'])):
        create_trashbin_notification(TrashbinsNotificationTypes.TRASHBIN_DOORS_ARE_OPEN, NotificationPriorities.HIGH)
    elif any(trashbin_actual_error_type_codes.intersection(['18'])):
        create_trashbin_notification(TrashbinsNotificationTypes.TRASHBIN_BATTERY_BELOW_THRESHOLD,
                                     NotificationPriorities.MEDIUM, battery_level=trashbin.battery)
