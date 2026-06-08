from django.urls import path
from . import views

# Sets up the namespace 'blog:' for your templates
app_name = 'blog'

# This variable name must be exactly lowercase 'urlpatterns'
urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/create/', views.create_post, name='create_post'),
]