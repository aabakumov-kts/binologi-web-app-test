import redis

from django.conf import settings


class RedisClient(object):
    def __init__(self):
        self._conn = redis.StrictRedis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DATABASE,
            password=None,
            socket_timeout=None,
            connection_pool=None,
            charset='utf-8',
            errors='strict',
            unix_socket_path=None
        )

    def set_route_to_send(self, driver_id, route):
        self._conn.hset(settings.ROUTE_TO_SEND_HASH, driver_id, route)

    def get_route_to_send(self, driver_id):
        value = self._conn.hget(settings.ROUTE_TO_SEND_HASH, driver_id)
        return value.decode('utf-8') if value is not None else None

    def clear_route_to_send(self, driver_id):
        self._conn.hdel(settings.ROUTE_TO_SEND_HASH, driver_id)

    def mark_driver_online(self, driver_id):
        self._conn.sadd(settings.ONLINE_MOBILE_USERS_SET, driver_id)

    def mark_driver_offline(self, driver_id):
        self._conn.srem(settings.ONLINE_MOBILE_USERS_SET, driver_id)

    def is_driver_online(self, driver_id):
        return self._conn.sismember(settings.ONLINE_MOBILE_USERS_SET, driver_id)
