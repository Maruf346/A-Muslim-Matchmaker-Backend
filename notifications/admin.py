from django.contrib import admin

from .models import DeviceToken, Notification
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__username', 'message')

@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'platform', 'updated_at')
    list_filter = ('platform',)
    search_fields = ('user__email',)
