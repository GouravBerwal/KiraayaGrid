from django.contrib import admin
from .models import (
    City, Locality, Amenity, OwnerKYC, Property, 
    Listing, Complaint, ChangeRequest, Transaction, 
    Review, SupportTicket, Notification, AuditLog
)

# Register your models here.

admin.site.register(City)
admin.site.register(Locality)
admin.site.register(Amenity)
admin.site.register(OwnerKYC)
admin.site.register(Property)
admin.site.register(Listing)
admin.site.register(Complaint)
admin.site.register(ChangeRequest)
admin.site.register(Transaction)
admin.site.register(Review)
admin.site.register(SupportTicket)
admin.site.register(Notification)
admin.site.register(AuditLog)