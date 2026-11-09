from django.urls import path
from . import views

app_name = 'public_portal'

urlpatterns = [
    # 1. Public Home & Landing Page (1:1 Figma Match)
    path('', views.home_landing, name='home'),

    # 2. About Us & Founder Spotlight Page
    path('about/', views.about_founder, name='about'),

    # 3. Public Explore Stays / Property Search (Max 5 Pagination)
    path('stays/', views.explore_stays, name='explore_stays'),

    # 4. Public Property Details View
    path('stay/<int:property_id>/', views.stay_details, name='stay_details'),

    # 5. Public Dedicated "List Your Property" Landing Page for Landlords
    path('list-property/', views.list_property_landing, name='list_property'),

    # 6. Public Locations & Neighborhoods Explorer
    path('locations/', views.locations_overview, name='locations'),

    # 7. Apple-grade Auth Suite (Login, Signup, Role Routing, Demo Auto-Login)
    path('login/', views.user_login, name='login'),
    path('signup/', views.user_signup, name='signup'),
    path('logout/', views.user_logout, name='logout'),
    path('auth/demo-login/<str:role_type>/', views.demo_quick_login, name='demo_quick_login'),

    # Auth APIs (Live Username Suggestions, Checking, OTP Mobile & Email)
    path('auth/api/suggest-usernames/', views.api_suggest_usernames, name='api_suggest_usernames'),
    path('auth/api/check-username/', views.api_check_username, name='api_check_username'),
    path('auth/api/send-signup-otp/', views.api_send_signup_otp, name='api_send_signup_otp'),
    path('auth/api/verify-signup-otp/', views.api_verify_signup_otp, name='api_verify_signup_otp'),
    path('auth/api/resend-signup-otp/', views.api_resend_signup_otp, name='api_resend_signup_otp'),

    # 8. Live Search API
    path('api/search-suggestions/', views.api_search_suggestions, name='search_suggestions'),
]
