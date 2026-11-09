from django.db import models
from django.conf import settings
from admin_portal.models import Property, City, Locality
from owner_portal.models import Room, Bed


class TenantProfile(models.Model):
    ACCOMMODATION_CHOICES = [
        ('ALL', 'All Types'),
        ('PG', 'Paying Guest (PG)'),
        ('HOSTEL', 'Student Hostel'),
        ('PRIVATE_ROOM', 'Private Room'),
        ('SHARED_ROOM', 'Shared Room'),
        ('FLAT', 'Independent Flat'),
        ('CO_LIVING', 'Co-living Space'),
    ]

    OCCUPANCY_CHOICES = [
        ('ANY', 'Any Occupancy'),
        ('SINGLE', 'Single Occupancy'),
        ('DOUBLE', 'Double Sharing'),
        ('TRIPLE', 'Triple Sharing'),
    ]

    FOOD_CHOICES = [
        ('ANY', 'No Food Preference'),
        ('VEG', 'Pure Vegetarian'),
        ('NON_VEG', 'Non-Vegetarian'),
        ('JAIN', 'Jain Food Available'),
        ('SELF_COOK', 'Self Cooking'),
    ]

    GENDER_CHOICES = [
        ('ANY', 'Any Gender / Unisex'),
        ('MALE', 'Male Only'),
        ('FEMALE', 'Female Only'),
    ]

    PROFESSION_CHOICES = [
        ('STUDENT', 'College Student'),
        ('WORKING_PROFESSIONAL', 'Working Professional'),
        ('FREELANCER', 'Freelancer / Remote'),
        ('OTHER', 'Other'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tenant_profile')
    preferred_city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True, related_name='preferred_tenants')
    preferred_locality = models.ForeignKey(Locality, on_delete=models.SET_NULL, null=True, blank=True, related_name='preferred_tenants')
    monthly_budget = models.DecimalField(max_digits=10, decimal_places=2, default=20000.00)
    min_budget = models.DecimalField(max_digits=10, decimal_places=2, default=5000.00)
    preferred_accommodation_type = models.CharField(max_length=30, default='ALL', choices=ACCOMMODATION_CHOICES)
    occupancy_preference = models.CharField(max_length=20, default='ANY', choices=OCCUPANCY_CHOICES)
    target_move_in_date = models.DateField(null=True, blank=True)
    food_preference = models.CharField(max_length=20, default='ANY', choices=FOOD_CHOICES)
    gender_preference = models.CharField(max_length=10, default='ANY', choices=GENDER_CHOICES)
    profession = models.CharField(max_length=30, default='WORKING_PROFESSIONAL', choices=PROFESSION_CHOICES)
    company_or_college = models.CharField(max_length=150, blank=True, default='')
    bio = models.TextField(blank=True, default='')

    # Alert Channels
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=True)
    whatsapp_notifications = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_portal_tenantprofile'
        verbose_name = 'Tenant Profile'
        verbose_name_plural = 'Tenant Profiles'

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.preferred_city or 'Unset City'})"


class SavedProperty(models.Model):
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_properties')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='favorited_by_tenants')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tenant_portal_savedproperty'
        unique_together = ('tenant', 'property')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tenant.username} ❤️ {self.property.title}"


class RecentlyViewedProperty(models.Model):
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recently_viewed_properties')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='viewed_by_tenants')
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_portal_recentlyviewedproperty'
        unique_together = ('tenant', 'property')
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.tenant.username} viewed {self.property.title}"


class RentalBooking(models.Model):
    BOOKING_STATUS_CHOICES = [
        ('REQUESTED', 'Requested / Awaiting Host'),
        ('ACCEPTED', 'Accepted by Owner'),
        ('PAYMENT_PENDING', 'Payment Pending'),
        ('CONFIRMED', 'Confirmed & Booked'),
        ('CANCELLED', 'Cancelled by Tenant'),
        ('REJECTED', 'Rejected by Owner'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('NOT_REQUIRED', 'No Payment Due Yet'),
        ('PENDING', 'Payment Pending'),
        ('PAID', 'Payment Received'),
        ('REFUNDED', 'Refunded'),
        ('FAILED', 'Failed'),
    ]

    booking_id = models.CharField(max_length=30, unique=True)
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tenant_bookings')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_bookings')
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='room_bookings')
    bed = models.ForeignKey(Bed, on_delete=models.SET_NULL, null=True, blank=True, related_name='bed_bookings')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_bookings')
    move_in_date = models.DateField()
    sharing_type = models.CharField(max_length=50, default='Twin Sharing')
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    booking_status = models.CharField(max_length=30, choices=BOOKING_STATUS_CHOICES, default='REQUESTED')
    payment_status = models.CharField(max_length=30, choices=PAYMENT_STATUS_CHOICES, default='NOT_REQUIRED')
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_reference = models.CharField(max_length=100, blank=True, default='')
    tenant_notes = models.TextField(blank=True, default='')
    owner_reply = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_portal_rentalbooking'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.booking_id} - {self.tenant.username} @ {self.property.title} ({self.booking_status})"
