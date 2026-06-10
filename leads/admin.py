import csv
import io
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import ChamberLead, Profile

# Customizing how ChamberLeads look inside the Admin dashboard grid
class ChamberLeadAdmin(admin.ModelAdmin):
    """Configures the column headers visible in the admin lead directory table."""
    list_display = ('first_name', 'last_name', 'title', 'organization', 'email', 'phone')
    search_fields = ('first_name', 'last_name', 'organization', 'email')
    #list_filter = ('organization',)

    # Point Django to a custom layout template that injects our button tool link
    #change_list_template = "admin/leads_changelist.html"

    def get_urls(self):
        """Adds a private route inside the admin wrapper for handling uploads safely."""
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='import-csv'),
        ]
        return custom_urls + urls

    def import_csv(self, request):
        """Processes the uploaded scraper file and maps items into Postgres."""
        if request.method == "POST":
            csv_file = request.FILES.get('csv_file')
            
            if not csv_file or not csv_file.name.endswith('.csv'):
                messages.error(request, "Invalid file format. Please upload a true system .csv file.")
                return redirect("..")

            # Read text stream without locking filesystem memory arrays
            data_set = csv_file.read().decode('utf-8')
            io_string = io.StringIO(data_set)
            next(io_string) # Skip row index 0 (The headers)

            success_count = 0
            for row in csv.reader(io_string, delimiter=',', quotechar='"'):
                if not row or len(row) < 5:
                    continue
                
                # Unpack exact positions matching your scraper list layout
                first_name = row[0].strip()
                last_name = row[1].strip()
                title = row[2].strip()
                org_name = row[3].strip()
                email = row[4].strip().lower()
                phone = row[5].strip() if len(row) > 5 else ""
                extension = row[6].strip() if len(row) > 6 else ""
                avatar_url = row[7].strip() if len(row) > 7 else ""

                if not email:
                    continue

                # Inject directly into Postgres, keeping existing user values intact if emails cross match
                ChamberLead.objects.update_or_create(
                    email=email,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'title': title,
                        'organization': org_name,
                        'chamber': org_name, # Sync both matching legacy field tracking maps
                        'phone': phone,
                        'extension': extension,
                        'avatar_url': avatar_url if avatar_url else None
                    }
                )
                success_count += 1

            messages.success(request, f"Success! Cleaned and imported {success_count} chamber leads directly to PostgreSQL.")
            return redirect("admin:leads_chamberlead_changelist")

        return render(request, "admin/csv_upload.html", {})

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