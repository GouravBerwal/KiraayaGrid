from django.contrib import admin
from .models import User

# Register your models here.

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'phone_number', 'role', 'admin_sub_role', 'is_verified_owner', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_verified_owner')
    search_fields = ('username', 'email', 'phone_number')