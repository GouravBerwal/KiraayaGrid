"""
URL configuration for Grahvia project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from public_portal import views as public_views

urlpatterns = [
    path('robots.txt', public_views.robots_txt, name='robots_txt'),
    path('sitemap.xml', public_views.sitemap_xml, name='sitemap_xml'),
    path('django-admin/', admin.site.urls),
    path('admin/', include('admin_portal.urls')),
    path('dashboard/', RedirectView.as_view(url='/admin/', permanent=False)),
    path('admin_portal/', RedirectView.as_view(url='/admin/', permanent=False)),
    path('admin-portal/', RedirectView.as_view(url='/admin/', permanent=False)),
    path('api/', include('admin_portal.api_urls')),
    path('owner/', include('owner_portal.urls')),
    path('tenant/', include('tenant_portal.urls')),
    path('', include('public_portal.urls')),
]
