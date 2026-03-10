from django.contrib import admin

from .models import MenuItem, Order, OrderItem, Outlet, Payment, Setting, Student, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "role", "created_at")
    search_fields = ("name", "email")
    list_filter = ("role",)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "roll_number", "department", "wallet_balance")
    search_fields = ("roll_number", "department", "user__email")


@admin.register(Outlet)
class OutletAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "location", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "location")


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("id", "item_name", "outlet", "price", "available_quantity", "is_available")
    list_filter = ("is_available", "outlet")
    search_fields = ("item_name",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "order_number", "student", "outlet", "total_amount", "payment_mode", "status", "created_at")
    list_filter = ("status", "payment_mode", "outlet")
    search_fields = ("order_number",)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "menu_item", "quantity", "price")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "payment_status", "transaction_id", "created_at")
    list_filter = ("payment_status",)
    search_fields = ("transaction_id",)


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "value")
    search_fields = ("key",)