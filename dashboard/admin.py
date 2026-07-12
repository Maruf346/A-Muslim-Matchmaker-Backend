from django.contrib import admin

from .models import RecentActivity


@admin.register(RecentActivity)
class RecentActivityAdmin(admin.ModelAdmin):
    list_display = ("title", "activity_type", "primary_user_name", "actor_user_name", "created_at")
    list_filter = ("activity_type", "created_at")
    search_fields = ("title", "description", "primary_user_name", "secondary_user_name", "actor_user_name")

# Register your models here.
