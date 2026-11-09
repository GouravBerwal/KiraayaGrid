from django.urls import path
from . import views

urlpatterns = [
    path('search/', views.global_search, name='global_search'),
    path('owner-verification/action/', views.owner_verification_action, name='owner_verification_action'),
    path('property-verification/action/', views.property_verification_action, name='property_verification_action'),
    # Listing Management APIs
    path('listing/toggle/', views.api_listing_toggle_status, name='listing_toggle_status'),
    path('listing/save/', views.api_listing_save, name='listing_save'),
    path('listing/delete/', views.api_listing_delete, name='listing_delete'),
    path('listing/bulk/', views.api_listing_bulk_action, name='listing_bulk_action'),
    path('listing/export/', views.api_listings_export_csv, name='listing_export_csv'),
    # User Management APIs
    path('user/toggle-status/', views.api_user_toggle_status, name='user_toggle_status'),
    path('user/reset-password/', views.api_user_reset_password, name='user_reset_password'),
    path('user/save/', views.api_user_save, name='user_save'),
    path('user/export/', views.api_users_export_csv, name='user_export_csv'),
    # Reports & Complaints APIs
    path('complaint/action/', views.api_complaint_action, name='complaint_action'),
    path('complaint/export/', views.api_complaint_export_csv, name='complaint_export_csv'),
    # Change Requests APIs
    path('change-request/action/', views.api_change_request_action, name='change_request_action'),
    path('change-request/export/', views.api_change_request_export_csv, name='change_request_export_csv'),
    # Location Management APIs
    path('location/get-city/', views.api_location_get_city, name='location_get_city'),
    path('location/save-city/', views.api_location_save_city, name='location_save_city'),
    path('location/save-locality/', views.api_location_save_locality, name='location_save_locality'),
    path('location/save-landmark/', views.api_location_save_landmark, name='location_save_landmark'),
    path('location/toggle-status/', views.api_location_toggle_status, name='location_toggle_status'),
    path('location/export/', views.api_location_export_csv, name='location_export_csv'),
    # Amenities Management APIs
    path('amenity/get/', views.api_amenity_get, name='amenity_get'),
    path('amenity/save/', views.api_amenity_save, name='amenity_save'),
    path('amenity/add/', views.api_amenity_add, name='amenity_add'),
    path('amenity/toggle-status/', views.api_amenity_toggle_status, name='amenity_toggle_status'),
    path('amenity/export/', views.api_amenity_export_csv, name='amenity_export_csv'),
    # Monetization APIs
    path('monetization/get-transaction/', views.api_monetization_get_transaction, name='monetization_get_transaction'),
    path('monetization/refund/', views.api_monetization_refund, name='monetization_refund'),
    path('monetization/record-payment/', views.api_monetization_record_payment, name='monetization_record_payment'),
    path('monetization/export/', views.api_monetization_export_csv, name='monetization_export_csv'),
    # Review Moderation APIs
    path('review/get-detail/', views.api_review_get_detail, name='review_get_detail'),
    path('review/action/', views.api_review_action, name='review_action'),
    path('review/export/', views.api_review_export_csv, name='review_export_csv'),
    # Support Center APIs
    path('support/get-ticket/', views.api_support_get_ticket, name='support_get_ticket'),
    path('support/reply/', views.api_support_send_reply, name='support_send_reply'),
    path('support/update/', views.api_support_update_ticket, name='support_update_ticket'),
    path('support/create/', views.api_support_create_ticket, name='support_create_ticket'),
    path('support/export/', views.api_support_export_csv, name='support_export_csv'),
    # Notifications APIs
    path('notifications/create/', views.api_notification_create_announcement, name='notification_create_announcement'),
    path('notifications/test-send/', views.api_notification_test_send, name='notification_test_send'),
    path('notifications/action/', views.api_notification_action, name='notification_action'),
    path('notifications/export/', views.api_notification_export_csv, name='notification_export_csv'),
    # Marketplace Analytics APIs
    path('analytics/export/', views.api_analytics_export_csv, name='analytics_export_csv'),
    # Audit Logs APIs
    path('audit-logs/get-event/', views.api_audit_logs_get_event, name='audit_logs_get_event'),
    path('audit-logs/export/', views.api_audit_logs_export_csv, name='audit_logs_export_csv'),
    # Staff & Settings APIs
    path('staff/invite/', views.api_staff_invite, name='staff_invite'),
    path('staff/update-access/', views.api_staff_update_access, name='staff_update_access'),
    path('staff/toggle-setting/', views.api_staff_toggle_setting, name='staff_toggle_setting'),
    path('staff/save-workspace/', views.api_staff_save_workspace, name='staff_save_workspace'),
]
