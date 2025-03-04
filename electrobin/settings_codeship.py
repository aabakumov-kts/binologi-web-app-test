# flake8: noqa
from .settings_base import *

DATABASES['default']['HOST'] = 'postgres'

REDIS_HOST = 'redis'
