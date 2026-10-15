from django.urls import path
from . import views

urlpatterns = [
    path('', views.lost_and_found, name='lost_and_found'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('lost_items/', views.lost_items, name='lost_items'),   
    path('found_items/', views.found_items, name='found_items'),
    path('search_results/', views.search_results, name='search_results'),
]