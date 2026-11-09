from django.db.models import Sum
from .models import OwnerKYC, Property, Complaint, ChangeRequest, Notification

def admin_portal_badges(request):
    """
    Globally provides live badge counts for the sidebar and topbar
    across all admin portal pages.
    """
    try:
        pending_kyc_count = OwnerKYC.objects.filter(status='PENDING').count()
        pending_properties_count = Property.objects.filter(status='PENDING').count()
        open_complaints_count = Complaint.objects.filter(status='OPEN').count()
        pending_changes_count = ChangeRequest.objects.filter(status='PENDING').count()
        
        unread_notifications_count = 0
        if request.user.is_authenticated:
            unread_notifications_count = Notification.objects.filter(
                recipient=request.user, 
                is_read=False
            ).count()
        if unread_notifications_count == 0:
            unread_notifications_count = Notification.objects.filter(is_read=False).count()

        return {
            'global_pending_kyc': pending_kyc_count,
            'global_pending_properties': pending_properties_count,
            'global_open_complaints': open_complaints_count,
            'global_pending_changes': pending_changes_count,
            'global_unread_notifications': unread_notifications_count,
        }
    except Exception:
        return {
            'global_pending_kyc': 0,
            'global_pending_properties': 0,
            'global_open_complaints': 0,
            'global_pending_changes': 0,
            'global_unread_notifications': 0,
        }
