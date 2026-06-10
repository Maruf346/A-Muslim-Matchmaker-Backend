from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import *


# ==============================
# FAQ Admin
# ==============================

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "created_at", "updated_at")
    search_fields = ("question", "answer")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)


# ==============================
# Singleton Base Admin
# ==============================

class SingletonAdmin(admin.ModelAdmin):
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # Prevent adding more than one instance
        if self.model.objects.exists():
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion (optional but recommended for singleton models)
        return False


# ==============================
# About Us Admin
# ==============================

@admin.register(AboutUs)
class AboutUsAdmin(SingletonAdmin):
    pass


# ==============================
# Terms & Conditions Admin
# ==============================

@admin.register(TermsAndConditions)
class TermsAndConditionsAdmin(SingletonAdmin):
    pass


# ==============================
# Privacy Policy Admin
# ==============================

@admin.register(PrivacyPolicy)
class PrivacyPolicyAdmin(SingletonAdmin):
    pass


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("email", "subject", "created_at")
    search_fields = ("email", "subject", "message")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)