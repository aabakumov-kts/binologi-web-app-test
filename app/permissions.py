from rest_framework.permissions import BasePermission

from app.models import Container


class IsContainerAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and type(request.user) == Container)
