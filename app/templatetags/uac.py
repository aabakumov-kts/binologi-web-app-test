from django import template


register = template.Library()


@register.simple_tag(takes_context=True)
def check_feature_enabled(context, feature):
    request = context['request']
    return request.uac.check_feature_enabled(feature)
