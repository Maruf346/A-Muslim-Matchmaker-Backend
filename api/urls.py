from django.urls import path, include
from rest_framework import routers
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from django.conf.urls.static import static
from django.conf import settings
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


urlpatterns = [
    # Include app-specific URL configurations
    path('user/', include('users.urls')),
    path('notification/', include('notifications.urls')),
    path("questions/",    include("questions.urls")),
    path('wishlists/', include('wishlists.urls')),
    path('matches/', include('matches.urls')),
    path('supports/', include('supports.urls')),
    path('chat/', include('chat.urls')),
    path('matchmaking/', include('matchmaking.urls')),
    path('private-matches/', include('private_matches.urls')),

    #JWT endpoints
    # path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # API schema and documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Minimal health-check endpoint used by Docker healthcheck + CI
    path("health/", lambda request: __import__("django.http", fromlist=["JsonResponse"]).JsonResponse({"status": "ok"})),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

