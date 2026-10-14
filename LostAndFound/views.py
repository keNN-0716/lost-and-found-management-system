from django.shortcuts import render

# Create your views here.
def lost_and_found(request):
    return render(request, 'lost_and_found.html')
def lost_items(request):
    return render(request, 'lost_items.html')
def found_items(request):
    return render(request, 'found_items.html')