from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from table import Table
from table.columns import Column, LinkColumn, Link
from table.utils import A

from apps.core.tables import create_default_table_meta_class
from app.models import RoutePoints
from apps.sensors.models import Sensor, Fullness, BatteryLevel, Error, Temperature


class BooleanColumn(Column):
    def render(self, obj):
        val = A(self.field).resolve(obj)
        return _('yes') if val else _('no')


class SensorTable(Table):
    serial_number = Column(field='serial_number', header=_('serial number'))
    country = Column(field='country.name', header=_('country'))
    disabled = BooleanColumn(field='disabled', header=_('disabled'))
    action = LinkColumn(
        header=_('action'),
        sortable=False,
        searchable=False,
        links=[
            Link(text=_('edit'), viewname='sensors:update', args=(A('id'),)),
            Link(text=_('control'), viewname='sensors:control-main', args=(A('id'),)),
        ],
    )

    class Meta:
        model = Sensor
        ajax = True
        ajax_source = reverse_lazy('sensors:data')
        zero_records = _('no_records_message')
        info_format = _('total_records_template')


class FullnessTable(Table):
    address = Column(
        field='sensor.address',
        header=_('address'),
        attrs={
            'width': '200px'
        },
    )
    serial_number = Column(
        field='sensor.serial_number',
        header=_('serial number'),
        attrs={
            'width': '230px'
        },
    )
    fullness_value = Column(
        field='value',
        header=_('fullness_header'),
        attrs={
            'width': '170px'
        }
    )
    created = Column(
        field='ctime',
        header=_('error create time'),
        attrs={
            'width': '170px'
        }
    )

    Meta = create_default_table_meta_class(Fullness)


class BatteryLevelTable(Table):
    city = Column(
        field='sensor.city.title',
        header=_('city'),
        attrs={
            'width': '100px'
        },
    )
    address = Column(
        field='sensor.address',
        header=_('address'),
        attrs={
            'width': '150px'
        },
    )
    serial_number = Column(
        field='sensor.serial_number',
        header=_('serial number'),
        attrs={
            'width': '170px'
        }
    )
    battery_level = Column(
        field='level',
        header=_('battery_level_header'),
        attrs={
            'width': '170px'
        }
    )
    created = Column(
        field='ctime',
        header=_('error create time'),
        attrs={
            'width': '140px'
        }
    )

    Meta = create_default_table_meta_class(BatteryLevel)


class ErrorTable(Table):
    address = Column(
        field='sensor.address',
        header=_('address'),
        attrs={
            'width': '200px'
        }
    )
    serial_number = Column(
        field='sensor.serial_number',
        header=_('serial number'),
        attrs={
            'width': '230px'
        }
    )
    error_type = Column(
        field='error_type.title',
        header=_('error type'),
        attrs={
            'width': '300px'
        }
    )
    created = Column(
        field='ctime',
        header=_('error create time'),
        attrs={
            'width': '200px'
        }
    )

    Meta = create_default_table_meta_class(Error)


class TemperatureTable(Table):
    address = Column(
        field='sensor.address',
        header=_('address'),
        attrs={
            'width': '150px'
        }
    )
    serial_number = Column(
        field='sensor.serial_number',
        header=_('serial number'),
        attrs={
            'width': '170px'
        }
    )
    temperature_value = Column(
        field='value',
        header=_('temperature_header'),
        attrs={
            'width': '170px'
        }
    )
    created = Column(
        field='ctime',
        header=_('error create time'),
        attrs={
            'width': '140px'
        }
    )

    Meta = create_default_table_meta_class(Temperature)


class CollectionTable(Table):
    fullness_color = Column(
        field='fullness_color',
        header=_('fullness'),
        sortable=False,
        attrs={
            'width': '100px',
        },
    )
    collections_count = Column(
        field='collections_count',
        header=_('count'),
        sortable=False,
        attrs={
            'width': '100px'
        }
    )
    volume = Column(
        field='volume',
        header=_('volume'),
        sortable=False,
        attrs={
            'width': '170px'
        }
    )
    weight = Column(
        field='weight',
        header=_('weight'),
        sortable=False,
        attrs={
            'width': '150px'
        }
    )

    Meta = create_default_table_meta_class(RoutePoints)
