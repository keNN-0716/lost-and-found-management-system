from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser

class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'id_number', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser')
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Profile Information', {
            'fields': ('id_number', 'role'),
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Custom Profile Information', {
            'fields': ('id_number', 'role'),
        }),
    )

# Only register CustomUser. Remove the old User registrations entirely.
admin.site.register(CustomUser, CustomUserAdmin)
