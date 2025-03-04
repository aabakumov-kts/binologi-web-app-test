import os
import sys
import logging
import django

from channels.routing import get_default_application


logging.basicConfig(stream=sys.stderr)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "electrobin.settings_docker")

django.setup()

application = get_default_application()
