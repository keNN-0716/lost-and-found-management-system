from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .forms import CustomLoginForm, CustomSignupForm
# Cleaned up unnecessary imports (Removed UserCreationForm and duplicate forms import)

# Sign up page for lost and found
def signup_view(request):
    if request.method == 'POST':
        form = CustomSignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()  # Triggers the profile row creation in DB
            
            # FIXED: Explicitly specify your custom ID backend for session consistency
            login(request, user, backend='LostAndFound.backends.IDNumberAuthBackend') 
            return redirect('lost_and_found')
    else:
        form = CustomSignupForm()
        
    return render(request, 'signup.html', {'form': form})

# Login page for lost and found
def login_view(request):
    error_message = None
    
    if request.method == 'POST':
        form = CustomLoginForm(request.POST)
        if form.is_valid():
            id_number = form.cleaned_data.get('id_number')
            password = form.cleaned_data.get('password')
            user = authenticate(request, id_number=id_number, password=password)
            
            if user is not None:
                login(request, user)
                return redirect('lost_and_found')
            else:
                error_message = 'Invalid ID number or password.'
    else:
        form = CustomLoginForm()
        
    return render(request, 'login.html', {
        'form': form, 
        'error_message': error_message
    })

# Logout page for lost and found
@csrf_exempt  # Added to allow POST requests without CSRF token for logout
def logout_view(request):
    logout(request)
    return redirect('login')
# Home page for lost and found
@login_required
def lost_and_found(request):
    return render(request, 'lost_and_found.html')

# Lost items page
@login_required # Pro-Tip: Added protection so non-logged-in users can't view these pages
def lost_items(request):
    return render(request, 'lost_items.html')

# Found items page
@login_required # Pro-Tip: Added protection here too
def found_items(request):
    return render(request, 'found_items.html')
