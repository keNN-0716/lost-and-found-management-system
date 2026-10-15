from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    class Roles(models.TextChoices):
        MANAGEMENT = 'Management', 'Management'
        NORMAL_USER = 'Normal_User', 'Normal User'
    
    # Put the id_number directly into your CustomUser layout
    id_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.NORMAL_USER
    )
    
    def __str__(self):
        return f"{self.username} ({self.role})"
    
class LostItem(models.Model):
    item_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    date_lost = models.DateField()
    location_lost = models.CharField(max_length=100)
    image = models.ImageField(upload_to='lost_items/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
