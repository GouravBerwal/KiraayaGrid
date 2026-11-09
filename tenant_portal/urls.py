from django.urls import path
from . import views

app_name = 'tenant_portal'

urlpatterns = [
    # 8. Tenant Overview / Dashboard
    path('', views.tenant_overview, name='overview'),
    path('dashboard/', views.tenant_overview, name='dashboard'),

    # 9. Find Accommodation (Full property search & filters)
    path('find/', views.find_accommodation, name='find_accommodation'),

    # 10. Saved Properties (Shortlist)
    path('saved/', views.saved_properties, name='saved_properties'),
    path('saved/toggle/<int:property_id>/', views.toggle_saved_property, name='toggle_saved_property'),

    # 11. My Enquiries
    path('enquiries/', views.my_enquiries, name='my_enquiries'),

    # 12. Enquiry Details & Chat
    path('enquiries/<int:enquiry_id>/', views.enquiry_details, name='enquiry_details'),

    # 13. Visit Requests
    path('visits/', views.visit_requests, name='visit_requests'),

    # 14. Visit Details
    path('visits/<str:request_id>/', views.visit_details, name='visit_details'),

    # 15. My Bookings / Rental Requests
    path('bookings/', views.my_bookings, name='my_bookings'),

    # 16. Notifications Center
    path('notifications/', views.notifications_center, name='notifications'),

    # 17. Profile & Preferences
    path('profile/', views.profile_preferences, name='profile_preferences'),

    # 18. Help & Support
    path('support/', views.help_support, name='help_support'),

    # 19. Account & Privacy Settings
    path('settings/', views.account_settings, name='account_settings'),

    # Dynamic API Endpoints for Dashboard Interactions
    path('api/property/<int:property_id>/', views.api_property_details, name='api_property_details'),
    path('api/quick-enquiry/', views.api_quick_enquiry, name='api_quick_enquiry'),
    path('api/quick-visit/', views.api_quick_visit, name='api_quick_visit'),
    path('api/switch-city/', views.api_switch_city, name='api_switch_city'),
    path('api/enquiry/close/<int:enquiry_id>/', views.api_close_enquiry, name='api_close_enquiry'),
    path('api/enquiry/<int:enquiry_id>/message/', views.api_send_enquiry_message, name='api_send_enquiry_message'),
    path('api/enquiry/<int:enquiry_id>/reopen/', views.api_reopen_enquiry, name='api_reopen_enquiry'),
    path('api/visit/accept/<str:request_id>/', views.api_accept_visit_time, name='api_accept_visit_time'),
    path('api/visit/reschedule/<str:request_id>/', views.api_reschedule_visit, name='api_reschedule_visit'),
    path('api/visit/cancel/<str:request_id>/', views.api_cancel_visit, name='api_cancel_visit'),

    # Booking APIs (Page 15)
    path('api/booking/cancel/<str:booking_id>/', views.api_cancel_booking, name='api_cancel_booking'),
    path('api/booking/pay-token/<str:booking_id>/', views.api_pay_booking_token, name='api_pay_booking_token'),
    path('api/booking/create/', views.api_create_booking, name='api_create_booking'),

    # Notification APIs (Page 16)
    path('api/notification/mark-read/<int:notification_id>/', views.api_mark_notification_read, name='api_mark_notification_read'),
    path('api/notification/mark-all-read/', views.api_mark_all_notifications_read, name='api_mark_all_notifications_read'),
    path('api/notification/delete/<int:notification_id>/', views.api_delete_notification, name='api_delete_notification'),

    # Profile & Preferences APIs (Page 17)
    path('api/city-localities/<int:city_id>/', views.api_city_localities, name='api_city_localities'),

    # Support APIs (Page 18)
    path('api/support/ticket/create/', views.api_create_support_ticket, name='api_create_support_ticket'),
    path('api/support/ticket/<int:ticket_id>/messages/', views.api_ticket_messages, name='api_ticket_messages'),
    path('api/support/ticket/<int:ticket_id>/reply/', views.api_reply_support_ticket, name='api_reply_support_ticket'),

    # Settings & Account Security APIs (Page 19)
    path('api/settings/password/', views.api_update_password, name='api_update_password'),
    path('api/settings/notifications/', views.api_update_notification_settings, name='api_update_notification_settings'),
    path('api/settings/privacy/', views.api_update_privacy_settings, name='api_update_privacy_settings'),
    path('api/settings/export-data/', views.api_export_personal_data, name='api_export_personal_data'),
    path('api/settings/delete-account/', views.api_delete_account, name='api_delete_account'),
    path('logout/', views.tenant_logout, name='logout'),
]
