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
        label='ID number',
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. 2024-00123',
            'autocomplete': 'username',
        })
    )
    password = forms.CharField(
        label='Password',
        required=True,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Your password',
            'autocomplete': 'current-password',
        })
    )


class CustomSignupForm(UserCreationForm):
    # Users log in with their ID number, so it must be collected at signup
    id_number = forms.CharField(
        label='ID number',
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Your college ID number',
            'autocomplete': 'off',
        })
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = UserCreationForm.Meta.fields + ('id_number',)

    field_order = ['username', 'id_number', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'placeholder': 'Choose a username',
            'autocomplete': 'username',
        })
        self.fields['password1'].widget.attrs.update({
            'placeholder': 'Create a password',
            'autocomplete': 'new-password',
        })
        self.fields['password2'].widget.attrs.update({
            'placeholder': 'Repeat your password',
            'autocomplete': 'new-password',
        })


class LostItemForm(forms.ModelForm):
    class Meta:
        model = LostItem
        fields = ['name', 'description', 'date_lost', 'location_lost', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Black Leather Wallet'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe the item — color, size, distinguishing features…'}),
            'date_lost': forms.DateInput(attrs={'type': 'date'}),
            'location_lost': forms.TextInput(attrs={'placeholder': 'e.g. Building A, Room 102'}),
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            validate_image(image)
        return image


class FoundItemForm(forms.ModelForm):
    class Meta:
        model = FoundItem
        fields = ['name', 'description', 'date_found', 'location_found', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Blue Umbrella'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe the item — color, size, distinguishing features…'}),
            'date_found': forms.DateInput(attrs={'type': 'date'}),
            'location_found': forms.TextInput(attrs={'placeholder': 'e.g. Library entrance'}),
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            validate_image(image)
        return image