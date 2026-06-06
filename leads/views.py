import datetime
import stripe
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout  # <-- logout utility imported here
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.utils.dateparse import parse_datetime
from .models import ChamberLead

def landing_page(request):
    """
    Renders the main platform homepage.
    Unified account navigation variables are passed to handle consistent dropdown menu layouts.
    """
    # Build the unified account navigation variables for the homepage navbar layout
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

    return render(request, 'index.html', context)


def leads_list(request):
    """
    Displays the list of chamber leads with live search query mapping and regional filtering. 
    Premium users see clean, full unmasked granular fields.
    Guests and free users see 'Chamber Member' and masked emails.
    """
    # 1. Pull base query set
    raw_leads = ChamberLead.objects.all()
    
    # 2. Extract GET filter parameters from search bar controls
    search_query = request.GET.get('q', '').strip()
    chamber_filter = request.GET.get('chamber', '').strip()

    if search_query:
        raw_leads = raw_leads.filter(title__icontains=search_query) | raw_leads.filter(name__icontains=search_query)

    if chamber_filter:
        raw_leads = raw_leads.filter(organization__icontains=chamber_filter) | raw_leads.filter(chamber__icontains=chamber_filter)

    # 3. Compile unique chamber dropdown collections dynamically from the database fields
    chambers_list = list(ChamberLead.objects.values_list('organization', flat=True).distinct()) + \
                    list(ChamberLead.objects.values_list('chamber', flat=True).distinct())
    unique_chambers = sorted(list(set([c.strip() for c in chambers_list if c and c.lower() not in ['false', 'none', 'general']])))

    # Unified Account Navigation Variables for your Profile Dropdown Menu Layout
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
            # Type safety check for email field
            lead_email = getattr(lead, 'email', "") or ""

            # Prioritize high-fidelity first/last name tracking fields
            first = getattr(lead, 'first_name', '') or ''
            last = getattr(lead, 'last_name', '') or ''
            
            if first or last:
                full_name = f"{first} {last}".strip()
            else:
                # Fallback to legacy string name field if granular fields are empty
                legacy_name = getattr(lead, 'name', '')
                if isinstance(legacy_name, (datetime.datetime, datetime.date)):
                    full_name = legacy_name.isoformat()
                else:
                    full_name = str(legacy_name).strip() if legacy_name else "Chamber Member"

            # Clean up default Title checks
            lead_title = getattr(lead, 'title', "")
            title_str = str(lead_title).strip() if lead_title else "Chamber Executive"
            final_title = "Chamber Executive" if title_str.lower() in ["false", "", "none"] else title_str

            # Prioritize Organization field over legacy Chamber string
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
                'is_locked': False  # Fully viewable row styling
            })

        context = {**user_context, 'leads': safe_leads}
        return render(request, 'leads/leads_list.html', context)
    
    # 5. FREE / ANONYMOUS BLOCK (Masked Data)
    masked_leads = []
    for lead in raw_leads:
        lead_email = getattr(lead, 'email', "") or ""

        if lead_email:
            email_parts = lead_email.split('@')
            if len(email_parts) == 2:
                # Mask user identification string before domain
                masked_email = f"{email_parts[0][:1]}***@{email_parts[1]}"
            else:
                masked_email = "l***@..."
        else:
            masked_email = "No Email Provided"

        # Safe fallback checks for organization visibility on restricted listings
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
            'is_locked': True  # Triggers greyed-out visual layout row filters
        })
        
    context = {**user_context, 'leads': masked_leads}
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
            if next_url:
                return redirect(next_url)
            return redirect('leads_list')
        else:
            messages.error(request, "Invalid username or password.")
            return redirect('login')

    return render(request, 'leads/login.html')


def logout_view(request):
    """Logs out the active user session and redirects to the natural home page."""
    logout(request)
    return redirect('home')  # Points straight back to your landing page route name


def register_view(request):
    """Handles both rendering the registration form and creating new user accounts securely."""
    if request.method == 'POST':
        u_name = request.POST.get('username')
        email = request.POST.get('email')
        p_word = request.POST.get('password')

        # Baseline empty value sanitization tracking
        if not u_name or not email or not p_word:
            messages.error(request, "All form input fields are required.")
            return render(request, 'register.html')

        # Check unique database states to avoid model exception crashes
        if User.objects.filter(username=u_name).exists():
            messages.error(request, "That username configuration has already been taken.")
            return render(request, 'register.html')
            
        if User.objects.filter(email=email).exists():
            messages.error(request, "An account matching that email address already exists.")
            return render(request, 'register.html')

        try:
            # 1. Save user object instance securely with hashed configuration blocks
            user = User.objects.create_user(username=u_name, email=email, password=p_word)
            
            # Note: Your post_save signal auto-attaches their blank Profile class here.
            
            # 2. Login the new creation token immediately
            login(request, user)
            
            messages.success(request, f"Welcome to the dashboard, {u_name}!")
            return redirect('leads_list')
            
        except Exception as e:
            messages.error(request, f"An application registration database error occurred: {str(e)}")
            return render(request, 'register.html')

    return render(request, 'register.html')


def create_checkout_session(request):
    """Generates a Stripe Checkout Session and redirects the user to payment."""
    if not request.user.is_authenticated:
        return redirect('login')

    if request.method == 'POST':
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {
                                'name': 'CommerceSales Premium Access',
                                'description': 'Full unmasked access to Georgia Chamber Lead directories.',
                            },
                            'unit_amount': 4900,  # Scaled down to $49.00 to keep it affordable
                        },
                        'quantity': 1,
                    },
                ],
                mode='payment',
                client_reference_id=request.user.id,
                success_url=request.build_absolute_uri('/payment-success/'),
                cancel_url=request.build_absolute_uri('/payment-cancel/'),
            )
            return redirect(checkout_session.url, code=303)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return redirect('purchase')


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
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                if hasattr(user, 'profile'):
                    user.profile.is_premium = True
                    user.profile.save()
            except User.DoesNotExist:
                pass

    return HttpResponse(status=200)