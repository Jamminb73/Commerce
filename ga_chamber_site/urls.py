from django.contrib import admin
from django.urls import path, include  
from django.contrib.sitemaps.views import sitemap  

from leads.sitemaps import StaticViewSitemap        
from leads.views import (
    landing_page,
    leads_list,       
    purchase_directory,             # <-- Imported the new dropdown checkout view
    register_view,
    login_view,
    logout_view,             
    purchase_view,
    monitor_view,                   # <-- Imported your new live terminal log view
    monitor_scrape_api,             # <-- Imported your new live log JSON api endpoint
    create_checkout_session,
    payment_success_view,
    payment_cancel_view,     
    stripe_webhook,
    request_custom_scrape,          
    request_success_view,           
    export_leads_csv,               
    active_directories_api,         # <-- Added the hidden live city lookup API endpoint
    about_page,                     # <-- Imported the new about view function
)

# Dictionary mapping for the sitemap framework
sitemaps = {
    'static': StaticViewSitemap,
}

urlpatterns = [
    # Search Engine Infrastructure
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

    # Auth Routes (Logout placed at top to ensure clean session termination)
    path('logout/', logout_view, name='logout'), 
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    
    # Core Application Routes
    path('admin/', admin.site.urls),
    path('', landing_page, name='home'),
    path('about/', about_page, name='about_page'), # <-- Registered the path for the new About page
    path('leads/', leads_list, name='leads_list'),  
    path('leads/export/', export_leads_csv, name='export_leads_csv'),  
    
    # Dedicated Dropdown Catalogue Checkout Flow
    path('purchase-directory/', purchase_directory, name='purchase_directory_base'),
    path('purchase-directory/<int:request_id>/', purchase_directory, name='purchase_directory'),
    
    # Hidden API Routing Layer
    path('api/active-cities/', active_directories_api, name='active_cities_api'),  # <-- Registered the city list query route
    
    # Custom Dynamic Scraping Requests System
    path('request-scrape/', request_custom_scrape, name='request_custom_scrape'),
    path('request-scrape/success/', request_success_view, name='request_success'),
    
    # Secure Backend Blog App Router
    path('blog/', include('blog.urls')), 
    
    # Stripe Checkout & Payment Flows (Updated with dynamic request_id parameter)
    path('purchase/', purchase_view, name='purchase'),
    
    # Live Pipeline Console Monitoring Deck 
    path('purchase/monitor/<int:request_id>/', monitor_view, name='monitor_view'),
    path('purchase/monitor/api/<int:request_id>/', monitor_scrape_api, name='monitor_scrape_api'),
    
    path('create-checkout-session/<int:request_id>/', create_checkout_session, name='create_checkout_session'),
    path('payment-success/', payment_success_view, name='payment_success'),
    path('payment-cancel/', payment_cancel_view, name='payment_cancel'),
    
    # Stripe Billing/Cancellation Management Portal
    #path('account/manage/', stripe_customer_portal, name='stripe_customer_portal'),  
    
    # Unified Webhook Receiver (Matches your stripe listen routing target)
    path('webhook/', stripe_webhook, name='stripe_webhook'),
]