import csv
import uuid
import datetime
import stripe
import threading
import time    # 🧭 REQUIRED: Active background thread throttle module
import random  # 🧭 REQUIRED: Random value selector generator
import urllib.parse
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse  # <-- Imported for secure dynamic reverse routing
from django.contrib.auth import login, authenticate, logout  
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator  
from django.core.mail import send_mail  

from .models import ChamberLead, ChamberDirectory, ChamberRequest, Order, OrderItem, UserPurchase
from .forms import ChamberRequestForm  
# Import your custom Playwright management command directly out of your directory hierarchy
from leads.management.commands.run_scraper import Command as ScraperCommand

def landing_page(request):
    """Renders the main platform homepage."""
    context = {
        'is_authenticated_user': request.user.is_authenticated,
        'user_email': request.user.email if request.user.is_authenticated else "",
        'username': request.user.username if request.user.is_authenticated else "",
        'avatar_url': getattr(request.user.profile, 'avatar_url', None) if request.user.is_authenticated and hasattr(request.user, 'profile') else None
    }
    return render(request, 'leads/index.html', context)


def request_custom_scrape(request):
    """
    Processes user requests for a custom scrape.
    Kicks off the scraper engine immediately for value-first previews.
    """
    if request.method == 'POST':
        form = ChamberRequestForm(request.POST)
        if form.is_valid():
            chamber_request = form.save(commit=False)
            
            # Intercept: Check if the user is manually requesting a territory that is already active in the store
            requested_city = form.cleaned_data.get('city_or_region', '').strip()
            existing_directory = ChamberDirectory.objects.filter(city_or_region__iexact=requested_city, is_active=True).first()
            
            if existing_directory:
                # Direct route to instant catalogue fulfillment bypass
                messages.info(request, f"Good news! {requested_city} data is already cataloged. Transferring to instant unlock portal.")
                return redirect('create_checkout_session', request_id=existing_directory.id)
            
            # Dynamic Price String Calculation based on Quantity Tier Selection
            qty = int(form.cleaned_data.get('chambers_count') or 1)
            if qty == 5:
                total_cost_float = 32.00  # "Buy 4, Get 1 Free" Promo pricing application
            else:
                total_cost_float = float(qty * 8.00)
                
            chamber_request.estimated_cost = total_cost_float
            price_string = f"${total_cost_float:.2f}"

            if request.user.is_authenticated and not chamber_request.user_email:
                chamber_request.user_email = request.user.email
                
            # Set initial processing parameters for risk-free deployment
            chamber_request.status = 'scraping'
            chamber_request.console_logs = "📡 [SYSTEM]: Initializing risk-free preview data capture sequence...\n"
            chamber_request.save()
            
            # 🚀 IGNITE BACKGROUND SCRAPER IMMEDIATELY (FREE INITIAL ENTRY)
            threading.Thread(
                target=run_background_scrape,
                args=(
                    chamber_request.id, 
                    chamber_request.chamber_url, 
                    chamber_request.chamber_name,
                    chamber_request.city_or_region,
                    chamber_request.state
                ),
                daemon=True
            ).start()

            # Automated Admin Notification Email Dispatch
            try:
                subject = f"[Live Preview Request] Target Location Tier: {price_string}"
                message = (
                    f"A user has initiated an on-demand data preview generation loop!\n\n"
                    f"Projected Unlock Tier: {price_string} ({qty} Locations)\n"
                    f"Target Chamber Name: {chamber_request.chamber_name}\n"
                    f"URL Provided:\n{chamber_request.chamber_url}\n\n"
                    f"Client Email Contact: {chamber_request.user_email}\n"
                )
                send_mail(
                    subject, message, settings.DEFAULT_FROM_EMAIL,
                    [settings.ADMINS[0][1] if hasattr(settings, 'ADMINS') else settings.DEFAULT_FROM_EMAIL],
                    fail_silently=True
                )
            except Exception:
                pass

            messages.success(
                request, 
                "Discovery Engine activated! Analyzing your target market in real time..."
            )
            return redirect('customer_monitor_view', request_id=chamber_request.id)
    else:
        initial_data = {}
        if request.user.is_authenticated:
            initial_data['user_email'] = request.user.email
        form = ChamberRequestForm(initial=initial_data)

    user_context = {
        'is_authenticated_user': request.user.is_authenticated,
        'user_email': request.user.email if request.user.is_authenticated else "",
        'username': request.user.username if request.user.is_authenticated else "",
        'avatar_url': getattr(request.user.profile, 'avatar_url', None) if request.user.is_authenticated and hasattr(request.user, 'profile') else None,
        'form': form,
    }
    return render(request, 'leads/request_form.html', user_context)


def request_success_view(request):
    """Simple confirmation wrapper passing core navigation status arrays."""
    context = {
        'is_authenticated_user': request.user.is_authenticated,
        'user_email': request.user.email if request.user.is_authenticated else "",
        'username': request.user.username if request.user.is_authenticated else "",
        'avatar_url': getattr(request.user.profile, 'avatar_url', None) if request.user.is_authenticated and hasattr(request.user, 'profile') else None
    }
    return render(request, 'leads/request_success.html', context)


def leads_list(request):
    """
    Displays the list of chamber leads with search queries and regional filtering. 
    New users see teaser masked rows; paid users see a clean, unmasked workspace.
    """
    raw_leads = ChamberLead.objects.all().order_by('organization', 'last_name', 'first_name')
    
    search_query = request.GET.get('q', '').strip()
    chamber_filter = request.GET.get('chamber', '').strip()

    if search_query:
        raw_leads = raw_leads.filter(title__icontains=search_query) | raw_leads.filter(name__icontains=search_query)

    if chamber_filter:
        raw_leads = raw_leads.filter(organization__icontains=chamber_filter) | raw_leads.filter(chamber__icontains=chamber_filter)

    chambers_list = list(ChamberLead.objects.values_list('organization', flat=True).distinct()) + \
                    list(ChamberLead.objects.values_list('chamber', flat=True).distinct())
    unique_chambers = sorted(list(set([c.strip() for c in chambers_list if c and c.lower() not in ['false', 'none', 'general']])))

    user_context = {
        'is_authenticated_user': request.user.is_authenticated,
        'user_email': request.user.email if request.user.is_authenticated else "",
        'username': request.user.username if request.user.is_authenticated else "",
        'unique_chambers': unique_chambers,
        'current_search': search_query,
        'current_chamber': chamber_filter,
        'avatar_url': getattr(request.user.profile, 'avatar_url', None) if request.user.is_authenticated and hasattr(request.user, 'profile') else None
    }

    purchased_directory_ids = set()
    is_staff_or_admin = False
    has_any_purchases = False
    
    if request.user.is_authenticated:
        # Check if this specific user session has ever bought any inventory catalog sets
        user_purchases = UserPurchase.objects.filter(user=request.user, directory__isnull=False)
        has_any_purchases = user_purchases.exists()
        
        purchased_directory_ids = set(user_purchases.values_list('directory_id', flat=True))
        is_staff_or_admin = request.user.is_staff or request.user.is_superuser

    processed_leads = []
    for lead in raw_leads:
        org_str = getattr(lead, 'organization', '') or ''
        chamber_str = getattr(lead, 'chamber', '') or ''
        final_chamber = org_str.strip() or chamber_str.strip() or "Georgia Chamber"
        
        if final_chamber.lower() in ["general", "false", "none"]:
            if getattr(lead, 'email', '') and '@' in lead.email:
                domain = lead.email.split('@')[1].split('.')[0]
                final_chamber = f"{domain.upper()} Chamber"
            else:
                final_chamber = "Georgia Chamber"

        has_purchased_item = (
            lead.directory_id in purchased_directory_ids or 
            is_staff_or_admin
        )

        # 💡 THE INTELLIGENT ROUTER SYSTEM: 
        # If they own active assets, hide locked rows to give them a pristine dashboard. 
        # If they are completely new/free tier, append the teaser rows to drive checkout sales.
        if not has_purchased_item and has_any_purchases:
            continue

        lead_email = getattr(lead, 'email', "") or ""
        lead_title = getattr(lead, 'title', "")
        title_str = str(lead_title).strip() if lead_title else "Chamber Executive"
        final_title = "Chamber Executive" if title_str.lower() in ["false", "", "none"] else title_str

        if has_purchased_item:
            first = getattr(lead, 'first_name', '') or ''
            last = getattr(lead, 'last_name', '') or ''
            full_name = f"{first} {last}".strip() if (first or last) else (getattr(lead, 'name', '') or "Chamber Member")

            processed_leads.append({
                'id': lead.id,
                'directory_id': lead.directory_id or 0,
                'name': full_name,
                'title': final_title,
                'chamber': final_chamber,
                'email': lead_email if lead_email else "No Email Provided",
                'is_locked': False  
            })
        else:
            if getattr(lead, 'email', '') and '@' in lead_email:
                email_parts = lead_email.split('@')
                masked_email = f"{email_parts[0][:1]}***@{email_parts[1]}"
            else:
                masked_email = "No Email Provided"

            processed_leads.append({
                'id': lead.id,
                'directory_id': lead.directory_id or 0,
                'name': 'Chamber Member',
                'title': final_title,
                'chamber': final_chamber,
                'email': masked_email,
                'is_locked': True  
            })
        
    paginator = Paginator(processed_leads, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        **user_context, 
        'page_obj': page_obj,
        'custom_requests': ChamberRequest.objects.filter(user_email__iexact=request.user.email).order_by('-id') if request.user.is_authenticated else None
    }
    return render(request, 'leads/leads_list.html', context)


def purchase_directory(request, request_id=0):
    """Renders the single dynamic catalog checkout menu view platform."""
    active_directories = ChamberDirectory.objects.filter(is_active=True).order_by('name')
    
    context = {
        'is_authenticated_user': request.user.is_authenticated,
        'user_email': request.user.email if request.user.is_authenticated else "",
        'username': request.user.username if request.user.is_authenticated else "",
        'avatar_url': getattr(request.user.profile, 'avatar_url', None) if request.user.is_authenticated and hasattr(request.user, 'profile') else None,
        
        'active_directories': active_directories,
        'pre_selected_id': int(request_id),
        'price_string': "$9.99"
    }
    return render(request, 'leads/purchase_directory.html', context)


def login_view(request):
    """Authenticates existing users into the application."""
    if request.method == 'POST':
        u_name = request.POST.get('username')
        p_word = request.POST.get('password')

        user = authenticate(request, username=u_name, password=p_word)

        if user is not None:
            login(request, user)
            next_url = request.GET.get('next')
            return redirect(next_url) if next_url else redirect('leads_list')
        else:
            messages.error(request, "Invalid username or password.")
            return redirect('login')

    return render(request, 'leads/login.html')


def logout_view(request):
    """Logs out the active user session."""
    logout(request)
    return redirect('home')  


def register_view(request):
    """Handles creating new user accounts securely."""
    if request.method == 'POST':
        honeypot = request.POST.get('hp_email', '')
        if honeypot:
            return redirect('login')

        u_name = request.POST.get('username')
        email = request.POST.get('email')
        p_word = request.POST.get('password')

        if not u_name or not email or not p_word:
            messages.error(request, "All form input fields are required.")
            return render(request, 'leads/register.html')

        if User.objects.filter(username=u_name).exists():
            messages.error(request, "That username configuration has already been taken.")
            return render(request, 'leads/register.html')
            
        if User.objects.filter(email=email).exists():
            messages.error(request, "An account matching that email address already exists.")
            return render(request, 'leads/register.html')

        try:
            user = User.objects.create_user(username=u_name, email=email, password=p_word)
            login(request, user)
            messages.success(request, f"Welcome to the dashboard, {u_name}!")
            return redirect('leads_list')
            
        except Exception as e:
            messages.error(request, f"An application registration database error occurred: {str(e)}")
            return render(request, 'leads/register.html')

    return render(request, 'leads/register.html')


def create_checkout_session(request, request_id):
    """
    Unified Stripe Checkout Engine with Role-Based Routing.
    Bypasses billing for Admins, routes regular customers straight to Stripe,
    and handles dynamic telemetry routing parameters on successful payment.
    """
    if not request.user.is_authenticated:
        return redirect('login')

    # 🛡️ ROLE-BASED OVERRIDE: If logged in as staff/admin, bypass Stripe completely & execute Track 1
    if request.user.is_staff or request.user.is_superuser:
        scrape_request = get_object_or_404(ChamberRequest, id=request_id)
        scrape_request.status = 'scraping'
        scrape_request.console_logs = "📡 [ADMIN BYPASS]: System superuser authorization confirmed. Bypassing billing gateway...\n"
        scrape_request.save()
        
        # Instantly launch the background scraper thread inside local context memory
        threading.Thread(
            target=run_background_scrape,
            args=(
                scrape_request.id, 
                scrape_request.chamber_url, 
                scrape_request.chamber_name,
                scrape_request.city_or_region,
                scrape_request.state
            ),
            daemon=True
        ).start()
        
        messages.success(request, "Admin configuration authenticated. Pipeline execution active.")
        return redirect(f'/purchase/monitor/{scrape_request.id}/')

    # --- STANDARD PRODUCTION STRIPE FLOW FOR REGULAR USERS ---
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        generated_order_id = f"CHB-{uuid.uuid4().hex[:12].upper()}"
        checkout_type = request.GET.get('type', 'directory')

        # --- ROUTE A: CUSTOM ON-DEMAND SCRAPE PIPELINE STAGE ($8.00 base) ---
        if checkout_type == 'custom':
            scrape_request = get_object_or_404(ChamberRequest, id=request_id)
            
            if scrape_request.user_email != request.user.email:
                messages.error(request, "Unauthorized data pipeline checkout attempt.")
                return redirect('leads_list')

            quantity = int(scrape_request.chambers_count or 1)
            package_name = f"Premium Custom Chamber Dataset Extraction ({quantity} Locations)"
            package_description = f"Target Focus: {scrape_request.chamber_name or 'On-Demand Area Operations'}."
            
            if quantity == 5:
                amount_in_cents = 3200  # "Buy 4, Get 1 Free" Activation 
                total_paid_float = 32.00
            else:
                amount_in_cents = quantity * 800  
                total_paid_float = float(quantity * 8.00)
            
            new_order = Order.objects.create(
                user=request.user,
                order_id=generated_order_id,
                amount_paid=total_paid_float,
                is_paid=False
            )
            
            # 💡 REDIRECT HOME TO PRISTINE LEADS LIST: Webhook will dynamically attach directory maps
            success_url = request.build_absolute_uri('/payment-success/')
            metadata = {
                'purchase_type': 'custom_scrape',
                'scrape_request_id': scrape_request.id,
                'order_id': new_order.order_id
            }

        # --- ROUTE B: CATALOG SINGLE DIRECTORY ACCESS TICKET ($9.99) ---
        else:
            if request_id == 0:
                first_directory = ChamberDirectory.objects.filter(is_active=True).first()
                if first_directory:
                    request_id = first_directory.id
                else:
                    messages.error(request, "No active chamber directories are configured for acquisition at this time.")
                    return redirect('leads_list')

            target_directory = get_object_or_404(ChamberDirectory, id=request_id)
            package_name = f"Premium Access: {target_directory.name} Directory"
            package_description = f"Full data unmasking and CSV lead export utility for the [{target_directory.state}] regional dataset."
            amount_in_cents = 999  
            
            new_order = Order.objects.create(
                user=request.user,
                order_id=generated_order_id,
                amount_paid=9.99,
                is_paid=False
            )
            OrderItem.objects.create(order=new_order, directory=target_directory)
            
            success_url = request.build_absolute_uri('/payment-success/')
            metadata = {
                'purchase_type': 'directory',
                'directory_id': target_directory.id,
                'order_id': new_order.order_id
            }

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': package_name,
                            'description': package_description,
                        },
                        'unit_amount': amount_in_cents,  
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            client_reference_id=request.user.id,
            metadata=metadata,
            success_url=success_url,
            cancel_url=request.build_absolute_uri('/request-scrape/'),
        )
        return redirect(checkout_session.url, code=303)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def run_background_scrape(request_id, target_url, chamber_name, city_string, state):
    """Worker function that runs your Playwright script safely inside a background thread context."""
    scraper = ScraperCommand()
    
    def log_to_database(text_line):
        req = ChamberRequest.objects.get(id=request_id)
        req.console_logs += f"{text_line}\n"
        req.save()
        print(text_line)  

    scraper.stdout.write = log_to_database
    scraper.style.SUCCESS = lambda text: text
    scraper.style.WARNING = lambda text: text
    scraper.style.ERROR = lambda text: text

    try:
        log_to_database("📡 [SYSTEM CORE]: Booting asynchronous worker thread pipeline...")
        
        cities = [c.strip() for c in city_string.split(',') if c.strip()]
        log_to_database(f"🗺️ [SYSTEM CORE]: Target batch coordinates parsed: {len(cities)} location nodes found ({', '.join(cities)}).")

        for idx, current_city in enumerate(cities, start=1):
            log_to_database(f"\n📍 [NODE {idx}/{len(cities)}]: Initiating data pipeline sweep for {current_city}, {state.upper()}...")
            
            derived_chamber_name = f"{current_city} Chamber of Commerce"
            derived_fallback_url = f"https://www.google.com/search?q={current_city.replace(' ', '+')}+{state}+chamber+of+commerce"
            
            directory_obj, _ = ChamberDirectory.objects.get_or_create(
                city_or_region__iexact=current_city,
                state__iexact=state,
                defaults={
                    'name': derived_chamber_name,
                    'state': state.upper(),
                    'city_or_region': current_city,
                    'directory_url': derived_fallback_url,
                    'is_active': True
                }
            )
            
            scraper.handle(url=derived_fallback_url, name=derived_chamber_name, state=state)
            
            if idx < len(cities):
                log_to_database(f"⏳ [NODE {idx} COMPLETE]: Pausing pipeline process matrix for throttle cooldown...")
                time.sleep(random.uniform(3.0, 5.0))
        
        req = ChamberRequest.objects.get(id=request_id)
        req.status = 'completed'
        req.save()
        log_to_database("\n🎉 [SYSTEM CORE]: Batch pipeline compilation complete. Operational thread sitting idle.")
        
    except Exception as e:
        log_to_database(f"\n❌ [CRASH INTERCEPT]: Core automation script failure: {str(e)}")
        req = ChamberRequest.objects.get(id=request_id)
        req.status = 'error'
        req.save()


def purchase_view(request):
    """
    Renders the internal data engine console and handles 
    direct database execution workflows.
    """
    if request.method == 'POST':
        chamber_request = ChamberRequest()
        
        chamber_request.state = request.POST.get('state_focus', '').strip()
        chamber_request.city_or_region = request.POST.get('region_name', '').strip()
        chamber_request.chamber_name = request.POST.get('chamber_name', '').strip()
        chamber_request.chamber_url = request.POST.get('target_url', '').strip()
        
        chamber_request.status = 'scraping'
        chamber_request.chambers_count = '1'
        chamber_request.estimated_cost = 0.00
        chamber_request.console_logs = "📡 Booting worker engine sequence...\n"
        
        if request.user.is_authenticated:
            chamber_request.user_email = request.user.email
            
        chamber_request.save()
        
        threading.Thread(
            target=run_background_scrape,
            args=(
                chamber_request.id, 
                chamber_request.chamber_url, 
                chamber_request.chamber_name,
                chamber_request.city_or_region,
                chamber_request.state
            ),
            daemon=True
        ).start()
        
        return redirect(f'/purchase/monitor/{chamber_request.id}/')

    context = {
        'is_authenticated_user': request.user.is_authenticated,
        'user_email': request.user.email if request.user.is_authenticated else "",
        'username': request.user.username if request.user.is_authenticated else "",
        'avatar_url': getattr(request.user.profile, 'avatar_url', None) if request.user.is_authenticated and hasattr(request.user, 'profile') else None,
    }
    return render(request, 'leads/purchase.html', context)


def monitor_view(request, request_id):
    """Renders the dedicated scrolling log window deck for the active scraping run."""
    context = {
        'request_id': request_id,
        'is_authenticated_user': request.user.is_authenticated,
        'username': request.user.username if request.user.is_authenticated else "",
    }
    return render(request, 'leads/purchase_processing.html', context)


def monitor_scrape_api(request, request_id):
    """API endpoint allowing JavaScript to read active database text logs on the fly."""
    req = get_object_or_404(ChamberRequest, id=request_id)
    return JsonResponse({
        'status': req.status,
        'logs': req.console_logs
    })


@login_required
def customer_monitor_view(request, request_id):
    """🎨 Renders the custom telemetry monitor template built for regular users with partial leads context."""
    scrape_request = get_object_or_404(ChamberRequest, id=request_id)
    
    if scrape_request.user_email != request.user.email and not request.user.is_staff:
        return redirect('leads_list')
        
    # Grab the partial leads generated by this run to display as blurred hooks
    preview_leads = ChamberLead.objects.filter(
        organization__icontains=scrape_request.city_or_region
    )[:5]  # Limit to 5 rows to provide proof-of-work value
        
    context = {
        'request_id': request_id,
        'city_or_region': scrape_request.city_or_region,
        'state_focus': scrape_request.state,
        'is_authenticated_user': request.user.is_authenticated,
        'username': request.user.username,
        'scrape_request': scrape_request,
        'preview_leads': preview_leads,
        'cost_string': f"${scrape_request.estimated_cost:.2f}",
        'avatar_url': getattr(request.user.profile, 'avatar_url', None) if hasattr(request.user, 'profile') else None
    }
    return render(request, 'leads/customer_purchase.html', context)


@login_required
def customer_monitor_api(request, request_id):
    """API gateway mapping specific client-safe counts and log parameters directly to front-end JSON tickers."""
    req = get_object_or_404(ChamberRequest, id=request_id)
    
    # Live count evaluation matching records created for this location string
    leads_found = ChamberLead.objects.filter(organization__icontains=req.city_or_region).count()
    
    current_status = req.status
    # 💡 ANTI-RACE CONDITION DELAY: If the background thread says 'completed' but Postgres is still 
    # writing data rows, hold the frontend status loop back in 'scraping' so the preview block maps cleanly.
    if current_status == 'completed' and leads_found == 0:
        current_status = 'scraping'
    
    return JsonResponse({
        'status': current_status,
        'logs': req.console_logs,
        'leads_count': leads_found
    })


def payment_success_view(request):
    return render(request, 'leads/payment_success.html')

def payment_cancel_view(request):
    return render(request, 'leads/payment_cancel.html')


@csrf_exempt
def stripe_webhook(request):
    """Listens for verified webhook calls from Stripe to fulfill purchases automatically."""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        session_dict = session.to_dict() if hasattr(session, 'to_dict') else session
        
        raw_user_id = session_dict.get('client_reference_id')
        try:
            user_id = int(raw_user_id) if raw_user_id else None
        except ValueError:
            user_id = None
            
        metadata = session_dict.get('metadata', {})
        purchase_type = metadata.get('purchase_type')
        order_id = metadata.get('order_id')
        
        if not user_id:
            return HttpResponse(status=200)

        order = Order.objects.filter(order_id=order_id).first()
        if order:
            order.is_paid = True
            order.save()

        try:
            user_obj = User.objects.get(id=user_id)
            
            if purchase_type == 'directory':
                directory_id = metadata.get('directory_id')
                if directory_id:
                    target_directory = ChamberDirectory.objects.filter(id=directory_id).first()
                    if target_directory:
                        UserPurchase.objects.get_or_create(
                            user=user_obj,
                            directory=target_directory,
                            defaults={'stripe_session_id': session_dict.get('id')}
                        )
            
            elif purchase_type == 'custom_scrape':
                scrape_request_id = metadata.get('scrape_request_id')
                if scrape_request_id:
                    scrape_request = ChamberRequest.objects.filter(id=scrape_request_id).first()
                    if scrape_request:
                        # Locate or generate the active ChamberDirectory element so the workspace permissions map open cleanly
                        target_directory, _ = ChamberDirectory.objects.get_or_create(
                            city_or_region__iexact=scrape_request.city_or_region,
                            state__iexact=scrape_request.state,
                            defaults={
                                'name': f"{scrape_request.city_or_region} Chamber of Commerce",
                                'state': scrape_request.state.upper(),
                                'city_or_region': scrape_request.city_or_region,
                                'is_active': True
                            }
                        )
                        
                        # Authorize the purchasing account to view this unlocked directory
                        UserPurchase.objects.get_or_create(
                            user=user_obj,
                            directory=target_directory,
                            defaults={'stripe_session_id': session_dict.get('id')}
                        )
                        
                        # Propagate the directory link back down to the raw leads table to unmask the teaser rows
                        ChamberLead.objects.filter(organization__icontains=scrape_request.city_or_region).update(directory=target_directory)
                        
        except User.DoesNotExist:
            pass

    return HttpResponse(status=200)


@login_required
def export_leads_csv(request):
    """Dynamically streams the user's filtered chamber leads list into a downloadable CSV spreadsheet."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="georgia_chamber_leads.csv"'

    writer = csv.writer(response)
    writer.writerow(['Name', 'First Name', 'Last Name', 'Title', 'Chamber', 'Organization', 'Email', 'Phone'])

    leads_queryset = ChamberLead.objects.all().order_by('organization', 'last_name', 'first_name')
    
    search_query = request.GET.get('q', '').strip()
    chamber_filter = request.GET.get('chamber', '').strip()

    if search_query:
        leads_queryset = leads_queryset.filter(title__icontains=search_query) | leads_queryset.filter(name__icontains=search_query)

    if chamber_filter:
        leads_queryset = leads_queryset.filter(organization__icontains=chamber_filter) | leads_queryset.filter(chamber__icontains=chamber_filter)

    purchased_directory_ids = set(UserPurchase.objects.filter(
        user=request.user, 
        directory__isnull=False
    ).values_list('directory_id', flat=True))
    
    is_staff_or_admin = request.user.is_staff or request.user.is_superuser
    has_any_purchases = len(purchased_directory_ids) > 0

    for lead in leads_queryset:
        org_str = getattr(lead, 'organization', '') or ''
        chamber_str = getattr(lead, 'chamber', '') or ''
        final_chamber = org_str.strip() or chamber_str.strip() or "Georgia Chamber"

        if final_chamber.lower() in ["general", "false", "none"]:
            if getattr(lead, 'email', '') and '@' in lead.email:
                domain = lead.email.split('@')[1].split('.')[0]
                final_chamber = f"{domain.upper()} Chamber"
            else:
                final_chamber = "Georgia Chamber"

        has_access = (
            lead.directory_id in purchased_directory_ids or 
            is_staff_or_admin
        )

        if not has_access and has_any_purchases:
            continue

        lead_email = getattr(lead, 'email', "") or ""
        if not has_access:
            if getattr(lead, 'email', '') and '@' in lead_email:
                email_parts = lead_email.split('@')
                lead_email = f"{email_parts[0][:1]}***@{email_parts[1]}"
            else:
                lead_email = "No Email Provided"

        first = getattr(lead, 'first_name', '') or ''
        last = getattr(lead, 'last_name', '') or ''
        if has_access:
            full_name = f"{first} {last}".strip() or getattr(lead, 'name', '') or "Chamber Member"
        else:
            full_name = "Chamber Member"

        lead_title = getattr(lead, 'title', "")
        title_str = str(lead_title).strip() if lead_title else "Chamber Executive"
        final_title = "Chamber Executive" if title_str.lower() in ["false", "", "none"] else title_str

        writer.writerow([
            full_name,
            first if has_access else '',
            last if has_access else '',
            final_title,
            final_chamber,
            org_str,
            lead_email,
            getattr(lead, 'phone', '') or ''
        ])

    return response


def active_directories_api(request):
    """Serves a raw array of lowercase city names currently cataloged in the database layout."""
    cities = ChamberDirectory.objects.filter(is_active=True).values_list('city_or_region', flat=True).distinct()
    cleaned_cities = [str(c).strip().lower() for c in cities if c]
    return JsonResponse({'active_cities': cleaned_cities})


def about_page(request):
    """Renders the trust, objective and customer-centric value positioning framework."""
    context = {
        'is_authenticated_user': request.user.is_authenticated,
        'user_email': request.user.email if request.user.is_authenticated else "",
        'username': request.user.username if request.user.is_authenticated else "",
        'avatar_url': getattr(request.user.profile, 'avatar_url', None) if request.user.is_authenticated and hasattr(request.user, 'profile') else None
    }
    return render(request, 'leads/about.html', context)