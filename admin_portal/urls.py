from django.urls import path
from . import views

app_name = 'admin_portal'

urlpatterns = [
    path('', views.marketplace_overview, name='marketplace_overview_root'),
    path('dashboard/', views.marketplace_overview, name='marketplace_overview'),
    path('owner-verification/', views.owner_verification, name='owner_verification'),
    path('property-verification/', views.property_verification, name='property_verification'),
    path('listing-management/', views.listing_management, name='listing_management'),
    path('user-management/', views.user_management, name='user_management'),
    path('reports-complaints/', views.reports_complaints, name='reports_complaints'),
    path('change-requests/', views.change_requests, name='change_requests'),
    path('location-management/', views.location_management, name='location_management'),
    path('amenities-management/', views.amenities_management, name='amenities_management'),
    path('monetization/', views.monetization, name='monetization'),
    path('review-moderation/', views.review_moderation, name='review_moderation'),
    path('support-center/', views.support_center, name='support_center'),
    path('notifications/', views.notifications, name='notifications'),
    path('analytics/', views.marketplace_analytics, name='marketplace_analytics'),
    path('audit-logs/', views.audit_logs, name='audit_logs'),
    path('staff-settings/', views.staff_settings, name='staff_settings'),
    path('api/search/', views.global_search, name='global_search'),
    path('api/owner-verification/action/', views.owner_verification_action, name='owner_verification_action'),
    path('api/property-verification/action/', views.property_verification_action, name='property_verification_action'),
    # Listing Management APIs
    path('api/listing/toggle/', views.api_listing_toggle_status, name='listing_toggle_status'),
    path('api/listing/save/', views.api_listing_save, name='listing_save'),
    path('api/listing/delete/', views.api_listing_delete, name='listing_delete'),
    path('api/listing/bulk/', views.api_listing_bulk_action, name='listing_bulk_action'),
    path('api/listing/export/', views.api_listings_export_csv, name='listing_export_csv'),
    # User Management APIs
    path('api/user/toggle-status/', views.api_user_toggle_status, name='user_toggle_status'),
    path('api/user/reset-password/', views.api_user_reset_password, name='user_reset_password'),
    path('api/user/save/', views.api_user_save, name='user_save'),
    path('api/user/export/', views.api_users_export_csv, name='user_export_csv'),
    # Reports & Complaints APIs
    path('api/complaint/action/', views.api_complaint_action, name='complaint_action'),
    path('api/complaint/export/', views.api_complaint_export_csv, name='complaint_export_csv'),
    # Change Requests APIs
    path('api/change-request/action/', views.api_change_request_action, name='change_request_action'),
    path('api/change-request/export/', views.api_change_request_export_csv, name='change_request_export_csv'),
    # Location Management APIs
    path('api/location/get-city/', views.api_location_get_city, name='location_get_city'),
    path('api/location/save-city/', views.api_location_save_city, name='location_save_city'),
    path('api/location/save-locality/', views.api_location_save_locality, name='location_save_locality'),
    path('api/location/save-landmark/', views.api_location_save_landmark, name='location_save_landmark'),
    path('api/location/toggle-status/', views.api_location_toggle_status, name='location_toggle_status'),
    path('api/location/export/', views.api_location_export_csv, name='location_export_csv'),
    # Amenities Management APIs
    path('api/amenity/get/', views.api_amenity_get, name='amenity_get'),
    path('api/amenity/save/', views.api_amenity_save, name='amenity_save'),
    path('api/amenity/add/', views.api_amenity_add, name='amenity_add'),
    path('api/amenity/toggle-status/', views.api_amenity_toggle_status, name='amenity_toggle_status'),
    path('api/amenity/export/', views.api_amenity_export_csv, name='amenity_export_csv'),
    # Monetization APIs
    path('api/monetization/get-transaction/', views.api_monetization_get_transaction, name='monetization_get_transaction'),
    path('api/monetization/refund/', views.api_monetization_refund, name='monetization_refund'),
    path('api/monetization/record-payment/', views.api_monetization_record_payment, name='monetization_record_payment'),
    path('api/monetization/export/', views.api_monetization_export_csv, name='monetization_export_csv'),
    # Review Moderation APIs
    path('api/review/get-detail/', views.api_review_get_detail, name='review_get_detail'),
    path('api/review/action/', views.api_review_action, name='review_action'),
    path('api/review/export/', views.api_review_export_csv, name='review_export_csv'),
    # Support Center APIs
    path('api/support/get-ticket/', views.api_support_get_ticket, name='support_get_ticket'),
    path('api/support/reply/', views.api_support_send_reply, name='support_send_reply'),
    path('api/support/update/', views.api_support_update_ticket, name='support_update_ticket'),
    path('api/support/create/', views.api_support_create_ticket, name='support_create_ticket'),
    path('api/support/export/', views.api_support_export_csv, name='support_export_csv'),
    # Notifications APIs
    path('api/notifications/create/', views.api_notification_create_announcement, name='notification_create_announcement'),
    path('api/notifications/test-send/', views.api_notification_test_send, name='notification_test_send'),
    path('api/notifications/action/', views.api_notification_action, name='notification_action'),
    path('api/notifications/export/', views.api_notification_export_csv, name='notification_export_csv'),
    # Marketplace Analytics APIs
    path('api/analytics/export/', views.api_analytics_export_csv, name='analytics_export_csv'),
    # Audit Logs APIs
    path('api/audit-logs/get-event/', views.api_audit_logs_get_event, name='audit_logs_get_event'),
    path('api/audit-logs/export/', views.api_audit_logs_export_csv, name='audit_logs_export_csv'),
    # Staff & Settings APIs
    path('api/staff/invite/', views.api_staff_invite, name='staff_invite'),
    path('api/staff/update-access/', views.api_staff_update_access, name='staff_update_access'),
    path('api/staff/toggle-setting/', views.api_staff_toggle_setting, name='staff_toggle_setting'),
    path('api/staff/save-workspace/', views.api_staff_save_workspace, name='staff_save_workspace'),
]