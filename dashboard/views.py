from datetime import date, timedelta

from drf_spectacular.utils import extend_schema
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdminUser

from .models import RecentActivity
from .serializers import (
    DashboardAnalyticsSerializer,
    DashboardStatsSerializer,
    DashboardSummarySerializer,
    FunnelSerializer,
    OutcomesSerializer,
    RecentActivitySerializer,
    UserGrowthSerializer,
)

from matches.models import Match, MatchStatus
from matchmaking.models import PrivateMatchmakingRequest, RequestStatus

User = get_user_model()


@extend_schema(tags=["Dashboard"])
class RecentActivityListView(APIView):
    """
    Admin dashboard feed of recent platform activities.
    Read-only list endpoint — newest first.
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Admin — List recent activities",
        description=(
            "Returns the latest dashboard activities such as registrations, "
            "match creation, matchmaking request updates, marriages, and verification events."
        ),
        responses={200: RecentActivitySerializer(many=True)},
    )
    def get(self, request):
        queryset = RecentActivity.objects.select_related(
            "primary_user", "secondary_user", "actor_user"
        ).order_by("-created_at")
        serializer = RecentActivitySerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(tags=["Dashboard"])
class DashboardStatsView(APIView):
    """
    Admin dashboard summary cards and chart data.
    Read-only stats endpoint.
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Admin — Dashboard stats",
        description=(
            "Returns dashboard summary counts and a last-6-month matches-over-time series."
        ),
        responses={200: DashboardStatsSerializer},
    )
    def get(self, request):
        today = date.today()
        months = []
        year = today.year
        month = today.month
        for _ in range(6):
            months.append((year, month))
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        months.reverse()

        first_year, first_month = months[0]
        first_month_start = date(first_year, first_month, 1)

        match_counts = (
            Match.objects.filter(created_at__date__gte=first_month_start)
            .annotate(month_bucket=TruncMonth("created_at"))
            .values("month_bucket")
            .annotate(matches=Count("id"))
            .order_by("month_bucket")
        )
        counts_by_month = {
            (item["month_bucket"].year, item["month_bucket"].month): item["matches"]
            for item in match_counts
        }
        matches_over_time = [
            {
                "month": date(y, m, 1).strftime("%b"),
                "matches": counts_by_month.get((y, m), 0),
            }
            for y, m in months
        ]

        payload = {
            "total_users": User.objects.count(),
            "active_users": User.objects.filter(is_active=True).count(),
            "total_matches": Match.objects.count(),
            "pending_matchmaking_requests": PrivateMatchmakingRequest.objects.filter(
                status=RequestStatus.PENDING
            ).count(),
            "total_married_count": Match.objects.filter(status=MatchStatus.MARRIED).count(),
            "matches_over_time": matches_over_time,
        }
        return Response(DashboardStatsSerializer(payload).data, status=status.HTTP_200_OK)


@extend_schema(tags=["Dashboard"])
class DashboardAnalyticsView(APIView):
    """
    Admin dashboard analytics summary.
    Read-only analytics endpoint.
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Admin — Dashboard analytics",
        description=(
            "Returns total users, total matches, match success rate, and conversion rate."
        ),
        responses={200: DashboardAnalyticsSerializer},
    )
    def get(self, request):
        total_users = User.objects.count()
        total_matches = Match.objects.count()
        married_matches = Match.objects.filter(status=MatchStatus.MARRIED).count()
        conversion_matches = Match.objects.filter(
            status__in=[
                MatchStatus.PENDING,
                MatchStatus.ACCEPTED,
                MatchStatus.WALI_REQUESTED,
                MatchStatus.WALI_ACCEPTED,
                MatchStatus.IN_DISCUSSION,
            ]
        ).count()

        success_rate = round((married_matches / total_matches) * 100, 2) if total_matches else 0.0
        conversion_rate = round((conversion_matches / total_matches) * 100, 2) if total_matches else 0.0

        payload = {
            "total_users": total_users,
            "total_matches": total_matches,
            "success_rate": success_rate,
            "conversion_rate": conversion_rate,
        }
        return Response(DashboardAnalyticsSerializer(payload).data, status=status.HTTP_200_OK)


@extend_schema(tags=["Dashboard"])
class UserGrowthView(APIView):
    """
    Admin dashboard user growth chart.
    Read-only user growth endpoint.
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Admin — User growth",
        description="Returns a last-6-month users-over-time series.",
        responses={200: UserGrowthSerializer},
    )
    def get(self, request):
        today = date.today()
        months = []
        year = today.year
        month = today.month
        for _ in range(6):
            months.append((year, month))
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        months.reverse()

        first_year, first_month = months[0]
        first_month_start = date(first_year, first_month, 1)

        user_counts = (
            User.objects.filter(created_at__date__gte=first_month_start)
            .annotate(month_bucket=TruncMonth("created_at"))
            .values("month_bucket")
            .annotate(users=Count("id"))
            .order_by("month_bucket")
        )
        counts_by_month = {
            (item["month_bucket"].year, item["month_bucket"].month): item["users"]
            for item in user_counts
        }
        payload = {
            "user_over_time": [
                {
                    "month": date(y, m, 1).strftime("%b"),
                    "users": counts_by_month.get((y, m), 0),
                }
                for y, m in months
            ]
        }
        return Response(UserGrowthSerializer(payload).data, status=status.HTTP_200_OK)


@extend_schema(tags=["Dashboard"])
class OutcomesView(APIView):
    """
    Admin dashboard outcomes breakdown for pie-chart usage.
    Read-only outcomes endpoint.
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Admin — Outcomes breakdown",
        description=(
            "Returns match outcome percentages for successful, in-progress, dropped, and cancelled buckets."
        ),
        responses={200: OutcomesSerializer},
    )
    def get(self, request):
        total_matches = Match.objects.count()

        successful_count = Match.objects.filter(status=MatchStatus.MARRIED).count()
        in_progress_count = Match.objects.filter(
            status__in=[
                MatchStatus.PENDING,
                MatchStatus.ACCEPTED,
                MatchStatus.WALI_REQUESTED,
                MatchStatus.WALI_ACCEPTED,
                MatchStatus.IN_DISCUSSION,
            ]
        ).count()
        dropped_count = Match.objects.filter(status=MatchStatus.DROPPED).count()
        cancelled_count = Match.objects.filter(
            status__in=[MatchStatus.DECLINED, MatchStatus.CANCELLED]
        ).count()

        def _pct(value: int) -> float:
            return round((value / total_matches) * 100, 2) if total_matches else 0.0

        payload = {
            "successful": _pct(successful_count),
            "in_progress": _pct(in_progress_count),
            "dropped": _pct(dropped_count),
            "cancelled": _pct(cancelled_count),
        }
        return Response(OutcomesSerializer(payload).data, status=status.HTTP_200_OK)


@extend_schema(tags=["Dashboard"])
class FunnelView(APIView):
    """
    Admin dashboard funnel counts.
    Read-only funnel endpoint.
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Admin — Funnel counts",
        description=(
            "Returns funnel counts for total, new, married, dropped, accepted, and in_discussion matches."
        ),
        responses={200: FunnelSerializer},
    )
    def get(self, request):
        new_cutoff = timezone.now() - timedelta(days=7)
        payload = {
            "funnel": [
                {"status": "total", "count": Match.objects.count()},
                {"status": "new", "count": Match.objects.filter(created_at__gte=new_cutoff).count()},
                {"status": "married", "count": Match.objects.filter(status=MatchStatus.MARRIED).count()},
                {"status": "dropped", "count": Match.objects.filter(status=MatchStatus.DROPPED).count()},
                {"status": "accepted", "count": Match.objects.filter(status=MatchStatus.ACCEPTED).count()},
                {"status": "in_discussion", "count": Match.objects.filter(status=MatchStatus.IN_DISCUSSION).count()},
            ]
        }
        return Response(FunnelSerializer(payload).data, status=status.HTTP_200_OK)


@extend_schema(tags=["Dashboard"])
class DashboardSummaryView(APIView):
    """
    Admin dashboard summary metrics.
    Read-only summary endpoint.
    """

    permission_classes = [IsAdminUser]

    @staticmethod
    def _format_duration(avg_delta):
        if avg_delta is None:
            return ""
        total_seconds = int(avg_delta.total_seconds())
        if total_seconds <= 0:
            return ""

        day_seconds = 86400
        week_seconds = 7 * day_seconds
        month_seconds = 30 * day_seconds

        if total_seconds >= month_seconds:
            months = round(total_seconds / month_seconds)
            return f"{months} month{'s' if months != 1 else ''}"
        if total_seconds >= week_seconds:
            weeks = round(total_seconds / week_seconds)
            return f"{weeks} week{'s' if weeks != 1 else ''}"
        days = round(total_seconds / day_seconds)
        return f"{days} day{'s' if days != 1 else ''}"

    @extend_schema(
        summary="Admin — Dashboard summary",
        description=(
            "Returns active matches count, average time to match, average time to marriage, "
            "and the month with the most matches created."
        ),
        responses={200: DashboardSummarySerializer},
    )
    def get(self, request):
        active_matches = Match.objects.filter(
            status__in=[
                MatchStatus.PENDING,
                MatchStatus.ACCEPTED,
                MatchStatus.WALI_REQUESTED,
                MatchStatus.WALI_ACCEPTED,
                MatchStatus.IN_DISCUSSION,
            ]
        ).count()

        accepted_deltas = [
            match.accepted_at - match.created_at
            for match in Match.objects.filter(accepted_at__isnull=False).only("created_at", "accepted_at")
            if match.accepted_at and match.created_at
        ]
        avg_time_to_match = ""
        if accepted_deltas:
            avg_match_delta = sum(accepted_deltas, timedelta()) / len(accepted_deltas)
            avg_time_to_match = self._format_duration(avg_match_delta)

        married_deltas = [
            match.married_at - match.created_at
            for match in Match.objects.filter(married_at__isnull=False).only("created_at", "married_at")
            if match.married_at and match.created_at
        ]
        avg_time_to_marriage = ""
        if married_deltas:
            avg_marriage_delta = sum(married_deltas, timedelta()) / len(married_deltas)
            avg_time_to_marriage = self._format_duration(avg_marriage_delta)

        month_counts = (
            Match.objects.annotate(month_bucket=TruncMonth("created_at"))
            .values("month_bucket")
            .annotate(total=Count("id"))
            .order_by("-total", "month_bucket")
        )
        most_successful_month = ""
        top_month = month_counts.first()
        if top_month and top_month["month_bucket"]:
            most_successful_month = top_month["month_bucket"].strftime("%b")

        payload = {
            "active_matches": active_matches,
            "avg_time_to_match": avg_time_to_match,
            "avg_time_to_marriage": avg_time_to_marriage,
            "most_successful_month": most_successful_month,
        }
        return Response(DashboardSummarySerializer(payload).data, status=status.HTTP_200_OK)
