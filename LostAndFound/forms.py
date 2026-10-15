from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm 
from .models import CustomUser 

class CustomLoginForm(forms.Form):
    id_number = forms.CharField(
        max_length=20, 
        required=True, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Enter your ID number'})
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'})
    )

class CustomSignupForm(UserCreationForm):

    class Meta(UserCreationForm.Meta):
        # 1. Point the form explicitly to your CustomUser model
        model = CustomUser
        
        # 2. Add your custom field to the registration form fields
        fields = UserCreationForm.Meta.fields