from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from notifications.models import Notification
from table import Table
from table.columns import Column, LinkColumn, Link
from table.utils import A


def create_default_table_meta_class(table_model):
    class Meta:
        model = table_model
        ajax = True
        paging = True
        zero_records = _('no_records_message')
        info_format = _('total_records_template')

    return Meta


class NotificationTable(Table):
    level = Column(
        field='level',
        header=_('priority'),
    )
    elapsed = Column(
        field='elapsed',
        header=_('elapsed'),
        searchable=False,
        sortable=False,
    )
    verb = Column(
        field='verb',
        header=_('notification type'),
    )
    actor = Column(
        field='actor',
        header=_('source'),
        sortable=False,
    )
    action = LinkColumn(
        header=_('action'),
        sortable=False,
        links=[
            Link(text=_('view'), viewname='notifications_follow', args=(A('id'),)),
        ]
    )

    class Meta:
        model = Notification
        ajax = True
        paging = True
        ajax_source = reverse_lazy('notifications_table_data')
        zero_records = _('no_records_message')
        info_format = _('total_records_template')
        search = False
        page_length = 50
