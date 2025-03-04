from app.models import Container
from apps.core.helpers import CompanyDeviceProfile
from apps.sensors.models import Sensor, CompanySensorsLicense


def get_raw_company_device_profile(request):
    if not request.uac.has_per_company_access:
        return True, True

    any_trashbin = Container.objects.filter(company=request.uac.company).count() > 0
    any_sensor = Sensor.objects.filter(company=request.uac.company).count() > 0
    return any_trashbin, any_sensor


def get_effective_company_device_profile(request):
    profile_override = None
    if 'device_profile_override' in request.session:
        profile_override = CompanyDeviceProfile(request.session['device_profile_override'])

    if not request.uac.has_per_company_access:
        # Fallbacks to trashbins profile
        return profile_override or CompanyDeviceProfile.TRASHBIN

    if profile_override:
        return profile_override

    any_trashbin, any_sensor = get_raw_company_device_profile(request)
    if any_trashbin or any_sensor:
        # There are some devices registered to the company
        if any_sensor and not any_trashbin:
            return CompanyDeviceProfile.SENSOR

        # Defaults to trashbins profile
        return CompanyDeviceProfile.TRASHBIN

    # Look at existing licenses if there's no devices
    sensors_license = CompanySensorsLicense.objects.filter(company=request.uac.company).order_by('-end').first()
    if sensors_license and sensors_license.is_valid:
        return CompanyDeviceProfile.SENSOR

    # Defaults to trashbins profile
    return CompanyDeviceProfile.TRASHBIN


def is_sector_referenced(sector):
    return sector.container_set.count() > 0
