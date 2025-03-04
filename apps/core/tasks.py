import boto3
import json
import logging
import requests

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from django.db.models.query import QuerySet
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _, override as current_language_override
from enum import Enum
from notifications.models import Notification
from notifications.base.models import notify_handler
from notifications.signals import notify

from apps.core.utils import (
    notification_subject_generators, notification_message_generators, notification_link_generators,
)


logger = logging.getLogger('app_main')


class NotificationLevels(Enum):
    SUCCESS = 'success'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'


class NotificationPriorities(Enum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3


notification_levels_resolver = {
    NotificationPriorities.HIGH: NotificationLevels.ERROR,
    NotificationPriorities.MEDIUM: NotificationLevels.WARNING,
    NotificationPriorities.LOW: NotificationLevels.INFO,
}


def _send_notifications_via_onesignal(recipient_id, notifications):
    first_notification = next(iter(notifications))
    heading = notification_subject_generators[first_notification.verb](first_notification) \
        if first_notification.verb in notification_subject_generators else None
    message = notification_message_generators[first_notification.verb](first_notification) \
        if first_notification.verb in notification_message_generators else None
    link = notification_link_generators[first_notification.verb](first_notification) \
        if first_notification.verb in notification_link_generators else None
    if not all((heading, message, link)):
        logger.warning(f"Missing some values - {heading}/{message}/{link} - "
                       f"for a notification {first_notification.verb}")
        return

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {settings.ONESIGNAL_REST_API_KEY}",
    }

    payload = {
        "app_id": settings.ONESIGNAL_APP_ID,
        "include_external_user_ids": [str(recipient_id)],
        "channel_for_external_user_ids": "push",
        "headings": {"en": heading},
        "contents": {"en": message},
        "url": f'{settings.WEB_APP_ROOT_URL}{link}',
    }
    if not settings.DEBUG:
        payload["priority"] = 10

    req = requests.post("https://onesignal.com/api/v1/notifications", headers=headers, data=json.dumps(payload))
    if req.status_code == 200:
        logger.debug(f"Successfully sent {first_notification.verb} notification to recipient with ID {recipient_id}")
    else:
        logger.warning(f"Failed to deliver notification (status code {req.status_code}):\n{req.text}")


def _send_notifications_via_email(recipient_email, notifications):
    first_notification = next(iter(notifications))
    message = notification_message_generators[first_notification.verb](first_notification) \
        if first_notification.verb in notification_message_generators else None
    link = notification_link_generators[first_notification.verb](first_notification) \
        if first_notification.verb in notification_link_generators else None
    if not all((message, link)):
        logger.warning(f"Missing some values - {message}/{link} - for a notification {first_notification.verb}")
        return

    notifications_messages_combined = '\n'.join((
        f"- {notification_subject_generators[n.verb](n)}: {notification_message_generators[n.verb](n)}"
        for n in notifications
        if n.verb in notification_subject_generators and n.verb in notification_message_generators))
    ses_client = boto3.client('ses')
    ses_client.send_templated_email(
        Source=settings.DEFAULT_FROM_EMAIL,
        Destination={
            'ToAddresses': [
                recipient_email,
            ],
        },
        Template=str(_('email-notification-ses-template-name')),  # Enforcing str here to bypass type validation
        TemplateData=json.dumps({
            'subject': message,
            'message': notifications_messages_combined,
            'link': f'{settings.WEB_APP_ROOT_URL}{link}',
            'notifications_list_link': f"{settings.WEB_APP_ROOT_URL}{reverse('notifications_list')}"
        })
    )


def _send_notifications_page(notifications):
    all_unique_recipients = set(notifications.values_list('recipient_id', flat=True)) \
        if isinstance(notifications, QuerySet) else set(map(lambda n: n.recipient.id, notifications))
    for recipient_id in all_unique_recipients:
        notifications_for_recipient = list(filter(lambda n: n.recipient.pk == recipient_id, notifications))
        if notifications_for_recipient:
            recipient = notifications_for_recipient[0].recipient
            notifications_with_actor = list(filter(lambda n: n.actor is not None, notifications_for_recipient))
            if notifications_with_actor:
                with current_language_override(recipient.user_to_company.company.lang):
                    _send_notifications_via_onesignal(recipient_id, notifications_with_actor)
                    if recipient.email:
                        _send_notifications_via_email(recipient.email, notifications_with_actor)
            Notification.objects.filter(pk__in=map(lambda n: n.id, notifications_for_recipient)).update(emailed=True)
        logger.debug(f"Sent {len(notifications_for_recipient)} notifications to recipient with ID: {recipient_id}")


def send_notifications(notifications_qs):
    qs_to_paginate = notifications_qs.order_by('id')
    notifications_count = qs_to_paginate.count()
    page_size = 1000
    offset = 0
    while offset < notifications_count:
        _send_notifications_page(qs_to_paginate[offset:offset + page_size])
        offset += page_size


def create_notification(*notify_args, **notify_kwargs):
    signal_results = notify.send(*notify_args, **notify_kwargs)
    new_notifications = next(results for handler, results in signal_results if handler == notify_handler)
    for note in new_notifications:
        async_to_sync(get_channel_layer().group_send)(
            settings.NOTIFICATIONS_CONSUMERS_GROUP_NAME,
            {
                'type': 'new_notification',
                'notification_id': note.id,
                'recipient_id': note.recipient.id,
            }
        )


@shared_task
def send_periodic_notifications(priority_value):
    try:
        priority_enum = NotificationPriorities(priority_value)
    except ValueError:
        raise Warning(f"There's no priority with code {priority_value}")
    logger.debug(f"Sending notifications of priority {priority_enum}")
    notifications_qs = Notification.objects.filter(
        level=notification_levels_resolver[priority_enum].value, emailed=False, unread=True)
    send_notifications(notifications_qs)
