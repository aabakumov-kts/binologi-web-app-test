from enum import Enum
from django.urls import reverse
from django.utils.translation import ugettext as _

from apps.core.utils import (
    notification_subject_generators, notification_message_generators, notification_link_generators,
)


class RouteNotificationTypes(Enum):
    ROUTE_ABORTED_BY_USER = 'ROUTE_ABORTED_BY_USER'
    ROUTE_COMPLETED = 'ROUTE_COMPLETED'
    ROUTE_POINT_COLLECTION_ISSUE = 'ROUTE_POINT_COLLECTION_ISSUE'


def register_notification_generators():
    def primary_subject_generator(n):
        return _('Route #%(route_id)s') % {'route_id': n.actor.id}

    def primary_link_generator(n):
        return reverse('routes:detail', kwargs={'pk': n.actor.id})

    for nt in [
        RouteNotificationTypes.ROUTE_ABORTED_BY_USER,
        RouteNotificationTypes.ROUTE_COMPLETED,
    ]:
        notification_subject_generators[nt.value] = primary_subject_generator
        notification_link_generators[nt.value] = primary_link_generator

    def generate_route_point_issue_subject(n):
        bin_or_sensor = n.actor.container or n.actor.sensor
        return _('Point %(point_serial)s of route #%(route_id)s') % \
            {'point_serial': bin_or_sensor.serial_number, 'route_id': n.actor.route.id}

    notification_subject_generators[RouteNotificationTypes.ROUTE_POINT_COLLECTION_ISSUE.value] = \
        generate_route_point_issue_subject
    notification_link_generators[RouteNotificationTypes.ROUTE_POINT_COLLECTION_ISSUE.value] = \
        lambda n: reverse('routes:detail', kwargs={'pk': n.actor.route.id})

    notification_message_generators[RouteNotificationTypes.ROUTE_ABORTED_BY_USER.value] = \
        lambda n: _('Route is aborted by driver')
    notification_message_generators[RouteNotificationTypes.ROUTE_COMPLETED.value] = \
        lambda n: _('Route is completed')
    notification_message_generators[RouteNotificationTypes.ROUTE_POINT_COLLECTION_ISSUE.value] = \
        lambda n: _('Driver commented about point collection issue: %(comment)s') % {'comment': n.actor.comment}
