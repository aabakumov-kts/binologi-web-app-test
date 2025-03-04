from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def is_checked(context, item, name, lst):
    value = hasattr(item, name) and getattr(item, name) or item[name]
    values_list = context.request.GET.getlist(lst)
    return str(value) in values_list and mark_safe('checked="checked"') or ''


@register.simple_tag(takes_context=True)
def is_selected(context, item, name, lst):
    value = hasattr(item, name) and getattr(item, name) or item[name]
    values_list = context.request.GET.getlist(lst)
    return str(value) in values_list and mark_safe('selected') or ''


@register.simple_tag(takes_context=True)
def array_value_of(context, item, name, lst, as_str=False):
    value = hasattr(item, name) and getattr(item, name) or item[name]
    values_list = context.request.GET.getlist(lst)
    format_str = '"{}",' if as_str else '{},'
    return str(value) in values_list and mark_safe(format_str.format(value)) or ''
