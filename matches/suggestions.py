"""
matches/suggestions.py

Suggested matches engine — preference-based, mutual matching.

Logic:
    For MALE user:
        - Candidates: Female + Wali profiles
        - Male's preferences checked against candidate's actual data:
            pref_age_min/max       → candidate's age
            pref_marital_status    → candidate's marital_status
            pref_ethnicity         → candidate's ethnicity (any overlap)
            preferred_dress        → candidate's dress field
        - Mutual check: candidate's preferences checked against male's data:
            pref_age_min/max       → male's age
            pref_marital_status    → male's marital_status
            pref_ethnicity         → male's ethnicity (any overlap)

    For FEMALE / WALI user:
        - Candidates: Male profiles
        - User's preferences checked against candidate's actual data:
            pref_age_min/max       → candidate's age
            pref_marital_status    → candidate's marital_status
            pref_ethnicity         → candidate's ethnicity (any overlap)
        - Mutual check: candidate's (male's) preferences checked against user:
            pref_age_min/max       → user's age
            pref_marital_status    → user's marital_status
            pref_ethnicity         → user's ethnicity (any overlap)
            preferred_dress        → user's dress

Exclusions applied before matching:
    - Blocked / hidden / reported profiles
    - Private matchmaking clients
    - Users with no basic info at all
    - Users with no preferences set at all (pref fields all null/empty)
    - Users the requester already has an active Match/request with

Subscription gate:
    Only Monthly and Annual subscribers can access suggestions.
    Free users receive HTTP 403.

Result ordering:
    Score-based — each matched preference criterion adds 1 point.
    Ties broken by last_active (most recently active first).
"""

import logging

from django.contrib.auth import get_user_model
from django.db.models import Q

from questions.models import FemaleBasicInfo, MaleBasicInfo, WaliBasicInfo

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_info(user):
    """Return the basic info object for a user, or None."""
    from users.models import UserRole
    if user.role == UserRole.MALE:
        return MaleBasicInfo.objects.filter(user=user).first()
    if user.role == UserRole.FEMALE:
        return FemaleBasicInfo.objects.filter(user=user).first()
    if user.role == UserRole.WALI:
        return WaliBasicInfo.objects.filter(user=user).first()
    return None


def _lists_overlap(list_a: list, list_b: list) -> bool:
    """True if two JSON lists share at least one common element."""
    if not list_a or not list_b:
        return False
    return bool(set(list_a) & set(list_b))


def _age_in_range(age: int | None, pref_min: int | None, pref_max: int | None) -> bool:
    """True if age satisfies the preference range. Partial ranges allowed."""
    if age is None:
        return False
    if pref_min is not None and age < pref_min:
        return False
    if pref_max is not None and age > pref_max:
        return False
    return True


def _has_any_preferences(info) -> bool:
    """True if the info record has at least one preference set."""
    if info is None:
        return False
    has_age     = info.pref_age_min is not None or info.pref_age_max is not None
    has_marital = bool(info.pref_marital_status)
    has_ethnic  = bool(info.pref_ethnicity)
    return has_age or has_marital or has_ethnic


# ─────────────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────────────

def _score_male_vs_female(male_info, female_info, female_user) -> int:
    """
    Score how well a female/wali candidate matches a male user's preferences.
    Each satisfied criterion = +1 point (max varies, higher = better match).
    """
    if male_info is None or female_info is None:
        return 0

    score = 0
    female_age       = getattr(female_info, "age", None)
    female_marital   = getattr(female_info, "marital_status", None)
    female_ethnicity = getattr(female_info, "ethnicity", None) or []
    female_dress     = getattr(female_info, "dress", None)

    # Male's prefs vs female's actual data
    if _age_in_range(female_age, male_info.pref_age_min, male_info.pref_age_max):
        score += 1
    if male_info.pref_marital_status and female_marital in male_info.pref_marital_status:
        score += 1
    if _lists_overlap(male_info.pref_ethnicity or [], female_ethnicity):
        score += 1
    if male_info.preferred_dress and female_dress == male_info.preferred_dress:
        score += 1

    return score


def _score_female_vs_male(female_info, male_info, male_user) -> int:
    """
    Score how well a male candidate matches a female/wali user's preferences.
    """
    if female_info is None or male_info is None:
        return 0

    score = 0
    male_age       = getattr(male_info, "age", None)
    male_marital   = getattr(male_info, "marital_status", None)
    male_ethnicity = getattr(male_info, "ethnicity", None) or []

    # Female's prefs vs male's actual data
    if _age_in_range(male_age, female_info.pref_age_min, female_info.pref_age_max):
        score += 1
    if female_info.pref_marital_status and male_marital in female_info.pref_marital_status:
        score += 1
    if _lists_overlap(female_info.pref_ethnicity or [], male_ethnicity):
        score += 1

    return score


def _mutual_score(requester_info, candidate_info, requester_user, candidate_user) -> int:
    """
    Combined mutual score. Both sides must satisfy some preference of the other.
    Returns 0 if either side scores 0 (no mutual interest at all).
    """
    from users.models import UserRole

    if requester_user.role == UserRole.MALE:
        requester_score = _score_male_vs_female(
            requester_info, candidate_info, candidate_user
        )
        candidate_score = _score_female_vs_male(
            candidate_info, requester_info, requester_user
        )
    else:
        # Female or Wali
        requester_score = _score_female_vs_male(
            requester_info, candidate_info, candidate_user
        )
        candidate_score = _score_male_vs_female(
            candidate_info, requester_info, requester_user
        )

    # Both sides must have at least 1 matching criterion for mutual match
    if requester_score == 0 or candidate_score == 0:
        return 0

    return requester_score + candidate_score


# ─────────────────────────────────────────────────────────────────────────────
# Main suggestion engine
# ─────────────────────────────────────────────────────────────────────────────

def get_suggested_matches(user, limit: int = 50) -> list[dict]:
    """
    Returns a scored, ordered list of suggested match dicts for `user`.

    Each dict:
        {
            "user":  <User instance>,
            "score": <int>,
            "info":  <BasicInfo instance>,
        }

    Ordered by score DESC, then last_active DESC.
    Returns [] if user has no preferences set or no qualifying candidates.
    """
    from users.models import UserRole
    from wishlists.services import VisibilityService
    from matches.models import Match, MatchStatus

    requester_info = _get_info(user)
    if not _has_any_preferences(requester_info):
        return []

    # Determine candidate roles
    if user.role == UserRole.MALE:
        candidate_roles = [UserRole.FEMALE, UserRole.WALI]
    else:
        candidate_roles = [UserRole.MALE]

    # Base queryset — active, opposite gender, not private clients
    candidates = User.objects.filter(
        role__in=candidate_roles,
        is_active=True,
        is_private_matchmaking_client=False,
    ).exclude(id=user.id)

    # Exclude blocked / hidden / reported
    excluded_ids = VisibilityService.get_excluded_user_ids(user)
    if excluded_ids:
        candidates = candidates.exclude(id__in=excluded_ids)

    # Exclude users already connected (any active Match status)
    already_connected_ids = set(
        Match.objects.filter(
            Q(male_user=user) | Q(other_user=user)
        ).exclude(
            status__in=[MatchStatus.DECLINED, MatchStatus.CANCELLED, MatchStatus.DROPPED]
        ).values_list(
            "male_user_id", flat=True
        )
    ) | set(
        Match.objects.filter(
            Q(male_user=user) | Q(other_user=user)
        ).exclude(
            status__in=[MatchStatus.DECLINED, MatchStatus.CANCELLED, MatchStatus.DROPPED]
        ).values_list(
            "other_user_id", flat=True
        )
    )
    already_connected_ids.discard(user.id)
    if already_connected_ids:
        candidates = candidates.exclude(id__in=already_connected_ids)

    # Score each candidate
    scored = []
    for candidate in candidates.select_related():
        candidate_info = _get_info(candidate)
        if candidate_info is None:
            continue

        score = _mutual_score(requester_info, candidate_info, user, candidate)
        if score > 0:
            scored.append({
                "user":  candidate,
                "score": score,
                "info":  candidate_info,
            })

    # Sort: score DESC, last_active DESC
    scored.sort(
        key=lambda x: (
            -x["score"],
            -(x["user"].last_active.timestamp() if x["user"].last_active else 0),
        )
    )

    return scored[:limit]
