from django.contrib import admin
from .models import ChamberLead, ChamberDirectory, ChamberRequest, Profile, Order, OrderItem, UserPurchase

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ['directory', 'lead']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin layout to track invoices and snapshots generated before going to Stripe."""
    list_display = ['order_id', 'user', 'amount_paid', 'is_paid', 'created_at']
    list_filter = ['is_paid', 'created_at']
    search_fields = ['order_id', 'user__username', 'user__email']
    inlines = [OrderItemInline]
    readonly_fields = ['created_at']


@admin.register(UserPurchase)
class UserPurchaseAdmin(admin.ModelAdmin):
    """The source-of-truth access control wall. Manage who explicitly owns what here."""
    list_display = ['user', 'get_asset_type', 'get_asset_name', 'purchased_at', 'stripe_session_id']
    list_filter = ['purchased_at', 'directory__state']
    search_fields = ['user__username', 'user__email', 'directory__name', 'lead__email', 'stripe_session_id']
    raw_id_fields = ['user', 'directory', 'lead']
    readonly_fields = ['purchased_at']

    def get_asset_type(self, obj):
        if obj.directory:
            return "Directory Asset"
        elif obj.lead:
            return "Individual Lead"
        return "Unknown"
    get_asset_type.short_description = 'Asset Type'

    def get_asset_name(self, obj):
        if obj.directory:
            return obj.directory.name
        elif obj.lead:
            return obj.lead.email
        return "-"
    get_asset_name.short_description = 'Asset Target'


@admin.register(ChamberRequest)
class ChamberRequestAdmin(admin.ModelAdmin):
    """Admin configuration to track and manage incoming custom tiered data pipeline requests."""
    list_display = ('id', 'user_email', 'chambers_count', 'state', 'city_or_region', 'estimated_cost', 'status', 'created_at')
    list_filter = ('status', 'state', 'chambers_count', 'created_at')
    search_fields = ('user_email', 'chamber_name', 'city_or_region')
    ordering = ('-created_at',)
    
    # Restored your exact fieldsets layout
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
    raw_id_fields = ['directory']


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Tracks premium user billing and account authorizations."""
    list_display = ('user', 'is_premium')
    list_filter = ('is_premium',)
    search_fields = ('user__username', 'user__email')