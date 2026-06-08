"""
users/permissions.py

Custom DRF permission classes for AMM role-based access control.

Usage:
    from users.permissions import IsSuperAdmin, IsAdminUser, IsMaleUser, ...

Permission classes available:
    IsSuperAdmin    — Superadmin only
    IsMatchmaker    — Matchmaker only
    IsAdminUser     — Matchmaker OR Superadmin
    IsMaleUser      — Male role only
    IsFemaleUser    — Female role only
    IsWaliUser      — Wali role only
    IsNormalUser    — Male, Female, or Wali
    IsSubscribed    — Monthly or Annual plan (normal users only)
    IsSubscribedMonthly  — Monthly plan only (normal users only)
    IsSubscribedAnnual   — Annual plan only (normal users only)
    IsOwnerOrAdmin  — Object owner OR any admin (use with has_object_permission)
"""

from rest_framework.permissions import BasePermission

from .models import UserRole


class IsSuperAdmin(BasePermission):
    """Allow access only to Superadmins."""
    message = "Access restricted to Super Administrators."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_superadmin
        )


class IsMatchmaker(BasePermission):
    """Allow access only to Matchmakers."""
    message = "Access restricted to Matchmakers."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_matchmaker
        )


class IsAdminUser(BasePermission):
    """Allow access to Matchmaker OR Superadmin."""
    message = "Access restricted to admin users."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_admin_user
        )


class IsMaleUser(BasePermission):
    """Allow access only to Male users."""
    message = "Access restricted to male users."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_male
        )


class IsFemaleUser(BasePermission):
    """Allow access only to Female users."""
    message = "Access restricted to female users."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_female
        )


class IsWaliUser(BasePermission):
    """Allow access only to Wali users."""
    message = "Access restricted to Wali users."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_wali
        )


class IsNormalUser(BasePermission):
    """Allow access to Male, Female, or Wali users (all non-admin roles)."""
    message = "Access restricted to registered members."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_normal_user
        )


class IsSubscribed(BasePermission):
    """
    Allow access only to users on Monthly or Annual subscription plans.
    Use this to gate: send requests, see suggestions, see profile viewers.
    """
    message = "This feature requires an active subscription (Monthly or Annual)."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_subscribed
        )


class IsSubscribedMonthly(BasePermission):
    """
    Allow access only to users on Monthly subscription plans.
    Use this to gate features exclusive to Monthly subscribers (if any).
    """
    message = "This feature requires an active Monthly subscription."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_subscribed_monthly
        )


class IsSubscribedAnnual(BasePermission):
    """
    Allow access only to users on Annual subscription plans.
    Use this to gate features exclusive to Annual subscribers (if any).
    """
    message = "This feature requires an active Annual subscription."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_subscribed_annual
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission: allow access if the user owns the object
    or is any admin (Matchmaker or Superadmin).

    Usage:
        permission_classes = [IsOwnerOrAdmin]
        # In the view, obj must have a `user` attribute pointing to the owner.
    """
    message = "You do not have permission to access this resource."

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.is_admin_user:
            return True
        owner = getattr(obj, "user", None)
        return owner == request.user