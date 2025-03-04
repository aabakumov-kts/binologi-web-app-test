import os
import sys
import logging

from django.core.wsgi import get_wsgi_application


logging.basicConfig(stream=sys.stderr)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "electrobin.settings_docker")

application = get_wsgi_application()
