from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from .models import UserProfile

User = get_user_model()

class IDNumberAuthBackend(ModelBackend):
    def authenticate(self, request, id_number=None, password=None, **kwargs):
        if not id_number or not password:
            return None
        
        try:
            profile = UserProfile.objects.select_related('user').get(id_number=id_number)
            user = profile.user
            
            if user.check_password(password):
                return user
        except ObjectDoesNotExist:
            return None
        
        return None