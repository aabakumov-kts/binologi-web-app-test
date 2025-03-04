import pytz

from datetime import datetime, timedelta
from django.contrib.gis import admin
from django.utils.html import format_html

from apps.core.admin import ok_status_icon_markup, fail_status_icon_markup
from app.models import Container as Trashbin, TrashbinData, Location
from apps.trashbins.models import CompanyTrashbinsLicense


@admin.register(CompanyTrashbinsLicense)
class CompanySensorsLicenseAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'begin', 'end')


class TrashbinPilot(Trashbin):
    @property
    def overall_status(self):
        now = datetime.utcnow()
        now = now.replace(tzinfo=pytz.utc)
        latest_data_timestamp = self.latest_data_timestamp
        data_ok = self.latest_data_timestamp + timedelta(hours=24) > now if latest_data_timestamp else False
        gps_ok = self.get_location_status(now)
        no_errors = self.errors.filter(actual=1).count() == 0
        overall_status_ok = data_ok and gps_ok and no_errors
        return format_html(ok_status_icon_markup if overall_status_ok else fail_status_icon_markup)

    @property
    def latest_data_timestamp(self):
        latest_data = TrashbinData.objects.filter(trashbin=self).order_by('-ctime').first()
        return None if latest_data is None else latest_data.ctime

    @property
    def location_status(self):
        status_ok = self.get_location_status()
        return format_html(ok_status_icon_markup if status_ok else fail_status_icon_markup)

    class Meta:
        proxy = True

    def get_location_status(self, now=None):
        if not self.is_master:
            return True
        if now is None:
            now = datetime.utcnow()
            now = now.replace(tzinfo=pytz.utc)
        day_ago = now - timedelta(hours=24)
        return Location.objects.filter(container=self, ctime__gte=day_ago, actual=1).count() > 0


@admin.register(TrashbinPilot)
class TrashbinPilotAdmin(admin.ModelAdmin):
    list_display = (
        'serial_number', 'company', 'overall_status', 'latest_data_timestamp', 'location_status', 'fullness', 'battery',
        'temperature', 'address',
    )
    list_filter = ('company',)
    list_display_links = None

    def has_view_permission(self, request, obj=None):
        return obj is None

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
