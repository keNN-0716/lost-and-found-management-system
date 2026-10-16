from django.contrib.auth.backends import ModelBackend
from .models import CustomUser

class IDNumberAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, id_number=None, password=None, **kwargs):
        # 1. If a regular username is passed (like logging into Django Admin), authenticate normally
        if username is not None and password is not None:
            user = CustomUser.objects.filter(username=username).first()
            if user is not None and user.check_password(password) and self.user_can_authenticate(user):
                return user

        # 2. If an id_number is passed (from your custom public login form)
        # Prevent empty search queries from fetching multiple blank rows
        if id_number and password is not None:
            user = CustomUser.objects.filter(id_number=id_number).first()
            if user is not None and user.check_password(password) and self.user_can_authenticate(user):
                return user

        return None

    def get_user(self, user_id):
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None
