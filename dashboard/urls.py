from django.urls import path

from .views import (
    DashboardAnalyticsView,
    DashboardStatsView,
    DashboardSummaryView,
    FunnelView,
    OutcomesView,
    RecentActivityListView,
    UserGrowthView,
)


urlpatterns = [
    path("activities/", RecentActivityListView.as_view(), name="dashboard-recent-activities"),
    path("stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("analytics/", DashboardAnalyticsView.as_view(), name="dashboard-analytics"),
    path("usergrowth/", UserGrowthView.as_view(), name="dashboard-user-growth"),
    path("outcomes/", OutcomesView.as_view(), name="dashboard-outcomes"),
    path("funnel/", FunnelView.as_view(), name="dashboard-funnel"),
    path("summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
]
