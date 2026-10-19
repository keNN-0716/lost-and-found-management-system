# LostAndFound/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dynamic Router Pattern
    path('login_redirect/', views.login_redirect_view, name='login_redirect'),
    
    # Target Roles Landing Paths
    path('lost_and_found/', views.lost_and_found, name='lost_and_found'),
    path('user_home_page/', views.user_home_page, name='user_home_page'),
    
    # Other items paths
    path('lost_items/', views.lost_items, name='lost_items'),
    path('found_items/', views.found_items, name='found_items'),
    path('search/', views.search_results, name='search_results'),
    path('heatmap/', views.heatmap, name='heatmap'),

    # Claim / resolve workflow
    path('claim/<str:item_type>/<int:item_id>/', views.claim_item, name='claim_item'),
    path('resolve/<str:item_type>/<int:item_id>/', views.resolve_item, name='resolve_item'),
]
