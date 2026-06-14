from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class ChamberDirectory(models.Model):
    """
    Represents a specific chamber asset nationwide. 
    Allows bundling leads by state or city for future packages.
    """
    name = models.CharField(max_length=255, help_text="e.g., Austin Chamber of Commerce")
    state = models.CharField(max_length=2, db_index=True, help_text="2-letter US state code (e.g., TX, FL, GA)")
    city_or_region = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., Austin")
    directory_url = models.URLField(max_length=500, blank=True, null=True, help_text="The source URL scraped")
    is_active = models.BooleanField(default=True, help_text="Controls visibility on the front-end market")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Chamber Directories"
        ordering = ['state', 'name']

    def __str__(self):
        return f"[{self.state}] {self.name}"


class ChamberLead(models.Model):
    """Upgraded model holding high-fidelity scraped chamber leads nationwide."""
    # Relationship to the nationwide parent directory
    directory = models.ForeignKey(
        ChamberDirectory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='leads',
        help_text="The nationwide chamber asset this lead belongs to"
    )
    
    # Historical field for fallback/backward compatibility
    name = models.CharField(max_length=255, blank=True, null=True)
    
    # New high-fidelity granular name tracking fields
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    
    # Historical short identifier field (e.g., 'MACOC Chamber')
    chamber = models.CharField(max_length=255, blank=True, null=True)
    # New structural organization tracking field (e.g., 'Metro Atlanta Chamber')
    organization = models.CharField(max_length=255, blank=True, null=True)
    
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    extension = models.CharField(max_length=10, blank=True, null=True)
    avatar_url = models.URLField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def temporary_username(self):
        """Safe alternative if you ever need an on-the-fly username tracking property."""
        return None

    def __str__(self):
        display_name = f"{self.first_name} {self.last_name}".strip() or self.name or "Unknown Lead"
        display_org = self.organization or self.chamber or (self.directory.name if self.directory else "Unknown Chamber")
        return f"{display_name} - {display_org}"


class ChamberRequest(models.Model):
    """Tracks custom nationwide user data pipeline requests based on flexible tiered volume limits."""
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('scraping', 'Scraping In Progress'),
        ('completed', 'Completed & Live'),
        ('rejected', 'Unfeasible/Requires Refund'),
    ]

    VOLUME_CHOICES = [
        (1, 'Single Local Area / Chamber Target ($9.99)'),
        (5, 'Regional Bundle Package (Up to 5 Areas) ($49.00)'),
        (10, 'Expanded Regional Pack (Up to 10 Areas) ($99.00)'),
        (20, 'Enterprise Multi-Region / Full State (Custom Quote - $10/ch)'),
    ]

    user_email = models.EmailField()
    state = models.CharField(max_length=2, help_text="2-letter US state code (e.g., TX)")
    city_or_region = models.CharField(max_length=255, help_text="e.g., Austin, Round Rock, Buda")
    
    # Upgraded fields to TextField so users can safely input multi-target listings without character clip errors
    chamber_name = models.TextField(help_text="List the specific Chambers of Commerce (one per line or comma-separated)")
    chamber_url = models.TextField(help_text="Provide the direct links showing their public online membership directory index layout")
    
    # Volume metrics and cost-tracking anchors
    chambers_count = models.IntegerField(choices=VOLUME_CHOICES, default=1, help_text="The requested data batch sizing tier")
    estimated_cost = models.DecimalField(max_digits=6, decimal_places=2, default=9.99, help_text="Calculated transaction price or quote evaluation benchmark")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Request Tier ({self.get_chambers_count_display()}): [{self.state}] by {self.user_email} - Status: {self.get_status_display()}"


class Profile(models.Model):
    """Extends the built-in User model to track premium payment status."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_premium = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}'s Profile (Premium: {self.is_premium})"


# --- New Strict Purchase & Access Control Isolation System ---

class Order(models.Model):
    """
    Captures the snapshot of what a user wants to purchase BEFORE they go to Stripe.
    Can hold 1, 5, or any arbitrary number of directory items or leads.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    order_id = models.CharField(max_length=100, unique=True, help_text="Unique tracking ID passed to Stripe metadata")
    is_paid = models.BooleanField(default=False, db_index=True)
    amount_paid = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.order_id} - User: {self.user.username} - Paid: {self.is_paid}"


class OrderItem(models.Model):
    """Maps specific items requested inside a single checkout session."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    # Link to directories or individual leads depending on how you plan to chunk purchases
    directory = models.ForeignKey(ChamberDirectory, on_delete=models.CASCADE, null=True, blank=True)
    lead = models.ForeignKey(ChamberLead, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        item_name = self.directory.name if self.directory else (self.lead.email if self.lead else "Unknown Item")
        return f"Item for Order {self.order.order_id}: {item_name}"


class UserPurchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchases')
    directory = models.ForeignKey(ChamberDirectory, on_delete=models.CASCADE, null=True, blank=True)
    lead = models.ForeignKey(ChamberLead, on_delete=models.CASCADE, null=True, blank=True)
    purchased_at = models.DateTimeField(auto_now_add=True)
    stripe_session_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-purchased_at']
        constraints = [
            # Only enforces uniqueness for directory purchases if lead is null
            models.UniqueConstraint(
                fields=['user', 'directory'], 
                condition=models.Q(lead__isnull=True),
                name='unique_user_directory_purchase'
            ),
            # Only enforces uniqueness for individual lead purchases if directory is null
            models.UniqueConstraint(
                fields=['user', 'lead'], 
                condition=models.Q(directory__isnull=True),
                name='unique_user_lead_purchase'
            )
        ]

# --- Automatic Profile Creation Signals ---

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically creates a Profile instance whenever a new User is saved."""
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Ensures the profile is updated whenever the User object updates."""
    if hasattr(instance, 'profile'):
        instance.profile.save()