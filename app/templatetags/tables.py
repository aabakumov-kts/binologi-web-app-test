from django import template

from apps.core.templatetags.core_tags import TableNodeWithDjango2Compat


register = template.Library()


def render_table_tag_function(func):
    table_template_name = func()

    class TableNodeClass(TableNodeWithDjango2Compat):
        template_name = table_template_name

    def render_table(parser, token):
        try:
            tag, table = token.split_contents()
        except ValueError:
            msg = '%r tag requires a single arguments' % token.split_contents()[0]
            raise template.TemplateSyntaxError(msg)
        return TableNodeClass(table)

    render_table.__name__ = func.__name__
    return render_table


@register.tag
@render_table_tag_function
def render_pressure_table():
    return 'table/pressure.html'


@register.tag
@render_table_tag_function
def render_traffic_table():
    return 'table/traffic.html'


@register.tag
@render_table_tag_function
def render_sim_table():
    return 'table/sim.html'


@register.tag
@render_table_tag_function
def render_humidity_table():
    return 'table/humidity.html'


@register.tag
@render_table_tag_function
def render_air_quality_table():
    return 'table/air_quality.html'
