from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _, override as current_language_override

from apps.core.models import Company, Sectors


# It's important to preserve signals receivers signature


# noinspection PyUnusedLocal
@receiver(post_save, sender=Company)
def create_default_sector(sender, instance, created, **kwargs):
    if created and instance.sectors_set.count() == 0:
        with current_language_override(instance.lang):
            Sectors.objects.create(company=instance, name=_('Default'))
