from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User

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

class CustomSignupForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Create a password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm your password'}))

    class Meta:
        model = User
        fields = ['username', 'email']  # ID number is completely hidden here

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data