import os
import sys
sys.path.insert(0, '/Users/gurjar/Desktop/RoomSetu/Grahvia')
import django
import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Grahvia.settings')
django.setup()

from django.contrib.auth import get_user_model
from admin_portal.models import Property, City, Locality, Notification
from owner_portal.models import Room, Bed, PropertyPhoto, Enquiry, EnquiryMessage, VisitRequest
from tenant_portal.models import TenantProfile, SavedProperty, RecentlyViewedProperty, RentalBooking

User = get_user_model()

def seed_tenant_portal_data():
    print("=== SEEDING TENANT PORTAL DATA ===")

    # 1. Fetch or create Tenant: Aarav Sharma
    aarav, created = User.objects.get_or_create(
        username='aarav_sharma',
        defaults={
            'first_name': 'Aarav',
            'last_name': 'Sharma',
            'email': 'aarav.sharma@gmail.com',
            'phone_number': '+91 98765 43210',
            'role': 'TENANT'
        }
    )
    aarav.first_name = 'Aarav'
    aarav.last_name = 'Sharma'
    aarav.email = 'aarav.sharma@gmail.com'
    aarav.phone_number = '+91 98765 43210'
    aarav.role = 'TENANT'
    aarav.set_password('aarav123')
    aarav.save()
    print(f"Tenant User: {aarav.username} (ID: {aarav.id}, Name: {aarav.get_full_name()})")

    # 2. Fetch Owner: Arjun Mehta
    arjun = User.objects.filter(username='arjun_mehta').first()
    if not arjun:
        print("Warning: arjun_mehta not found, using first owner")
        arjun = User.objects.filter(role='OWNER').first()

    # 3. Fetch Bengaluru Localities
    bengaluru = City.objects.filter(name__icontains='Bengaluru').first()
    loc_indiranagar = Locality.objects.filter(city=bengaluru, name__icontains='Indiranagar').first()
    loc_hsr = Locality.objects.filter(city=bengaluru, name__icontains='HSR Layout').first()
    loc_koramangala = Locality.objects.filter(city=bengaluru, name__icontains='Koramangala').first()

    # 4. Synchronize 3 Bengaluru Properties matching Figma
    # Property 1: The Palm House (Indiranagar)
    prop_palm = Property.objects.filter(id=34).first()
    if not prop_palm:
        prop_palm = Property.objects.filter(title__icontains='Palm House').first()
    if not prop_palm:
        prop_palm = Property.objects.create(
            owner=arjun,
            city=bengaluru,
            locality=loc_indiranagar,
            title='The Palm House',
            property_type='PG',
            verification_status='VERIFIED',
            address='14, 12th Main Road, HAL 2nd Stage, Indiranagar, Bengaluru - 560038'
        )
    else:
        prop_palm.title = 'The Palm House'
        prop_palm.property_type = 'PG'
        prop_palm.locality = loc_indiranagar
        prop_palm.verification_status = 'VERIFIED'
        prop_palm.save()

    # Property 2: Olive Co-living (HSR Layout)
    prop_olive = Property.objects.filter(id=35).first()
    if not prop_olive:
        prop_olive = Property.objects.filter(title__icontains='Olive Co-living').first()
    if not prop_olive:
        prop_olive = Property.objects.create(
            owner=arjun,
            city=bengaluru,
            locality=loc_hsr,
            title='Olive Co-living',
            property_type='CO_LIVING',
            verification_status='VERIFIED',
            address='42, Sector 1, 14th Main, HSR Layout, Bengaluru - 560102'
        )
    else:
        prop_olive.title = 'Olive Co-living'
        prop_olive.property_type = 'CO_LIVING'
        prop_olive.locality = loc_hsr
        prop_olive.verification_status = 'VERIFIED'
        prop_olive.save()

    # Property 3: Aster Residences (Koramangala)
    prop_aster = Property.objects.filter(id=33).first()
    if not prop_aster:
        prop_aster = Property.objects.filter(title__icontains='Aster Residences').first()
    if not prop_aster:
        prop_aster = Property.objects.create(
            owner=arjun,
            city=bengaluru,
            locality=loc_koramangala,
            title='Aster Residences',
            property_type='FLAT',
            verification_status='VERIFIED',
            address='88, 5th Block, 1st Cross, Koramangala, Bengaluru - 560034'
        )
    else:
        prop_aster.title = 'Aster Residences'
        prop_aster.property_type = 'FLAT'
        prop_aster.locality = loc_koramangala
        prop_aster.verification_status = 'VERIFIED'
        prop_aster.save()

    print(f"Properties aligned: Palm={prop_palm.id}, Olive={prop_olive.id}, Aster={prop_aster.id}")

    # Set photos for these 3 properties
    photos_data = [
        (prop_palm, 'https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=1000&auto=format&fit=crop&q=80', 'Bedroom with work desk', True),
        (prop_palm, 'https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=1000&auto=format&fit=crop&q=80', 'Common lounge', False),
        (prop_olive, 'https://images.unsplash.com/photo-1598928506311-c55ded91a20c?w=1000&auto=format&fit=crop&q=80', 'Twin sharing bedroom', True),
        (prop_olive, 'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=1000&auto=format&fit=crop&q=80', 'Dining & kitchen', False),
        (prop_aster, 'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=1000&auto=format&fit=crop&q=80', 'Chic studio living space', True),
        (prop_aster, 'https://images.unsplash.com/photo-1584622650111-993a426fbf0a?w=1000&auto=format&fit=crop&q=80', 'Modular kitchenette', False),
    ]
    for p, url, caption, is_cov in photos_data:
        photo, _ = PropertyPhoto.objects.get_or_create(
            property=p,
            photo_url=url,
            defaults={'caption': caption, 'is_cover': is_cov}
        )
        if is_cov:
            photo.is_cover = True
            photo.save()

    # 5. Seed TenantProfile for Aarav Sharma
    profile, _ = TenantProfile.objects.get_or_create(
        user=aarav,
        defaults={
            'preferred_city': bengaluru,
            'preferred_locality': loc_indiranagar,
            'monthly_budget': 20000.00,
            'min_budget': 8000.00,
            'preferred_accommodation_type': 'ALL',
            'occupancy_preference': 'SINGLE',
            'target_move_in_date': datetime.date(2026, 12, 1),
            'food_preference': 'ANY',
            'gender_preference': 'ANY',
            'profession': 'WORKING_PROFESSIONAL',
            'company_or_college': 'TechCorp Solutions',
            'bio': 'Software Engineer at TechCorp. Looking for a clean, quiet stay near Indiranagar/HSR Layout.',
            'email_notifications': True,
            'sms_notifications': True,
            'whatsapp_notifications': True,
        }
    )
    profile.preferred_city = bengaluru
    profile.preferred_locality = loc_indiranagar
    profile.monthly_budget = 20000.00
    profile.save()
    print("TenantProfile verified.")

    # 6. Seed Saved Properties for Aarav (Olive Co-living & The Palm House)
    SavedProperty.objects.get_or_create(tenant=aarav, property=prop_olive, defaults={'notes': 'Liked the twin sharing room and gym facility'})
    SavedProperty.objects.get_or_create(tenant=aarav, property=prop_palm, defaults={'notes': 'Private room in Indiranagar near metro'})
    print(f"Saved properties for Aarav: {SavedProperty.objects.filter(tenant=aarav).count()}")

    # 7. Seed Recently Viewed Properties for Aarav (The Palm House & Aster Residences)
    RecentlyViewedProperty.objects.get_or_create(tenant=aarav, property=prop_palm)
    RecentlyViewedProperty.objects.get_or_create(tenant=aarav, property=prop_aster)
    print(f"Recently viewed properties for Aarav: {RecentlyViewedProperty.objects.filter(tenant=aarav).count()}")

    # 8. Seed Enquiries for Aarav
    # Enquiry 1: The Palm House (Status: CONTACTED, "Reply received")
    enq_palm, _ = Enquiry.objects.get_or_create(
        property=prop_palm,
        seeker=aarav,
        defaults={
            'seeker_name': aarav.get_full_name(),
            'seeker_phone': aarav.phone_number,
            'seeker_email': aarav.email,
            'interested_room_type': 'Private room · PG',
            'budget': 14500.00,
            'preferred_move_in': datetime.date(2026, 12, 1),
            'message': 'Hi, I am looking for a single private room in Indiranagar starting 1st December. Is food included in the monthly rent?',
            'status': 'CONTACTED'
        }
    )
    enq_palm.status = 'CONTACTED'
    enq_palm.seeker_name = aarav.get_full_name()
    enq_palm.seeker_phone = aarav.phone_number
    enq_palm.save()

    # Messages for Enquiry 1
    EnquiryMessage.objects.get_or_create(
        enquiry=enq_palm,
        sender_type='SEEKER',
        message_text='Hi, I am looking for a single private room in Indiranagar starting 1st December. Is food included in the monthly rent?'
    )
    EnquiryMessage.objects.get_or_create(
        enquiry=enq_palm,
        sender_type='OWNER',
        message_text="Hi Aarav, the room is available. We'd love to show you around on Tuesday."
    )

    # Enquiry 2: Olive Co-living (Status: NEW, "Awaiting reply")
    enq_olive, _ = Enquiry.objects.get_or_create(
        property=prop_olive,
        seeker=aarav,
        defaults={
            'seeker_name': aarav.get_full_name(),
            'seeker_phone': aarav.phone_number,
            'seeker_email': aarav.email,
            'interested_room_type': 'Twin sharing · Co-living',
            'budget': 11000.00,
            'preferred_move_in': datetime.date(2026, 12, 1),
            'message': 'Hello, interested in the twin sharing room. Are the gym and laundry facilities included or charged separately?',
            'status': 'NEW'
        }
    )
    enq_olive.status = 'NEW'
    enq_olive.seeker_name = aarav.get_full_name()
    enq_olive.seeker_phone = aarav.phone_number
    enq_olive.save()

    EnquiryMessage.objects.get_or_create(
        enquiry=enq_olive,
        sender_type='SEEKER',
        message_text='Hello, interested in the twin sharing room. Are the gym and laundry facilities included or charged separately?'
    )
    EnquiryMessage.objects.get_or_create(
        enquiry=enq_olive,
        sender_type='SYSTEM',
        message_text='Your enquiry is with the property team. We will let you know as soon as they respond.'
    )
    print("Enquiries seeded for Aarav.")

    # 9. Seed Visit Requests for Aarav
    # Visit 1: The Palm House (10 Nov, Confirmed)
    vr1, _ = VisitRequest.objects.get_or_create(
        request_id='VR-90412',
        defaults={
            'property': prop_palm,
            'seeker': aarav,
            'seeker_name': aarav.get_full_name(),
            'seeker_phone': aarav.phone_number,
            'seeker_email': aarav.email,
            'request_type': 'VISIT',
            'scheduled_date': datetime.date(2026, 11, 10),
            'scheduled_time_slot': '11:00 AM – 11:30 AM',
            'status': 'ACCEPTED',
            'notes': 'Looking forward to checking out the private room and rooftop cafe.',
            'owner_reply': 'Confirmed! Our manager Ramesh (+91 98801 12345) will welcome you at the gate.'
        }
    )
    vr1.seeker = aarav
    vr1.status = 'ACCEPTED'
    vr1.scheduled_date = datetime.date(2026, 11, 10)
    vr1.scheduled_time_slot = '11:00 AM – 11:30 AM'
    vr1.save()

    # Visit 2: Aster Residences (11 Nov, Pending)
    vr2, _ = VisitRequest.objects.get_or_create(
        request_id='VR-90413',
        defaults={
            'property': prop_aster,
            'seeker': aarav,
            'seeker_name': aarav.get_full_name(),
            'seeker_phone': aarav.phone_number,
            'seeker_email': aarav.email,
            'request_type': 'VISIT',
            'scheduled_date': datetime.date(2026, 11, 11),
            'scheduled_time_slot': '4:00 PM – 4:30 PM',
            'status': 'PENDING',
            'notes': 'Interested in the studio flat layout.',
            'owner_reply': ''
        }
    )
    vr2.seeker = aarav
    vr2.status = 'PENDING'
    vr2.scheduled_date = datetime.date(2026, 11, 11)
    vr2.scheduled_time_slot = '4:00 PM – 4:30 PM'
    vr2.save()
    print("VisitRequests seeded for Aarav.")

    # 10. Seed RentalBooking for Aarav (Olive Co-living, BK-89021)
    rb, _ = RentalBooking.objects.get_or_create(
        booking_id='BK-89021',
        defaults={
            'tenant': aarav,
            'property': prop_olive,
            'owner': arjun,
            'move_in_date': datetime.date(2026, 12, 1),
            'sharing_type': 'Twin sharing · Co-living',
            'monthly_rent': 11000.00,
            'security_deposit': 22000.00,
            'booking_status': 'REQUESTED',
            'payment_status': 'NOT_REQUIRED',
            'payment_amount': 0.00,
            'tenant_notes': 'Awaiting host confirmation. Target move-in 1 Dec 2026.'
        }
    )
    rb.booking_status = 'REQUESTED'
    rb.payment_status = 'NOT_REQUIRED'
    rb.save()
    print("RentalBooking seeded for Aarav (BK-89021).")

    # 11. Seed Notifications for Aarav
    notifs = [
        ('Owner Replied to Your Enquiry', 'Arjun Mehta replied: "Hi Aarav, the room is available. We would love to show you around on Tuesday."', 'IN_APP', 'View Enquiry', '/tenant/enquiries/'),
        ('Property Visit Confirmed', 'Your physical walkthrough visit to The Palm House is confirmed for Tuesday, 10 Nov at 11:00 AM.', 'IN_APP', 'View Visit', '/tenant/visits/'),
        ('Booking Request Awaiting Host Confirmation', 'Your booking request BK-89021 for Olive Co-living was received. The host will confirm within 24 hours.', 'IN_APP', 'View Booking', '/tenant/bookings/'),
        ('Welcome to KiraayaGrid', 'Find your kind of home in Bengaluru with verified stays and 0% brokerage fees.', 'IN_APP', 'Explore Homes', '/tenant/find/'),
    ]
    for title, msg, chan, btn_label, url in notifs:
        Notification.objects.get_or_create(
            recipient=aarav,
            title=title,
            defaults={
                'message': msg,
                'channel': chan,
                'is_read': False,
                'status': 'SENT',
                'button_label': btn_label,
                'button_url': url
            }
        )
    print("Notifications seeded for Aarav.")
    print("=== SEEDING COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    seed_tenant_portal_data()
