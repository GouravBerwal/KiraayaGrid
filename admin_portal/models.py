from django.db import models
from django.conf import settings
builtin_property = property

# Create your models here.

# -------------------------------------------------------------
# 1. Location Models (Cities & Localities)
# -------------------------------------------------------------
class City(models.Model):
    name = models.CharField(max_length=100, unique=True)
    state = models.CharField(max_length=100)
    tier = models.CharField(
        max_length=10, 
        choices=[('TIER_1', 'Tier 1'), ('TIER_2', 'Tier 2'), ('TIER_3', 'Tier 3')], 
        default='TIER_1'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_portal_city'

    def __str__(self):
        return f"{self.name}, {self.state}"


class Locality(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='localities')
    name = models.CharField(max_length=150)
    pincode = models.CharField(max_length=10)
    popular_hub_type = models.CharField(
        max_length=20,
        choices=[
            ('IT_HUB', 'IT Hub'),
            ('COLLEGE_CAMPUS', 'College Campus'),
            ('COACHING_HUB', 'Coaching Hub'),
            ('RESIDENTIAL', 'Residential')
        ],
        default='RESIDENTIAL'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_portal_locality'

    def __str__(self):
        return f"{self.name} ({self.pincode}) - {self.city.name}"


class Landmark(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='landmarks')
    locality = models.ForeignKey(Locality, on_delete=models.SET_NULL, null=True, blank=True, related_name='landmarks')
    name = models.CharField(max_length=200)
    category = models.CharField(
        max_length=20,
        choices=[
            ('COLLEGE', 'College'),
            ('UNIVERSITY', 'University'),
            ('WORKPLACE', 'Workplace / Tech Park')
        ],
        default='COLLEGE'
    )
    nearby_listings_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_portal_landmark'

    def __str__(self):
        return f"{self.name} ({self.category}) - {self.city.name}"


# -------------------------------------------------------------
# 2. Amenities Model
# -------------------------------------------------------------
class Amenity(models.Model):
    CATEGORY_CHOICES = [
        ('CONNECTIVITY', 'Connectivity'),
        ('ESSENTIALS', 'Essentials'),
        ('SAFETY', 'Safety'),
        ('SERVICES', 'Services'),
        ('LIFESTYLE', 'Lifestyle'),
        ('FOOD', 'Food'),
        ('CONVENIENCE', 'Convenience'),
        ('BASIC', 'Basic'),
    ]
    VERIFICATION_CHOICES = [
        ('OWNER_DECLARED', 'Owner declared'),
        ('PHOTO_REQUIRED', 'Photo required'),
        ('INVOICE_REQUIRED', 'Invoice required'),
        ('MENU_REQUIRED', 'Menu required'),
        ('PHYSICAL_INSPECTION', 'Physical inspection'),
    ]

    code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='ESSENTIALS')
    icon_name = models.CharField(max_length=100, default='check-circle')
    applicable_property_types = models.CharField(max_length=150, default='All property types')
    verification_type = models.CharField(max_length=50, choices=VERIFICATION_CHOICES, default='OWNER_DECLARED')
    used_in_listings = models.IntegerField(default=0)
    sort_order = models.IntegerField(default=1)
    available_to_owners = models.BooleanField(default=True)
    show_as_filter = models.BooleanField(default=True)
    require_evidence = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_portal_amenity'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.code or 'AMN'} - {self.name}"

    @property
    def formatted_used_in_listings(self):
        return f"{self.used_in_listings:,}"

    @property
    def category_badge_class(self):
        cat_map = {
            'CONNECTIVITY': 'cat-blue',
            'ESSENTIALS': 'cat-indigo',
            'SAFETY': 'cat-teal',
            'SERVICES': 'cat-amber',
            'LIFESTYLE': 'cat-purple',
        }
        return cat_map.get(self.category, 'cat-blue')

    @property
    def avatar_initial(self):
        words = self.name.split()
        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()
        return self.name[:2].upper() if len(self.name) >= 2 else self.name.upper()


# -------------------------------------------------------------
# 3. Owner KYC Model
# -------------------------------------------------------------
class OwnerKYC(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kyc_documents')
    document_type = models.CharField(
        max_length=20,
        choices=[
            ('AADHAAR', 'Aadhaar Card'),
            ('PAN', 'PAN Card'),
            ('PASSPORT', 'Passport'),
            ('VOTER_ID', 'Voter ID')
        ]
    )
    document_number = models.CharField(max_length=50)
    document_file_url = models.CharField(max_length=500)
    status = models.CharField(
        max_length=20,
        choices=[('PENDING', 'Pending'), ('VERIFIED', 'Verified'), ('REJECTED', 'Rejected')],
        default='PENDING'
    )
    rejection_reason = models.TextField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='reviewed_kycs'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_portal_ownerkyc'

    def __str__(self):
        return f"{self.user.username} - {self.document_type} ({self.status})"


# -------------------------------------------------------------
# 4. Property Model
# -------------------------------------------------------------
class Property(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='properties')
    title = models.CharField(max_length=255)
    property_type = models.CharField(
        max_length=20,
        choices=[('PG', 'PG'), ('HOSTEL', 'Hostel'), ('FLAT', 'Flat'), ('CO_LIVING', 'Co-Living')]
    )
    gender_category = models.CharField(
        max_length=10,
        choices=[('MALE', 'Boys / Male'), ('FEMALE', 'Girls / Female'), ('CO_ED', 'Co-ed / Anyone')],
        default='CO_ED'
    )
    address_line = models.TextField()
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name='properties')
    locality = models.ForeignKey(Locality, on_delete=models.PROTECT, related_name='properties')
    pincode = models.CharField(max_length=10)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    total_rooms = models.IntegerField(default=1)
    electricity_bill_url = models.CharField(max_length=500, null=True, blank=True)
    property_tax_url = models.CharField(max_length=500, null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=[
            ('PENDING', 'Pending'),
            ('APPROVED', 'Approved'),
            ('CHANGES_REQUESTED', 'Changes Requested'),
            ('REJECTED', 'Rejected'),
            ('PAUSED', 'Paused'),
            ('ARCHIVED', 'Archived')
        ],
        default='PENDING'
    )
    rejection_reason = models.TextField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='verified_properties'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_portal_property'

    def __str__(self):
        return f"{self.title} ({self.get_property_type_display()}) - {self.city.name}"


# -------------------------------------------------------------
# 5. Listing Model
# -------------------------------------------------------------
class Listing(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='listings')
    title = models.CharField(max_length=255)
    room_sharing_type = models.CharField(
        max_length=20,
        choices=[
            ('SINGLE', 'Single Room'),
            ('DOUBLE', 'Double Sharing'),
            ('TRIPLE', 'Triple Sharing'),
            ('FOUR_PLUS', '4+ Sharing')
        ]
    )
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    lock_in_period_months = models.IntegerField(default=1)
    available_beds = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_portal_listing'

    def __str__(self):
        return f"{self.title} - ₹{self.monthly_rent}/mo"


# -------------------------------------------------------------
# 6. Complaint Model
# -------------------------------------------------------------
class Complaint(models.Model):
    complaint_ticket = models.CharField(max_length=20, unique=True)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='filed_complaints')
    target_type = models.CharField(
        max_length=20,
        choices=[('PROPERTY', 'Property'), ('OWNER', 'Owner'), ('TENANT', 'Tenant'), ('LISTING', 'Listing')]
    )
    target_id = models.BigIntegerField()
    category = models.CharField(
        max_length=30,
        choices=[
            ('FAKE_LISTING', 'Fake Listing'),
            ('BROKERAGE_DEMAND', 'Brokerage Demand'),
            ('HYGIENE_MAINTENANCE', 'Hygiene / Maintenance'),
            ('HARASSMENT', 'Harassment'),
            ('DEPOSIT_REFUND', 'Deposit Refund Issue'),
            ('INCORRECT_PRICING', 'Incorrect Pricing'),
            ('MISLEADING_PHOTOS', 'Misleading Photos'),
            ('DUPLICATE_LISTING', 'Duplicate Listing')
        ]
    )
    description = models.TextField()
    evidence_url = models.CharField(max_length=500, null=True, blank=True)
    priority = models.CharField(
        max_length=10,
        choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High'), ('CRITICAL', 'Critical')],
        default='MEDIUM'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('OPEN', 'Open'),
            ('IN_INVESTIGATION', 'In Investigation'),
            ('RESOLVED', 'Resolved'),
            ('DISMISSED', 'Dismissed')
        ],
        default='OPEN'
    )
    resolution_notes = models.TextField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_complaints'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_portal_complaint'

    def __str__(self):
        return f"[{self.complaint_ticket}] {self.category} ({self.status})"


# -------------------------------------------------------------
# 7. Change Request Model
# -------------------------------------------------------------
class ChangeRequest(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='change_requests')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='requested_changes')
    field_name = models.CharField(max_length=100)
    old_value = models.TextField()
    new_value = models.TextField()
    reason = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('IN_REVIEW', 'In Review'),
            ('APPROVED', 'Approved'),
            ('REJECTED', 'Rejected')
        ],
        default='PENDING'
    )
    reviewer_note = models.TextField(null=True, blank=True)
    document_url = models.CharField(max_length=500, null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='reviewed_change_requests'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_portal_changerequest'

    def __str__(self):
        return f"CR for {self.property.title}: {self.field_name}"


# -------------------------------------------------------------
# 8. Transactions Model
# -------------------------------------------------------------
class Transaction(models.Model):
    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('PENDING', 'Pending'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded')
    ]
    PRODUCT_CHOICES = [
        ('SUBSCRIPTION', 'Subscription Plan'),
        ('FEATURED_LISTING', 'Featured Listing'),
        ('TENANT_CONTACT', 'Tenant Contacts'),
        ('OTHER', 'Other')
    ]

    txn_id = models.CharField(max_length=50, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    plan_name = models.CharField(max_length=100)
    product_type = models.CharField(max_length=50, choices=PRODUCT_CHOICES, default='SUBSCRIPTION')
    linked_property = models.ForeignKey('Property', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions', db_column='property_id')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment_method = models.CharField(max_length=50, default='UPI')
    invoice_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    gateway_ref = models.CharField(max_length=100, null=True, blank=True)
    refund_reason = models.TextField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_portal_transaction'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.txn_id} - ₹{self.amount} ({self.payment_status})"

    @property
    def formatted_amount(self):
        return f"{int(self.amount):,}" if self.amount == int(self.amount) else f"{self.amount:,.2f}"

    @property
    def total_with_gst(self):
        tot = float(self.amount) + float(self.gst_amount)
        return f"{int(tot):,}" if tot == int(tot) else f"{tot:,.2f}"

    @property
    def status_badge_class(self):
        m = {
            'SUCCESS': 'success',
            'PENDING': 'pending',
            'FAILED': 'danger',
            'REFUNDED': 'neutral'
        }
        return m.get(self.payment_status, 'neutral')

    @property
    def avatar_initial(self):
        if self.user:
            fn = (self.user.first_name or '').strip()
            ln = (self.user.last_name or '').strip()
            if fn and ln:
                return (fn[0] + ln[0]).upper()
            if fn:
                return fn[:2].upper()
            un = self.user.username or 'OW'
            return un[:2].upper()
        return 'TX'


# -------------------------------------------------------------
# 9. Review Moderation Model
# -------------------------------------------------------------
class Review(models.Model):
    STATUS_CHOICES = [
        ('REPORTED', 'Reported'),
        ('PENDING', 'Pending Moderation'),
        ('APPROVED', 'Published'),
        ('REJECTED', 'Removed'),
    ]
    REASON_CHOICES = [
        ('DISPUTED_CONTENT', 'Disputed content'),
        ('ABUSIVE_LANGUAGE', 'Abusive language'),
        ('POSSIBLE_SPAM', 'Possible spam'),
        ('PERSONAL_INFO', 'Personal information'),
        ('OFF_TOPIC', 'Off-topic review'),
    ]

    review_code = models.CharField(max_length=30, unique=True, null=True, blank=True)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(default=5)
    title = models.CharField(max_length=255, null=True, blank=True)
    comment = models.TextField()
    is_flagged = models.BooleanField(default=False)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='REPORTED')
    
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reported_reviews')
    report_reason = models.CharField(max_length=100, choices=REASON_CHOICES, null=True, blank=True)
    report_details = models.TextField(null=True, blank=True)
    reported_time_text = models.CharField(max_length=100, null=True, blank=True)
    stay_verification = models.CharField(max_length=100, default='Verified enquiry')
    
    decision_note = models.TextField(null=True, blank=True)
    moderated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderated_reviews')
    moderated_at = models.DateTimeField(null=True, blank=True)
    
    owner_reply = models.TextField(null=True, blank=True)
    owner_reply_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_portal_review'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.review_code or 'REV'} · {self.property.title} · {self.rating}★ by {self.user.username}"

    @builtin_property
    def reviewer_name(self):
        return self.user.get_full_name() or self.user.username

    @builtin_property
    def stars_display(self):
        return f"★ {self.rating} / 5"

    @builtin_property
    def avatar_initial(self):
        fn = (self.user.first_name or '').strip()
        ln = (self.user.last_name or '').strip()
        if fn and ln:
            return (fn[0] + ln[0]).upper()
        if fn:
            return fn[:2].upper()
        return self.user.username[:2].upper()

    @builtin_property
    def reason_tag_display(self):
        m = {
            'DISPUTED_CONTENT': '! Disputed content',
            'ABUSIVE_LANGUAGE': '! Abusive language',
            'POSSIBLE_SPAM': '◔ Possible spam',
            'PERSONAL_INFO': '◔ Personal information',
            'OFF_TOPIC': '◔ Off-topic review',
        }
        return m.get(self.report_reason, self.report_reason or 'Flagged')

    @builtin_property
    def tag_class(self):
        if self.report_reason in ['DISPUTED_CONTENT', 'ABUSIVE_LANGUAGE']:
            return 'tag-warning'
        return 'tag-review'


# -------------------------------------------------------------
# 10. Support Ticket & Message Models
# -------------------------------------------------------------
class SupportTicket(models.Model):
    ticket_code = models.CharField(max_length=30, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=255)
    category = models.CharField(max_length=50, default='General')
    channel = models.CharField(max_length=30, default='Email') # Email, Platform, Phone, WhatsApp
    message = models.TextField(null=True, blank=True)
    priority = models.CharField(
        max_length=20,
        default='MEDIUM'
    )
    status = models.CharField(
        max_length=30,
        default='OPEN'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_tickets'
    )
    sla_due_text = models.CharField(max_length=100, null=True, blank=True)
    sla_status = models.CharField(max_length=30, default='WITHIN_SLA')
    related_transaction = models.ForeignKey(
        'Transaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_tickets'
    )
    related_property = models.ForeignKey(
        'Property',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_tickets'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_portal_supportticket'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.ticket_code}] {self.subject}"

    @property
    def priority_badge_class(self):
        p = (self.priority or '').upper()
        if p in ['URGENT', 'HIGH']:
            return 'priority-high'
        if p in ['MEDIUM', 'NORMAL']:
            return 'priority-medium'
        return 'priority-low'

    @property
    def status_badge_class(self):
        s = (self.status or '').upper()
        if s == 'OPEN':
            return 'status-open'
        if s == 'IN_PROGRESS':
            return 'status-progress'
        if s == 'AWAITING_REPLY':
            return 'status-awaiting'
        if s == 'RESOLVED':
            return 'status-resolved'
        return 'status-closed'

    @property
    def tag_display(self):
        s = (self.status or '').upper()
        if self.sla_due_text:
            return self.sla_due_text
        if s == 'OPEN':
            return '◔ Open'
        if s == 'IN_PROGRESS':
            return '↻ In progress'
        if s == 'AWAITING_REPLY':
            return '↻ Awaiting reply'
        if s == 'RESOLVED':
            return '✓ Resolved'
        return '✕ Closed'


class TicketMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    sender_name = models.CharField(max_length=150)
    sender_role = models.CharField(max_length=50, default='User') # 'Owner', 'Tenant', 'Support Agent', 'Internal note'
    is_internal = models.BooleanField(default=False)
    message = models.TextField()
    attachment_name = models.CharField(max_length=255, null=True, blank=True)
    attachment_size = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_portal_ticketmessage'
        ordering = ['created_at']

    def __str__(self):
        return f"Message by {self.sender_name} on {self.ticket.ticket_code}"



# -------------------------------------------------------------
# 11. Notification & Announcement Model
# -------------------------------------------------------------
class Notification(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sent_notifications'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='received_notifications'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    channel = models.CharField(
        max_length=100,
        default='IN_APP'
    )
    is_broadcast = models.BooleanField(default=False)
    audience_type = models.CharField(max_length=50, default='ALL_USERS') # ALL_OWNERS, VERIFIED_OWNERS, ALL_TENANTS, ALL_USERS, LOCATION_SPECIFIC, SPECIFIC_USER
    target_city = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=30, default='SENT') # SENT, SCHEDULED, DRAFT, FAILED
    button_label = models.CharField(max_length=100, null=True, blank=True)
    button_url = models.CharField(max_length=255, null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    recipients_count = models.IntegerField(default=1)
    delivered_count = models.IntegerField(default=1)
    opened_count = models.IntegerField(default=0)
    clicked_count = models.IntegerField(default=0)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_portal_notification'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def channel_list(self):
        ch = self.channel or ''
        parts = [p.strip() for p in ch.replace(';', ',').split(',') if p.strip()]
        return parts if parts else ['Platform']

    @property
    def audience_display(self):
        if self.target_city:
            return f"{self.target_city} {self.get_audience_name()}"
        return self.get_audience_name()

    def get_audience_name(self):
        m = {
            'ALL_OWNERS': 'All property owners',
            'VERIFIED_OWNERS': 'Verified owners',
            'ALL_TENANTS': 'Active tenants',
            'ALL_USERS': 'All registered users',
            'UNVERIFIED_OWNERS': 'Unverified owners',
            'SPECIFIC_USER': f"User: {self.recipient.username}" if self.recipient else 'Direct recipient',
        }
        return m.get(self.audience_type, self.audience_type or 'All users')

    @property
    def status_badge_class(self):
        s = (self.status or '').upper()
        if s == 'SCHEDULED':
            return 'status-scheduled'
        if s == 'SENT':
            return 'status-sent'
        if s == 'DRAFT':
            return 'status-draft'
        return 'status-failed'



# -------------------------------------------------------------
# 12. Audit Log Model
# -------------------------------------------------------------
class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='audit_logs'
    )
    action_type = models.CharField(max_length=100)
    target_entity = models.CharField(max_length=100)
    target_id = models.BigIntegerField(null=True, blank=True)
    module = models.CharField(max_length=100, default='', blank=True)
    status = models.CharField(max_length=50, default='SUCCESS', blank=True)
    ip_address = models.CharField(max_length=45, null=True, blank=True)
    details = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_portal_auditlog'

    def __str__(self):
        return f"{self.action_type} on {self.target_entity} by {self.actor}"


# -------------------------------------------------------------
# 13. Platform Settings Model
# -------------------------------------------------------------
class PlatformSettings(models.Model):
    workspace_name = models.CharField(max_length=200, default='KiraayaGrid India')
    support_email = models.EmailField(default='support@kiraayagrid.in')
    support_phone = models.CharField(max_length=30, default='+91 80 4567 8900', blank=True)
    timezone = models.CharField(max_length=100, default='Asia/Kolkata')
    currency = models.CharField(max_length=10, default='INR')
    require_2fa = models.BooleanField(default=True)
    dual_approval = models.BooleanField(default=True)
    auto_session_timeout = models.BooleanField(default=True)
    ip_whitelist_enabled = models.BooleanField(default=False)
    allowed_ips = models.TextField(blank=True, null=True, default='103.21.58.0/24, 192.168.1.0/24')
    auto_approve_verified_owners = models.BooleanField(default=False)
    price_change_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    min_photos_required = models.IntegerField(default=3)
    kyc_mandatory = models.BooleanField(default=True)
    auto_escalate_hours = models.IntegerField(default=48)
    sla_threshold_hours = models.IntegerField(default=24)
    default_commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    razorpay_key_id = models.CharField(max_length=100, default='rzp_live_9aK8x2LpQ', blank=True)
    msg91_sender_id = models.CharField(max_length=20, default='ROOMST', blank=True)
    smtp_from_email = models.CharField(max_length=254, default='notifications@kiraayagrid.in', blank=True)
    google_maps_key = models.CharField(max_length=100, default='AIzaSyB8xQ2_LiveKey', blank=True)
    last_policy_updated_by = models.CharField(max_length=100, default='Ananya Shah')
    last_policy_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_portal_platformsettings'

    def __str__(self):
        return f"Settings for {self.workspace_name}"