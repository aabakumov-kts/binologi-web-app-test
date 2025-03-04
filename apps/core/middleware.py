from django.utils import timezone
from functools import wraps

from apps.core.models import FeatureFlag


class UserAccessControl:
    def __init__(self, user_getter):
        self._user_getter = user_getter

    @property
    def role_name(self):
        if not self._user.is_authenticated:
            return None
        if self.is_superadmin:
            return 'superadmin'
        return self._user.user_to_company.get_role_display() if self._user.user_to_company else None

    @property
    def company(self):
        if not self.has_per_company_access:
            return None
        return self._user.user_to_company.company if self._user.user_to_company else None

    @property
    def company_id(self):
        company = self.company
        return company.id if company else None

    @property
    def is_superadmin(self):
        return self._user.is_superuser if self._user.is_authenticated else False

    @property
    def is_administrator(self):
        if not self.has_per_company_access:
            return False
        return self._user.user_to_company.is_administrator()

    @property
    def is_driver(self):
        if not self.has_per_company_access:
            return False
        return self._user.user_to_company.is_driver()

    @property
    def has_per_company_access(self):
        if self.is_superadmin:
            return False
        return self._user.is_authenticated and hasattr(self._user, 'user_to_company')

    def check_feature_enabled(self, feature):
        if not self.has_per_company_access:
            return True

        try:
            flag = self.company.features.get(feature=feature)
        except FeatureFlag.DoesNotExist:
            flag = None
        return FeatureFlag.FEATURE_DEFAULTS[feature] if flag is None else flag.enabled

    @property
    def _user(self):
        return self._user_getter()


def license_check_exempt(view_func):
    """Mark a view function as being exempt from the licenses check."""
    # view_func.license_check_exempt = True would also work, but decorators are nicer
    # if they don't have side effects, so return a new function.
    def wrapped_view(*args, **kwargs):
        return view_func(*args, **kwargs)
    wrapped_view.license_check_exempt = True
    return wraps(view_func)(wrapped_view)


class UserAccessControlMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.uac = UserAccessControl(lambda: request.user)
        return self.get_response(request)


class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.uac.has_per_company_access:
            tz = request.user.user_to_company.timezone or request.uac.company.timezone
        else:
            tz = None
        if tz:
            timezone.activate(tz)
        else:
            timezone.deactivate()
        return self.get_response(request)
