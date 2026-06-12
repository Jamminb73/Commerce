from django.contrib import admin
from django.urls import path, include  
from django.contrib.sitemaps.views import sitemap  

from leads.sitemaps import StaticViewSitemap        
from leads.views import (
    landing_page,
    leads_list,       
    register_view,
    login_view,
    logout_view,             
    purchase_view,
    create_checkout_session,
    payment_success_view,
    payment_cancel_view,
    manual_upgrade_test,     
    stripe_webhook,
    stripe_customer_portal,  
    request_custom_scrape,          # <-- Imported your new intake view
    request_success_view,           # <-- Imported your new success view
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
    path('leads/', leads_list, name='leads_list'),  
    
    # Custom $49 Scraping Requests System
    path('request-scrape/', request_custom_scrape, name='request_custom_scrape'),
    path('request-scrape/success/', request_success_view, name='request_custom_scrape_success'),
    
    # Secure Backend Blog App Router
    path('blog/', include('blog.urls')), 
    
    # Local Development Cheat Code Backdoor
    path('manual-upgrade/', manual_upgrade_test, name='manual_upgrade'),
    
    # Stripe Checkout & Payment Flows
    path('purchase/', purchase_view, name='purchase'),
    path('create-checkout-session/', create_checkout_session, name='create_checkout_session'),
    path('payment-success/', payment_success_view, name='payment_success'),
    path('payment-cancel/', payment_cancel_view, name='payment_cancel'),
    
    # Stripe Billing/Cancellation Management Portal
    path('account/manage/', stripe_customer_portal, name='stripe_customer_portal'),  
    
    # Unified Webhook Receiver (Matches your stripe listen routing target)
    path('webhook/', stripe_webhook, name='stripe_webhook'),
]
