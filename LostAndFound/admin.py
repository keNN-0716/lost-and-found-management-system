from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, LostItem, FoundItem

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


class LostItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_lost', 'date_lost', 'status', 'reported_by', 'claimed_by', 'created_at')
    list_filter = ('status', 'date_lost')
    search_fields = ('name', 'description', 'location_lost')


class FoundItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_found', 'date_found', 'status', 'reported_by', 'claimed_by', 'created_at')
    list_filter = ('status', 'date_found')
    search_fields = ('name', 'description', 'location_found')


# Only register CustomUser. Remove the old User registrations entirely.
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(LostItem, LostItemAdmin)
admin.site.register(FoundItem, FoundItemAdmin)
