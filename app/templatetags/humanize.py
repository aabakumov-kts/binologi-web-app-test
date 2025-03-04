from django import template
from django.utils.translation import ngettext_lazy

register = template.Library()


# Courtesy of this SO answer: https://stackoverflow.com/a/46928226/9335150
@register.filter
def smooth_timedelta(timedeltaobj):
    """Convert a datetime.timedelta object into Days, Hours, Minutes, Seconds."""
    secs = timedeltaobj.total_seconds()
    parts = []
    if secs > 86400:  # 60sec * 60min * 24hrs
        days = int(secs // 86400)
        parts.append(ngettext_lazy(
            '%(count)d day',
            '%(count)d days',
            days,
        ) % {
            'count': days,
        })
        secs = secs - days*86400

    if secs > 3600:
        hrs = int(secs // 3600)
        parts.append(ngettext_lazy(
            '%(count)d hour',
            '%(count)d hours',
            hrs,
        ) % {
            'count': hrs,
        })
        secs = secs - hrs*3600

    if secs > 60:
        mins = int(secs // 60)
        parts.append(ngettext_lazy(
            '%(count)d minute',
            '%(count)d minutes',
            mins,
        ) % {
            'count': mins,
        })
        secs = secs - mins*60

    if secs > 0:
        secs_int = round(secs)
        parts.append(ngettext_lazy(
            '%(count)d second',
            '%(count)d seconds',
            secs_int,
        ) % {
            'count': secs_int,
        })

    return ', '.join(parts)
