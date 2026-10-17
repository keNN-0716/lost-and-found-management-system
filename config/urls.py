# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from LostAndFound import views

urlpatterns = [
    path('', views.login_view, name='login_root'),
    path('admin/', admin.site.urls),
    path('', include('LostAndFound.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
