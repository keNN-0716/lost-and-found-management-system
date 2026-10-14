from django.shortcuts import render

# Create your views here.
def lost_and_found(request):
    return render(request, 'lost_and_found.html')
