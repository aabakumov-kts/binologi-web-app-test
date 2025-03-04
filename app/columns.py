from django.urls import reverse
from django.utils.html import format_html
from table.columns import Column


class ReferencedColumn(Column):
    def __init__(self, viewname, *args, **kwargs):
        super(ReferencedColumn, self).__init__(*args, **kwargs)
        self.viewname = viewname

    def render(self, obj):
        text = super(ReferencedColumn, self).render(obj)
        link = reverse(self.viewname, args=(obj.pk,))
        return format_html('<a href=\"{}\">{}</a>', link, text)
