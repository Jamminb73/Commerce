import uuid
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

from .models import ChamberLead, ChamberDirectory, ChamberRequest, Order, OrderItem, UserPurchase
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
    Anchored cleanly to our primary entry-level price point of $49.00.
    """
    if request.method == 'POST':
        form = ChamberRequestForm(request.POST)
        if form.is_valid():
            chamber_request = form.save(commit=False)
            
            # Align database parameters explicitly with our verified $49 pricing entry boundary
            chamber_request.estimated_cost = 49.00
            price_string = "$49.00"

            # Fallback to current authenticated user's email if field was left blank
            if request.user.is_authenticated and not chamber_request.user_email:
                chamber_request.user_email = request.user.email
                
            chamber_request.save()
            
            # Automated Workspace Admin Notification Email Dispatch
            try:
                subject = f"[Scrape Request] New Order Tier Level: {price_string}"
                message = (
                    f"New client dataset pipeline submission alert!\n\n"
                    f"Plan Selection: {price_string}\n"
                    f"Target Chamber Name: {chamber_request.chamber_name}\n"
                    f"URL Provided:\n{chamber_request.target_url}\n\n"
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
    Users who have explicitly purchased specific directories or leads see clean, full unmasked data.
    Unpurchased rows default to 'Chamber Member' and masked emails.
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

    # Compile the active set of items this specific user has paid access boundaries for
    purchased_directory_ids = set()
    purchased_lead_ids = set()
    
    if request.user.is_authenticated:
        purchased_directory_ids = set(UserPurchase.objects.filter(user=request.user, directory__isnull=False).values_list('directory_id', flat=True))
        purchased_lead_ids = set(UserPurchase.objects.filter(user=request.user, lead__isnull=False).values_list('lead_id', flat=True))

    processed_leads = []
    for lead in raw_leads:
        # Check if the user has unlocked this specific item by directory OR individual lead purchase
        has_purchased_item = (
            (lead.directory_id in purchased_directory_ids) or 
            (lead.id in purchased_lead_ids) or
            user_context['is_premium_member']  # Backward compatibility global override
        )

        lead_email = getattr(lead, 'email', "") or ""
        org_str = getattr(lead, 'organization', '') or ''
        chamber_str = getattr(lead, 'chamber', '') or ''
        final_chamber = org_str.strip() or chamber_str.strip() or "Georgia Chamber"
        
        if final_chamber.lower() in ["general", "false", "none"]:
            if lead_email and '@' in lead_email:
                domain = lead_email.split('@')[1].split('.')[0]
                final_chamber = f"{domain.upper()} Chamber"
            else:
                final_chamber = "Georgia Chamber"

        lead_title = getattr(lead, 'title', "")
        title_str = str(lead_title).strip() if lead_title else "Chamber Executive"
        final_title = "Chamber Executive" if title_str.lower() in ["false", "", "none"] else title_str

        if has_purchased_item:
            # 1. PAID/UNLOCKED DATA FLOW
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

            processed_leads.append({
                'name': full_name,
                'title': final_title,
                'chamber': final_chamber,
                'email': lead_email if lead_email else "No Email Provided",
                'is_locked': False  
            })
        else:
            # 2. MASKED DATA FLOW (User hasn't paid for this asset yet)
            if lead_email:
                email_parts = lead_email.split('@')
                if len(email_parts) == 2:
                    masked_email = f"{email_parts[0][:1]}***@{email_parts[1]}"
                else:
                    masked_email = "l***@..."
            else:
                masked_email = "No Email Provided"

            processed_leads.append({
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
    Generates a Stripe Checkout Session. Maps to a specific $49 custom scrape 
    if request_id > 0, or processes a global sitewide Premium Upgrade if request_id == 0.
    """
    if not request.user.is_authenticated:
        return redirect('login')

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # INTERCEPT INTERNALLY FLAG: Global Premium Sitewide Upgrade ($49.00 fixed entry point)
        if request_id == 0:
            package_name = "Chamber Pipeline Premium Membership"
            package_description = "Unlimited access to all unmasked Chamber directories and lead exports."
            amount_in_cents = 4900  
            
            generated_order_id = f"SUB-{uuid.uuid4().hex[:12].upper()}"
            new_order = Order.objects.create(
                user=request.user,
                order_id=generated_order_id,
                amount_paid=49.00,
                is_paid=False
            )
            metadata = {
                'order_id': new_order.order_id,
                'global_upgrade': 'true'
            }

        # STANDARD PATHWAY: Custom Dataset Scrape Checkout Flow
        else:
            scrape_request = ChamberRequest.objects.get(id=request_id)
            
            # Security Boundary
            if scrape_request.user_email != request.user.email:
                messages.error(request, "Unauthorized request checkout attempt.")
                return redirect('leads_list')
                
            package_name = "Premium Custom Chamber Dataset Extraction"
            package_description = f"Target Focus: {scrape_request.chamber_name}. Scope Target URL: {scrape_request.target_url}"
            amount_in_cents = int(float(scrape_request.estimated_cost) * 100)
            
            generated_order_id = f"ORD-{uuid.uuid4().hex[:12].upper()}"
            new_order = Order.objects.create(
                user=request.user,
                order_id=generated_order_id,
                amount_paid=scrape_request.estimated_cost,
                is_paid=False
            )
            OrderItem.objects.create(order=new_order)
            metadata = {
                'chamber_request_id': scrape_request.id,
                'order_id': new_order.order_id,
                'global_upgrade': 'false'
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
    """Renders the entry-level premium access information page with sticky nav context arrays."""
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

    return render(request, 'leads/purchase.html', context)

def payment_success_view(request):
    return render(request, 'leads/payment_success.html')

def payment_cancel_view(request):
    return render(request, 'leads/cancel.html')


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
        order_id = metadata.get('order_id')
        global_upgrade = metadata.get('global_upgrade')
        
        # 1. Handle incoming isolated item purchase matches via tracking orders
        if order_id and user_id:
            try:
                order = Order.objects.get(order_id=order_id, user_id=user_id)
                order.is_paid = True
                order.save()

                # Process specific item fulfillments inside UserPurchase boundary layout
                for item in order.items.all():
                    UserPurchase.objects.get_or_create(
                        user_id=user_id,
                        directory=item.directory,
                        lead=item.lead,
                        stripe_session_id=session.id
                    )
            except Order.DoesNotExist:
                pass

        # 2. Update tracking state on the ChamberRequest model
        if chamber_request_id:
            try:
                scrape_req = ChamberRequest.objects.get(id=chamber_request_id)
                scrape_req.status = 'completed'  
                scrape_req.save()
            except ChamberRequest.DoesNotExist:
                pass
        
        # 3. Handle global flat directory upgrades or explicit sitewide dashboard overrides
        if (global_upgrade == 'true' or not order_id) and user_id:
            try:
                user = User.objects.get(id=user_id)
                if hasattr(user, 'profile'):
                    user.profile.is_premium = True
                    user.profile.save()
            except User.DoesNotExist:
                pass

    return HttpResponse(status=200)