import json
import os
import sentry_sdk

from django.utils.log import DEFAULT_LOGGING
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '2q6fsi9z%ifeagj3u%%vdx#izs&3*6yp1#@uw*sxp(1os@%i*&'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True') != 'False'

if DEBUG:
    INTERNAL_IPS = ['127.0.0.1']

ALLOWED_HOSTS = ['*']

# Application definition

INSTALLED_APPS = (
    # utils
    'sslserver',
    'whitenoise.runserver_nostatic',

    # contrib applications
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.gis',
    'django.contrib.messages',
    'django.contrib.postgres',
    'django.contrib.sessions',
    'django.contrib.staticfiles',

    # third-party applications
    'bootstrap3',
    'rest_framework',
    'rest_framework.authtoken',
    'table',
    'modeltranslation',
    'channels',
    'push_notifications',
    'django_extensions',
    'django_celery_beat',
    'notifications',

    # our applications
    'apps.core.apps.CoreConfig',
    'app.apps.ElectrobinConfig',
    'apps.trashbins.apps.TrashbinsConfig',
    'apps.sensors.apps.SensorsConfig',
    'apps.main.apps.MainConfig',
)

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.UserAccessControlMiddleware',
    'apps.main.middleware.LicenseCheckMiddleware',
    'apps.core.middleware.TimezoneMiddleware',
]

ROOT_URLCONF = 'electrobin.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.feature_flag_model',
                'apps.core.context_processors.process_messages',
                'apps.core.context_processors.app_env_name',
                'apps.core.context_processors.return_url',
                'apps.core.context_processors.freshdesk_widget_fields',
                'apps.core.context_processors.notifications',
                'apps.main.context_processors.company_device_profile',
                'apps.main.context_processors.feedback_survey',
            ],
        },
    },
]

WSGI_APPLICATION = 'electrobin.wsgi.application'

# Database

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'HOST': 'localhost',
        'USER': 'postgres',
        'PASSWORD': 'password',
        'NAME': 'binology_web',
    }
}

# Internationalization

LANGUAGE_CODE = 'en'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

LANGUAGES = [
    ('en', 'English'),
    ('ru', 'Russian'),
]

LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]

FORMAT_MODULE_PATH = [
    'formats',
]

# Static files (CSS, JavaScript, Images)

LOGIN_URL = "/"
LOGIN_REDIRECT_URL = "/main/"

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static_root')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Default settings
BOOTSTRAP3 = {
    # The URL to the jQuery JavaScript file
    'jquery_url': '//code.jquery.com/jquery-3.4.1.min.js',
    # The Bootstrap base URL
    'base_url': '//maxcdn.bootstrapcdn.com/bootstrap/3.4.0/',
    # The complete URL to the Bootstrap CSS file (None means derive it from base_url)
    'css_url': None,
    # The complete URL to the Bootstrap CSS file (None means no theme)
    'theme_url': None,
    # The complete URL to the Bootstrap JavaScript file (None means derive it from base_url)
    'javascript_url': None,
    # Put JavaScript in the HEAD section of the HTML document (only relevant if you use bootstrap3.html)
    'javascript_in_head': False,
    # Include jQuery with Bootstrap JavaScript (affects django-bootstrap3 template tags)
    'include_jquery': False,
    # Label class to use in horizontal forms
    'horizontal_label_class': 'col-md-3',
    # Field class to use in horizontal forms
    'horizontal_field_class': 'col-md-9',
    # Set HTML required attribute on required fields
    'set_required': True,
    # Set HTML disabled attribute on disabled fields
    'set_disabled': False,
    # Set placeholder attributes to label if no placeholder is provided
    'set_placeholder': True,
    # Class to indicate required (better to set this in your Django form)
    'required_css_class': '',
    # Class to indicate error (better to set this in your Django form)
    'error_css_class': 'has-error',
    # Class to indicate success, meaning the field has valid input (better to set this in your Django form)
    'success_css_class': 'has-success',
    # Renderers (only set these if you have studied the source and understand the inner workings)
    'formset_renderers': {
        'default': 'bootstrap3.renderers.FormsetRenderer',
    },
    'form_renderers': {
        'default': 'bootstrap3.renderers.FormRenderer',
    },
    'field_renderers': {
        'default': 'bootstrap3.renderers.FieldRenderer',
        'inline': 'bootstrap3.renderers.InlineFieldRenderer',
    },
}

# Redis settings

REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
REDIS_DATABASE = 5

custom_redis_host = os.environ.get('REDIS_HOST', None)
if custom_redis_host:
    REDIS_HOST = custom_redis_host

custom_redis_port = os.environ.get('REDIS_PORT', None)
if custom_redis_port:
    REDIS_PORT = int(custom_redis_port)

ROUTE_TO_SEND_HASH = 'route_to_send'

ONLINE_MOBILE_USERS_SET = 'online_mobile_users'

# Misc

DEFAULT_CONTAINER_VOLUME = 120  # liters, standard container

GOOGLE_MAPS_API_KEY = 'AIzaSyAxA4tUKoc2uEGI_6aZqm8lv9upJ_9LoGg'

GA_TRACKING_ID = os.environ.get('GA_TRACKING_ID', None)

APP_ENV_NAME = os.environ.get('APP_ENV_NAME', 'Default')

LOW_BATTERY_STATUS_ICON_LEVEL_THRESHOLD = 30
custom_low_battery_status_icon_level_threshold = os.environ.get('LOW_BATTERY_STATUS_ICON_LEVEL_THRESHOLD', None)
if custom_low_battery_status_icon_level_threshold:
    LOW_BATTERY_STATUS_ICON_LEVEL_THRESHOLD = int(custom_low_battery_status_icon_level_threshold)

ACCUM_MIN_VOLTAGE = 11.8
custom_accum_min_voltage = os.environ.get('ACCUM_MIN_VOLTAGE', None)
if custom_accum_min_voltage:
    ACCUM_MIN_VOLTAGE = float(custom_accum_min_voltage)

ACCUM_MAX_VOLTAGE = 12.8
custom_accum_max_voltage = os.environ.get('ACCUM_MAX_VOLTAGE', None)
if custom_accum_max_voltage:
    ACCUM_MAX_VOLTAGE = float(custom_accum_max_voltage)

E2E_DEFAULT_CONTAINER_PASSWORD = 'oYyScvrxbP9Q3DDsN3c6'

sensor_asset_holder_company_id = os.environ.get('SENSOR_ASSET_HOLDER_COMPANY_ID', None)
SENSOR_ASSET_HOLDER_COMPANY_ID = int(sensor_asset_holder_company_id) if sensor_asset_holder_company_id else None

WEB_APP_ROOT_URL = os.environ.get('WEB_APP_ROOT_URL', 'http://localhost:8000')

REALTIME_API_ROOT_URL = os.environ.get('REALTIME_API_ROOT_URL', 'ws://localhost:8000')

DISABLE_SENSOR_JOB_SEND_DELAY = os.environ.get('DISABLE_SENSOR_JOB_SEND_DELAY', 'False') == 'True'

# Logging

# Make sure logs always make it to console
DEFAULT_LOGGING['handlers']['console']['filters'] = []

log_level = 'DEBUG' if DEBUG else 'INFO'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'app_main': {
            'format': 'APP - {levelname} {module}: {message}',
            'style': '{',
        }
    },
    'handlers': {
        'app_console': {
            'level': log_level,
            'class': 'logging.StreamHandler',
            'formatter': 'app_main',
        }
    },
    'loggers': {
        'app_main': {
            'handlers': ['app_console'],
            'level': log_level,
        },
        'fbprophet.plot': {
            'level': 'CRITICAL',
        }
    },
}

# REST Framework

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'app.authentication.ExpiringContainerTokenAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
}

TOKEN_EXPIRATION_MINUTES = 14400  # 60 minutes per hour * 24 hours per day * 10 days

custom_token_expiration_minutes = os.environ.get('TOKEN_EXPIRATION_MINUTES', None)
if custom_token_expiration_minutes:
    # Fail fast if setting is of invalid format
    TOKEN_EXPIRATION_MINUTES = int(custom_token_expiration_minutes)

# Sentry


def filter_out_gdal_errors(event, _):
    if 'level' in event and 'logger' in event and 'logentry' in event:
        contrib_gis_error = event['level'] == 'error' and event['logger'] == 'django.contrib.gis'
        log_entry = event['logentry']
        gdal_error = contrib_gis_error and 'message' in log_entry and log_entry['message'].startswith('GDAL_ERROR')
        if gdal_error:
            return None
    return event


if not DEBUG:
    init_args = {
        'dsn': 'https://f4190923fe29485f99ae43ebe73368a2@o288425.ingest.sentry.io/1524057',
        'integrations': [DjangoIntegration(), RedisIntegration(), CeleryIntegration()],
        'environment': APP_ENV_NAME,
        'before_send': filter_out_gdal_errors,
        'send_default_pii': True,
    }
    if os.path.isfile('release-info.txt'):
        with open('release-info.txt') as f:
            release_name = f.readline().strip()
            init_args['release'] = release_name
    sentry_sdk.init(**init_args)

# Channels

ASGI_APPLICATION = 'app.routing.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(REDIS_HOST, REDIS_PORT)],
        },
    },
}

MOBILE_API_CONSUMERS_GROUP_NAME = 'mobile_api_consumers'
NOTIFICATIONS_CONSUMERS_GROUP_NAME = 'notifications_consumers'

# Push notifications

PUSH_NOTIFICATIONS_SETTINGS = {
     "FCM_API_KEY": "AAAAYYpKIMU:APA91bH4oQ71YumDOfBW568ECqsidEHIEjpE3mNpAdB7Kfs3VN782L1AGHslTnsl0vfTWY230YIrpkNzcndB8X"
                    "FscVaW11r1LA6KjZd5SNMdlcIcgjRuFXel48wQfdI0QNHPxBVKZ_Ud",
}

NEW_ROUTE_PUSH_MESSAGE_CODE = 'new_route_push_message'

DEFAULT_MESSAGES_BY_CODES = {
    'new_route_push_message': 'New route received',
}

# Celery

CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/4'

CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Fake data generator settings

DATA_GEN_TEMPERATURE_MIN, DATA_GEN_TEMPERATURE_MAX, DATA_GEN_TEMPERATURE_RANDOM_DELTA = 10, 30, 3  # Celsius

DATA_GEN_PRESSURE_MIN, DATA_GEN_PRESSURE_MAX = 960, 1040  # hPa

DATA_GEN_BATTERY_MAX_DAILY_DISCHARGE, DATA_GEN_BATTERY_MAX_DAILY_CHARGE = 50, 25  # percent

DATA_GEN_TRAFFIC_MAX_DAILY = 30  # amount

DATA_GEN_FULLNESS_MAX_DAILY_INCREASE = 40  # percent

DATA_GEN_SIM_BALANCE_TOP_UP_AMOUNT, DATA_GEN_SIM_BALANCE_MAX_DAILY_WITHDRAW = 300, 100  # rub

DATA_GEN_ERROR_PROBABILITY = 10  # percent

DATA_GEN_HUMIDITY_MIN, DATA_GEN_HUMIDITY_MAX = 20, 70  # percent

DATA_GEN_AIR_QUALITY_MIN, DATA_GEN_AIR_QUALITY_MAX = 0, 400000  # AQI * 1000

# MQTT settings

MQTT_BROKER_HOST = os.environ.get('MQTT_BROKER_HOST', 'localhost')
MQTT_USERNAME = os.environ.get('MQTT_USERNAME', None)
MQTT_PASSWORD = os.environ.get('MQTT_PASSWORD', None)

# Licenses

LICENSE_DATA_REMOVAL_GRACE_PERIOD_DAYS = 30
custom_subscriptions_data_removal_grace_period = os.environ.get('LICENSE_DATA_REMOVAL_GRACE_PERIOD_DAYS', None)
if custom_subscriptions_data_removal_grace_period:
    # Fail fast if setting is of invalid format
    LICENSE_DATA_REMOVAL_GRACE_PERIOD_DAYS = int(custom_subscriptions_data_removal_grace_period)

REMOVE_COMPANIES_WITHOUT_DEVICES = os.environ.get('REMOVE_COMPANIES_WITHOUT_DEVICES', 'False') == 'True'

# S3 integration

FIRMWARE_S3_BUCKET_NAME = os.environ.get('FIRMWARE_S3_BUCKET_NAME', 'binology-group-firmware-updates')

S3_SIGNED_URL_EXPIRATION = 3600  # In seconds, 1 hour

VPN_CONFIGS_S3_BUCKET_NAME = os.environ.get('VPN_CONFIGS_S3_BUCKET_NAME', 'binology-group-vpn-configs')

# Trashbin notifications settings

TRASHBIN_NOTIFICATIONS_ENABLED = os.environ.get('TRASHBIN_NOTIFICATIONS_ENABLED', 'False') == 'True'

TRASHBIN_NOTIFICATIONS_TG_BOT_API_KEY = '709560450:AAFDn42ttieCtSeRz340TyvilFbIw5C8qrU'

TRASHBIN_NOTIFICATIONS_TG_BOT_CHAT_ID = os.environ.get('TRASHBIN_NOTIFICATIONS_TG_BOT_CHAT_ID', '-1001963526778')

TRASHBIN_NOTIFICATIONS_SEND_ALL = os.environ.get('TRASHBIN_NOTIFICATIONS_SEND_ALL', 'False') == 'True'

# Demo settings

demo_sandbox_template_company_ids = os.environ.get('DEMO_SANDBOX_TEMPLATE_COMPANY_IDS', None)
DEMO_SANDBOX_TEMPLATE_COMPANY_IDS = \
    json.loads(demo_sandbox_template_company_ids) if demo_sandbox_template_company_ids else []

DEMO_DATA_GEN_DAYS = 14

DEMO_FEEDBACK_SURVEY_ENABLED = os.environ.get('DEMO_FEEDBACK_SURVEY_ENABLED', 'False') == 'True'

# Email via AWS SES

DEFAULT_FROM_EMAIL = 'Binology <support@binology.freshdesk.com>'

# OneSignal

ONESIGNAL_APP_ID = os.environ.get('ONESIGNAL_APP_ID', 'afeeb4f6-20af-4f42-b812-0e16e8591244')
ONESIGNAL_REST_API_KEY = os.environ.get('ONESIGNAL_REST_API_KEY', 'YWVhMDVhZWMtY2U3Yy00YzFiLWJkOTItYmRiNWIwZWQ5N2Mz')

# Django Notifications

DJANGO_NOTIFICATIONS_CONFIG = {'USE_JSONFIELD': True}
