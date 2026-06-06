from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class ChamberLead(models.Model):
    """Upgraded model holding high-fidelity scraped chamber leads."""
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
        # Prioritize granular tracking strings, fall back to legacy name, default to placeholder
        display_name = f"{self.first_name} {self.last_name}".strip() or self.name or "Unknown Lead"
        display_org = self.organization or self.chamber or "Unknown Chamber"
        return f"{display_name} - {display_org}"


class Profile(models.Model):
    """Extends the built-in User model to track premium payment status."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_premium = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}'s Profile (Premium: {self.is_premium})"


# --- Automatic Profile Creation Signals ---

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically creates a Profile instance whenever a new User is saved."""
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Ensures the profile is updated whenever the User object updates."""
    # Wrapped in a safe check to prevent race conditions during test fixture loading
    if hasattr(instance, 'profile'):
        instance.profile.save()