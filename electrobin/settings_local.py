# flake8: noqa
from .settings_base import *

log_sql_queries = os.environ.get('LOG_SQL_QUERIES', 'False') == 'True'
if log_sql_queries:
    LOGGING = {
        'version': 1,
        'filters': {
            'require_debug_true': {
                '()': 'django.utils.log.RequireDebugTrue',
            }
        },
        'handlers': {
            'console': {
                'level': 'DEBUG',
                'filters': ['require_debug_true'],
                'class': 'logging.StreamHandler',
            }
        },
        'loggers': {
            'django.db.backends': {
                'level': 'DEBUG',
                'handlers': ['console'],
            }
        }
    }

custom_db_name = os.environ.get('CUSTOM_DB_NAME', None)
if custom_db_name is not None:
    DATABASES['default']['NAME'] = custom_db_name
