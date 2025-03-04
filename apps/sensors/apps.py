from django.apps import AppConfig


class SensorsConfig(AppConfig):
    name = 'apps.sensors'

    def ready(self):
        from apps.sensors.shared import register_notification_generators
        # noinspection PyUnresolvedReferences
        import apps.sensors.signals  # noqa: F401
        register_notification_generators()
