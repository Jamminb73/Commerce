import datetime
import stripe
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout  
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.utils.dateparse import parse_datetime
from django.core.paginator import Paginator  
from django.core.mail import send_mail  

from .models import ChamberLead, ChamberDirectory, ChamberRequest
from .forms import ChamberRequestForm  

def landing_page(request):
    """
    Renders the main platform homepage.
    Unified account navigation variables are passed to handle consistent dropdown menu layouts.
    """
    context = {
        'is_authenticated_user': request.user.is_authenticated,
        'user_email': request.user.email if request.user.is_authenticated else "",
        'username': request.user.username if request.user.is_authenticated else "",
        'is_premium_member': False,
        'avatar_url': None
    }
    
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        context['is_premium_member'] = request.user.profile.is_premium
        context['avatar_url'] = getattr(request.user.profile, 'avatar_url', None)

    return render(request, 'leads/index.html', context)


def request_custom_scrape(request):
    """
    Processes user submission requests for custom tiered data extraction batches.
    Calculates value points dynamically from $9.99 up to scale multi-unit packs.
    """
    if request.method == 'POST':
        form = ChamberRequestForm(request.POST)
        if form.is_valid():
            chamber_request = form.save(commit=False)
            
            # 1. Map dynamic cost structures based on chosen tier constraints
            selected_count = int(form.cleaned_data.get('chambers_count', 1))
            if selected_count == 1:
                chamber_request.estimated_cost = 9.99
                price_string = "$9.99"
            elif selected_count == 5:
                chamber_request.estimated_cost = 49.00
                price_string = "$49.00"
            elif selected_count == 10:
                chamber_request.estimated_cost = 99.00
                price_string = "$99.00"
            else:
                chamber_request.estimated_cost = 0.00  # Flagged for manual custom quote review
                price_string = "Custom Quote ($10/ch)"

            # Fallback to current authenticated user's email if field was left blank
            if request.user.is_authenticated and not chamber_request.user_email:
                chamber_request.user_email = request.user.email
                
            chamber_request.save()
            
            # 2. Automated Workspace Admin Notification Email Dispatch
            try:
                subject = f"[Scrape Request] Tier Level: {price_string} for {chamber_request.state}"
                message = (
                    f"New client dataset pipeline submission alert!\n\n"
                    f"Plan Selection: {price_string} (Tier Target Count: {selected_count})\n"
                    f"State Focus: {chamber_request.state}\n"
                    f"Cities: {chamber_request.city_or_region}\n"
                    f"Targets:\n{chamber_request.chamber_name}\n\n"
                    f"URLs Provided:\n{chamber_request.chamber_url}\n\n"
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
                "Your custom scrape request has been successfully logged! Redirecting to secure checkout..."
            )
            return redirect('create_checkout_session', request_id=chamber_request.id)
    else:
        initial_data = {}
        if request.user.is_authenticated:
            initial_data['user_email'] = request.user.email
        form = ChamberRequestForm(initial=initial_data)

    user_context = {
        'is_authenticated_user': request.user.is_authenticated,
        'user_email': request.user.email if request.user.is_authenticated else "",
        'username': request.user.username if request.user.is_authenticated else "",
        'is_premium_member': False,
        'avatar_url': None,
        'form': form,
    }
    
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        user_context['is_premium_member'] = request.user.profile.is_premium
        user_context['avatar_url'] = getattr(request.user.profile, 'avatar_url', None)
        
    return render(request, 'leads/request_form.html', user_context)


def request_success_view(request):
    """Simple confirmation wrapper passing core navigation status arrays."""
    context = {
        'is_authenticated_user': request.user.is_authenticated,
        'user_email': request.user.email if request.user.is_authenticated else "",
        'username': request.user.username if request.user.is_authenticated else "",
        'is_premium_member': False,
        'avatar_url': None
    }
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        context['is_premium_member'] = request.user.profile.is_premium
        context['avatar_url'] = getattr(request.user.profile, 'avatar_url', None)
        
    return render(request, 'leads/request_success.html', context)


def leads_list(request):
    """
    Displays the list of chamber leads with live search query mapping and regional filtering. 
    Premium users see clean, full unmasked granular fields.
    Guests and free users see 'Chamber Member' and masked emails.
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
        'is_premium_member': False,
        'avatar_url': None,
        'unique_chambers': unique_chambers,
        'current_search': search_query,
        'current_chamber': chamber_filter,
    }
    
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        user_context['is_premium_member'] = request.user.profile.is_premium
        user_context['avatar_url'] = getattr(request.user.profile, 'avatar_url', None)

    # 4. PREMIUM USER BLOCK (Full Unmasked Data)
    if request.user.is_authenticated and user_context['is_premium_member']:
        safe_leads = []
        for lead in raw_leads:
            lead_email = getattr(lead, 'email', "") or ""
            first = getattr(lead, 'first_name', '') or ''
            last = getattr(lead, 'last_name', '') or ''
            
            if first or last:
                full_name = f"{first} {last}".strip()
            else:
                legacy_name = getattr(lead, 'name', '')
                if isinstance(legacy_name, (datetime.datetime, datetime.date)):
                    full_name = legacy_name.isoformat()
                else:
                    full_name = str(legacy_name).strip() if legacy_name else "Chamber Member"

            lead_title = getattr(lead, 'title', "")
            title_str = str(lead_title).strip() if lead_title else "Chamber Executive"
            final_title = "Chamber Executive" if title_str.lower() in ["false", "", "none"] else title_str

            org_str = getattr(lead, 'organization', '') or ''
            chamber_str = getattr(lead, 'chamber', '') or ''
            final_chamber = org_str.strip() or chamber_str.strip() or "Georgia Chamber"
            
            if final_chamber.lower() in ["general", "false", "none"]:
                if lead_email and '@' in lead_email:
                    domain = lead_email.split('@')[1].split('.')[0]
                    final_chamber = f"{domain.upper()} Chamber"
                else:
                    final_chamber = "Georgia Chamber"

            safe_leads.append({
                'name': full_name,
                'title': final_title,
                'chamber': final_chamber,
                'email': lead_email if lead_email else "No Email Provided",
                'is_locked': False  
            })

        paginator = Paginator(safe_leads, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {**user_context, 'page_obj': page_obj}
        return render(request, 'leads/leads_list.html', context)
    
    # 5. FREE / ANONYMOUS BLOCK (Masked Data)
    masked_leads = []
    for lead in raw_leads:
        lead_email = getattr(lead, 'email', "") or ""

        if lead_email:
            email_parts = lead_email.split('@')
            if len(email_parts) == 2:
                masked_email = f"{email_parts[0][:1]}***@{email_parts[1]}"
            else:
                masked_email = "l***@..."
        else:
            masked_email = "No Email Provided"

        org_str = getattr(lead, 'organization', '') or ''
        chamber_str = getattr(lead, 'chamber', '') or ''
        final_chamber = org_str.strip() or chamber_str.strip() or "Georgia Chamber"
        if final_chamber.lower() in ["general", "false"]:
            if lead_email and '@' in lead_email:
                final_chamber = f"{lead_email.split('@')[1].split('.')[0].upper()} Chamber"

        lead_title = getattr(lead, 'title', "")
        title_str = str(lead_title).strip() if lead_title else "Chamber Executive"
        final_title = "Chamber Executive" if title_str.lower() in ["false", ""] else title_str

        masked_leads.append({
            'name': 'Chamber Member',
            'title': final_title,
            'chamber': final_chamber,
            'email': masked_email,
            'is_locked': True  
        })
        
    paginator = Paginator(masked_leads, 50)
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
    """Logs out the active user session and redirects to the natural home page."""
    logout(request)
    return redirect('home')  


def register_view(request):
    """Handles both rendering the registration form and creating new user accounts securely."""
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
    Dynamically generates a Stripe Checkout Session matching the specific 
    cost tier recorded on the incoming ChamberRequest instance.
    """
    if not request.user.is_authenticated:
        return redirect('login')

    try:
        scrape_request = ChamberRequest.objects.get(id=request_id)
        
        # Security Boundary: Ensure users can only pay for their own requests
        if scrape_request.user_email != request.user.email:
            messages.error(request, "Unauthorized request checkout attempt.")
            return redirect('leads_list')
            
        # Convert cost database decimal directly into Stripe integer cents ($9.99 -> 999)
        amount_in_cents = int(float(scrape_request.estimated_cost) * 100)
        
        # Build clean visual identifiers for the customer's billing invoice panel
        package_name = f"Custom Dataset Extraction ({scrape_request.chambers_count} Chamber Pack)"
        if scrape_request.chambers_count == 1:
            package_name = "Single Target Chamber Dataset Extraction"

        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': package_name,
                            'description': f"Target Focus: {scrape_request.city_or_region}, {scrape_request.state}. Scope targets: {scrape_request.chamber_name}",
                        },
                        'unit_amount': amount_in_cents,  
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            client_reference_id=request.user.id,
            metadata={
                'chamber_request_id': scrape_request.id
            },
            success_url=request.build_absolute_uri('/payment-success/'),
            cancel_url=request.build_absolute_uri('/payment-cancel/'),
        )
        return redirect(checkout_session.url, code=303)
    except ChamberRequest.DoesNotExist:
        messages.error(request, "Target workspace request dataset not located.")
        return redirect('leads_list')
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def stripe_customer_portal(request):
    """Secure direct redirect route to let active users modify or cancel recurring subs via Stripe."""
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to manage your subscription accounts.")
        return redirect('login')

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        profile = request.user.profile
        
        customer_id = getattr(profile, 'stripe_customer_id', None)
        if not customer_id:
            customers = stripe.Customer.list(email=request.user.email, limit=1)
            if customers.data:
                customer_id = customers.data[0].id
            else:
                messages.error(request, "No billing history or active subscription token found.")
                return redirect('leads_list')

        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url='http://127.0.0.1:8000/leads/',
        )
        return redirect(session.url, code=303)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ==========================================
# ORIGINAL PROJECT VIEWS, HOOKS, & TEST VIEWS
# ==========================================

def purchase_view(request):
    return render(request, 'purchase.html')

def payment_success_view(request):
    return render(request, 'payment_success.html')

def payment_cancel_view(request):
    return render(request, 'cancel.html')


def manual_upgrade_test(request):
    """Temporary local development cheat code to flip profile status instantly without the Stripe CLI."""
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        request.user.profile.is_premium = True
        request.user.profile.save()
        messages.success(request, f"Local Dev Override: {request.user.username} has been granted Premium Access!")
    return redirect('leads_list')


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
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('client_reference_id')
        metadata = session.get('metadata', {})
        chamber_request_id = metadata.get('chamber_request_id')
        
        # Case A: Handle incoming paid custom tiered requests
        if chamber_request_id:
            try:
                scrape_req = ChamberRequest.objects.get(id=chamber_request_id)
                scrape_req.status = 'PAID'
                scrape_req.save()
            except ChamberRequest.DoesNotExist:
                pass
        
        # Case B: Handle legacy flat directory upgrades
        elif user_id:
            try:
                user = User.objects.get(id=user_id)
                if hasattr(user, 'profile'):
                    user.profile.is_premium = True
                    user.profile.save()
            except User.DoesNotExist:
                pass

    return HttpResponse(status=200)