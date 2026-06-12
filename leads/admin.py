from django.contrib import admin
from .models import ChamberLead, ChamberDirectory, ChamberRequest, Profile

@admin.register(ChamberRequest)
class ChamberRequestAdmin(admin.ModelAdmin):
    """Admin configuration to track and manage incoming custom tiered data pipeline requests."""
    list_display = ('id', 'user_email', 'chambers_count', 'state', 'city_or_region', 'estimated_cost', 'status', 'created_at')
    list_filter = ('status', 'state', 'chambers_count', 'created_at')
    search_fields = ('user_email', 'chamber_name', 'city_or_region')
    ordering = ('-created_at',)
    
    # Groups fields into clean blocks when editing a specific order request
    fieldsets = (
        ('Client Information', {
            'fields': ('user_email', 'status')
        }),
        ('Target Scope Details', {
            'fields': ('chambers_count', 'estimated_cost', 'state', 'city_or_region')
        }),
        ('Scraping Coordinates', {
            'fields': ('chamber_name', 'chamber_url'),
            'description': 'Review listed targets and directory URL structures before starting execution.'
        }),
    )

@admin.register(ChamberDirectory)
class ChamberDirectoryAdmin(admin.ModelAdmin):
    """Admin layout to view parent directory collections nationwide."""
    list_display = ('name', 'state', 'city_or_region', 'is_active', 'created_at')
    list_filter = ('state', 'is_active')
    search_fields = ('name', 'city_or_region')

@admin.register(ChamberLead)
class ChamberLeadAdmin(admin.ModelAdmin):
    """Admin display setup for high-fidelity scraped chamber contacts."""
    list_display = ('first_name', 'last_name', 'title', 'organization', 'email', 'phone', 'created_at')
    list_filter = ('directory__state', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'organization', 'chamber')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Tracks premium user billing and account authorizations."""
    list_display = ('user', 'is_premium')
    list_filter = ('is_premium',)
    search_fields = ('user__username', 'user__email')