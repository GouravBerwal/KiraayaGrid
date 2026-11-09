from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

class User(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('OWNER', 'Owner'),
        ('TENANT', 'Tenant'),
    )
    ADMIN_SUB_ROLE_CHOICES = (
        ('SUPER_ADMIN', 'Super Admin'),
        ('VERIFICATION_STAFF', 'Verification Staff'),
        ('SUPPORT_STAFF', 'Support Staff'),
        ('FINANCE_STAFF', 'Finance Staff'),
    )

    phone_number = models.CharField(max_length=15, unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='TENANT')
    admin_sub_role = models.CharField(max_length=30, choices=ADMIN_SUB_ROLE_CHOICES, null=True, blank=True)
    is_verified_owner = models.BooleanField(default=False)
    avatar_url = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_user'  # Yeh hamare MySQL Workbench wali table se jodega

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"