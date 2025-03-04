from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db.models.signals import post_save
from django.dispatch import receiver

from app.models import Container


# It's important to preserve signals receivers signature


# noinspection PyUnusedLocal
@receiver(post_save, sender=Container)
def update_default_password(sender, instance, created, **kwargs):
    if not created or instance.password != '':
        return
    raw_pwd = settings.E2E_DEFAULT_CONTAINER_PASSWORD if instance.serial_number.startswith('e2e-tests-bin-') else None
    instance.password = make_password(raw_pwd)
    instance.save(update_fields=['password'])
