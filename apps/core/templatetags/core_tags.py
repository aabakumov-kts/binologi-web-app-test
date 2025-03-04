from django import template
from table.templatetags.table_tags import TableNode


register = template.Library()


class TableNodeWithDjango2Compat(TableNode):
    def render(self, context):
        table = self.table.resolve(context)
        t = template.loader.get_template(table.opts.template_name or self.template_name)
        return t.render({'table': table})


@register.tag
def render_table_with_django2_compat(parser, token):
    try:
        tag, table = token.split_contents()
    except ValueError:
        msg = '%r tag requires a single table variable name argument' % token.split_contents()[0]
        raise template.TemplateSyntaxError(msg)
    return TableNodeWithDjango2Compat(table)
