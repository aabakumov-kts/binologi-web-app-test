from django.apps import AppConfig

from apps.trashbins.shared import register_notification_generators


class TrashbinsConfig(AppConfig):
    name = 'apps.trashbins'

    def ready(self):
        register_notification_generators()
