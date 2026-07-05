"""
matches/permissions.py

Permission classes specific to the matches app.
Reuses base role permissions from users.permissions where possible.
"""

from rest_framework.permissions import BasePermission

from users.models import UserRole


class IsMaleOrFemaleOrWali(BasePermission):
    """Allow access to Male, Female, or Wali users (browse, requests, matches)."""
    message = "Access restricted to registered members."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in (UserRole.MALE, UserRole.FEMALE, UserRole.WALI)
        )


class IsParticipantInMatch(BasePermission):
    """
    Object-level permission: only the male_user or other_user in a Match
    (or an admin) can view/act on it.
    """
    message = "You are not a participant in this match."

    def has_object_permission(self, request, view, obj):
        if request.user.is_admin_user:
            return True
        return request.user in (obj.male_user, obj.other_user)


class CanSendConnectionRequest(BasePermission):
    """
    Checks subscription-based permission to send a NEW connection request.
    Free users cannot send requests at all.
    Monthly users have a per-cycle limit (checked in the service layer).
    Annual users have unlimited requests.

    This permission only blocks FREE users outright — Monthly limit
    checks happen in MatchService since they require querying usage count.
    """
    message = "Your subscription plan does not allow sending connection requests. Please upgrade to Monthly or Annual."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        
        # Private matchmaking clients cannot send standard connection requests
        if user.is_private_matchmaking_client:
            return False
        
        # Free users cannot send requests at all
        if user.subscription_plan == "free":
            return False
        return True
