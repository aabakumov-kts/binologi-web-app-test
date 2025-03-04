from django import template
from django.conf import settings


register = template.Library()


@register.inclusion_tag('analytics/ga.html', takes_context=True)
def render_tracking_code(context):
    request = context['request']
    company_name = request.uac.company.name if request.uac.has_per_company_access and request.uac.company else None
    return {
        'ga_tracking_id': settings.GA_TRACKING_ID,
        'company_name': company_name,
    }
