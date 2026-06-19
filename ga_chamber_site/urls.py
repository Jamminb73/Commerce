# urls.py
from django.contrib import admin
from django.urls import path, include  
from django.contrib.sitemaps.views import sitemap  

from leads.sitemaps import StaticViewSitemap        
from leads.views import (
    landing_page,
    leads_list,       
    purchase_directory,             
    register_view,
    login_view,
    logout_view,             
    purchase_view,
    monitor_view,                   
    monitor_scrape_api,             
    create_checkout_session,
    payment_success_view,
    payment_cancel_view,     
    stripe_webhook,
    request_custom_scrape,          
    request_success_view,           
    export_leads_csv,               
    active_directories_api,         
    about_page,                     
    customer_monitor_view,          # 💡 FIXED: Imported your new user-facing telemetry view
    customer_monitor_api            # 💡 FIXED: Imported your new user-facing JSON API view
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
    path('about/', about_page, name='about_page'), 
    path('leads/', leads_list, name='leads_list'),  
    path('leads/export/', export_leads_csv, name='export_leads_csv'),  
    
    # Dedicated Dropdown Catalogue Checkout Flow
    path('purchase-directory/', purchase_directory, name='purchase_directory_base'),
    path('purchase-directory/<int:request_id>/', purchase_directory, name='purchase_directory'),
    
    # Hidden API Routing Layer
    path('api/active-cities/', active_directories_api, name='active_cities_api'),  
    
    # Custom Dynamic Scraping Requests System
    path('request-scrape/', request_custom_scrape, name='request_custom_scrape'),
    path('request-scrape/success/', request_success_view, name='request_success'),
    
    # Secure Backend Blog App Router
    path('blog/', include('blog.urls')), 
    
    # Stripe Checkout & Payment Flows
    path('purchase/', purchase_view, name='purchase'),
    path('create-checkout-session/<int:request_id>/', create_checkout_session, name='create_checkout_session'),
    path('payment-success/', payment_success_view, name='payment_success'),
    path('payment-cancel/', payment_cancel_view, name='payment_cancel'),
    
    # TRACK 1: Admin Telemetry & Manual Scraping Terminal Logs
    path('purchase/monitor/<int:request_id>/', monitor_view, name='monitor_view'),
    path('purchase/monitor/api/<int:request_id>/', monitor_scrape_api, name='monitor_scrape_api'),
    
    # TRACK 2: Client Workspace Branded Telemetry Tickers
    path('workspace/monitor/<int:request_id>/', customer_monitor_view, name='customer_monitor_view'),
    path('workspace/monitor/api/<int:request_id>/', customer_monitor_api, name='customer_monitor_api'),
    
    # Unified Webhook Receiver (Matches your stripe listen routing target)
    path('webhook/', stripe_webhook, name='stripe_webhook'),
]