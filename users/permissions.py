# users/permissions.py

from rest_framework.permissions import BasePermission, IsAuthenticated


class IsAdmin(BasePermission):
    """Allow access only to admins (is_superuser=True)."""
    message = "Access restricted to administrators."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_admin
        )

