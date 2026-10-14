from django.urls import path
from . import views

urlpatterns = [
    path('', views.lost_and_found, name='lost_and_found'),
]