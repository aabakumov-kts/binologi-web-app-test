from django import template
from django.urls import resolve
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def url_match(context, name, css_class='active'):
    path = context['request'].path
    match = resolve(path)
    if match.view_name == name:
        return mark_safe(' class="%s" ' % css_class)
    return ''
