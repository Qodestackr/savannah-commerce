from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    readonly_fields = ("total_price",)
    extra = 1


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "status",
        "total_amount",
        "item_count",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("customer__email", "customer__first_name", "customer__last_name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "quantity", "unit_price", "total_price")
    list_filter = ("created_at",)
    search_fields = ("product__name", "order__customer__email")
    readonly_fields = ("total_price", "created_at", "updated_at")
