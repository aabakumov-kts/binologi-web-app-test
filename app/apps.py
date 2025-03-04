from django.apps import AppConfig

from app.shared import register_notification_generators


class ElectrobinConfig(AppConfig):
    name = 'app'

    def ready(self):
        # noinspection PyUnresolvedReferences
        import app.signals  # noqa: F401
        register_notification_generators()
