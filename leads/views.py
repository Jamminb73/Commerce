import csv
import uuid
import datetime
import stripe
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
    Intercepts pre-existing database regions to bypass delays and route directly to instant purchase.
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
            
            # Continue with normal custom pipeline extraction assignment ($8.00)
            chamber_request.estimated_cost = 8.00
            price_string = "$8.00"

            if request.user.is_authenticated and not chamber_request.user_email:
                chamber_request.user_email = request.user.email
                
            chamber_request.save()
            
            # Automated Admin Notification Email Dispatch
            try:
                subject = f"[Scrape Request] New Order Tier Level: {price_string}"
                message = (
                    f"New client dataset pipeline submission alert!\n\n"
                    f"Plan Selection: {price_string}\n"
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
                "Your custom scrape request has been logged! Redirecting to secure checkout..."
            )
            
            # 💡 SAFE ROUTING FIX: Utilizing reverse matching to ensure trailing slashes play nice with URL parameters
            checkout_url = reverse('create_checkout_session', kwargs={'request_id': chamber_request.id})
            return redirect(f"{checkout_url}?type=custom")
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
    Users who have explicitly purchased specific directories see full unmasked data.
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

    # Compile the active set of directories this specific user has paid access to
    purchased_directory_names = set()
    is_staff_or_admin = False
    
    if request.user.is_authenticated:
        # Get all purchased directory models, and map access strictly by their string names
        purchased_directories = ChamberDirectory.objects.filter(
            id__in=UserPurchase.objects.filter(user=request.user, directory__isnull=False).values_list('directory_id', flat=True)
        )
        purchased_directory_names = set([d.name.strip().lower() for d in purchased_directories if d.name])
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

        # 💡 DATA GUARD LOCKDOWN: Verifies if the lead belongs strictly to an unmasked chamber string the user bought
        has_purchased_item = (
            final_chamber.strip().lower() in purchased_directory_names or 
            is_staff_or_admin
        )

        lead_email = getattr(lead, 'email', "") or ""
        lead_title = getattr(lead, 'title', "")
        title_str = str(lead_title).strip() if lead_title else "Chamber Executive"
        final_title = "Chamber Executive" if title_str.lower() in ["false", "", "none"] else title_str

        if has_purchased_item:
            first = getattr(lead, 'first_name', '') or ''
            last = getattr(lead, 'last_name', '') or ''
            
            if first or last:
                full_name = f"{first} {last}".strip()
            else:
                legacy_name = getattr(lead, 'name', '')
                full_name = legacy_name.isoformat() if isinstance(legacy_name, (datetime.datetime, datetime.date)) else str(legacy_name).strip() if legacy_name else "Chamber Member"

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
            if lead_email and '@' in lead_email:
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

    context = {**user_context, 'page_obj': page_obj}
    return render(request, 'leads/leads_list.html', context)


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
    Unified Stripe Checkout Engine.
    Segregates inventory assets and custom pipelines cleanly using explicit routing arguments.
    """
    if not request.user.is_authenticated:
        return redirect('login')

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        generated_order_id = f"CHB-{uuid.uuid4().hex[:12].upper()}"
        checkout_type = request.GET.get('type', 'directory') # 💡 Sensor: Checks if custom type parameter exists

        # --- ROUTE A: CUSTOM ON-DEMAND SCRAPE PIPELINE STAGE ($8.00) ---
        if checkout_type == 'custom':
            scrape_request = get_object_or_404(ChamberRequest, id=request_id)
            
            if scrape_request.user_email != request.user.email:
                messages.error(request, "Unauthorized data pipeline checkout attempt.")
                return redirect('leads_list')
                
            package_name = "Premium Custom Chamber Dataset Extraction"
            package_description = f"Target Focus: {scrape_request.chamber_name}. Target URL: {scrape_request.chamber_url}"
            amount_in_cents = 800  
            
            new_order = Order.objects.create(
                user=request.user,
                order_id=generated_order_id,
                amount_paid=8.00,
                is_paid=False
            )
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
            success_url=request.build_absolute_uri('/payment-success/'),
            cancel_url=request.build_absolute_uri('/payment-cancel/'),
        )
        return redirect(checkout_session.url, code=303)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def purchase_view(request):
    """Renders the entry-level pricing selection board."""
    context = {
        'is_authenticated_user': request.user.is_authenticated,
        'user_email': request.user.email if request.user.is_authenticated else "",
        'username': request.user.username if request.user.is_authenticated else "",
        'avatar_url': getattr(request.user.profile, 'avatar_url', None) if request.user.is_authenticated and hasattr(request.user, 'profile') else None
    }
    return render(request, 'leads/purchase.html', context)

def payment_success_view(request):
    return render(request, 'leads/payment_success.html')

def payment_cancel_view(request):
    return render(request, 'leads/cancel.html')


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
                        scrape_request.status = 'scraping'
                        scrape_request.save()
                        
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

    purchased_directories = ChamberDirectory.objects.filter(
        id__in=UserPurchase.objects.filter(user=request.user, directory__isnull=False).values_list('directory_id', flat=True)
    )
    purchased_directory_names = set([d.name.strip().lower() for d in purchased_directories if d.name])
    is_staff_or_admin = request.user.is_staff or request.user.is_superuser

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

        # 💡 CSV LOCKDOWN: Verifies rows match a specific unmasked chamber string before outputting data
        has_access = (
            final_chamber.strip().lower() in purchased_directory_names or 
            is_staff_or_admin
        )

        lead_email = getattr(lead, 'email', "") or ""
        if not has_access:
            if lead_email and '@' in lead_email:
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