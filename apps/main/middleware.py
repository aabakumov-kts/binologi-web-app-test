from django.shortcuts import redirect
from django.urls import reverse

from apps.core.helpers import CompanyDeviceProfile
from apps.sensors.models import CompanySensorsLicense
from apps.trashbins.models import CompanyTrashbinsLicense
from apps.main.helpers import get_effective_company_device_profile


def get_license(request):
    device_profile = get_effective_company_device_profile(request)
    if device_profile == CompanyDeviceProfile.SENSOR:
        return CompanySensorsLicense.objects.filter(company=request.uac.company).order_by('-end').first()
    if device_profile == CompanyDeviceProfile.TRASHBIN:
        return CompanyTrashbinsLicense.objects.filter(company=request.uac.company).order_by('-end').first()
    return None


def check_license_is_valid(request):
    if not request.uac.has_per_company_access:
        return True

    device_license = get_license(request)
    return device_license.is_valid if device_license else False


class LicenseCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if getattr(view_func, 'license_check_exempt', False):
            return None

        license_is_valid = check_license_is_valid(request)
        if not license_is_valid:
            return redirect(reverse('invalid-license'))
        return None
