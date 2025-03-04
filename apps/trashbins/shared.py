from enum import Enum
from django.utils.translation import ugettext as _

from apps.core.utils import (
    notification_subject_generators, notification_message_generators, notification_link_generators,
)


class TrashbinsNotificationTypes(Enum):
    TRASHBIN_FULLNESS_ABOVE_THRESHOLD = 'TRASHBIN_FULLNESS_ABOVE_THRESHOLD'
    TRASHBIN_BATTERY_BELOW_THRESHOLD = 'TRASHBIN_BATTERY_BELOW_THRESHOLD'
    TRASHBIN_FIRE_DETECTED = 'TRASHBIN_FIRE_DETECTED'
    TRASHBIN_VANDALISM_DETECTED = 'TRASHBIN_VANDALISM_DETECTED'
    TRASHBIN_TRASH_RECEIVER_BLOCKED = 'TRASHBIN_TRASH_RECEIVER_BLOCKED'
    TRASHBIN_DOORS_ARE_OPEN = 'TRASHBIN_DOORS_ARE_OPEN'


def register_notification_generators():
    from apps.core.helpers import CompanyDeviceProfile

    def primary_subject_generator(n):
        return _('Bin %(serial_number)s') % {'serial_number': n.actor.serial_number}

    def primary_link_generator(n):
        return f'/main/?device_profile={CompanyDeviceProfile.TRASHBIN.value}&lat={n.actor.location.y}' \
               f'&lng={n.actor.location.x}'

    for nt in [
        TrashbinsNotificationTypes.TRASHBIN_FULLNESS_ABOVE_THRESHOLD,
        TrashbinsNotificationTypes.TRASHBIN_BATTERY_BELOW_THRESHOLD,
        TrashbinsNotificationTypes.TRASHBIN_FIRE_DETECTED,
        TrashbinsNotificationTypes.TRASHBIN_VANDALISM_DETECTED,
        TrashbinsNotificationTypes.TRASHBIN_TRASH_RECEIVER_BLOCKED,
        TrashbinsNotificationTypes.TRASHBIN_DOORS_ARE_OPEN,
    ]:
        notification_subject_generators[nt.value] = primary_subject_generator
        notification_link_generators[nt.value] = primary_link_generator

    notification_message_generators[TrashbinsNotificationTypes.TRASHBIN_FULLNESS_ABOVE_THRESHOLD.value] = \
        lambda n: _('Bin fullness is %(fullness)s percent') % {'fullness': n.data['fullness_level']}
    notification_message_generators[TrashbinsNotificationTypes.TRASHBIN_BATTERY_BELOW_THRESHOLD.value] = \
        lambda n: _('Bin battery level is %(battery)s percent') % {'battery': n.data['battery_level']}
    notification_message_generators[TrashbinsNotificationTypes.TRASHBIN_FIRE_DETECTED.value] = \
        lambda n: _('Fire, smoke and/or high temperature detected')
    notification_message_generators[TrashbinsNotificationTypes.TRASHBIN_VANDALISM_DETECTED.value] = \
        lambda n: _('Possible vandalism detected')
    notification_message_generators[TrashbinsNotificationTypes.TRASHBIN_TRASH_RECEIVER_BLOCKED.value] = \
        lambda n: _('Trash receiver is blocked')
    notification_message_generators[TrashbinsNotificationTypes.TRASHBIN_DOORS_ARE_OPEN.value] = \
        lambda n: _('One or more doors are open')
