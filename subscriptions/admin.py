from django.contrib import admin

from .models import StorePurchase


@admin.register(StorePurchase)
class StorePurchaseAdmin(admin.ModelAdmin):
    list_display  = ("user", "platform", "product_id", "status", "expires_at", "auto_renewing", "created_at")
    list_filter   = ("platform", "product_id", "status", "kind")
    search_fields = ("user__email", "store_key", "order_id")
    readonly_fields = [f.name for f in StorePurchase._meta.fields]

    def has_add_permission(self, request):
        return False
