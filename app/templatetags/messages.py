from django import template
from django.contrib.messages import constants as messages


register = template.Library()


DEFAULT_ALERT_CLASS = 'alert-secondary'

LEVEL_TO_CLASS_MAPPING = {
    messages.INFO: 'alert-info',
    messages.SUCCESS: 'alert-success',
    messages.WARNING: 'alert-warning',
    messages.ERROR: 'alert-danger',
}


@register.simple_tag
def message_level_to_alert_class(message):
    return LEVEL_TO_CLASS_MAPPING[message.level] if message.level in LEVEL_TO_CLASS_MAPPING else DEFAULT_ALERT_CLASS
