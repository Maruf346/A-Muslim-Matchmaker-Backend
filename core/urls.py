from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from core.public_pages import account_deletion, child_safety



urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('health/', lambda request: JsonResponse({"status": "ok"})),
    path('account-deletion/', account_deletion, name='account-deletion'),
    path('child-safety/', child_safety, name='child-safety'),

    # CKEditor 5 upload
    path('ckeditor5/', include('django_ckeditor_5.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
