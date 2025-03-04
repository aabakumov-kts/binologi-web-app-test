from django.utils.translation import ugettext_lazy as _
from table import Table
from table.columns import Column

from app.models import RoutesDrivers


class TrackTable(Table):
    containers_count = Column(
        field='containers_count',
        header=_('count containers'),
        attrs={
            'width': '100px'
        }
    )
    track_full = Column(
        field='track_full',
        header=_('track_full'),
        attrs={
            'width': '100px'
        }
    )
    driver_username = Column(
        field='driver__username',
        header=_('username'),
        attrs={
            'width': '100px'
        }
    )
    driver_comment = Column(
        field='comment',
        header=_('comment'),
        attrs={
            'width': '100px',
        }
    )

    class Meta:
        model = RoutesDrivers
        ajax = True
        pagination = False
        zero_records = _('no_records_message')
        info_format = _('total_records_template')
