from django.utils.translation import ugettext_lazy as _
from table import Table
from table.columns import Column

from apps.core.tables import create_default_table_meta_class
from app.models import FullnessValues, Battery_Level, Error, Temperature, Collection


class FullnessTable(Table):
    address = Column(
        field='container.address',
        header=_('address'),
        attrs={
            'width': '150px'
        },
    )
    waste_type = Column(
        field='container.waste_type.title',
        header=_('waste type'),
        attrs={
            'width': '150px'
        },
    )
    serial_number = Column(
        field='container.serial_number',
        header=_('serial number'),
        attrs={
            'width': '200px'
        },
    )
    sector = Column(
        field='container.sector.name',
        header=_('sector'),
        attrs={
            'width': '150px'
        },
    )
    fullness_value = Column(
        field='fullness_value',
        header=_('fullness_header'),
        attrs={
            'width': '170px'
        },
    )
    created = Column(
        field='ctime',
        header=_('error create time'),
        attrs={
            'width': '140px'
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setattr(self.header_rows[0][3], 'append_template', 'info_buttons/sector.html')

    Meta = create_default_table_meta_class(FullnessValues)


class BatteryLevelTable(Table):
    city = Column(
        field='container.city.title',
        header=_('city'),
        attrs={
            'width': '100px'
        },
    )
    address = Column(
        field='container.address',
        header=_('address'),
        attrs={
            'width': '150px'
        },
    )
    waste_type = Column(
        field='container.waste_type.title',
        header=_('waste type'),
        attrs={
            'width': '150px'
        }
    )
    serial_number = Column(
        field='container.serial_number',
        header=_('serial number'),
        attrs={
            'width': '200px'
        }
    )
    sector = Column(
        field='container.sector.name',
        header=_('sector'),
        attrs={
            'width': '150px'
        }
    )
    battery_level = Column(
        field='level',
        header=_('battery_level_header'),
        attrs={
            'width': '150px'
        }
    )
    created = Column(
        field='ctime',
        header=_('error create time'),
        attrs={
            'width': '140px'
        }
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setattr(self.header_rows[0][4], 'append_template', 'info_buttons/sector.html')

    Meta = create_default_table_meta_class(Battery_Level)


class ErrorTable(Table):
    address = Column(
        field='container.address',
        header=_('address'),
        attrs={
            'width': '150px'
        }
    )
    container_type = Column(
        field='container.waste_type.title',
        header=_('waste type'),
        attrs={
            'width': '150px'
        }
    )
    serial_number = Column(
        field='container.serial_number',
        header=_('serial number'),
        attrs={
            'width': '170px'
        }
    )
    sector = Column(
        field='container.sector.name',
        header=_('sector'),
        attrs={
            'width': '120px'
        }
    )
    error_type = Column(
        field='error_type.title',
        header=_('error type'),
        attrs={
            'width': '150px'
        }
    )
    created = Column(
        field='ctime',
        header=_('error create time'),
        attrs={
            'width': '140px'
        }
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setattr(self.header_rows[0][3], 'append_template', 'info_buttons/sector.html')

    Meta = create_default_table_meta_class(Error)


class TemperatureTable(Table):
    address = Column(
        field='container.address',
        header=_('address'),
        attrs={
            'width': '150px'
        }
    )
    container_type = Column(
        field='container.waste_type.title',
        header=_('waste type'),
        attrs={
            'width': '150px'
        }
    )
    serial_number = Column(
        field='container.serial_number',
        header=_('serial number'),
        attrs={
            'width': '170px'
        }
    )
    temperature_value = Column(
        field='temperature_value',
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
    volume_before_pressed = Column(
        field='volume_before_pressed',
        header=_('volume_before_pressed'),
        sortable=False,
        attrs={
            'width': '170px'
        }
    )
    volume_after_pressed = Column(
        field='volume_after_pressed',
        header=_('volume_after_pressed'),
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

    Meta = create_default_table_meta_class(Collection)
