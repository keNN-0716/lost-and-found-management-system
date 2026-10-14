from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required

# Create your views here.
#Sign up page for lost and found
def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save() 
            login(request, user)
            return redirect('lost_and_found')
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})
# Login page for lost and found
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('lost_and_found')
        else:
            return render(request, 'login.html', {'error': 'Invalid username or password'})
    else:
        return render(request, 'login.html')
# Logout page for lost and found
def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return redirect('login')
    return redirect('lost_and_found')
#Home page for lost and found
@login_required
def lost_and_found(request):
    return render(request, 'lost_and_found.html')
#Lost items page
def lost_items(request):
    return render(request, 'lost_items.html')
#Found items page
def found_items(request):
    return render(request, 'found_items.html')