from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .forms import CustomLoginForm, CustomSignupForm
from django.db.models import Q
from .models import LostItem

# Search backend for lost and found
def search_results(request):
    query = request.GET.get('q', '').strip() # Clean trailing spaces
    results = []
    
    if query:
        results = LostItem.objects.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query) | 
            Q(location_lost__icontains=query)
        ).order_by('-created_at')
        
    return render(request, 'search_results.html', {'results': results, 'query': query})
# Sign up page for lost and found
def signup_view(request):
    if request.method == 'POST':
        form = CustomSignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()  # Triggers the profile row creation in DB
            
            # FIXED: Explicitly specify your custom ID backend for session consistency 
            return redirect('login')  # Redirect to login page after successful signup
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
# Lost items page for lost and found
@login_required
def lost_items(request):
    # 1. Handle Form Submission (Manager uploads an item)
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        date_lost = request.POST.get('date_lost')
        location_lost = request.POST.get('location_lost')
        image = request.FILES.get('image')  # Handle image upload
        
        # Save the new item to the database
        LostItem.objects.create(
            name=name,
            description=description,
            date_lost=date_lost,
            location_lost=location_lost,
            image=image  # Save the uploaded image
        )
        # Redirect back to the same page to prevent double-submitting on refresh
        return redirect('lost_items') 

    # 2. Handle Page Display (Fetch items from newest to oldest)
    lost_items = LostItem.objects.all().order_by('-created_at')
    
    return render(request, 'lost_items.html', {'lost_items': lost_items})
# Home page for lost and found
@login_required
def lost_and_found(request):
    return render(request, 'lost_and_found.html')

# Found items page
@login_required # Pro-Tip: Added protection here too
def found_items(request):
    return render(request, 'found_items.html')
