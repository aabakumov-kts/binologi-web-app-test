# coding=utf-8
from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from django.utils.html import escape
from table import Table
from table.columns import Column, LinkColumn, Link, DatetimeColumn
from table.utils import A
from django.utils import timezone

from apps.core.models import Company, City, Sectors
from apps.main.helpers import is_sector_referenced
from app.columns import ReferencedColumn
from app.models import (
    Container, RoutePoints, SimBalance, Humidity, AirQuality, Route, DriverUnavailabilityPeriod, Pressure, Traffic,
)
from app.helpers import any_routes_in_progress


DATETIME_FORMAT = '%d.%m.%Y %H:%M'


DATE_FORMAT = '%d.%m.%Y'


class ConditionalLinkColumn(LinkColumn):
    def __init__(self, conditions=None, **kwargs):
        super().__init__(**kwargs)
        self.conditions = conditions

    def render(self, obj):
        return self.delimiter.join([
            link.render(obj) for index, link in enumerate(self.links)
            if (self.conditions[index](obj) if self.conditions else True)])


class NullableDatetimeColumn(DatetimeColumn):
    def render(self, obj):
        datetime = A(self.field).resolve(obj)
        text = timezone.localtime(datetime).strftime(self.format) if datetime else ''
        return escape(text)


class UsersTable(Table):
    username = Column(
        field='username',
        header=_('username')
    )
    comment = Column(
        field='user_to_company.comment',
        header=_('comment')
    )
    company = Column(
        field='user_to_company.company.name',
        header=_('company'),
        visible=False,
    )
    role = Column(
        field='user_to_company.get_role_display',
        header=_('role'),
        sortable=False,
    )
    action = LinkColumn(
        header=_('action'),
        sortable=False,
        links=[Link(text=_('edit'), viewname='users:update', args=(A('id'),)),
               Link(text=_('delete'), viewname='users:delete',
                    args=(A('id'),))]
    )

    class Meta:
        model = User
        ajax = True
        ajax_source = reverse_lazy('users:data')
        zero_records = _('no_records_message')
        info_format = _('total_records_template')


class CompanyUserTable(UsersTable):
    class Meta:
        ajax = False


class CompanyTable(Table):
    name = ReferencedColumn(
        field='name',
        header=_('title'),
        viewname='companies:users',
    )
    country = Column(
        field='country',
        header=_('country')
    )
    minsim = Column(
        field='minsim',
        header=_('minimal SIM balance')
    )
    username_prefix = Column(
        field='username_prefix',
        header=_('username prefix')
    )
    action = LinkColumn(
        header=_('action'),
        sortable=False,
        links=[
            Link(text=_('edit'), viewname='companies:update', args=(A('id'),)),
            Link(text=_('delete'), viewname='companies:delete',
                 args=(A('id'),))]
    )

    class Meta:
        model = Company
        ajax = True
        ajax_source = reverse_lazy('companies:data')
        zero_records = _('no_records_message')
        info_format = _('total_records_template')


class ContainerTable(Table):
    serial_number = Column(
        field='serial_number',
        header=_('serial number'),
    )
    company = Column(
        field='company.name',
        header=_('company'),
        visible=False,
    )
    sector = Column(
        field='sector.name',
        header=_('sector'),
    )
    action_superadmin = LinkColumn(
        header=_('action'),
        sortable=False,
        searchable=False,
        links=[
            Link(text=_('detail'), viewname='containers:detail', args=(A('id'),)),
            Link(text=_('edit'), viewname='containers:update', args=(A('id'),)),
            Link(text=_('delete'), viewname='containers:delete', args=(A('id'),)),
        ],
        visible=False,
    )
    action_operator = LinkColumn(
        header=_('action'),
        sortable=False,
        searchable=False,
        links=[
            Link(text=_('detail'), viewname='containers:detail', args=(A('id'),)),
            Link(text=_('edit'), viewname='containers:update', args=(A('id'),)),
        ],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setattr(self.header_rows[0][2], 'append_template', 'info_buttons/sector.html')

    class Meta:
        model = Container
        ajax = True
        ajax_source = reverse_lazy('containers:data')
        zero_records = _('no_records_message')
        info_format = _('total_records_template')


class SectorsTable(Table):
    name = Column(
        field='name',
        header=_('title')
    )
    company = Column(
        field='company.name',
        header=_('company'),
        visible=False,
    )
    action = ConditionalLinkColumn(
        header=_('action'),
        searchable=False,
        sortable=False,
        links=[
            Link(text=_('edit'), viewname='sectors:update', args=(A('id'),)),
            Link(text=_('delete'), viewname='sectors:delete', args=(A('id'),)),
        ],
        conditions=[
            lambda sector: True,
            lambda sector: not (sector.is_last_for_company or is_sector_referenced(sector)),
        ],
    )

    class Meta:
        model = Sectors
        ajax = True
        ajax_source = reverse_lazy('sectors:data')
        zero_records = _('no_records_message')
        info_format = _('total_records_template')


class CityTable(Table):
    country = Column(
        field='country.name',
        header=_('country'),
    )
    city = Column(
        field='title',
        header=_('city'),
    )
    action = LinkColumn(
        header=_('action'),
        sortable=False,
        searchable=False,
        links=[
            Link(text=_('edit'), viewname='cities:update', args=(A('id'),)),
            Link(text=_('delete'), viewname='cities:delete', args=(A('id'),)),
        ],
    )

    class Meta:
        model = City
        ajax = True
        ajax_source = reverse_lazy('cities:data')
        localize = ('country', 'city',)
        zero_records = _('no_records_message')
        info_format = _('total_records_template')


def create_container_columns_table_mixin(city_kwargs=None, address_kwargs=None, sector_kwargs=None):
    effective_city_kwargs = {
        'attrs': {
            'width': '100px'
        }
    }
    effective_city_kwargs.update(city_kwargs if city_kwargs else {})
    effective_address_kwargs = {
        'attrs': {
            'width': '150px'
        }
    }
    effective_address_kwargs.update(address_kwargs if address_kwargs else {})
    effective_sector_kwargs = {
        'attrs': {
            'width': '150px'
        }
    }
    effective_sector_kwargs.update(sector_kwargs if sector_kwargs else {})

    # Subclassing Table here is important due to columns inheritance implementation
    # See table/tables.py:216 for details
    class ContainerColumnsTableMixin(Table):
        company = Column(
            field='container.company.name',
            header=_('company'),
            attrs={
                'width': '100px',
                'id': 'container-company-name'
            }
        )
        country = Column(
            field='container.country.name',
            header=_('country'),
            attrs={
                'width': '100px'
            }
        )
        city = Column(
            field='container.city.title',
            header=_('city'),
            **effective_city_kwargs,
        )
        address = Column(
            field='container.address',
            header=_('address'),
            **effective_address_kwargs,
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
            **effective_sector_kwargs
        )

    return ContainerColumnsTableMixin


class PressureTable(create_container_columns_table_mixin(sector_kwargs={'visible': False}), Table):
    pressure_value = Column(
        field='pressure_value',
        header=_('pressure_header'),
        attrs={
            'width': '200px'
        }
    )
    created = Column(
        field='ctime',
        header=_('error create time'),
        attrs={
            'width': '140px'
        }
    )
    elapsed = Column(
        field='elapsed',
        header=_('elapsed'),
        searchable=False,
        sortable=False,
        attrs={
            'width': '140px'
        }
    )

    class Meta:
        model = Pressure
        ajax = True
        zero_records = _('no_records_message')
        info_format = _('total_records_template')


class TrafficTable(create_container_columns_table_mixin(sector_kwargs={'visible': False}), Table):
    traffic_value = Column(
        field='traffic_value',
        header=_('traffic'),
        attrs={
            'width': '120px'
        }
    )
    created = Column(
        field='ctime',
        header=_('error create time'),
        attrs={
            'width': '140px'
        }
    )
    elapsed = Column(
        field='elapsed',
        header=_('elapsed'),
        searchable=False,
        sortable=False,
        attrs={
            'width': '140px'
        }
    )

    class Meta:
        model = Traffic
        ajax = True
        zero_records = _('no_records_message')
        info_format = _('total_records_template')


class SimBalanceTable(create_container_columns_table_mixin(sector_kwargs={'visible': False}), Table):
    phone = Column(
        field='container.phone_number',
        header=_('phone number'),
        attrs={
            'width': '150px',
        },
        visible=False
    )
    balance = Column(
        field='balance',
        header=_('balance'),
        attrs={
            'width': '100px'
        }
    )
    created = Column(
        field='ctime',
        header=_('error create time'),
        attrs={
            'width': '140px'
        }
    )
    elapsed = Column(
        field='elapsed',
        header=_('elapsed'),
        searchable=False,
        sortable=False,
        attrs={
            'width': '140px'
        }
    )

    class Meta:
        model = SimBalance
        ajax = True
        zero_records = _('no_records_message')
        info_format = _('total_records_template')


class HumidityTable(Table):
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
    humidity_value = Column(
        field='humidity_value',
        header=_('humidity_header'),
        attrs={
            'width': '170px'
        }
    )
    created = Column(
        field='ctime',
        header=_('create time'),
        attrs={
            'width': '140px'
        }
    )
    elapsed = Column(
        field='elapsed',
        header=_('elapsed'),
        searchable=False,
        sortable=False,
        attrs={
            'width': '140px'
        }
    )

    class Meta:
        model = Humidity
        ajax = True
        zero_records = _('no_records_message')
        info_format = _('total_records_template')


class AirQualityTable(Table):
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
    air_quality_value = Column(
        field='air_quality_value',
        header=_('air_quality'),
        attrs={
            'width': '200px'
        }
    )
    created = Column(
        field='ctime',
        header=_('create time'),
        attrs={
            'width': '140px'
        }
    )
    elapsed = Column(
        field='elapsed',
        header=_('elapsed'),
        searchable=False,
        sortable=False,
        attrs={
            'width': '140px'
        }
    )

    def __init__(self, *args, **kwargs):
        super(AirQualityTable, self).__init__(*args, **kwargs)
        setattr(self.header_rows[0][3], 'append_template', 'info_buttons/air_quality.html')

    class Meta:
        model = AirQuality
        ajax = True
        zero_records = _('no_records_message')
        info_format = _('total_records_template')


class RoutesTable(Table):
    route_no = Column(field='id', header=_('route_no'))
    username = Column(field='user.username', header=_('driver'))
    created = NullableDatetimeColumn(field='ctime', header=_('route created'), format=DATETIME_FORMAT)
    points_count = Column(field='route_points_count', searchable=False, sortable=False, header=_('points count'))
    status = Column(field='humanized_status', header=_('status'), searchable=False, sortable=False)
    action = ConditionalLinkColumn(
        header=_('action'),
        searchable=False,
        sortable=False,
        links=[
            Link(text=_('detail'), viewname='routes:detail', args=(A('id'),)),
            Link(text=_('abort'), viewname='routes:abort', args=(A('id'),)),
        ],
        conditions=[
            lambda route: True,
            lambda route: not route.is_finished,
        ],
    )

    class Meta:
        model = Route
        ajax = True
        ajax_source = reverse_lazy('routes:data')
        zero_records = _('no_records_message')
        info_format = _('total_records_template')


class RoutePointsTable(Table):
    container_serial_number = Column(field='container.serial_number', header=_('serial number'))
    sensor_serial_number = Column(field='sensor.serial_number', header=_('serial number'))
    modified = NullableDatetimeColumn(field='mtime', header=_('update time'), format=DATETIME_FORMAT)
    comment = Column(field='comment', header=_('comment'))
    status = Column(field='humanized_status', header=_('status'))
    fullness = Column(field='fullness', header=_('fullness'))
    volume = Column(field='volume', header=_('volume'))

    class Meta:
        model = RoutePoints
        zero_records = _('no_records_message')
        info_format = _('total_records_template')


class DriverAvailabilityColumn(Column):
    def render(self, obj):
        available = not (any_routes_in_progress(obj) or DriverUnavailabilityPeriod.any_period_active_now(obj))
        return _('yes') if available else _('no')


class DriversTable(Table):
    username = Column(field='username', header=_('driver'))
    comment = Column(field='user_to_company.comment', header=_('comment'))
    company = Column(field='user_to_company.company.name', header=_('company'), visible=False, searchable=False)
    availability = DriverAvailabilityColumn(header=_('available?'), searchable=False)
    action = LinkColumn(
        header=_('action'),
        searchable=False,
        sortable=False,
        links=[
            Link(text=_('detail'), viewname='drivers:detail', args=(A('id'),)),
        ],
    )

    class Meta:
        model = User
        ajax = True
        ajax_source = reverse_lazy('drivers:data')
        zero_records = _('no_records_message')
        info_format = _('total_records_template')


class DriverUnavailabilityPeriodTable(Table):
    begin = DatetimeColumn(field='begin', header=_('period begin'), format=DATE_FORMAT)
    end = DatetimeColumn(field='end', header=_('period end'), format=DATE_FORMAT)
    reason = Column(field='reason', header=_('reason'))
    action = LinkColumn(
        header=_('action'),
        sortable=False,
        searchable=False,
        links=[
            Link(text=_('edit'), viewname='drivers:update_unavailability_period', args=(A('id'),)),
            Link(text=_('delete'), viewname='drivers:delete_unavailability_period', args=(A('id'),)),
        ],
    )

    class Meta:
        model = DriverUnavailabilityPeriod
        zero_records = _('no_records_message')
        info_format = _('total_records_template')
