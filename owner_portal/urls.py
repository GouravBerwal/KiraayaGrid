from django.urls import path
from . import views

app_name = 'owner_portal'

urlpatterns = [
    # Part 1: Owner Dashboard & Management
    path('', views.owner_dashboard, name='dashboard'),
    path('dashboard/', views.owner_dashboard, name='dashboard_alt'),
    path('properties/', views.my_properties, name='my_properties'),
    path('properties/<int:property_id>/', views.manage_property, name='manage_property'),
    path('properties/<int:property_id>/rooms/', views.room_bed_management, name='room_bed_management'),
    path('properties/<int:property_id>/status-action/', views.property_status_action, name='property_status_action'),
    path('drafts/<int:draft_id>/delete/', views.delete_draft_action, name='delete_draft_action'),
    path('rooms/', views.all_rooms_management, name='all_rooms'),
    path('enquiries/', views.enquiries_list, name='enquiries'),
    path('enquiries/<int:enquiry_id>/', views.enquiry_details, name='enquiry_details'),
    path('booking-requests/', views.booking_requests, name='booking_requests'),
    path('booking-requests/<int:request_id>/', views.booking_request_details, name='booking_request_details'),
    path('pricing-availability/', views.pricing_availability, name='pricing_availability'),
    path('reviews/', views.reviews_ratings, name='reviews'),
    path('subscription/', views.subscription_billing, name='subscription'),
    path('subscription/invoice/<int:invoice_id>/', views.view_invoice_receipt, name='view_invoice_receipt'),
    path('support/', views.help_support, name='support'),
    path('support/ticket/<int:ticket_id>/', views.ticket_detail_api, name='ticket_detail_api'),
    path('notifications/', views.notifications, name='notifications'),
    path('settings/', views.profile_settings, name='profile_settings'),

    # Part 2: 15-Step Add Property Listing Flow
    path('properties/add/', views.add_property_wizard, name='add_property'),
    path('properties/add/step/<int:step>/', views.add_property_step, name='add_property_step'),
    path('properties/add/save-draft/', views.save_listing_draft_api, name='save_draft_api'),
]
