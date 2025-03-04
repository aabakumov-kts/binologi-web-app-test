import datetime
import ujson as json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.formats import date_format
from django.utils.translation import ugettext_lazy as _, ngettext_lazy
from django.views import generic
from django.views.generic.detail import SingleObjectTemplateResponseMixin, BaseDetailView
from rest_framework.authtoken.models import Token
from table.views import FeedDataView

from app.forms import (
    UserForm, CompanyForm, SectorForm, CityForm, DriverUnavailabilityPeriodForm, get_container_form_class,
)
from app.helpers import any_routes_in_progress
from app.models import (
    Container, Route, RoutePoints, Routes, RoutesDrivers, ROUTE_STATUS_ABORTED_BY_OPERATOR,
    ROUTE_POINT_STATUS_NOT_COLLECTED,
)
from app.redis_client import RedisClient
from app.tables import (
    UsersTable, CompanyUserTable, CompanyTable, ContainerTable, SectorsTable, CityTable, RoutesTable, RoutePointsTable,
    DriversTable, DriverUnavailabilityPeriodTable, DriverUnavailabilityPeriod,
)
from apps.core.data import Fullness, get_battery_card_class
from apps.core.helpers import CompanyDeviceProfile
from apps.core.models import Company, UsersToCompany, City, Sectors
from apps.core.views import (
    ensure_object_access_or_404, LOW_BATTERY_LEVEL_ICON_DATA_URL, send_route, BIN_ON_ROUTE_ICON_DATA_URL,
    WARNING_ICON_DATA_URL,
)
from apps.main.helpers import is_sector_referenced, get_effective_company_device_profile


"""
Пользователи
"""


class UserList(LoginRequiredMixin, generic.TemplateView):
    template_name = 'users/list.html'

    def get_context_data(self, **kwargs):
        context = super(UserList, self).get_context_data(**kwargs)
        table = UsersTable()
        if len(table.columns) >= 5 and self.request.uac.is_superadmin:
            table.columns[2].visible = True
        context['users'] = table
        return context


class CompanyUserList(LoginRequiredMixin, generic.TemplateView):
    company = None
    template_name = 'users/list.html'

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs.get('pk'))
        return super(CompanyUserList, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(CompanyUserList, self).get_context_data(**kwargs)
        users_pk = self.company.userstocompany_set.values_list('pk')
        users = User.objects.filter(pk__in=users_pk)
        context['users'] = CompanyUserTable(users)
        return context


def save_user_form(form):
    user = form.save()

    role = form.cleaned_data.get('role')
    company = form.cleaned_data.get('company')
    password = form.cleaned_data.get('new_password')
    timezone = form.cleaned_data.get('timezone')
    comment = form.cleaned_data.get('comment')

    if not hasattr(user, 'user_to_company'):
        user.user_to_company = UsersToCompany()
    user.user_to_company.role = role
    user.user_to_company.company = company
    user.user_to_company.timezone = timezone
    user.user_to_company.comment = comment
    user.user_to_company.save()

    if password:
        user.set_password(password)
        user.save()

    return user


class UserCreate(generic.CreateView):
    model = User
    form_class = UserForm
    template_name = 'users/user_form.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not (request.uac.is_superadmin or request.uac.is_administrator):
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = save_user_form(form)
        Token.objects.create(user=user)
        messages.success(self.request, _('New user "%(username)s" created successfully') % {'username': user.username})
        return redirect('users:list')

    def get_form_kwargs(self):
        kwarg = super().get_form_kwargs()
        kwarg['request'] = self.request
        return kwarg


class UserUpdate(LoginRequiredMixin, generic.UpdateView):
    model = User
    form_class = UserForm
    template_name = 'users/user_form.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not (self.request.uac.is_superadmin or self.request.uac.is_administrator):
            raise Http404()
        return obj

    def form_valid(self, form):
        user = save_user_form(form)
        messages.success(self.request, _('User "%(username)s" updated successfully') % {'username': user.username})
        return redirect('users:list')

    def get_form_kwargs(self):
        kwarg = super().get_form_kwargs()
        kwarg['request'] = self.request
        return kwarg

    def get_initial(self):
        initial = super().get_initial()
        if hasattr(self.object, 'user_to_company'):
            initial['company'] = self.object.user_to_company.company
            initial['role'] = self.object.user_to_company.role
            initial['timezone'] = self.object.user_to_company.timezone
        return initial


class UserDelete(LoginRequiredMixin, generic.DeleteView):
    model = User
    template_name = 'users/confirm_delete.html'

    def get_object(self, queryset=None):
        obj = super(UserDelete, self).get_object(queryset)
        if not (self.request.uac.is_superadmin or self.request.uac.is_administrator):
            raise Http404()
        return obj

    def get_success_url(self):
        return reverse('users:list')

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        user = kwargs['object']
        deleting_self = self._deleting_self(user)
        result.update(
            deleting_self=deleting_self,
            button_attrs='disabled' if deleting_self else None)
        return result

    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        if self._deleting_self(user):
            raise PermissionDenied('Removal of yourself is not allowed')
        messages.success(request, _('User "%(username)s" deleted successfully') % {'username': user.username})
        return super().delete(request, *args, **kwargs)

    def _deleting_self(self, user):
        return self.request.user.id == user.id


class UsersDataView(LoginRequiredMixin, FeedDataView):
    token = UsersTable.token
    model = UsersTable
    columns = ['id', 'username']
    order_columns = ['id', 'username']

    def get_queryset(self):
        queryset = super(UsersDataView, self).get_queryset()
        if self.request.uac.is_superadmin:
            return queryset
        if self.request.uac.has_per_company_access:
            return queryset.filter(user_to_company__company=self.request.uac.company)
        raise Http404()

    def filter_queryset(self, qs):
        # use parameters passed in GET request to filter queryset

        # simple example:
        search = self.request.GET.get('search[value]', None)
        if search:
            qs = qs.filter(id__istartswith=search)

        # more advanced example using extra parameters
        filter_customer = self.request.GET.get('sSearch', None)

        if filter_customer:
            customer_parts = filter_customer.split(' ')
            qs_params = None
            for part in customer_parts:
                roles = [x[0] for x in [x for x in UsersToCompany.ROLES if part in x[1]]]
                q = Q(user_to_company__comment__icontains=part) | \
                    Q(username__icontains=part) | \
                    Q(user_to_company__role__in=roles)
                qs_params = qs_params | q if qs_params else q
                qs = qs.filter(qs_params)

        return qs


"""
Компании
"""


class CompanyList(LoginRequiredMixin, generic.TemplateView):
    template_name = 'companies/list.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.uac.is_superadmin:
            raise Http404()
        return super(CompanyList, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(CompanyList, self).get_context_data(**kwargs)
        context['companies'] = CompanyTable()
        return context


class CompanyCreate(LoginRequiredMixin, generic.CreateView):
    model = Company
    form_class = CompanyForm
    template_name = 'companies/company_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.uac.is_superadmin:
            raise Http404()
        return super(CompanyCreate, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        company = form.save()
        messages.success(self.request, _('New company "%(company_name)s" created successfully') % {'company_name': company.name})
        return redirect('companies:list')


class CompanyUpdate(LoginRequiredMixin, generic.UpdateView):
    model = Company
    form_class = CompanyForm
    template_name = 'companies/company_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.uac.is_superadmin:
            raise Http404()
        return super(CompanyUpdate, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        company = form.save()
        messages.success(self.request,
                         _('Company "%(company_name)s" updated successfully') % {'company_name': company.name})
        return redirect('companies:list')


class CompanyDelete(LoginRequiredMixin, generic.DeleteView):
    model = Company
    template_name = 'companies/confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.uac.is_superadmin:
            raise Http404()
        return super(CompanyDelete, self).dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('companies:list')

    def delete(self, request, *args, **kwargs):
        result = super().delete(request, *args, **kwargs)
        messages.success(request,
                         _('Company "%(company_name)s" deleted successfully') % {'company_name': self.object.name})
        return result


class CompaniesDataView(LoginRequiredMixin, FeedDataView):
    token = CompanyTable.token
    model = CompanyTable
    columns = ['id', 'name']
    order_columns = ['id', 'name']

    def get_queryset(self):
        queryset = super(CompaniesDataView, self).get_queryset()
        if self.request.uac.is_superadmin:
            return queryset
        elif self.request.uac.has_per_company_access:
            return queryset.filter(pk=self.request.uac.company.pk)
        raise Http404()

    def filter_queryset(self, qs):
        # use parameters passed in GET request to filter queryset

        # simple example:
        search = self.request.GET.get('search[value]', None)
        if search:
            qs = qs.filter(id__istartswith=search)

        # more advanced example using extra parameters
        filter_customer = self.request.GET.get('sSearch', None)

        if filter_customer:
            customer_parts = [_f for _f in filter_customer.split(' ') if _f]
            qs_params = None
            for part in customer_parts:
                q = Q(name__icontains=part) | \
                    Q(country__name__icontains=part)
                qs_params = qs_params | q if qs_params else q
                qs = qs.filter(qs_params)
        return qs


class ContainerList(LoginRequiredMixin, generic.TemplateView):
    template_name = 'containers/list.html'

    def get_context_data(self, **kwargs):
        if not (self.request.uac.is_superadmin or self.request.uac.has_per_company_access):
            raise Http404()
        context = super(ContainerList, self).get_context_data(**kwargs)
        table = ContainerTable()
        if len(table.columns) >= 5:
            company_column = table.columns[1]
            superadmin_actions = table.columns[3]
            operator_actions = table.columns[4]
            if self.request.uac.is_superadmin:
                company_column.visible = True
                superadmin_actions.visible = True
                operator_actions.visible = False
        context['containers'] = table
        return context


class ContainerCreate(generic.CreateView):
    model = Container
    template_name = 'containers/container_form.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not self.request.uac.is_superadmin:
            raise Http404()
        return super(ContainerCreate, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        container = form.save(commit=False)
        if self.request.uac.has_per_company_access:
            container.company = self.request.uac.company
        container.save()
        messages.success(self.request,
                         _('New container "%(serial)s" created successfully') % {'serial': container.serial_number})
        return redirect('containers:list')

    def get_form_kwargs(self):
        kwargs = super(ContainerCreate, self).get_form_kwargs()
        kwargs.update(request=self.request)
        return kwargs

    def get_form_class(self):
        return get_container_form_class()


class ContainerUpdate(LoginRequiredMixin, generic.UpdateView):
    model = Container
    template_name = 'containers/container_form.html'

    def form_valid(self, form):
        container = form.save(commit=False)
        if self.request.uac.has_per_company_access:
            container.company = self.request.uac.company
        container.save()
        messages.success(self.request,
                         _('Container "%(serial)s" updated successfully') % {'serial': container.serial_number})
        return redirect('containers:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(request=self.request)
        return kwargs

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        ensure_object_access_or_404(self.request, obj.company)
        return obj

    def get_form_class(self):
        return get_container_form_class()


class ContainerDelete(LoginRequiredMixin, generic.DeleteView):
    model = Container
    template_name = 'containers/confirm_delete.html'

    def get_object(self, queryset=None):
        obj = super(ContainerDelete, self).get_object(queryset)
        if not self.request.uac.is_superadmin:
            raise Http404()
        return obj

    def get_success_url(self):
        return reverse('containers:list')

    def delete(self, request, *args, **kwargs):
        result = super().delete(request, *args, **kwargs)
        messages.success(request,
                         _('Container "%(serial)s" deleted successfully') % {'serial': self.object.serial_number})
        return result


class ContainersDataView(LoginRequiredMixin, FeedDataView):
    token = ContainerTable.token

    def get_queryset(self):
        queryset = super(ContainersDataView, self).get_queryset()
        if self.request.uac.is_superadmin:
            return queryset
        elif self.request.uac.has_per_company_access:
            return queryset.filter(company=self.request.uac.company)
        raise Http404()


def get_air_quality_card_class(value):
    if value <= 50:
        cls = 'dark-green'
    elif value <= 100:
        cls = 'yellow'
    elif value <= 150:
        cls = 'orange'
    elif value <= 200:
        cls = 'red'
    elif value <= 300:
        cls = 'violet'
    else:
        cls = 'black'
    return cls


def populate_container_context(context, container):
    if not container.is_master:
        title = _('satellite bin')
    else:
        title = _('bin') if len(container.satellites.all()) == 0 else _('master bin')
    context['title'] = title

    context['low_battery_level_icon_url'] = LOW_BATTERY_LEVEL_ICON_DATA_URL
    context['bin_on_route_icon_url'] = BIN_ON_ROUTE_ICON_DATA_URL
    context['warning_icon_url'] = WARNING_ICON_DATA_URL
    context['any_active_errors'] = container.errors.filter(actual=1).count() > 0
    context['low_battery_level'] = \
        container.is_master and container.battery <= settings.LOW_BATTERY_STATUS_ICON_LEVEL_THRESHOLD
    context['any_active_routes'] = container.routepoints.filter(status=ROUTE_POINT_STATUS_NOT_COLLECTED).count() > 0
    context['fullness_card_class'] = Fullness.get_card_class(container.fullness)
    context['battery_card_class'] = get_battery_card_class(container.battery)
    context['air_quality_card_class'] = get_air_quality_card_class(container.air_quality)

    today_date = datetime.date.today()
    month_ago = today_date - datetime.timedelta(days=30)
    collection_qs = container.collection_set.filter(ctime__gt=month_ago).order_by('-ctime')
    collections_count = collection_qs.count()
    if collections_count == 0:
        context['collection_stats_summary'] = _('There were no collections during last 30 days.')
        context['last_collection_info'] = None
    else:
        context['collection_stats_summary'] = ngettext_lazy(
            'There was %(count)d collection during last 30 days.',
            'There were %(count)d collections during last 30 days.',
            collections_count,
        ) % {
            'count': collections_count,
        }
        last_collection_date = date_format(timezone.localtime(collection_qs.first().ctime), "SHORT_DATE_FORMAT")
        context['last_collection_info'] = _('Last collection was on %(date)s.') % {'date': last_collection_date}

    if container.is_master:
        week_ago = today_date - datetime.timedelta(days=7)
        trash_receiver_open_count = container.trash_recv_stats.filter(ctime__gt=week_ago).\
            aggregate(open_total=Sum('open_count'))['open_total'] or 0
        if trash_receiver_open_count == 0:
            context['trash_recv_stats_summary'] = _('There were no trash receiver openings during last 7 days.')
        else:
            context['trash_recv_stats_summary'] = ngettext_lazy(
                'There was %(count)d trash receiver opening during last 7 days.',
                'There were %(count)d trash receiver openings during last 7 days.',
                trash_receiver_open_count,
            ) % {
                'count': trash_receiver_open_count,
            }


class ContainerMapCard(generic.DetailView):
    model = Container
    template_name = 'containers/map_card.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        ensure_object_access_or_404(self.request, obj.company)
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        populate_container_context(context, self.object)
        context['is_master'] = self.object.is_master
        if self.object.is_master:
            error_types = set()
            for err in self.object.errors.filter(actual=1):
                error_types.add(err.error_type.title)
            context['errors'] = error_types
        if self.object.is_master and self.object.satellites.count() < 3:
            satellite_info = []
            for satellite in self.object.satellites.all():
                satellite_info.append({
                    'serial_number': satellite.serial_number,
                    'waste_type': satellite.waste_type.title,
                    'fullness': satellite.fullness,
                    'fullness_card_class': Fullness.get_card_class(satellite.fullness),
                })
            context['satellites'] = satellite_info
        if self.request.uac.is_driver:
            context['shortened_version'] = True
        else:
            containers = [{'id': self.object.pk, 'serial_number': self.object.serial_number}]
            base_qs = Container.objects.none()
            if self.request.uac.is_superadmin:
                # TODO: This is an unbounded data set
                base_qs = Container.objects.all()
            elif self.request.uac.has_per_company_access:
                base_qs = Container.objects.filter(company=self.request.uac.company)
            base_qs = base_qs.exclude(pk=self.object.pk).exclude(is_master=False).order_by('pk').\
                values('id', 'serial_number')
            containers.extend(base_qs)
            base_url = reverse('main:map')
            context['container_nav_links'] = [
                (f"{base_url}?openDeviceType=bin&openDeviceId={s['id']}", s['serial_number']) for s in containers]
        return context


class ContainerDetail(LoginRequiredMixin, SingleObjectTemplateResponseMixin, BaseDetailView):
    model = Container
    template_name = 'containers/detail.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        ensure_object_access_or_404(self.request, obj.company)
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        populate_container_context(context, self.object)
        context['maps_api_key'] = settings.GOOGLE_MAPS_API_KEY
        master_bin = self.object if self.object.is_master else self.object.master_bin
        satellites_count = len(master_bin.satellites.all()) if master_bin else 0
        context['separation_station_2'] = satellites_count == 1
        context['separation_station_3'] = satellites_count == 2
        context['indoor_tv'] = satellites_count == 0 and all((
            key_part in self.object.serial_number for key_part in ['BBI', 'CILP']))
        context['bin_type_description'] = self.object.container_type.description or self.object.container_type.title
        return context


class SectorList(LoginRequiredMixin, generic.TemplateView):
    template_name = 'sectors/list.html'

    def get_context_data(self, **kwargs):
        if not (self.request.uac.is_superadmin or self.request.uac.has_per_company_access):
            raise Http404()
        context = super(SectorList, self).get_context_data(**kwargs)
        table = SectorsTable()
        if len(table.columns) >= 2:
            company_column = table.columns[1]
            if self.request.uac.is_superadmin:
                company_column.visible = True
        context['sectors'] = table
        return context


class SectorCreate(generic.CreateView):
    model = Sectors
    form_class = SectorForm
    template_name = 'sectors/sector_form.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not (request.uac.is_superadmin or request.uac.has_per_company_access):
            raise Http404()
        return super(SectorCreate, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        sector = form.save()
        messages.success(self.request,
                         _('New sector "%(sector_name)s" created successfully') % {'sector_name': sector.name})
        return redirect('sectors:list')

    def get_form_kwargs(self):
        kwargs = super(SectorCreate, self).get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs


class SectorUpdate(generic.UpdateView):
    model = Sectors
    form_class = SectorForm
    template_name = 'sectors/sector_form.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not (request.uac.is_superadmin or request.uac.has_per_company_access):
            raise Http404()
        return super(SectorUpdate, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        sector = form.save()
        messages.success(self.request,
                         _('Sector "%(sector_name)s" updated successfully') % {'sector_name': sector.name})
        return redirect('sectors:list')

    def get_form_kwargs(self):
        kwarg = super(SectorUpdate, self).get_form_kwargs()
        kwarg['request'] = self.request
        return kwarg

    def get_object(self, queryset=None):
        obj = super(SectorUpdate, self).get_object(queryset)
        ensure_object_access_or_404(self.request, obj.company)
        return obj


class SectorDelete(LoginRequiredMixin, generic.DeleteView):
    model = Sectors
    template_name = 'sectors/confirm_delete.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        ensure_object_access_or_404(self.request, obj.company)
        return obj

    def get_success_url(self):
        return reverse('sectors:list')

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        sector = kwargs['object']
        last_company_sector = sector.is_last_for_company
        sector_is_referenced = is_sector_referenced(sector)
        result.update(
            last_company_sector=last_company_sector,
            sector_is_referenced=sector_is_referenced,
            button_attrs='disabled' if last_company_sector or sector_is_referenced else None)
        return result

    def delete(self, request, *args, **kwargs):
        sector = self.get_object()
        if sector.is_last_for_company:
            raise PermissionDenied('Removal of the last company sector is not allowed')
        if is_sector_referenced(sector):
            raise PermissionDenied('Removal of a sector referenced by devices is not allowed')
        messages.success(request, _('Sector "%(sector_name)s" deleted successfully') % {'sector_name': sector.name})
        return super().delete(request, *args, **kwargs)


class SectorsDataView(LoginRequiredMixin, FeedDataView):
    token = SectorsTable.token

    def get_queryset(self):
        queryset = super(SectorsDataView, self).get_queryset()
        if self.request.uac.is_superadmin:
            return queryset
        if self.request.uac.has_per_company_access:
            return queryset.filter(company=self.request.uac.company)
        raise Http404()


class CityList(LoginRequiredMixin, generic.ListView):
    model = City
    template_name = 'cities/list.html'

    def get_context_data(self, **kwargs):
        context = super(CityList, self).get_context_data(**kwargs)
        table = CityTable()
        if len(table.columns) >= 3:
            table.columns[2].visible = self.request.uac.is_superadmin
        context['cities'] = table
        return context


class CityCreate(generic.CreateView):
    model = City
    form_class = CityForm
    template_name = 'cities/city_form.html'
    success_url = reverse_lazy('cities:list')

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not (request.uac.is_superadmin or request.uac.is_administrator):
            raise Http404()
        return super(CityCreate, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request,
                         _('New city "%(city_title)s" created successfully') % {'city_title': self.object.title})
        return result


class CityUpdate(generic.UpdateView):
    model = City
    form_class = CityForm
    template_name = 'cities/city_form.html'
    success_url = reverse_lazy('cities:list')

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not (request.uac.is_superadmin or request.uac.is_administrator):
            raise Http404()
        return super(CityUpdate, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request,
                         _('City "%(city_title)s" updated successfully') % {'city_title': self.object.title})
        return result


class CityDelete(generic.DeleteView):
    model = City
    success_url = reverse_lazy('cities:list')
    template_name = 'cities/confirm_delete.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not (request.uac.is_superadmin or request.uac.is_administrator):
            raise Http404()
        return super(CityDelete, self).dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        result = super().delete(request, *args, **kwargs)
        messages.success(request, _('City "%(city_title)s" deleted successfully') % {'city_title': self.object.title})
        return result


class CityDataView(LoginRequiredMixin, FeedDataView):
    token = CityTable.token

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(title__isnull=False)
        return queryset


class RoutesList(LoginRequiredMixin, generic.TemplateView):
    template_name = 'routes/list.html'

    def get_context_data(self, **kwargs):
        if not (self.request.uac.is_superadmin or self.request.uac.has_per_company_access):
            raise Http404()
        context = super().get_context_data(**kwargs)
        context['routes_table'] = RoutesTable()
        return context


class RoutesDataView(LoginRequiredMixin, FeedDataView):
    token = RoutesTable.token

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.uac.is_superadmin:
            return queryset
        if self.request.uac.has_per_company_access:
            return queryset.filter(parent_route__company=self.request.uac.company)
        raise Http404()


class RouteAbort(LoginRequiredMixin, SingleObjectTemplateResponseMixin, BaseDetailView):
    model = Route
    template_name = 'routes/confirm_abort.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if self.request.uac.has_per_company_access and obj.parent_route.company != self.request.uac.company:
            raise Http404()
        return obj

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        route = kwargs['object']
        aborting_not_supported_by_status = route.is_finished
        result.update(
            aborting_not_supported_by_status=aborting_not_supported_by_status,
            button_attrs='disabled' if aborting_not_supported_by_status else None)
        return result

    def post(self, request, *args, **kwargs):
        route = self.get_object()
        if route.is_finished:
            raise PermissionDenied('Aborting of this route is not allowed by current status')

        RoutesDrivers.finish_routes(route.user_id, route.id)
        RoutePoints.close_route_points(route.user_id, ROUTE_STATUS_ABORTED_BY_OPERATOR, route.id)
        Routes.close_parent_routes_if_possible(route.user_id)
        route.status = ROUTE_STATUS_ABORTED_BY_OPERATOR
        route.save()

        abort_route_command = json.dumps({
            'action': 'abort_route',
            'id': route.id,
        })
        driver_id = route.user_id
        redis = RedisClient()
        async_to_sync(get_channel_layer().group_send)(
            settings.MOBILE_API_CONSUMERS_GROUP_NAME,
            {
                'type': 'abort_route',
                'driver_id': driver_id,
                'command': abort_route_command,
            }
        )
        route_to_send = redis.get_route_to_send(driver_id)
        if route_to_send is not None and not redis.is_driver_online(driver_id):
            redis.clear_route_to_send(driver_id)

        messages.success(request, _('Route #%(route_id)s aborted successfully') % {'route_id': route.pk})
        return HttpResponseRedirect(reverse('routes:list'))


class RouteResend(LoginRequiredMixin, BaseDetailView):
    model = Route

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if self.request.uac.has_per_company_access and obj.parent_route.company != self.request.uac.company:
            raise Http404()
        return obj

    def post(self, request, *args, **kwargs):
        route = self.get_object()
        if route.is_new:
            send_route(route)
            messages.success(request, _('Existing route #%(route_id)s resent successfully') % {'route_id': route.pk})
        else:
            raise PermissionDenied('Route cannot be resent due to current status')
        return HttpResponseRedirect(reverse('routes:list'))


class RouteDetail(LoginRequiredMixin, SingleObjectTemplateResponseMixin, BaseDetailView):
    model = Route
    template_name = 'routes/detail.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if self.request.uac.has_per_company_access and obj.parent_route.company != self.request.uac.company:
            raise Http404()
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        route = kwargs['object']
        table = RoutePointsTable(RoutePoints.objects.filter(route=route))
        column_to_hide_index = \
            0 if get_effective_company_device_profile(self.request) == CompanyDeviceProfile.SENSOR else 1
        table.columns[column_to_hide_index].visible = False
        context['points_table'] = table
        context['can_be_resent'] = route.is_new
        context['route_duration'] = route.route_driver.finish_time - route.route_driver.start_time \
            if route.route_driver and route.route_driver.start_time and route.route_driver.finish_time else None
        return context


class DriversList(LoginRequiredMixin, generic.TemplateView):
    template_name = 'drivers/list.html'

    def get_context_data(self, **kwargs):
        if not (self.request.uac.is_superadmin or self.request.uac.has_per_company_access):
            raise Http404()
        context = super().get_context_data(**kwargs)
        table = DriversTable()
        if len(table.columns) >= 4 and self.request.uac.is_superadmin:
            company_column = table.columns[3]
            company_column.visible = True
        context['drivers_table'] = table
        return context


class DriversDataView(LoginRequiredMixin, FeedDataView):
    token = DriversTable.token

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(user_to_company__role=UsersToCompany.DRIVER_ROLE)
        if self.request.uac.is_superadmin:
            return queryset
        if self.request.uac.has_per_company_access:
            return queryset.filter(user_to_company__company=self.request.uac.company)
        raise Http404()


class DriverDetail(LoginRequiredMixin, SingleObjectTemplateResponseMixin, BaseDetailView):
    model = User
    template_name = 'drivers/detail.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if self.request.uac.has_per_company_access:
            try:
                users_to_company_exists = obj.user_to_company is not None
            except UsersToCompany.DoesNotExist:
                users_to_company_exists = False
            if not users_to_company_exists or obj.user_to_company.company != self.request.uac.company:
                raise Http404()
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        driver = kwargs['object']
        context['any_routes_in_progress'] = any_routes_in_progress(driver)
        context['any_period_active_now'] = DriverUnavailabilityPeriod.any_period_active_now(driver)
        context['availability_table'] = DriverUnavailabilityPeriodTable(
            DriverUnavailabilityPeriod.objects.filter(driver=driver))
        context['comment'] = driver.user_to_company.comment
        return context


class DriverUnavailabilityPeriodCreate(generic.CreateView):
    model = DriverUnavailabilityPeriod
    form_class = DriverUnavailabilityPeriodForm
    template_name = 'drivers/unavailability_period_form.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not (request.uac.is_superadmin or request.uac.has_per_company_access):
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('New unavailability period created successfully'))
        return redirect('drivers:detail', self.kwargs['pk'])

    def get_initial(self):
        return {'driver': User.objects.get(pk=self.kwargs['pk'])}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['driver_id'] = self.kwargs['pk']
        return context


class DriverUnavailabilityPeriodUpdate(generic.UpdateView):
    model = DriverUnavailabilityPeriod
    form_class = DriverUnavailabilityPeriodForm
    template_name = 'drivers/unavailability_period_form.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not (request.uac.is_superadmin or request.uac.has_per_company_access):
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('Unavailability period updated successfully'))
        return redirect('drivers:detail', form.instance.driver.id)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        ensure_object_access_or_404(self.request, obj.driver.user_to_company.company)
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context['form']
        context['driver_id'] = form.instance.driver.id
        return context


class DriverUnavailabilityPeriodDelete(LoginRequiredMixin, generic.DeleteView):
    model = DriverUnavailabilityPeriod
    template_name = 'drivers/unavailability_period_confirm_delete.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        ensure_object_access_or_404(self.request, obj.driver.user_to_company.company)
        return obj

    def get_success_url(self):
        return reverse('drivers:detail', kwargs={'pk': self.object.driver.id})

    def delete(self, request, *args, **kwargs):
        result = super().delete(request, *args, **kwargs)
        messages.success(request, _('Unavailability period deleted successfully'))
        return result
