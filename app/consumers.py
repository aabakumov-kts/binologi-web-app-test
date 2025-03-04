import ujson as json
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from channels.generic.websocket import WebsocketConsumer
from rest_framework.authtoken.models import Token
from asgiref.sync import async_to_sync
from channels.auth import login, logout
from datetime import datetime
from push_notifications.models import GCMDevice

from apps.core.tasks import NotificationPriorities, notification_levels_resolver, create_notification
from app.models import (
    Route, RoutesDrivers, RoutePoints, Routes,
    ROUTE_STATUS_STARTED_BY_USER, ROUTE_STATUS_ABORTED_BY_USER, ROUTE_STATUS_MOVING_HOME, ROUTE_STATUS_COMPLETE_BY_USER,
    ROUTE_POINT_STATUS_COLLECTED, ROUTE_POINT_STATUS_ERROR,
)
from app.helpers import send_push, validate_user_license
from app.redis_client import RedisClient
from app.shared import RouteNotificationTypes


logger = logging.getLogger('app_main')


def _validate_auth_token(token_value):
    try:
        token = Token.objects.get(key=token_value)
    except Token.DoesNotExist:
        token = None
    if token is None:
        return None

    validation_result = validate_user_license(token.user)
    return token if validation_result is None or validation_result else None


class MobileApiConsumer(WebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis_client = RedisClient()

    def connect(self):
        if 'token' not in self.scope['url_route']['kwargs']:
            return

        token = _validate_auth_token(self.scope['url_route']['kwargs']['token'])
        if token is None:
            return

        async_to_sync(login)(self.scope, token.user)
        self.scope["session"].save()

        async_to_sync(self.channel_layer.group_add)(settings.MOBILE_API_CONSUMERS_GROUP_NAME, self.channel_name)

        self.accept()

        self.redis_client.mark_driver_online(token.user.id)
        route_to_send = self.redis_client.get_route_to_send(token.user.id)
        if route_to_send is not None:
            self.send(route_to_send)
            self.redis_client.clear_route_to_send(token.user.id)

    def disconnect(self, close_code):
        session_user_id = self._get_session_user().id
        async_to_sync(self.channel_layer.group_discard)(settings.MOBILE_API_CONSUMERS_GROUP_NAME, self.channel_name)
        if session_user_id is not None:
            self.redis_client.mark_driver_offline(session_user_id)
            async_to_sync(logout)(self.scope)

    def receive(self, text_data=None, bytes_data=None):
        try:
            payload = json.loads(text_data)
            cmd_method_name = f"_cmd_{payload['action']}" if 'action' in payload else None
            if hasattr(self, cmd_method_name):
                getattr(self, cmd_method_name)(payload)
            else:
                logger.warning(f'Unexpected JSON payload received: "{str(payload)}"')
        except Exception:
            logger.exception(f'Failure on receive, payload is: "{text_data}"')
            self.close()

    def new_route(self, event):
        session_user = self._get_session_user()
        if session_user.id != event['driver_id']:
            return

        try:
            self.send(event['command'])
            self.redis_client.clear_route_to_send(session_user.id)
        except Exception as e:
            logger.warning(f'Failed to send route to "{str(session_user)}": {type(e).__name__} - {str(e)}')
            self.redis_client.set_route_to_send(session_user.id, event['command'])
            send_push(session_user.id, settings.NEW_ROUTE_PUSH_MESSAGE_CODE)

    def abort_route(self, event):
        session_user = self._get_session_user()
        if session_user.id != event['driver_id']:
            return

        try:
            self.send(event['command'])
        except Exception as e:
            logger.warning(f'Failed to abort route for "{str(session_user)}": {type(e).__name__} - {str(e)}')

    def _cmd_start_route(self, msg):
        route = Route.objects.get(pk=msg['route_id'])
        session_user_id = self._get_session_user().id
        if route.user_id != session_user_id:
            raise ValueError(f'Route (pk={route.id}) driver does not match session user (pk={session_user_id})')

        route.status = ROUTE_STATUS_STARTED_BY_USER
        route.save()
        try:
            existing_driver = RoutesDrivers.objects.get(
                driver_id=session_user_id, route=route, base_route=route.parent_route,
                company=route.parent_route.company)
        except RoutesDrivers.DoesNotExist:
            RoutesDrivers.objects.create(
                start_time=datetime.now(), driver_id=session_user_id, route=route, base_route=route.parent_route,
                company=route.parent_route.company)
        else:
            existing_driver.start_time = datetime.now()
            existing_driver.save()

    def _cmd_route_stop(self, msg):
        route = self._close_route_and_update_status(msg['route_id'], ROUTE_STATUS_ABORTED_BY_USER)
        recipients = self._get_route_notification_recipients(route)
        if recipients:
            create_notification(
                route, recipient=recipients, verb=RouteNotificationTypes.ROUTE_ABORTED_BY_USER.value,
                level=notification_levels_resolver[NotificationPriorities.MEDIUM].value)

    def _cmd_collection(self, msg):
        route_id = msg['route_id']
        driver_id = self._get_session_user().id
        point_status = ROUTE_POINT_STATUS_COLLECTED if msg['unloaded_ok'] else ROUTE_POINT_STATUS_ERROR
        points_qs = RoutePoints.objects.\
            filter(user_id=driver_id, route_id=route_id). \
            filter(Q(container_id=msg['container_id']) | Q(sensor_id=msg['container_id']))
        points_qs.update(status=point_status, mtime=datetime.now(), comment=msg['comment'], fullness=msg['fullness'])
        self._update_route_track(route_id, msg['track'] if 'track' in msg else 0)
        if point_status == ROUTE_POINT_STATUS_ERROR and points_qs.count() > 0:
            route_point = points_qs.first()
            recipients = self._get_route_notification_recipients(route_point.route)
            if recipients:
                create_notification(
                    route_point, recipient=recipients, verb=RouteNotificationTypes.ROUTE_POINT_COLLECTION_ISSUE.value,
                    level=notification_levels_resolver[NotificationPriorities.MEDIUM].value)

    def _cmd_moving_home(self, msg):
        route_id = msg['route_id']
        self._close_route_and_update_status(route_id, ROUTE_STATUS_MOVING_HOME)
        self._update_route_track(route_id, msg['track'] if 'track' in msg else 0)

    def _cmd_route_complete(self, msg):
        route_id = msg['route_id']
        route = self._close_route_and_update_status(route_id, ROUTE_STATUS_COMPLETE_BY_USER)
        self._update_route_track(route_id, msg['track'] if 'track' in msg else 0, True)
        recipients = self._get_route_notification_recipients(route)
        if recipients:
            create_notification(
                route, recipient=recipients, verb=RouteNotificationTypes.ROUTE_COMPLETED.value,
                level=notification_levels_resolver[NotificationPriorities.LOW].value)

    def _cmd_update_token(self, msg):
        user = self._get_session_user()
        registration_id = msg['token']
        try:
            device = GCMDevice.objects.get(user=user)
            device.registration_id = registration_id
            device.save()
        except Exception as e:
            logger.warning(f'FCM Device for user "{str(user)}" not found: {type(e).__name__} - {str(e)}')

            try:
                GCMDevice.objects.filter(registration_id=registration_id).delete()
                GCMDevice.objects.filter(user=user).delete()
            except Exception as e:
                logger.warning(
                    f'Failed to delete FCM Devices by token/user "{registration_id}"/"{str(user)}" not found:'
                    f'{type(e).__name__} - {str(e)}')

            GCMDevice.objects.create(registration_id=registration_id, user=user, cloud_message_type="FCM")

    def _close_route_and_update_status(self, route_id, status):
        driver_id = self._get_session_user().id
        RoutesDrivers.finish_routes(driver_id)
        RoutePoints.close_route_points(driver_id, status)
        Routes.close_parent_routes_if_possible(driver_id)
        route = Route.objects.get(pk=route_id)
        route.status = status
        route.save()
        return route

    def _update_route_track(self, route_id, track, update_full_track=False):
        route_driver = RoutesDrivers.objects.get(route_id=route_id, driver_id=self._get_session_user().id)
        field_name = 'track_full' if update_full_track else 'track'
        setattr(route_driver, field_name, round(float(track)))
        route_driver.save()

    def _get_session_user(self):
        return self.scope['user']

    @staticmethod
    def _get_route_notification_recipients(route):
        recipients = get_user_model().objects.filter(user_to_company__company=route.parent_route.company)
        if recipients.count() == 0:
            logger.debug(f"There's no receivers for route {route.id} notifications")
        return recipients if recipients else None


class NotificationsWebsocketConsumer(WebsocketConsumer):
    def connect(self):
        if 'token' not in self.scope['url_route']['kwargs']:
            return

        token = _validate_auth_token(self.scope['url_route']['kwargs']['token'])
        if token is None:
            return

        async_to_sync(login)(self.scope, token.user)
        self.scope["session"].save()
        async_to_sync(self.channel_layer.group_add)(settings.NOTIFICATIONS_CONSUMERS_GROUP_NAME, self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(settings.NOTIFICATIONS_CONSUMERS_GROUP_NAME, self.channel_name)

    def new_notification(self, event):
        session_user = self.scope['user']
        if session_user.id != event['recipient_id']:
            return

        payload = json.dumps({
            'unread_notifications_count': session_user.notifications.unread().count(),
        })
        try:
            self.send(payload)
        except Exception as e:
            logger.warning(f'Failed to notify "{session_user}" about new notification: {type(e).__name__} - {str(e)}')
