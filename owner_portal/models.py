from django.db import models
from django.conf import settings
from admin_portal.models import Property, City, Locality


class Room(models.Model):
    ROOM_TYPE_CHOICES = [
        ('SINGLE', 'Private / Single'),
        ('DOUBLE', 'Double Sharing'),
        ('TRIPLE', 'Triple Sharing'),
        ('FOUR_SHARING', 'Four Sharing'),
        ('DORM', 'Dormitory'),
    ]
    BATHROOM_CHOICES = [
        ('ATTACHED', 'Attached Bathroom'),
        ('SHARED', 'Shared Bathroom'),
    ]
    AC_CHOICES = [
        ('AC', 'Air Conditioned (AC)'),
        ('NON_AC', 'Non-AC'),
    ]

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=50)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPE_CHOICES, default='SINGLE')
    max_occupancy = models.PositiveIntegerField(default=1)
    total_beds = models.PositiveIntegerField(default=1)
    occupied_beds = models.PositiveIntegerField(default=0)
    available_beds = models.PositiveIntegerField(default=1)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    bathroom_type = models.CharField(max_length=20, choices=BATHROOM_CHOICES, default='ATTACHED')
    ac_type = models.CharField(max_length=20, choices=AC_CHOICES, default='AC')
    furnishing = models.CharField(max_length=50, default='Fully Furnished')
    amenities = models.TextField(blank=True, default='')  # Comma separated amenities
    cover_photo = models.CharField(max_length=500, blank=True, null=True)
    available_from = models.DateField(null=True, blank=True, help_text="Date from which vacancy opens")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'owner_portal_room'
        ordering = ['room_number', 'id']

    def __str__(self):
        return f"{self.property.title} - Room {self.room_number} ({self.get_room_type_display()})"


class Bed(models.Model):
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available / Vacant'),
        ('OCCUPIED', 'Occupied'),
        ('RESERVED', 'Reserved'),
        ('MAINTENANCE', 'Under Maintenance'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='beds')
    bed_number = models.CharField(max_length=50)  # e.g. "Bed A", "Bed B"
    bed_position = models.CharField(max_length=50, default='Window Side')  # "Window Side", "Door Side", etc.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    tenant_name = models.CharField(max_length=150, blank=True, null=True)
    occupied_since = models.DateField(blank=True, null=True)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'owner_portal_bed'
        ordering = ['bed_number', 'id']

    def __str__(self):
        return f"{self.room.property.title} - {self.room.room_number} - {self.bed_number} ({self.status})"


class PropertyPhoto(models.Model):
    PHOTO_TYPE_CHOICES = [
        ('COVER', 'Cover Photo'),
        ('EXTERIOR', 'Exterior Building'),
        ('BEDROOM', 'Bedroom'),
        ('BATHROOM', 'Bathroom'),
        ('KITCHEN', 'Kitchen & Dining'),
        ('COMMON', 'Common Lounge & Terrace'),
    ]

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='gallery_photos')
    photo_url = models.CharField(max_length=500)
    photo_type = models.CharField(max_length=20, choices=PHOTO_TYPE_CHOICES, default='BEDROOM')
    caption = models.CharField(max_length=150, blank=True, null=True)
    is_cover = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'owner_portal_propertyphoto'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.property.title} - {self.photo_type} ({self.photo_url[:30]})"


class Enquiry(models.Model):
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('CONTACTED', 'Contacted'),
        ('INTERESTED', 'Interested'),
        ('VISIT_REQUESTED', 'Visit Requested'),
        ('CONVERTED', 'Converted'),
        ('CLOSED', 'Closed'),
    ]

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='owner_enquiries')
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='enquiries')
    seeker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_enquiries')
    seeker_name = models.CharField(max_length=150)
    seeker_phone = models.CharField(max_length=20)
    seeker_email = models.CharField(max_length=150, blank=True, null=True)
    interested_room_type = models.CharField(max_length=50, default='Single Room')
    budget = models.DecimalField(max_digits=10, decimal_places=2, default=15000.00)
    preferred_move_in = models.DateField(null=True, blank=True)
    message = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'owner_portal_enquiry'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.seeker_name} -> {self.property.title} ({self.status})"


class EnquiryMessage(models.Model):
    SENDER_CHOICES = [
        ('OWNER', 'Owner'),
        ('SEEKER', 'Seeker'),
        ('SYSTEM', 'System Alert'),
    ]

    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name='messages')
    sender_type = models.CharField(max_length=20, choices=SENDER_CHOICES, default='OWNER')
    message_text = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'owner_portal_enquirymessage'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender_type}: {self.message_text[:30]}"


class VisitRequest(models.Model):
    TYPE_CHOICES = [
        ('VISIT', 'Property Visit'),
        ('BOOKING', 'Room Booking Request'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('RESCHEDULED', 'Rescheduled'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('REJECTED', 'Rejected'),
    ]

    request_id = models.CharField(max_length=30, unique=True)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='visit_requests')
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='visits')
    seeker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='tenant_visits')
    seeker_name = models.CharField(max_length=150)
    seeker_phone = models.CharField(max_length=20)
    seeker_email = models.CharField(max_length=150, blank=True, null=True)
    request_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='VISIT')
    scheduled_date = models.DateField()
    scheduled_time_slot = models.CharField(max_length=50, default='11:00 AM - 12:00 PM')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True, default='')
    owner_reply = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'owner_portal_visitrequest'
        ordering = ['-scheduled_date', '-created_at']

    def __str__(self):
        return f"{self.request_id} - {self.seeker_name} ({self.status})"


class DraftListing(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='draft_listings')
    current_step = models.PositiveIntegerField(default=1)  # 1 to 15
    title = models.CharField(max_length=255, default='Untitled Property Draft')
    property_type = models.CharField(max_length=50, blank=True, default='')
    form_data = models.TextField(default='{}')  # JSON serialized data
    is_submitted = models.BooleanField(default=False)
    submitted_property = models.ForeignKey(Property, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'owner_portal_draftlisting'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.owner.username} - {self.title} (Step {self.current_step})"


class OwnerSubscription(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owner_subscription')
    plan_name = models.CharField(max_length=50, default='Standard Free')
    is_active = models.BooleanField(default=True)
    valid_until = models.DateField(null=True, blank=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    featured_listings_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'owner_portal_subscription'

    def __str__(self):
        return f"{self.owner.username} - {self.plan_name}"


class Invoice(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.CharField(max_length=50, unique=True)
    plan_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, default='PAID')
    billing_date = models.DateField()
    invoice_pdf_url = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'owner_portal_invoice'
        ordering = ['-billing_date']

    def __str__(self):
        return f"{self.invoice_number} - ₹{self.amount} ({self.status})"


class PropertyMetadata(models.Model):
    property = models.OneToOneField(Property, on_delete=models.CASCADE, related_name='meta_details')
    description = models.TextField(blank=True, default='')
    furnishing = models.CharField(max_length=50, default='Fully Furnished')
    property_condition = models.CharField(max_length=50, default='Brand New / Excellent')
    total_floors = models.PositiveIntegerField(default=4)
    built_up_area = models.CharField(max_length=50, default='6,500 sq.ft.')
    has_lift = models.BooleanField(default=True)
    power_backup = models.CharField(max_length=100, default='24/7 Full DG Backup')
    water_supply = models.CharField(max_length=100, default='Corporation & Borewell (24/7)')
    amenities = models.TextField(blank=True, default='')  # Comma-separated names or tags
    rules_visitors = models.CharField(max_length=150, default='Visitors allowed in lounge (10:00 AM - 8:00 PM)')
    rules_smoking = models.BooleanField(default=False)
    rules_quiet_hours = models.CharField(max_length=100, default='11:00 PM - 7:00 AM')
    rules_pets = models.BooleanField(default=False)
    rules_notice_period = models.CharField(max_length=50, default='30 Days')
    rules_minimum_stay = models.CharField(max_length=50, default='3 Months')
    move_in_immediate = models.BooleanField(default=True)
    visiting_hours = models.CharField(max_length=100, default='10:00 AM – 7:00 PM (All days)')
    electricity_charges = models.CharField(max_length=150, default='Included up to ₹1,000 / room')
    maintenance_charges = models.CharField(max_length=150, default='₹0 (Included in Rent)')
    food_charges = models.CharField(max_length=150, default='₹3,500 / month (Optional 3-time meals)')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'owner_portal_propertymetadata'

    def __str__(self):
        return f"Metadata for {self.property.title}"

