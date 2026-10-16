from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .forms import CustomLoginForm, CustomSignupForm, LostItemForm, FoundItemForm
from .models import LostItem, FoundItem, ItemStatus
from .decorators import management_required


def is_management(user):
    """Helper: True if the user is staff or has the Management role."""
    return user.is_staff or getattr(user, 'role', None) == 'Management'


# Search backend for lost and found
@login_required
def search_results(request):
    query = request.GET.get('q', '').strip()  # Clean trailing spaces
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
            form.save()
            return redirect('login')
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

                return redirect('login_redirect')
            else:
                error_message = 'Invalid ID number or password.'
    else:
        form = CustomLoginForm()

    return render(request, 'login.html', {'form': form, 'error_message': error_message})


@login_required
def login_redirect_view(request):
    if is_management(request.user):
        return redirect('lost_and_found')
    else:
        return redirect('user_home_page')


# Logout page for lost and found
def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('login')


# Lost items page for lost and found
@login_required
def lost_items(request):
    # 1. Handle Form Submission (Manager uploads an item)
    if request.method == 'POST':
        form = LostItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.reported_by = request.user
            item.save()
            messages.success(request, f'"{item.name}" has been reported.')
            # Redirect back to the same page to prevent double-submitting on refresh
            return redirect('lost_items')
    else:
        form = LostItemForm()

    # 2. Handle Page Display (Fetch items from newest to oldest)
    lost_items = LostItem.objects.all().order_by('-created_at')

    return render(request, 'lost_items.html', {
        'lost_items': lost_items,
        'form': form,
        'is_management': is_management(request.user),
    })


# Home page for lost and found
@login_required
@management_required
def lost_and_found(request):
    # Role protection is enforced by the management_required decorator
    return render(request, 'lost_and_found.html')


# Found items page
@login_required
def found_items(request):
    # Handle Form Submission (a user reports a found item)
    if request.method == 'POST':
        form = FoundItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.reported_by = request.user
            item.save()
            messages.success(request, f'"{item.name}" has been reported as found.')
            return redirect('found_items')
    else:
        form = FoundItemForm()

    found_items = FoundItem.objects.all().order_by('-created_at')

    return render(request, 'found_items.html', {
        'found_items': found_items,
        'form': form,
        'is_management': is_management(request.user),
    })


# Claim an item (lost or found) - marks it as Claimed under this user
@login_required
def claim_item(request, item_type, item_id):
    if request.method != 'POST':
        return redirect('user_home_page')

    model = {'lost': LostItem, 'found': FoundItem}.get(item_type)
    if model is None:
        return HttpResponseForbidden('Unknown item type.')

    item = get_object_or_404(model, item_id=item_id)

    if item.status == ItemStatus.OPEN:
        item.status = ItemStatus.CLAIMED
        item.claimed_by = request.user
        item.save()
        messages.success(request, f'You claimed "{item.name}". Management will verify your request.')
    else:
        messages.error(request, f'"{item.name}" is no longer available to claim.')

    return redirect('found_items' if item_type == 'found' else 'lost_items')


# Resolve a claimed item (management only) - marks it as returned/handed over
@login_required
@management_required
def resolve_item(request, item_type, item_id):
    if request.method != 'POST':
        model = {'lost': LostItem, 'found': FoundItem}.get(item_type)
        if model is None:
            return redirect('user_home_page')
        return redirect('found_items' if item_type == 'found' else 'lost_items')

    model = {'lost': LostItem, 'found': FoundItem}.get(item_type)
    if model is None:
        return HttpResponseForbidden('Unknown item type.')

    item = get_object_or_404(model, item_id=item_id)

    if item.status == ItemStatus.CLAIMED:
        item.status = ItemStatus.RESOLVED
        item.save()
        messages.success(request, f'"{item.name}" has been marked as resolved.')
    else:
        messages.error(request, f'Only claimed items can be resolved ("{item.name}" is {item.status}).')

    return redirect('found_items' if item_type == 'found' else 'lost_items')


# Home page for normal users
@login_required
def user_home_page(request):
    my_lost_reports = LostItem.objects.filter(reported_by=request.user).order_by('-created_at')
    my_found_reports = FoundItem.objects.filter(reported_by=request.user).order_by('-created_at')
    my_claims = list(
        LostItem.objects.filter(claimed_by=request.user).order_by('-created_at')
    ) + list(
        FoundItem.objects.filter(claimed_by=request.user).order_by('-created_at')
    )

    return render(request, 'user_home_page.html', {
        'my_lost_reports': my_lost_reports,
        'my_found_reports': my_found_reports,
        'my_claims': my_claims,
        'is_management': is_management(request.user),
    })