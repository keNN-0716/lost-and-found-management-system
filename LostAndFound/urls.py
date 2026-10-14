from django.urls import path
from . import views

urlpatterns = [
    path('', views.lost_and_found, name='lost_and_found'),
    path('lost_items/', views.lost_items, name='lost_items'),
    path('found_items/', views.found_items, name='found_items'),
]