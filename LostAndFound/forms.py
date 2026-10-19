from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, LostItem, FoundItem

# Upload limits for item images
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']


def validate_image(image):
    """Shared server-side validation for item image uploads."""
    if image.size > MAX_IMAGE_SIZE:
        raise forms.ValidationError('Image must be 5 MB or smaller.')
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise forms.ValidationError('Only JPEG, PNG, GIF, or WebP images are allowed.')
    return image


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
    # Users log in with their ID number, so it must be collected at signup
    id_number = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your college/school ID number'})
    )

    class Meta(UserCreationForm.Meta):
        # 1. Point the form explicitly to your CustomUser model
        model = CustomUser

        # 2. Add your custom field to the registration form fields
        fields = UserCreationForm.Meta.fields + ('id_number',)


class LostItemForm(forms.ModelForm):
    class Meta:
        model = LostItem
        fields = ['name', 'description', 'date_lost', 'location_lost', 'image', 'latitude', 'longitude']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'date_lost': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'location_lost': forms.TextInput(attrs={'class': 'form-input'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            validate_image(image)
        return image


class FoundItemForm(forms.ModelForm):
    class Meta:
        model = FoundItem
        fields = ['name', 'description', 'date_found', 'location_found', 'image', 'latitude', 'longitude']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'date_found': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'location_found': forms.TextInput(attrs={'class': 'form-input'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            validate_image(image)
        return image