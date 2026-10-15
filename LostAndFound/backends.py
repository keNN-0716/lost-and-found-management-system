from django.contrib.auth.backends import ModelBackend
from .models import CustomUser

class IDNumberAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, id_number=None, password=None, **kwargs):
        # 1. If a regular username is passed (like logging into Django Admin), authenticate normally
        if username is not None:
            try:
                user = CustomUser.objects.get(username=username)
                if user.check_password(password):
                    return user
            except CustomUser.DoesNotExist:
                return None

        # 2. If an id_number is passed (from your custom public login form)
        if id_number is not None:
            # Prevent empty search queries from fetching multiple blank rows
            if not id_number: 
                return None
            try:
                user = CustomUser.objects.get(id_number=id_number)
                if user.check_password(password):
                    return user
            except CustomUser.DoesNotExist:
                return None
                
        return None

    def get_user(self, user_id):
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None
