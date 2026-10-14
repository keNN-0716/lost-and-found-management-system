from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# --- Your model definition ---
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    id_number = models.CharField(max_length=20, unique=True, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


# --- Your Safe Signal (No internal imports!) ---
@receiver(post_save, sender=User)
def create_or_save_user_profile(sender, instance, created, **kwargs):
    if created:
        # We do not import UserProfile here, we just use it directly!
        UserProfile.objects.get_or_create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()