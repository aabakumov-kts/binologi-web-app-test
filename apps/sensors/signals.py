import binascii
import os

from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from slugify import slugify

from apps.core.models import Company
from apps.sensors.models import SensorSettingsProfile, SensorsAuthCredentials, VerneMQAuthAcl


settings_fields = [f.name for f in SensorSettingsProfile._meta.get_fields() if f.name != 'id']


# It's important to preserve signals receivers signature


@receiver(pre_save, sender=SensorSettingsProfile)
def track_changed_settings(sender, instance, **kwargs):
    if instance.pk is None:
        # When new profile is created there's no sensors to notify
        return
    db_instance = SensorSettingsProfile.objects.get(pk=instance.pk)
    changed_fields = []
    for f in settings_fields:
        if getattr(instance, f) != getattr(db_instance, f):
            changed_fields.append(f)
    instance.changed_fields = changed_fields


@receiver(post_save, sender=SensorSettingsProfile)
def configure_devices(sender, instance, created, **kwargs):
    changed_fields = getattr(instance, 'changed_fields', [])
    if changed_fields:
        from apps.sensors.tasks import configure_devices
        # For yet unclear reasons it's required to set some countdown for task execution.
        # Otherwise, task will get stale settings profile from the DB.
        configure_devices.apply_async(args=[instance.pk, changed_fields], countdown=1)


SENSOR_USERNAME_SUFFIX = 'sensor'


@receiver(post_save, sender=Company)
def create_sensors_auth(sender, instance, created, **kwargs):
    if created:
        try:
            _ = instance.sensorsauthcredentials
        except Company.sensorsauthcredentials.RelatedObjectDoesNotExist:
            username_prefix = (instance.username_prefix if instance.username_prefix else slugify(instance.name))[:25]
            if not username_prefix.endswith('-'):
                username_prefix += '-'
            username = username_prefix + SENSOR_USERNAME_SUFFIX
            password = binascii.hexlify(os.urandom(16)).decode('utf-8')
            SensorsAuthCredentials.objects.create(company=instance, username=username, password=password)
            # TODO: Restore this when MQTT broker will support DB-based auth
            # server_side_password_hash = VerneMQAuthAcl.hash_password(password)
            # if server_side_password_hash:
            #     VerneMQAuthAcl.objects.create(
            #         mountpoint=VerneMQAuthAcl.DEFAULT_MOUNTPOINT, client_id=VerneMQAuthAcl.DEFAULT_CLIENT_ID,
            #         username=username, password=server_side_password_hash, publish_acl=VerneMQAuthAcl.DEFAULT_ACL,
            #         subscribe_acl=VerneMQAuthAcl.DEFAULT_ACL)


@receiver(post_delete, sender=SensorsAuthCredentials)
def delete_vernemq_auth_acl(sender, instance, using, **kwargs):
    VerneMQAuthAcl.objects.filter(username=instance.username).delete()
