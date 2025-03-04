# flake8: noqa
import dj_database_url

from .settings_base import *

app_host = os.environ.get('APP_HOSTS', None)
if app_host:
    ALLOWED_HOSTS = app_host.split(',')

# Keep engine as is since it's special
db_engine = DATABASES['default']['ENGINE']
DATABASES['default'].update(dj_database_url.config(engine=db_engine))

GOOGLE_MAPS_API_KEY = 'AIzaSyBBYSnXQV4NdO5gahAMmYJH2JpVC7OHasU'

if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

custom_signed_url_expiration = os.environ.get('S3_SIGNED_URL_EXPIRATION', None)
if custom_signed_url_expiration:
    # Fail fast if setting is of invalid format
    S3_SIGNED_URL_EXPIRATION = int(custom_signed_url_expiration)
