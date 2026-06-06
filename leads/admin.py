# leads/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import ChamberLead, Profile

# Customizing how ChamberLeads look inside the Admin dashboard grid
class ChamberLeadAdmin(admin.ModelAdmin):
    """Configures the column headers visible in the admin lead directory table."""
    # UPDATED: Matches your high-fidelity fields perfectly
    list_display = ('first_name', 'last_name', 'title', 'organization', 'email', 'phone')
    search_fields = ('first_name', 'last_name', 'organization', 'email')
    list_filter = ('organization',)

# Register the model with its custom admin panel settings configuration
admin.site.register(ChamberLead, ChamberLeadAdmin)


# --- User Profile Administration Layout ---

class ProfileInline(admin.StackedInline):
    """Allows profile options to be edited inside the default User panel layout."""
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profiles'

class UserAdmin(BaseUserAdmin):
    """Merges profile data properties into the standard User management module."""
    inlines = (ProfileInline,)

# Re-register standard User models with our new tracking architecture configuration
admin.site.unregister(User)
admin.site.register(User, UserAdmin)