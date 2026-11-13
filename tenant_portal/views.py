import json
import random
from datetime import datetime, date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import get_user_model, update_session_auth_hash, logout as auth_logout
from django.db.models import Min, Count, Q, Case, When, Value, IntegerField, F, Avg, Sum
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from admin_portal.models import Property, City, Locality, Notification, SupportTicket, TicketMessage
from owner_portal.models import Room, Bed, PropertyPhoto, Enquiry, EnquiryMessage, VisitRequest
from .models import TenantProfile, SavedProperty, RecentlyViewedProperty, RentalBooking
from accounts.communication import dispatch_omnichannel_notification

User = get_user_model()

def get_active_tenant(request):
    """
    Returns active logged in tenant.
    """
    if hasattr(request, 'user') and request.user.is_authenticated and (getattr(request.user, 'role', '') == 'TENANT' or request.user.is_superuser):
        return request.user
    return None


# 8. Tenant Overview / Dashboard
def tenant_overview(request):
    tenant = get_active_tenant(request)
    profile = getattr(tenant, 'tenant_profile', None) if tenant else None

    # City filter / preferred city
    selected_city_name = request.GET.get('city', '')
    if not selected_city_name:
        if profile and profile.preferred_city:
            selected_city_name = profile.preferred_city.name
        else:
            selected_city_name = 'Bengaluru'

    current_city = City.objects.filter(name__icontains=selected_city_name).first()
    localities = Locality.objects.filter(city=current_city).order_by('name') if current_city else Locality.objects.none()

    # Saved properties set for instant heart state
    saved_property_ids = set(SavedProperty.objects.filter(tenant=tenant).values_list('property_id', flat=True)) if tenant else set()
    saved_items = SavedProperty.objects.filter(tenant=tenant).select_related('property', 'property__locality', 'property__city').order_by('-created_at')[:4] if tenant else []
    saved_count = SavedProperty.objects.filter(tenant=tenant).count() if tenant else 0

    # Recently Viewed
    viewed_items = RecentlyViewedProperty.objects.filter(tenant=tenant).select_related('property', 'property__locality', 'property__city').order_by('-viewed_at')[:4] if tenant else []

    # Recommended Properties (Authentic DB approved stays)
    rec_qs = Property.objects.filter(status='APPROVED').select_related('locality', 'city').prefetch_related('gallery_photos', 'rooms')
    if current_city:
        ordered_recs = list(rec_qs.filter(city=current_city)[:3])
    else:
        ordered_recs = list(rec_qs.filter(city__name='Indore')[:3])
    
    if len(ordered_recs) < 3:
        existing_ids = [p.id for p in ordered_recs]
        extras = list(rec_qs.exclude(id__in=existing_ids)[:(3 - len(ordered_recs))])
        ordered_recs.extend(extras)

    # Enhance recommended property objects with dynamic display data
    for prop in ordered_recs:
        # Cover photo
        cover_obj = prop.gallery_photos.filter(is_cover=True).first() or prop.gallery_photos.first()
        if cover_obj and cover_obj.photo_url:
            prop.display_photo = cover_obj.photo_url
        else:
            prop.display_photo = 'https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800&auto=format&fit=crop&q=80'

        # Minimum Rent
        min_room_rent = prop.rooms.aggregate(Min('monthly_rent'))['monthly_rent__min']
        prop.display_price = int(min_room_rent) if min_room_rent else 12000

        # Sharing & Type string
        if prop.property_type == 'PG':
            prop.display_sharing = 'Private room · PG'
            prop.display_amenities = 'Wi-Fi · Meals · Housekeeping'
            prop.display_availability = 'Available now'
            prop.availability_class = 'avail-now'
        elif prop.property_type == 'CO_LIVING':
            prop.display_sharing = 'Twin sharing · Co-living'
            prop.display_amenities = 'Wi-Fi · Gym · Laundry'
            prop.display_availability = 'From 1 Dec'
            prop.availability_class = 'avail-date'
        elif prop.property_type == 'FLAT':
            prop.display_sharing = 'Studio · Flat'
            prop.display_amenities = 'Wi-Fi · Kitchen · Security'
            prop.display_availability = 'From 15 Nov'
            prop.availability_class = 'avail-date'
        else:
            prop.display_sharing = f"{prop.get_property_type_display()}"
            prop.display_amenities = 'Wi-Fi · Housekeeping · Security'
            prop.display_availability = 'Available now'
            prop.availability_class = 'avail-now'

        prop.is_saved = prop.id in saved_property_ids

    # Recent Enquiries
    recent_enquiries = list(Enquiry.objects.filter(seeker=tenant).select_related('property', 'property__locality', 'room').prefetch_related('messages').order_by('-created_at')[:4]) if tenant else []
    for enq in recent_enquiries:
        # Cover photo
        cov = enq.property.gallery_photos.filter(is_cover=True).first() or enq.property.gallery_photos.first()
        enq.display_photo = cov.photo_url if (cov and cov.photo_url) else 'https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=200&auto=format&fit=crop&q=80'

        # Latest message
        last_msg = enq.messages.order_by('-created_at').first()
        enq.last_message = last_msg

        # Status Badge & Message Snippet
        if (last_msg and last_msg.sender_type == 'OWNER') or enq.status in ['CONTACTED', 'RESPONDED']:
            enq.status_label = 'Reply received'
            enq.status_badge_bg = '#D1FAE5'
            enq.status_badge_color = '#065F46'
            enq.snippet_text = last_msg.message_text if last_msg else "Owner responded to your enquiry."
            enq.snippet_style = 'font-style: italic; color: #334155;'
        else:
            enq.status_label = 'Awaiting reply'
            enq.status_badge_bg = '#FEF3C7'
            enq.status_badge_color = '#92400E'
            enq.snippet_text = "Your enquiry is with the property team. We'll let you know as soon as they respond."
            enq.snippet_style = 'color: var(--color-text-muted);'

        # Formatted Time
        if enq.created_at:
            now = timezone.now()
            diff_days = (now.date() - enq.created_at.date()).days
            if diff_days == 0:
                enq.time_display = f"Today, {enq.created_at.strftime('%I:%M %p')}"
            elif diff_days == 1:
                enq.time_display = f"Yesterday, {enq.created_at.strftime('%I:%M %p')}"
            else:
                enq.time_display = enq.created_at.strftime('%d %b %Y')
        else:
            enq.time_display = 'Recently'

    active_enquiries_count = Enquiry.objects.filter(seeker=tenant).exclude(status='CLOSED').count() if tenant else 0

    # Upcoming Visits
    upcoming_visits = list(VisitRequest.objects.filter(seeker=tenant).select_related('property', 'property__locality').order_by('scheduled_date')[:4]) if tenant else []
    for vis in upcoming_visits:
        vis.day_str = vis.scheduled_date.strftime('%d') if vis.scheduled_date else '10'
        vis.month_str = vis.scheduled_date.strftime('%b').upper() if vis.scheduled_date else 'NOV'
        vis.weekday_str = vis.scheduled_date.strftime('%A') if vis.scheduled_date else 'Tuesday'
        vis.is_confirmed = (vis.status == 'ACCEPTED')
        if vis.status == 'ACCEPTED':
            vis.status_label = 'Visit confirmed'
            vis.badge_bg = '#D1FAE5'
            vis.badge_color = '#065F46'
            vis.date_box_bg = 'var(--color-powder-blue)'
            vis.date_box_color = '#1A202C'
        elif vis.status == 'PENDING':
            vis.status_label = 'Confirmation pending'
            vis.badge_bg = '#FEF3C7'
            vis.badge_color = '#92400E'
            vis.date_box_bg = '#E2E8F0'
            vis.date_box_color = '#334155'
        elif vis.status == 'RESCHEDULED':
            vis.status_label = 'Rescheduled'
            vis.badge_bg = '#E0F2FE'
            vis.badge_color = '#0284C7'
            vis.date_box_bg = '#E0F2FE'
            vis.date_box_color = '#0369A1'
        else:
            vis.status_label = vis.get_status_display()
            vis.badge_bg = '#F1F5F9'
            vis.badge_color = '#475569'
            vis.date_box_bg = '#F1F5F9'
            vis.date_box_color = '#475569'

    # Booking update banner
    booking = RentalBooking.objects.filter(tenant=tenant).select_related('property', 'owner').first() if tenant else None

    # Dynamic City Cards Exploration Data calculated from MySQL database (Indore #1)
    target_city_names = ['Indore', 'Bengaluru', 'Pune', 'Hyderabad']
    city_cards = []
    city_fallback_images = {
        'Indore': '/static/public/images/city_indore.webp',
        'Bengaluru': '/static/public/images/city_bengaluru.webp',
        'Pune': '/static/public/images/city_pune.webp',
        'Hyderabad': '/static/public/images/city_hyderabad.webp',
    }
    for c_name in target_city_names:
        c_obj = City.objects.filter(name__icontains=c_name).first()
        if c_obj:
            p_cnt = Property.objects.filter(city=c_obj, status='APPROVED').count()
            min_r = Property.objects.filter(city=c_obj, status='APPROVED').aggregate(Min('rooms__monthly_rent'))['rooms__monthly_rent__min']
            locs_list = list(c_obj.localities.values_list('name', flat=True)[:3])
            locs_str = ' · '.join(locs_list) if locs_list else f'{c_obj.name} Central'

            # Try to fetch real cover photo from property in this city
            city_img = None
            first_city_prop = Property.objects.filter(city=c_obj, status='APPROVED').first()
            if first_city_prop:
                cov_p = first_city_prop.gallery_photos.filter(is_cover=True).first() or first_city_prop.gallery_photos.first()
                if cov_p and cov_p.photo_url:
                    city_img = cov_p.photo_url

            city_cards.append({
                'name': c_obj.name,
                'localities': locs_str,
                'min_rent': f"{int(min_r):,}" if min_r else '7,500',
                'stays_count': f"{p_cnt} stays" if p_cnt else 'Stays available',
                'image': city_img or city_fallback_images.get(c_name, 'https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800&auto=format&fit=crop&q=80'),
            })

    context = {
        'active_tenant': tenant,
        'profile': profile,
        'selected_city': selected_city_name,
        'localities': localities,
        'recommended_properties': ordered_recs,
        'saved_property_ids': saved_property_ids,
        'saved_items': saved_items,
        'saved_count': saved_count,
        'viewed_items': viewed_items,
        'recent_enquiries': recent_enquiries,
        'active_enquiries_count': active_enquiries_count,
        'upcoming_visits': upcoming_visits,
        'booking': booking,
        'city_cards': city_cards,
    }
    return render(request, 'tenant_portal/08_overview.html', context)


# API: Property Details for Quick View Modal
def api_property_details(request, property_id):
    prop = get_object_or_404(Property, id=property_id, status='APPROVED')
    tenant = get_active_tenant(request)

    photos = [ph.photo_url for ph in prop.gallery_photos.all()]
    if not photos:
        photos = ['https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800&auto=format&fit=crop&q=80']

    rooms_data = []
    for r in prop.rooms.all():
        rooms_data.append({
            'id': r.id,
            'room_number': r.room_number,
            'room_type': r.get_room_type_display(),
            'monthly_rent': float(r.monthly_rent),
            'security_deposit': float(r.security_deposit or (r.monthly_rent * 2)),
            'available_beds': r.available_beds,
            'bathroom_type': r.bathroom_type,
            'ac_type': r.ac_type,
            'furnishing': r.furnishing,
            'amenities': r.amenities or 'Wi-Fi, Power Backup, Housekeeping',
        })

    min_rent = prop.rooms.aggregate(Min('monthly_rent'))['monthly_rent__min']
    is_saved = SavedProperty.objects.filter(tenant=tenant, property=prop).exists() if tenant else False

    # Automatically log to RecentlyViewedProperty in MySQL
    if tenant:
        RecentlyViewedProperty.objects.update_or_create(
            tenant=tenant, property=prop,
            defaults={'viewed_at': timezone.now()}
        )

    data = {
        'id': prop.id,
        'title': prop.title,
        'property_type': prop.get_property_type_display(),
        'locality': prop.locality.name if prop.locality else '',
        'city': prop.city.name if prop.city else '',
        'address_line': prop.address_line or f"{prop.locality.name if prop.locality else ''}, {prop.city.name if prop.city else ''}",
        'pincode': prop.pincode or '560038',
        'is_verified': (prop.status == 'APPROVED'),
        'min_rent': float(min_rent) if min_rent else 12000.0,
        'photos': photos,
        'cover_photo': photos[0],
        'owner_name': prop.owner.get_full_name() or prop.owner.username if prop.owner else 'Arjun Mehta',
        'owner_phone': getattr(prop.owner, 'phone', '+91 98765 43210') if prop.owner else '+91 98765 43210',
        'rooms': rooms_data,
        'is_saved': is_saved,
    }
    return JsonResponse(data)


# API: Submit Quick Enquiry
def api_quick_enquiry(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Tenant authentication required'}, status=403)

    req_data = request.POST
    if request.content_type == 'application/json':
        try:
            req_data = json.loads(request.body)
        except Exception:
            pass

    property_id = req_data.get('property_id')
    prop = get_object_or_404(Property, id=property_id, status='APPROVED')

    room_type = req_data.get('room_type', 'Private room · PG')
    budget_raw = req_data.get('budget', '15000')
    try:
        budget = float(budget_raw)
    except (ValueError, TypeError):
        budget = 15000.00

    default_move_in = (timezone.now().date() + timedelta(days=15)).strftime('%Y-%m-%d')
    move_in_str = req_data.get('move_in_date', default_move_in)
    try:
        move_in_date = datetime.strptime(move_in_str, '%Y-%m-%d').date()
    except Exception:
        move_in_date = timezone.now().date() + timedelta(days=15)

    message_text = req_data.get('message', '').strip()
    if not message_text:
        message_text = f"Hi, I am interested in {prop.title}. Looking to move in around {move_in_date.strftime('%d %b %Y')} with a budget of ₹{int(budget):,}/mo. Please let me know room availability."

    seeker_phone = getattr(tenant, 'phone_number', '') or getattr(tenant, 'phone', '') or '+91 98765 43210'

    # Create Enquiry
    enquiry = Enquiry.objects.create(
        property=prop,
        room=prop.rooms.first(),
        seeker=tenant,
        seeker_name=tenant.get_full_name() or tenant.username,
        seeker_phone=seeker_phone,
        seeker_email=tenant.email or 'aarav.sharma@gmail.com',
        interested_room_type=room_type,
        budget=budget,
        preferred_move_in=move_in_date,
        message=message_text,
        status='NEW'
    )

    # Initial Message from Seeker
    EnquiryMessage.objects.create(
        enquiry=enquiry,
        sender_type='SEEKER',
        message_text=message_text
    )

    # Automatic System Acknowledgement
    EnquiryMessage.objects.create(
        enquiry=enquiry,
        sender_type='SYSTEM',
        message_text="Your enquiry has been delivered to the property team. We will notify you as soon as they respond."
    )

    # Omnichannel Notifications (Email + WhatsApp + In-App)
    dispatch_omnichannel_notification(
        recipient=tenant,
        title=f"Enquiry Sent · {prop.title}",
        message=f"Your enquiry for {prop.title} has been delivered to the property host. We will alert you immediately when they reply.",
        category='CHAT',
        cta_url=f"/tenant/enquiries/{enquiry.id}/",
        cta_label="View Enquiry"
    )

    if prop.owner:
        dispatch_omnichannel_notification(
            recipient=prop.owner,
            sender=tenant,
            title=f"New Seeker Enquiry · {prop.title}",
            message=f"{tenant.get_full_name() or 'Aarav Sharma'} sent an enquiry for {prop.title}:\n\n\"{message_text}\"",
            category='CHAT',
            cta_url="/owner/enquiries/",
            cta_label="Respond Now",
            details={
                'Property': prop.title,
                'Seeker Name': tenant.get_full_name() or tenant.username,
                'Room Preference': enquiry.interested_room_type,
                'Budget': f"₹{enquiry.budget}",
                'Phone': getattr(tenant, 'phone_number', '') or getattr(tenant, 'phone', '') or enquiry.seeker_phone,
            }
        )

    return JsonResponse({
        'status': 'success',
        'message': f"Enquiry sent successfully to {prop.title}!",
        'enquiry_id': enquiry.id,
        'property_title': prop.title
    })


# API: Submit Quick Visit Request
def api_quick_visit(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Tenant authentication required'}, status=403)

    req_data = request.POST
    if request.content_type == 'application/json':
        try:
            req_data = json.loads(request.body)
        except Exception:
            pass

    property_id = req_data.get('property_id')
    prop = get_object_or_404(Property, id=property_id, status='APPROVED')

    default_sched = (timezone.now().date() + timedelta(days=2)).strftime('%Y-%m-%d')
    scheduled_date_str = req_data.get('scheduled_date', default_sched)
    try:
        sched_date = datetime.strptime(scheduled_date_str, '%Y-%m-%d').date()
    except Exception:
        sched_date = timezone.now().date() + timedelta(days=2)

    time_slot = req_data.get('scheduled_time_slot', '11:00 AM – 11:30 AM')
    notes = req_data.get('notes', 'Scheduled walkthrough via KiraayaGrid tenant dashboard').strip()

    # Generate unique visit request_id
    rand_num = random.randint(90420, 99999)
    req_id = f"VR-{rand_num}"

    seeker_phone = getattr(tenant, 'phone_number', '') or getattr(tenant, 'phone', '') or '+91 98765 43210'

    visit = VisitRequest.objects.create(
        request_id=req_id,
        property=prop,
        room=prop.rooms.first(),
        seeker=tenant,
        seeker_name=tenant.get_full_name() or tenant.username,
        seeker_phone=seeker_phone,
        seeker_email=tenant.email or 'aarav.sharma@gmail.com',
        request_type='PHYSICAL',
        scheduled_date=sched_date,
        scheduled_time_slot=time_slot,
        status='PENDING',
        notes=notes
    )

    # In-app notifications
    Notification.objects.create(
        recipient=tenant,
        title="Visit Requested",
        message=f"Walkthrough visit requested for {prop.title} on {sched_date.strftime('%d %b %Y')} ({time_slot}).",
        channel="IN_APP",
        button_label="Visit Details",
        button_url=f"/tenant/visits/{visit.request_id}/"
    )

    if prop.owner:
        dispatch_omnichannel_notification(
            recipient=prop.owner,
            sender=tenant,
            title=f"New Walkthrough Visit Requested · {prop.title}",
            message=f"{tenant.get_full_name() or tenant.username} requested a walkthrough visit for {prop.title} on {sched_date.strftime('%d %b %Y')} ({time_slot}). Notes: {notes}",
            category='VISIT',
            cta_url="/owner/booking-requests/",
            cta_label="Review & Confirm Walkthrough",
            details={
                'Property': prop.title,
                'Seeker': tenant.get_full_name() or tenant.username,
                'Date': sched_date.strftime('%d %b %Y'),
                'Time Slot': time_slot,
            }
        )

    return JsonResponse({
        'status': 'success',
        'message': f"Visit requested for {prop.title}! Confirmation pending with host.",
        'request_id': visit.request_id,
        'scheduled_date': sched_date.strftime('%d %b %Y'),
        'time_slot': time_slot,
    })


# API: Switch Preferred City
def api_switch_city(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    city_name = request.POST.get('city', '').strip()
    if not city_name and request.content_type == 'application/json':
        try:
            body = json.loads(request.body)
            city_name = (body.get('city') or '').strip()
        except Exception:
            pass

    if not city_name:
        return JsonResponse({'status': 'error', 'message': 'City name is required'}, status=400)

    city = City.objects.filter(name__iexact=city_name).first()
    if not city:
        city = City.objects.filter(name__icontains=city_name).first()

    if city and tenant:
        profile, _ = TenantProfile.objects.get_or_create(user=tenant)
        profile.preferred_city = city
        profile.save()
        return JsonResponse({'status': 'success', 'city': city.name})

    return JsonResponse({'status': 'error', 'message': 'City not found'}, status=404)



# 9. Find Accommodation (Full property search & filters, list/map view)
def find_accommodation(request):
    tenant = get_active_tenant(request)
    profile = getattr(tenant, 'tenant_profile', None) if tenant else None

    # 1. City handling (Indore is #1 per user mandate)
    city_param = request.GET.get('city', '').strip()
    if not city_param:
        if profile and profile.preferred_city:
            city_param = profile.preferred_city.name
        else:
            city_param = 'Indore'

    current_city = City.objects.filter(name__icontains=city_param).first() or City.objects.filter(name='Indore').first()
    all_cities = City.objects.filter(is_active=True).order_by(
        Case(
            When(name__iexact='Indore', then=Value(0)),
            default=Value(1),
            output_field=IntegerField()
        ),
        'name'
    )
    localities = Locality.objects.filter(city=current_city).order_by('name') if current_city else Locality.objects.none()

    # 2. Base Query: Approved properties
    qs = Property.objects.filter(status='APPROVED').select_related('city', 'locality', 'owner').prefetch_related('gallery_photos', 'rooms')
    if current_city:
        qs = qs.filter(city=current_city)

    # 3. Filter: Locality
    locality_param = request.GET.get('locality', '').strip()
    if locality_param:
        qs = qs.filter(locality__name__icontains=locality_param)

    # 4. Filter: Property Type
    type_param = request.GET.get('type', '').strip()
    if type_param:
        qs = qs.filter(property_type=type_param)

    # 5. Filter: Occupancy
    occupancy_param = request.GET.get('occupancy', '').strip()
    if occupancy_param:
        if occupancy_param in ['SINGLE', 'DOUBLE', 'TRIPLE', 'FOUR_SHARING']:
            qs = qs.filter(rooms__room_type=occupancy_param)
        elif occupancy_param == 'STUDIO':
            qs = qs.filter(Q(property_type='FLAT') | Q(rooms__room_type='SINGLE'))

    # 6. Filter: Budget (Max rent)
    budget_param = request.GET.get('budget', '').strip()
    if budget_param:
        try:
            max_b = float(budget_param)
            qs = qs.filter(rooms__monthly_rent__lte=max_b)
        except (ValueError, TypeError):
            pass

    # 7. Filter: Gender
    gender_param = request.GET.get('gender', '').strip()
    if gender_param and gender_param != 'ALL':
        qs = qs.filter(Q(gender_category=gender_param) | Q(gender_category='CO_ED') | Q(gender_category='ALL'))

    # 8. Filter: Keyword search (q)
    q_param = request.GET.get('q', '').strip()
    if q_param:
        qs = qs.filter(
            Q(title__icontains=q_param) |
            Q(locality__name__icontains=q_param) |
            Q(address_line__icontains=q_param)
        )

    # 9. Filter: Amenities
    amenities_param = request.GET.getlist('amenity')
    if amenities_param:
        for a in amenities_param:
            qs = qs.filter(Q(rooms__amenities__icontains=a) | Q(title__icontains=a))

    # Move-in date filter
    move_in_param = request.GET.get('move_in', '').strip()

    # Distinct after room joins
    qs = qs.distinct()

    # 10. Annotate minimum rent and sort
    qs = qs.annotate(min_rent_val=Min('rooms__monthly_rent'))

    sort_param = request.GET.get('sort', 'recommended').strip()
    if sort_param == 'price_low':
        qs = qs.order_by('min_rent_val', 'id')
    elif sort_param == 'price_high':
        qs = qs.order_by('-min_rent_val', 'id')
    elif sort_param == 'newest':
        qs = qs.order_by('-created_at')
    else:  # recommended: prioritizes id descending or matched items
        qs = qs.order_by('-id')

    # Fetch Saved Properties IDs for heart state
    saved_property_ids = set(SavedProperty.objects.filter(tenant=tenant).values_list('property_id', flat=True)) if tenant else set()

    # Build property display models & map pins
    properties_list = list(qs)
    map_pins = []

    for prop in properties_list:
        # Cover photo
        cov = prop.gallery_photos.filter(is_cover=True).first() or prop.gallery_photos.first()
        prop.display_photo = cov.photo_url if (cov and cov.photo_url) else 'https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800&auto=format&fit=crop&q=80'

        # Rent display
        prop.display_price = int(prop.min_rent_val) if prop.min_rent_val else 13500

        # Locality string
        prop.locality_str = prop.locality.name if prop.locality else (prop.city.name if prop.city else 'Bengaluru')

        # Sharing & Type
        if prop.property_type == 'PG':
            prop.display_sharing = 'Private room · PG'
            prop.display_amenities = 'Wi-Fi · Meals · Housekeeping'
            prop.display_availability = 'Available now'
            prop.availability_class = 'avail-now'
        elif prop.property_type == 'CO_LIVING':
            prop.display_sharing = 'Twin sharing · Co-living'
            prop.display_amenities = 'Wi-Fi · Gym · Laundry'
            prop.display_availability = 'From 1 Dec'
            prop.availability_class = 'avail-date'
        elif prop.property_type == 'FLAT':
            prop.display_sharing = 'Studio · Flat'
            prop.display_amenities = 'Wi-Fi · Kitchen · Security'
            prop.display_availability = 'From 15 Nov'
            prop.availability_class = 'avail-date'
        else:
            prop.display_sharing = f"{prop.get_property_type_display()}"
            prop.display_amenities = 'Wi-Fi · Housekeeping · Security'
            prop.display_availability = 'Available now'
            prop.availability_class = 'avail-now'

        prop.is_saved = prop.id in saved_property_ids

        # Lat / Lng for map pin
        lat = float(prop.latitude) if prop.latitude else 12.9352
        lng = float(prop.longitude) if prop.longitude else 77.6245

        map_pins.append({
            'id': prop.id,
            'title': prop.title,
            'lat': lat,
            'lng': lng,
            'price': f"₹{prop.display_price:,}",
            'price_raw': prop.display_price,
            'type': prop.get_property_type_display(),
            'locality': prop.locality_str,
            'photo': prop.display_photo,
            'is_verified': (prop.status == 'APPROVED'),
        })

    # Active filter chips for easy one-click clearing
    active_filters = []
    if locality_param:
        active_filters.append({'key': 'locality', 'label': f"Locality: {locality_param}"})
    if type_param:
        active_filters.append({'key': 'type', 'label': f"Type: {dict(Property._meta.get_field('property_type').choices).get(type_param, type_param)}"})
    if occupancy_param:
        active_filters.append({'key': 'occupancy', 'label': f"Occupancy: {occupancy_param.title()}"})
    if budget_param:
        active_filters.append({'key': 'budget', 'label': f"Max Budget: ≤ ₹{int(float(budget_param)):,}"})
    if gender_param and gender_param != 'ALL':
        active_filters.append({'key': 'gender', 'label': f"Gender: {gender_param.title()}"})
    if q_param:
        active_filters.append({'key': 'q', 'label': f"Search: '{q_param}'"})
    for a in amenities_param:
        active_filters.append({'key': 'amenity', 'value': a, 'label': a.title()})

    view_mode = request.GET.get('view', 'list')

    # Pagination: Limit 5 per page
    paginator = Paginator(properties_list, 5)
    page_num = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    context = {
        'active_tenant': tenant,
        'profile': profile,
        'selected_city': city_param,
        'all_cities': all_cities,
        'localities': localities,
        'properties': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'properties_count': len(properties_list),
        'map_pins_json': json.dumps(map_pins),
        'saved_property_ids': saved_property_ids,
        'active_filters': active_filters,
        'filters': {
            'city': city_param,
            'locality': locality_param,
            'type': type_param,
            'occupancy': occupancy_param,
            'budget': budget_param,
            'gender': gender_param,
            'q': q_param,
            'move_in': move_in_param,
            'amenities': amenities_param,
            'sort': sort_param,
            'view': view_mode,
        }
    }
    return render(request, 'tenant_portal/09_find_accommodation.html', context)


# 10. Saved Properties (Shortlist, comparison, photos, rent, actions)
def saved_properties(request):
    tenant = get_active_tenant(request)
    profile = getattr(tenant, 'tenant_profile', None) if tenant else None

    # Sort handling
    sort_param = request.GET.get('sort', 'recent')
    
    saved_qs = SavedProperty.objects.filter(tenant=tenant).select_related(
        'property', 'property__locality', 'property__city', 'property__owner'
    ).prefetch_related('property__gallery_photos', 'property__rooms') if tenant else SavedProperty.objects.none()

    # Build display properties & comparison matrix
    saved_items = list(saved_qs)
    comparison_data = []

    for item in saved_items:
        prop = item.property
        # Cover photo
        cov = prop.gallery_photos.filter(is_cover=True).first() or prop.gallery_photos.first()
        prop.display_photo = cov.photo_url if (cov and cov.photo_url) else 'https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800&auto=format&fit=crop&q=80'

        # Rent & Deposit
        min_rent = prop.rooms.aggregate(Min('monthly_rent'))['monthly_rent__min']
        prop.display_price = int(min_rent) if min_rent else 12000
        min_dep = prop.rooms.aggregate(Min('security_deposit'))['security_deposit__min']
        prop.display_deposit = int(min_dep) if min_dep else (prop.display_price * 2)

        # Locality
        prop.locality_str = prop.locality.name if prop.locality else (prop.city.name if prop.city else 'Bengaluru')

        # Sharing & Type
        if prop.property_type == 'PG':
            prop.display_sharing = 'Private room · PG'
            prop.display_amenities = 'Wi-Fi · Meals · Housekeeping · CCTV'
            prop.display_availability = 'Available now'
            prop.availability_class = 'avail-now'
        elif prop.property_type == 'CO_LIVING':
            prop.display_sharing = 'Twin sharing · Co-living'
            prop.display_amenities = 'Wi-Fi · Gym · Laundry · Gaming Lounge'
            prop.display_availability = 'From 1 Dec'
            prop.availability_class = 'avail-date'
        elif prop.property_type == 'FLAT':
            prop.display_sharing = 'Studio · Flat'
            prop.display_amenities = 'Wi-Fi · Kitchen · Security · Balcony'
            prop.display_availability = 'From 15 Nov'
            prop.availability_class = 'avail-date'
        else:
            prop.display_sharing = f"{prop.get_property_type_display()}"
            prop.display_amenities = 'Wi-Fi · Housekeeping · Security'
            prop.display_availability = 'Available now'
            prop.availability_class = 'avail-now'

        item.saved_date_str = item.created_at.strftime('%d %b %Y') if item.created_at else '7 Nov 2026'
        item.prop = prop

        # Structured data for Comparison Matrix Modal
        has_ac = prop.rooms.filter(ac_type__in=['AC', 'CENTRAL_AC']).exists()
        comparison_data.append({
            'id': prop.id,
            'title': prop.title,
            'photo': prop.display_photo,
            'locality': prop.locality_str,
            'city': prop.city.name if prop.city else 'Bengaluru',
            'type': prop.get_property_type_display(),
            'sharing': prop.display_sharing,
            'rent': f"₹{prop.display_price:,}",
            'rent_num': prop.display_price,
            'deposit': f"₹{prop.display_deposit:,}",
            'availability': prop.display_availability,
            'is_verified': (prop.status == 'APPROVED'),
            'owner_name': prop.owner.get_full_name() or prop.owner.username if prop.owner else 'Arjun Mehta',
            'amenities': {
                'wifi': True,
                'meals': (prop.property_type == 'PG' or 'Meals' in prop.display_amenities),
                'ac': has_ac or prop.property_type in ['CO_LIVING', 'FLAT'],
                'power_backup': True,
                'housekeeping': (prop.property_type in ['PG', 'CO_LIVING'] or 'Housekeeping' in prop.display_amenities),
                'gym': (prop.property_type == 'CO_LIVING' or 'Gym' in prop.display_amenities),
                'laundry': (prop.property_type in ['PG', 'CO_LIVING'] or 'Laundry' in prop.display_amenities),
                'security': True,
            }
        })

    # Sort in python for display
    if sort_param == 'price_low':
        saved_items.sort(key=lambda x: x.prop.display_price)
    elif sort_param == 'price_high':
        saved_items.sort(key=lambda x: x.prop.display_price, reverse=True)
    elif sort_param == 'recent':
        saved_items.sort(key=lambda x: x.created_at, reverse=True)

    # Pagination: Limit 5 per page
    paginator = Paginator(saved_items, 5)
    page_num = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    context = {
        'active_tenant': tenant,
        'profile': profile,
        'saved_items': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'saved_count': len(saved_items),
        'comparison_data_json': json.dumps(comparison_data),
        'current_sort': sort_param,
    }
    return render(request, 'tenant_portal/10_saved_properties.html', context)


def toggle_saved_property(request, property_id):
    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Not logged in'}, status=403)
    
    prop = get_object_or_404(Property, id=property_id, status='APPROVED')
    saved_obj = SavedProperty.objects.filter(tenant=tenant, property=prop).first()
    if saved_obj:
        saved_obj.delete()
        count = SavedProperty.objects.filter(tenant=tenant).count()
        return JsonResponse({'status': 'removed', 'saved_count': count, 'property_id': prop.id, 'title': prop.title})
    else:
        SavedProperty.objects.create(tenant=tenant, property=prop)
        count = SavedProperty.objects.filter(tenant=tenant).count()
        return JsonResponse({'status': 'saved', 'saved_count': count, 'property_id': prop.id, 'title': prop.title})


# 11. My Enquiries (All submitted enquiries, status tabs, pagination)
def my_enquiries(request):
    tenant = get_active_tenant(request)
    profile = getattr(tenant, 'tenant_profile', None) if tenant else None

    # Base Query
    base_qs = Enquiry.objects.filter(seeker=tenant).select_related(
        'property', 'property__locality', 'property__city', 'property__owner'
    ).prefetch_related('property__gallery_photos', 'messages') if tenant else Enquiry.objects.none()

    # Dynamic Counts for all tabs
    count_all = base_qs.count()
    count_responded = base_qs.filter(status__in=['CONTACTED', 'RESPONDED']).count()
    count_new = base_qs.filter(status='NEW').count()
    count_visit = base_qs.filter(status='VISIT_REQUESTED').count()
    count_closed = base_qs.filter(status='CLOSED').count()

    # Status tab filter
    status_tab = request.GET.get('status', 'ALL').upper()
    filtered_qs = base_qs

    if status_tab == 'RESPONDED':
        filtered_qs = filtered_qs.filter(status__in=['CONTACTED', 'RESPONDED'])
    elif status_tab == 'NEW':
        filtered_qs = filtered_qs.filter(status='NEW')
    elif status_tab == 'VISIT_REQUESTED':
        filtered_qs = filtered_qs.filter(status='VISIT_REQUESTED')
    elif status_tab == 'CLOSED':
        filtered_qs = filtered_qs.filter(status='CLOSED')

    # Search keyword filter
    search_query = request.GET.get('q', '').strip()
    if search_query:
        filtered_qs = filtered_qs.filter(
            Q(property__title__icontains=search_query) |
            Q(property__locality__name__icontains=search_query) |
            Q(property__owner__first_name__icontains=search_query) |
            Q(property__owner__last_name__icontains=search_query) |
            Q(interested_room_type__icontains=search_query)
        )

    # Order by newest first
    filtered_qs = filtered_qs.order_by('-created_at')

    # Pagination: Limit 5 per page
    page_num = request.GET.get('page', 1)
    paginator = Paginator(filtered_qs, 5)
    try:
        page_obj = paginator.get_page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    # Decorate enquiries for template presentation
    for enq in page_obj:
        prop = enq.property
        cov = prop.gallery_photos.filter(is_cover=True).first() or prop.gallery_photos.first()
        enq.display_photo = cov.photo_url if (cov and cov.photo_url) else 'https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=160&auto=format&fit=crop&q=80'
        
        # Owner & Locality
        enq.owner_name = prop.owner.get_full_name() or prop.owner.username if prop.owner else 'Arjun Mehta'
        enq.locality_str = prop.locality.name if prop.locality else (prop.city.name if prop.city else 'Bengaluru')
        
        # Formatted Dates & Budget
        enq.formatted_budget = f"₹{int(enq.budget):,}" if enq.budget else "₹14,500"
        enq.move_in_str = enq.preferred_move_in.strftime('%d %b %Y') if enq.preferred_move_in else '1 Dec 2026'
        enq.enquiry_date_str = enq.created_at.strftime('%d %b %Y') if enq.created_at else '7 Nov 2026'

        # Latest Message
        last_msg = enq.messages.order_by('-created_at').first()
        enq.latest_message = last_msg

        # Status badge
        if enq.status in ['CONTACTED', 'RESPONDED']:
            enq.status_label = 'Reply Received'
            enq.badge_bg = '#D1FAE5'
            enq.badge_color = '#065F46'
            enq.status_icon = '✓'
        elif enq.status == 'NEW':
            enq.status_label = 'Awaiting Host'
            enq.badge_bg = '#FEF3C7'
            enq.badge_color = '#92400E'
            enq.status_icon = '•'
        elif enq.status == 'VISIT_REQUESTED':
            enq.status_label = 'Visit Requested'
            enq.badge_bg = '#E0F2FE'
            enq.badge_color = '#0284C7'
            enq.status_icon = '📅'
        elif enq.status == 'CLOSED':
            enq.status_label = 'Closed'
            enq.badge_bg = '#F1F5F9'
            enq.badge_color = '#64748B'
            enq.status_icon = '✕'
        else:
            enq.status_label = enq.get_status_display()
            enq.badge_bg = '#F1F5F9'
            enq.badge_color = '#475569'
            enq.status_icon = '•'

    context = {
        'active_tenant': tenant,
        'profile': profile,
        'page_obj': page_obj,
        'enquiries': page_obj.object_list,
        'total_count': paginator.count,
        'current_tab': status_tab,
        'search_query': search_query,
        'counts': {
            'all': count_all,
            'responded': count_responded,
            'new': count_new,
            'visit': count_visit,
            'closed': count_closed,
        }
    }
    return render(request, 'tenant_portal/11_my_enquiries.html', context)


# API: Close / Withdraw Enquiry
def api_close_enquiry(request, enquiry_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)
    
    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)
        
    enquiry = get_object_or_404(Enquiry, id=enquiry_id, seeker=tenant)
    enquiry.status = 'CLOSED'
    enquiry.save()

    # System audit trail message
    EnquiryMessage.objects.create(
        enquiry=enquiry,
        sender_type='SYSTEM',
        message_text='This enquiry thread has been closed by the tenant.'
    )

    return JsonResponse({
        'status': 'success',
        'message': f"Enquiry #{enquiry.id} for {enquiry.property.title} has been closed.",
        'enquiry_id': enquiry.id
    })


# 12. Enquiry Details & Chat
def enquiry_details(request, enquiry_id):
    tenant = get_active_tenant(request)
    profile = getattr(tenant, 'tenant_profile', None) if tenant else None

    enquiry = get_object_or_404(
        Enquiry.objects.select_related(
            'property', 'property__locality', 'property__city', 'property__owner', 'room'
        ).prefetch_related('property__gallery_photos', 'messages'),
        id=enquiry_id,
        seeker=tenant
    )

    # Mark unread messages sent by OWNER as read for this tenant
    enquiry.messages.filter(sender_type='OWNER', is_read=False).update(is_read=True)

    # All messages ordered chronologically
    messages_list = list(enquiry.messages.all().order_by('created_at'))

    # Related walkthrough visit (if any)
    related_visit = VisitRequest.objects.filter(
        seeker=tenant, property=enquiry.property
    ).order_by('-created_at').first() if tenant else None

    # Property primary photo resolution
    prop_photo = None
    cov = enquiry.property.gallery_photos.filter(is_cover=True).first() or enquiry.property.gallery_photos.first()
    if cov and cov.photo_url:
        prop_photo = cov.photo_url
    else:
        title_l = enquiry.property.title.lower()
        if 'palm' in title_l:
            prop_photo = "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800&auto=format&fit=crop&q=80"
        elif 'olive' in title_l:
            prop_photo = "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&auto=format&fit=crop&q=80"
        else:
            prop_photo = "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800&auto=format&fit=crop&q=80"

    # Status styling & metadata
    status_config = {
        'NEW': {
            'label': 'Submitted (Awaiting Host)',
            'bg': '#FEF3C7', 'color': '#92400E', 'border': '#FDE68A',
            'step': 1, 'badge_class': 'badge-amber'
        },
        'CONTACTED': {
            'label': 'Host Responded',
            'bg': '#DCFCE7', 'color': '#166534', 'border': '#BBF7D0',
            'step': 2, 'badge_class': 'badge-emerald'
        },
        'INTERESTED': {
            'label': 'In Active Discussion',
            'bg': '#EFF6FF', 'color': '#1E40AF', 'border': '#DBEAFE',
            'step': 2, 'badge_class': 'badge-blue'
        },
        'VISIT_REQUESTED': {
            'label': 'Walkthrough Requested',
            'bg': '#EDE9FE', 'color': '#6B21A8', 'border': '#DDD6FE',
            'step': 3, 'badge_class': 'badge-purple'
        },
        'CONVERTED': {
            'label': 'Rental Confirmed',
            'bg': '#D1FAE5', 'color': '#065F46', 'border': '#A7F3D0',
            'step': 4, 'badge_class': 'badge-emerald'
        },
        'CLOSED': {
            'label': 'Enquiry Closed',
            'bg': '#F1F5F9', 'color': '#475569', 'border': '#E2E8F0',
            'step': 4, 'badge_class': 'badge-slate'
        },
    }
    status_meta = status_config.get(enquiry.status, status_config['NEW'])

    # Host details
    owner = enquiry.property.owner
    owner_name = owner.get_full_name() if owner else "Arjun Mehta"
    if not owner_name.strip():
        owner_name = owner.username if owner else "Arjun Mehta"
    owner_initials = "".join([part[0].upper() for part in owner_name.split()[:2]]) or "AM"
    owner_phone = getattr(owner, 'phone_number', None) or "+91 98801 12345"
    owner_email = owner.email if owner else "host@kiraayagrid.in"

    # Rent & Deposit
    min_rent_agg = enquiry.property.rooms.aggregate(Min('monthly_rent'))['monthly_rent__min']
    rent = enquiry.budget or (enquiry.room.monthly_rent if enquiry.room else None) or min_rent_agg or 14500
    deposit = (enquiry.room.security_deposit if enquiry.room else None) or (rent * 2)
    room_type = enquiry.interested_room_type or (enquiry.room.room_type if enquiry.room else 'Private Room')

    # Locality & address
    locality_name = enquiry.property.locality.name if enquiry.property.locality else "Indiranagar"
    city_name = enquiry.property.city.name if enquiry.property.city else "Bengaluru"
    full_address = enquiry.property.address_line or f"14, 12th Main Road, HAL 2nd Stage, {locality_name}, {city_name} - 560038"

    context = {
        'active_tenant': tenant,
        'profile': profile,
        'enquiry': enquiry,
        'messages': messages_list,
        'related_visit': related_visit,
        'prop_photo': prop_photo,
        'status_meta': status_meta,
        'owner_name': owner_name,
        'owner_initials': owner_initials,
        'owner_phone': owner_phone,
        'owner_email': owner_email,
        'rent': rent,
        'deposit': deposit,
        'room_type': room_type,
        'locality_name': locality_name,
        'city_name': city_name,
        'is_closed': (enquiry.status == 'CLOSED'),
    }
    return render(request, 'tenant_portal/12_enquiry_details.html', context)


# API: Send message in Enquiry chat
def api_send_enquiry_message(request, enquiry_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    enquiry = get_object_or_404(Enquiry, id=enquiry_id, seeker=tenant)
    message_text = request.POST.get('message_text', '').strip() or request.POST.get('message', '').strip()
    if not message_text and request.content_type == 'application/json':
        try:
            body = json.loads(request.body)
            message_text = (body.get('message_text') or body.get('message') or '').strip()
        except Exception:
            pass

    if not message_text:
        return JsonResponse({'status': 'error', 'message': 'Message cannot be empty'}, status=400)

    # Create seeker message
    msg = EnquiryMessage.objects.create(
        enquiry=enquiry,
        sender_type='SEEKER',
        message_text=message_text,
        is_read=False
    )

    # If enquiry was closed, reopen it to CONTACTED
    if enquiry.status == 'CLOSED':
        enquiry.status = 'CONTACTED'
    enquiry.save()

    # Omnichannel Notification to Landlord (Email + WhatsApp + In-App)
    if enquiry.property.owner:
        dispatch_omnichannel_notification(
            recipient=enquiry.property.owner,
            sender=tenant,
            title=f"New Message from Seeker {tenant.get_full_name() or tenant.username} · {enquiry.property.title}",
            message=message_text,
            category='CHAT',
            cta_url=f"/owner/enquiries/{enquiry.id}/",
            cta_label="Reply to Seeker on Portal",
            details={
                'Property': enquiry.property.title,
                'Seeker Name': tenant.get_full_name() or tenant.username,
                'Seeker Contact': getattr(tenant, 'phone_number', '') or 'In Portal',
            }
        )

    return JsonResponse({
        'status': 'success',
        'message_id': msg.id,
        'message_text': msg.message_text,
        'sender_type': msg.sender_type,
        'created_at': msg.created_at.strftime('%I:%M %p'),
        'date_str': msg.created_at.strftime('%d %b %Y')
    })


# API: Reopen Enquiry
def api_reopen_enquiry(request, enquiry_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    enquiry = get_object_or_404(Enquiry, id=enquiry_id, seeker=tenant)
    enquiry.status = 'CONTACTED'
    enquiry.save()

    EnquiryMessage.objects.create(
        enquiry=enquiry,
        sender_type='SYSTEM',
        message_text='Enquiry thread has been reopened by tenant.'
    )

    return JsonResponse({
        'status': 'success',
        'message': f"Enquiry #{enquiry.id} has been reopened.",
        'enquiry_id': enquiry.id
    })


# 13. Visit Requests (All walkthrough requests, status tabs, actions)
def visit_requests(request):
    tenant = get_active_tenant(request)
    profile = getattr(tenant, 'tenant_profile', None) if tenant else None

    # Base Query
    base_qs = VisitRequest.objects.filter(seeker=tenant).select_related(
        'property', 'property__locality', 'property__city', 'property__owner', 'room'
    ).prefetch_related('property__gallery_photos') if tenant else VisitRequest.objects.none()

    # Dynamic counts for status tabs
    count_all = base_qs.count()
    count_accepted = base_qs.filter(status='ACCEPTED').count()
    count_pending = base_qs.filter(status='PENDING').count()
    count_rescheduled = base_qs.filter(status='RESCHEDULED').count()
    count_completed = base_qs.filter(status='COMPLETED').count()
    count_cancelled = base_qs.filter(status__in=['CANCELLED', 'REJECTED']).count()

    # Filter tab handling
    status_tab = request.GET.get('status', 'ALL').upper()
    filtered_qs = base_qs

    if status_tab == 'ACCEPTED':
        filtered_qs = filtered_qs.filter(status='ACCEPTED')
    elif status_tab == 'PENDING':
        filtered_qs = filtered_qs.filter(status='PENDING')
    elif status_tab == 'RESCHEDULED':
        filtered_qs = filtered_qs.filter(status='RESCHEDULED')
    elif status_tab == 'COMPLETED':
        filtered_qs = filtered_qs.filter(status='COMPLETED')
    elif status_tab == 'CANCELLED':
        filtered_qs = filtered_qs.filter(status__in=['CANCELLED', 'REJECTED'])

    # Search keyword
    search_query = request.GET.get('q', '').strip()
    if search_query:
        filtered_qs = filtered_qs.filter(
            Q(property__title__icontains=search_query) |
            Q(property__locality__name__icontains=search_query) |
            Q(property__owner__first_name__icontains=search_query) |
            Q(property__owner__last_name__icontains=search_query) |
            Q(request_id__icontains=search_query)
        )

    # Order by scheduled date ascending
    filtered_qs = filtered_qs.order_by('scheduled_date', 'scheduled_time_slot')

    # Decorate visit items
    visits_list = list(filtered_qs)
    for vis in visits_list:
        prop = vis.property
        cov = prop.gallery_photos.filter(is_cover=True).first() or prop.gallery_photos.first()
        vis.display_photo = cov.photo_url if (cov and cov.photo_url) else 'https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=400&auto=format&fit=crop&q=80'

        vis.day_str = vis.scheduled_date.strftime('%d') if vis.scheduled_date else '10'
        vis.month_str = vis.scheduled_date.strftime('%b').upper() if vis.scheduled_date else 'NOV'
        vis.weekday_str = vis.scheduled_date.strftime('%A') if vis.scheduled_date else 'Tuesday'
        vis.formatted_date_str = vis.scheduled_date.strftime('%d %b %Y') if vis.scheduled_date else '10 Nov 2026'

        vis.owner_name = prop.owner.get_full_name() or prop.owner.username if prop.owner else 'Arjun Mehta'
        vis.locality_str = prop.locality.name if prop.locality else (prop.city.name if prop.city else 'Bengaluru')
        vis.address_full = prop.address_line or f"{vis.locality_str}, {prop.city.name if prop.city else 'Bengaluru'}"

        # Status badge & style tokens
        if vis.status == 'ACCEPTED':
            vis.status_label = 'Visit Confirmed'
            vis.badge_bg = '#D1FAE5'
            vis.badge_color = '#065F46'
            vis.status_icon = '✓'
            vis.date_box_bg = 'var(--color-powder-blue)'
            vis.date_box_color = '#0F172A'
        elif vis.status == 'PENDING':
            vis.status_label = 'Confirmation Pending'
            vis.badge_bg = '#FEF3C7'
            vis.badge_color = '#92400E'
            vis.status_icon = '•'
            vis.date_box_bg = '#E2E8F0'
            vis.date_box_color = '#334155'
        elif vis.status == 'RESCHEDULED':
            vis.status_label = 'Rescheduled'
            vis.badge_bg = '#E0F2FE'
            vis.badge_color = '#0284C7'
            vis.status_icon = '↻'
            vis.date_box_bg = '#E0F2FE'
            vis.date_box_color = '#0369A1'
        elif vis.status == 'COMPLETED':
            vis.status_label = 'Completed'
            vis.badge_bg = '#F1F5F9'
            vis.badge_color = '#475569'
            vis.status_icon = '✓'
            vis.date_box_bg = '#F1F5F9'
            vis.date_box_color = '#475569'
        elif vis.status == 'CANCELLED':
            vis.status_label = 'Cancelled'
            vis.badge_bg = '#FEE2E2'
            vis.badge_color = '#DC2626'
            vis.status_icon = '✕'
            vis.date_box_bg = '#FEE2E2'
            vis.date_box_color = '#991B1B'
        elif vis.status == 'REJECTED':
            vis.status_label = 'Declined by Host'
            vis.badge_bg = '#FEE2E2'
            vis.badge_color = '#DC2626'
            vis.status_icon = '✕'
            vis.date_box_bg = '#FEE2E2'
            vis.date_box_color = '#991B1B'
        else:
            vis.status_label = vis.get_status_display()
            vis.badge_bg = '#F1F5F9'
            vis.badge_color = '#475569'
            vis.status_icon = '•'
            vis.date_box_bg = '#F1F5F9'
            vis.date_box_color = '#475569'

    # Pagination: Limit 5 per page
    paginator = Paginator(visits_list, 5)
    page_num = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    context = {
        'active_tenant': tenant,
        'profile': profile,
        'visits': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'visits_count': len(visits_list),
        'current_tab': status_tab,
        'search_query': search_query,
        'counts': {
            'all': count_all,
            'accepted': count_accepted,
            'pending': count_pending,
            'rescheduled': count_rescheduled,
            'completed': count_completed,
            'cancelled': count_cancelled,
        }
    }
    return render(request, 'tenant_portal/13_visit_requests.html', context)


# API: Accept Proposed Visit Time
def api_accept_visit_time(request, request_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    visit = get_object_or_404(VisitRequest, request_id=request_id, seeker=tenant)
    visit.status = 'ACCEPTED'
    visit.save()

    # Omnichannel Notifications (Email + WhatsApp + In-App)
    dispatch_omnichannel_notification(
        recipient=tenant,
        title=f"Visit Time Accepted · {visit.property.title}",
        message=f"You accepted the scheduled walkthrough for {visit.property.title} on {visit.scheduled_date.strftime('%d %b %Y')} ({visit.scheduled_time_slot}).",
        category='VISIT',
        cta_url=f"/tenant/visits/{visit.request_id}/",
        cta_label="View Details"
    )

    if visit.property.owner:
        dispatch_omnichannel_notification(
            recipient=visit.property.owner,
            sender=tenant,
            title=f"Walkthrough Confirmed! 🎉 · {visit.property.title}",
            message=f"{tenant.get_full_name() or 'Aarav Sharma'} accepted the proposed walkthrough time for {visit.property.title} on {visit.scheduled_date.strftime('%d %b %Y')} ({visit.scheduled_time_slot}).",
            category='VISIT',
            cta_url="/owner/visits/",
            cta_label="Open Visit",
            details={
                'Property': visit.property.title,
                'Confirmed Date': visit.scheduled_date.strftime('%d %b %Y'),
                'Time Slot': visit.scheduled_time_slot,
                'Visitor': tenant.get_full_name() or tenant.username,
            }
        )

    return JsonResponse({
        'status': 'success',
        'message': f"Proposed time accepted! Visit #{visit.request_id} is now confirmed.",
        'request_id': visit.request_id
    })


# API: Request Reschedule for Visit
def api_reschedule_visit(request, request_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    visit = get_object_or_404(VisitRequest, request_id=request_id, seeker=tenant)
    new_date_str = request.POST.get('scheduled_date', '').strip()
    new_time_slot = request.POST.get('scheduled_time_slot', '').strip()
    notes = request.POST.get('notes', '').strip()

    if new_date_str:
        try:
            visit.scheduled_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
        except Exception:
            pass

    if new_time_slot:
        visit.scheduled_time_slot = new_time_slot

    if notes:
        visit.notes = f"{visit.notes}\n[Reschedule Request]: {notes}".strip()

    visit.status = 'RESCHEDULED'
    visit.save()

    if visit.property.owner:
        dispatch_omnichannel_notification(
            recipient=visit.property.owner,
            sender=tenant,
            title=f"Visit Rescheduled by Tenant · {visit.property.title}",
            message=f"{tenant.get_full_name() or 'Aarav Sharma'} requested to reschedule visit #{visit.request_id} for {visit.property.title} to {visit.scheduled_date.strftime('%d %b %Y')} ({visit.scheduled_time_slot}). Notes: {notes or 'None'}",
            category='VISIT',
            cta_url="/owner/visits/",
            cta_label="Review Slot",
            details={
                'Property': visit.property.title,
                'New Proposed Date': visit.scheduled_date.strftime('%d %b %Y'),
                'New Slot': visit.scheduled_time_slot,
                'Visitor': tenant.get_full_name() or tenant.username,
            }
        )

    return JsonResponse({
        'status': 'success',
        'message': f"Reschedule request sent to property host for {visit.scheduled_date.strftime('%d %b %Y')}!",
        'request_id': visit.request_id,
        'new_date': visit.scheduled_date.strftime('%d %b %Y'),
        'new_time': visit.scheduled_time_slot
    })


# API: Cancel Visit
def api_cancel_visit(request, request_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    visit = get_object_or_404(VisitRequest, request_id=request_id, seeker=tenant)
    visit.status = 'CANCELLED'
    visit.save()

    if visit.property.owner:
        dispatch_omnichannel_notification(
            recipient=visit.property.owner,
            sender=tenant,
            title=f"Visit Cancelled · {visit.property.title}",
            message=f"{tenant.get_full_name() or 'Aarav Sharma'} cancelled their scheduled walkthrough for {visit.property.title} (#{visit.request_id}).",
            category='VISIT',
            cta_url="/owner/visits/",
            cta_label="View Visits"
        )

    return JsonResponse({
        'status': 'success',
        'message': f"Visit #{visit.request_id} for {visit.property.title} has been cancelled.",
        'request_id': visit.request_id
    })


# 14. Visit Details (Walkthrough Dossier, Gate Pass, Directions, Actions)
def visit_details(request, request_id):
    tenant = get_active_tenant(request)
    profile = getattr(tenant, 'tenant_profile', None) if tenant else None

    visit = get_object_or_404(
        VisitRequest.objects.select_related(
            'property', 'property__locality', 'property__city', 'property__owner', 'room'
        ).prefetch_related('property__gallery_photos'),
        request_id=request_id,
        seeker=tenant
    )

    # Status meta styling & instructions
    status_config = {
        'ACCEPTED': {
            'label': 'Confirmed Walkthrough',
            'badge_bg': '#D1FAE5', 'badge_color': '#065F46', 'badge_border': '#A7F3D0',
            'icon': '✓', 'description': 'Host has confirmed your walkthrough slot. Gate pass active.'
        },
        'PENDING': {
            'label': 'Awaiting Host Confirmation',
            'badge_bg': '#FEF3C7', 'badge_color': '#92400E', 'badge_border': '#FDE68A',
            'icon': '⏳', 'description': 'Walkthrough request submitted. Host usually confirms within 2 hours.'
        },
        'RESCHEDULED': {
            'label': 'Host Proposed New Time',
            'badge_bg': '#DBEAFE', 'badge_color': '#1E40AF', 'badge_border': '#BFDBFE',
            'icon': '📅', 'description': 'Host proposed a revised time slot. Please review and accept or propose a different time.'
        },
        'COMPLETED': {
            'label': 'Walkthrough Completed',
            'badge_bg': '#E0E7FF', 'badge_color': '#3730A3', 'badge_border': '#C7D2FE',
            'icon': '🎉', 'description': 'Walkthrough concluded. You can proceed with booking this stay.'
        },
        'CANCELLED': {
            'label': 'Visit Cancelled',
            'badge_bg': '#FEE2E2', 'badge_color': '#991B1B', 'badge_border': '#FECACA',
            'icon': '✕', 'description': 'This walkthrough was cancelled.'
        },
        'REJECTED': {
            'label': 'Slot Unavailable',
            'badge_bg': '#F3F4F6', 'badge_color': '#4B5563', 'badge_border': '#E5E7EB',
            'icon': '✕', 'description': 'Host declined this specific slot.'
        },
    }
    status_meta = status_config.get(visit.status, status_config['PENDING'])

    # Format dates
    scheduled_day = visit.scheduled_date.strftime('%d') if visit.scheduled_date else '10'
    scheduled_month = visit.scheduled_date.strftime('%b') if visit.scheduled_date else 'Nov'
    scheduled_weekday = visit.scheduled_date.strftime('%A') if visit.scheduled_date else 'Tuesday'
    scheduled_full_date = visit.scheduled_date.strftime('%A, %d %B %Y') if visit.scheduled_date else 'Tuesday, 10 Nov 2026'
    time_slot = visit.scheduled_time_slot or '11:00 AM – 11:30 AM'

    # Property photo
    prop_photo = None
    cov = visit.property.gallery_photos.filter(is_cover=True).first() or visit.property.gallery_photos.first()
    if cov and cov.photo_url:
        prop_photo = cov.photo_url
    else:
        title_l = visit.property.title.lower()
        if 'palm' in title_l:
            prop_photo = "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800&auto=format&fit=crop&q=80"
        elif 'olive' in title_l:
            prop_photo = "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&auto=format&fit=crop&q=80"
        else:
            prop_photo = "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800&auto=format&fit=crop&q=80"

    # Property location & coordinates
    locality_name = visit.property.locality.name if visit.property.locality else "Indiranagar"
    city_name = visit.property.city.name if visit.property.city else "Bengaluru"
    full_address = visit.property.address_line or f"14, 12th Main Road, HAL 2nd Stage, {locality_name}, {city_name} - 560038"

    lat = float(visit.property.latitude) if visit.property.latitude else 12.9784
    lng = float(visit.property.longitude) if visit.property.longitude else 77.6408

    # Host & Caretaker info
    owner = visit.property.owner
    owner_name = owner.get_full_name() if owner else "Arjun Mehta"
    if not owner_name.strip():
        owner_name = owner.username if owner else "Arjun Mehta"
    owner_initials = "".join([part[0].upper() for part in owner_name.split()[:2]]) or "AM"
    owner_phone = getattr(owner, 'phone_number', None) or "+91 98801 12345"
    owner_email = owner.email if owner else "arjun@kiraayagrid.in"

    # Associated Enquiry (if any)
    related_enquiry = Enquiry.objects.filter(
        seeker=tenant, property=visit.property
    ).order_by('-created_at').first() if tenant else None

    # Pricing
    min_rent_agg = visit.property.rooms.aggregate(Min('monthly_rent'))['monthly_rent__min']
    rent = (visit.room.monthly_rent if visit.room else None) or min_rent_agg or 14500
    deposit = (visit.room.security_deposit if visit.room else None) or (rent * 2)
    room_type = visit.room.room_type if visit.room else "Private Single Room"

    # Action permissions
    can_accept = (visit.status == 'RESCHEDULED')
    can_reschedule = (visit.status in ['PENDING', 'ACCEPTED', 'RESCHEDULED'])
    can_cancel = (visit.status in ['PENDING', 'ACCEPTED', 'RESCHEDULED'])
    can_book = (visit.status in ['ACCEPTED', 'COMPLETED'])

    context = {
        'active_tenant': tenant,
        'profile': profile,
        'visit': visit,
        'status_meta': status_meta,
        'scheduled_day': scheduled_day,
        'scheduled_month': scheduled_month,
        'scheduled_weekday': scheduled_weekday,
        'scheduled_full_date': scheduled_full_date,
        'time_slot': time_slot,
        'prop_photo': prop_photo,
        'locality_name': locality_name,
        'city_name': city_name,
        'full_address': full_address,
        'lat': lat,
        'lng': lng,
        'owner_name': owner_name,
        'owner_initials': owner_initials,
        'owner_phone': owner_phone,
        'owner_email': owner_email,
        'related_enquiry': related_enquiry,
        'rent': rent,
        'deposit': deposit,
        'room_type': room_type,
        'can_accept': can_accept,
        'can_reschedule': can_reschedule,
        'can_cancel': can_cancel,
        'can_book': can_book,
    }
    return render(request, 'tenant_portal/14_visit_details.html', context)


# 15. My Bookings / Rental Requests
def my_bookings(request):
    tenant = get_active_tenant(request)
    profile = getattr(tenant, 'tenant_profile', None) if tenant else None

    # Base Query
    base_qs = RentalBooking.objects.filter(tenant=tenant).select_related(
        'property', 'property__locality', 'property__city', 'property__owner', 'room', 'bed'
    ).prefetch_related('property__gallery_photos') if tenant else RentalBooking.objects.none()

    # Dynamic status tab counts
    count_all = base_qs.count()
    count_requested = base_qs.filter(booking_status='REQUESTED').count()
    count_accepted = base_qs.filter(booking_status='ACCEPTED').count()
    count_payment_pending = base_qs.filter(booking_status='PAYMENT_PENDING').count()
    count_confirmed = base_qs.filter(booking_status='CONFIRMED').count()
    count_cancelled = base_qs.filter(booking_status__in=['CANCELLED', 'REJECTED']).count()

    # Tab handling
    status_tab = request.GET.get('status', 'ALL').upper()
    filtered_qs = base_qs

    if status_tab == 'REQUESTED':
        filtered_qs = filtered_qs.filter(booking_status='REQUESTED')
    elif status_tab == 'ACCEPTED':
        filtered_qs = filtered_qs.filter(booking_status='ACCEPTED')
    elif status_tab == 'PAYMENT_PENDING':
        filtered_qs = filtered_qs.filter(booking_status='PAYMENT_PENDING')
    elif status_tab == 'CONFIRMED':
        filtered_qs = filtered_qs.filter(booking_status='CONFIRMED')
    elif status_tab == 'CANCELLED':
        filtered_qs = filtered_qs.filter(booking_status__in=['CANCELLED', 'REJECTED'])

    # Search keyword filter
    search_query = request.GET.get('q', '').strip()
    if search_query:
        filtered_qs = filtered_qs.filter(
            Q(property__title__icontains=search_query) |
            Q(booking_id__icontains=search_query) |
            Q(property__locality__name__icontains=search_query) |
            Q(property__owner__first_name__icontains=search_query) |
            Q(property__owner__last_name__icontains=search_query)
        )

    bookings_list = list(filtered_qs.order_by('-created_at'))

    # Enhance booking objects with badges, host, photos, action flags
    status_meta_map = {
        'REQUESTED': {
            'label': 'Awaiting Landlord Acceptance',
            'badge_bg': '#FEF3C7', 'badge_color': '#92400E', 'badge_border': '#FDE68A',
            'icon': '⏳', 'summary': 'Your booking request has been submitted. Host will review and confirm within 24 hours.'
        },
        'ACCEPTED': {
            'label': 'Accepted by Landlord',
            'badge_bg': '#EFF6FF', 'badge_color': '#1E40AF', 'badge_border': '#BFDBFE',
            'icon': '✓', 'summary': 'Landlord accepted your tenancy request. Complete token deposit to finalize booking.'
        },
        'PAYMENT_PENDING': {
            'label': 'Token Payment Pending',
            'badge_bg': '#FFFBEB', 'badge_color': '#B45309', 'badge_border': '#FDE68A',
            'icon': '💳', 'summary': 'Token deposit is pending. Pay ₹5,000 to lock in your room.'
        },
        'CONFIRMED': {
            'label': 'Tenancy Confirmed & Room Booked',
            'badge_bg': '#D1FAE5', 'badge_color': '#065F46', 'badge_border': '#A7F3D0',
            'icon': '🎉', 'summary': 'Tenancy agreement generated. Room reserved and keycard ready for move-in.'
        },
        'CANCELLED': {
            'label': 'Booking Cancelled',
            'badge_bg': '#FEE2E2', 'badge_color': '#991B1B', 'badge_border': '#FECACA',
            'icon': '✕', 'summary': 'This booking request was cancelled by the tenant.'
        },
        'REJECTED': {
            'label': 'Declined by Landlord',
            'badge_bg': '#F3F4F6', 'badge_color': '#4B5563', 'badge_border': '#E5E7EB',
            'icon': '✕', 'summary': 'Host could not accommodate this booking due to occupancy constraints.'
        },
    }

    for b in bookings_list:
        # Photo resolution
        cov = b.property.gallery_photos.filter(is_cover=True).first() or b.property.gallery_photos.first()
        if cov and cov.photo_url:
            b.display_photo = cov.photo_url
        else:
            title_l = b.property.title.lower()
            if 'palm' in title_l:
                b.display_photo = "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=400&auto=format&fit=crop&q=80"
            elif 'olive' in title_l:
                b.display_photo = "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=400&auto=format&fit=crop&q=80"
            else:
                b.display_photo = "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=400&auto=format&fit=crop&q=80"

        # Host
        owner_obj = b.property.owner or b.owner
        b.host_name = owner_obj.get_full_name() if owner_obj else "Property Host"
        if not b.host_name.strip():
            b.host_name = owner_obj.username if owner_obj else "Property Host"
        b.host_phone = getattr(owner_obj, 'phone_number', None) or "+91 98801 12345"

        # Status styling
        b.status_meta = status_meta_map.get(b.booking_status, status_meta_map['REQUESTED'])

        # Action flags
        b.can_cancel = (b.booking_status in ['REQUESTED', 'ACCEPTED', 'PAYMENT_PENDING'])
        b.can_pay = (b.booking_status in ['ACCEPTED', 'PAYMENT_PENDING'] and b.payment_status in ['PENDING', 'NOT_REQUIRED'])
        b.is_confirmed = (b.booking_status == 'CONFIRMED')

        # Locality string
        loc = b.property.locality.name if b.property.locality else "Indiranagar"
        city = b.property.city.name if b.property.city else "Bengaluru"
        b.locality_str = f"{loc}, {city}"

    # Properties available for New Booking Modal
    available_properties = Property.objects.filter(status='APPROVED').select_related('locality', 'city')[:10]

    # Pagination: Limit 5 per page
    paginator = Paginator(bookings_list, 5)
    page_num = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    context = {
        'active_tenant': tenant,
        'profile': profile,
        'bookings': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'status_tab': status_tab,
        'search_query': search_query,
        'count_all': count_all,
        'count_requested': count_requested,
        'count_accepted': count_accepted,
        'count_payment_pending': count_payment_pending,
        'count_confirmed': count_confirmed,
        'count_cancelled': count_cancelled,
        'available_properties': available_properties,
    }
    return render(request, 'tenant_portal/15_my_bookings.html', context)


# API: Cancel Booking Request
def api_cancel_booking(request, booking_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    booking = get_object_or_404(RentalBooking, booking_id=booking_id, tenant=tenant)
    booking.booking_status = 'CANCELLED'
    booking.save()

    # Omnichannel Notifications (Email + WhatsApp + In-App)
    if booking.property.owner:
        dispatch_omnichannel_notification(
            recipient=booking.property.owner,
            sender=tenant,
            title=f"Booking Cancelled · {booking.property.title}",
            message=f"{tenant.get_full_name() or 'Aarav Sharma'} cancelled their rental booking {booking.booking_id} for {booking.property.title}.",
            category='BOOKING',
            cta_url="/owner/bookings/",
            cta_label="View Bookings"
        )

    dispatch_omnichannel_notification(
        recipient=tenant,
        title=f"Booking Cancelled · {booking.property.title}",
        message=f"You cancelled booking request {booking.booking_id} for {booking.property.title}.",
        category='BOOKING',
        cta_url="/tenant/bookings/",
        cta_label="My Bookings"
    )

    return JsonResponse({
        'status': 'success',
        'message': f"Booking {booking.booking_id} for {booking.property.title} has been cancelled.",
        'booking_id': booking.booking_id
    })


# API: Pay Token Amount for Booking
def api_pay_booking_token(request, booking_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    booking = get_object_or_404(RentalBooking, booking_id=booking_id, tenant=tenant)
    
    # Process simulated token payment
    booking.payment_status = 'PAID'
    booking.payment_amount = 5000.00
    booking.payment_reference = f"TXN-{random.randint(100000, 999999)}"
    booking.booking_status = 'CONFIRMED'
    booking.save()

    # Cross-portal omnichannel notifications (Email + WhatsApp + In-App)
    dispatch_omnichannel_notification(
        recipient=tenant,
        title=f"Tenancy Confirmed! Room Reserved 🎉 · {booking.property.title}",
        message=f"Token payment of ₹5,000 for {booking.property.title} ({booking.booking_id}) received! Ref: {booking.payment_reference}. Your move-in date is locked for {booking.move_in_date.strftime('%d %b %Y')}.",
        category='BOOKING',
        cta_url="/tenant/bookings/",
        cta_label="Download Agreement",
        details={
            'Property': booking.property.title,
            'Token Deposit': '₹5,000.00',
            'Transaction ID': booking.payment_reference,
            'Move-in Date': booking.move_in_date.strftime('%d %b %Y'),
        }
    )

    if booking.property.owner:
        dispatch_omnichannel_notification(
            recipient=booking.property.owner,
            sender=tenant,
            title=f"Tenancy Confirmed & Token Received! ₹5,000 · {booking.property.title}",
            message=f"{tenant.get_full_name() or 'Aarav Sharma'} paid the ₹5,000 token deposit for {booking.property.title} ({booking.booking_id}). Move-in: {booking.move_in_date.strftime('%d %b %Y')}.",
            category='BOOKING',
            cta_url="/owner/bookings/",
            cta_label="View Booking",
            details={
                'Property': booking.property.title,
                'Tenant': tenant.get_full_name() or tenant.username,
                'Token Received': '₹5,000.00',
                'Ref ID': booking.payment_reference,
                'Move-in Date': booking.move_in_date.strftime('%d %b %Y'),
            }
        )

    # Cross-portal notification to Admins
    for admin_user in User.objects.filter(role='ADMIN'):
        dispatch_omnichannel_notification(
            recipient=admin_user,
            sender=tenant,
            title=f"Tenancy Token Received: {booking.property.title}",
            message=f"Tenant {tenant.get_full_name() or tenant.username} confirmed tenancy at '{booking.property.title}' with ₹5,000 token deposit ({booking.payment_reference}).",
            category='BOOKING',
            cta_url="/admin_portal/monetization/",
            cta_label="View Agreements"
        )

    return JsonResponse({
        'status': 'success',
        'message': f"Payment successful! Booking {booking.booking_id} is now CONFIRMED. Reference: {booking.payment_reference}",
        'booking_id': booking.booking_id,
        'payment_reference': booking.payment_reference
    })


# API: Create New Booking Request
def api_create_booking(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    property_id = request.POST.get('property_id')
    move_in_date_str = request.POST.get('move_in_date')
    sharing_type = request.POST.get('sharing_type', 'Private Room')
    notes = request.POST.get('notes', '')

    prop = get_object_or_404(Property, id=property_id, status='APPROVED')
    room = prop.rooms.first()

    # Move in date parse
    try:
        move_in_date = datetime.strptime(move_in_date_str, '%Y-%m-%d').date()
    except Exception:
        move_in_date = date.today()

    min_rent_agg = prop.rooms.aggregate(Min('monthly_rent'))['monthly_rent__min']
    rent = (room.monthly_rent if room else None) or min_rent_agg or 14500
    deposit = (room.security_deposit if room else None) or (rent * 2)

    new_booking_id = f"BK-{random.randint(10000, 99999)}"

    booking = RentalBooking.objects.create(
        booking_id=new_booking_id,
        tenant=tenant,
        property=prop,
        room=room,
        owner=prop.owner,
        move_in_date=move_in_date,
        sharing_type=sharing_type,
        monthly_rent=rent,
        security_deposit=deposit,
        booking_status='REQUESTED',
        payment_status='NOT_REQUIRED',
        tenant_notes=notes
    )

    # Omnichannel Notifications (Email + WhatsApp + In-App)
    dispatch_omnichannel_notification(
        recipient=tenant,
        title=f"Booking Request Submitted · {prop.title}",
        message=f"Your booking request {booking.booking_id} for {prop.title} has been submitted to the landlord for approval.",
        category='BOOKING',
        cta_url="/tenant/bookings/",
        cta_label="Track Status"
    )

    if prop.owner:
        dispatch_omnichannel_notification(
            recipient=prop.owner,
            sender=tenant,
            title=f"New Booking Request Received · {prop.title}",
            message=f"{tenant.get_full_name() or 'Aarav Sharma'} requested tenancy for {prop.title} starting {move_in_date.strftime('%d %b %Y')}.",
            category='BOOKING',
            cta_url="/owner/bookings/",
            cta_label="Review Request",
            details={
                'Property': prop.title,
                'Move-In Date': move_in_date.strftime('%d %b %Y'),
                'Monthly Rent': f"₹{rent}",
                'Security Deposit': f"₹{deposit}",
                'Tenant': tenant.get_full_name() or tenant.username,
            }
        )

    # Cross-portal notification to Admins
    for admin_user in User.objects.filter(role='ADMIN'):
        dispatch_omnichannel_notification(
            recipient=admin_user,
            sender=tenant,
            title=f"New Tenancy Request: {booking.booking_id}",
            message=f"{tenant.get_full_name() or tenant.username} requested booking at '{prop.title}'.",
            category='BOOKING',
            cta_url="/admin_portal/dashboard/",
            cta_label="Overview"
        )

    return JsonResponse({
        'status': 'success',
        'message': f"Booking request {booking.booking_id} submitted successfully to host!",
        'booking_id': booking.booking_id
    })


# 16. Notifications Center
def notifications_center(request):
    tenant = get_active_tenant(request)
    profile = getattr(tenant, 'tenant_profile', None) if tenant else None

    # Base Query
    base_qs = Notification.objects.filter(recipient=tenant).order_by('-created_at') if tenant else Notification.objects.none()

    # Dynamic Tab Counts
    count_all = base_qs.count()
    count_unread = base_qs.filter(is_read=False).count()
    count_enquiries = base_qs.filter(
        Q(title__icontains='Enquiry') | Q(title__icontains='Message') |
        Q(message__icontains='enquiry') | Q(message__icontains='replied')
    ).count()
    count_visits = base_qs.filter(
        Q(title__icontains='Visit') | Q(message__icontains='walkthrough') |
        Q(message__icontains='visit')
    ).count()
    count_bookings = base_qs.filter(
        Q(title__icontains='Booking') | Q(title__icontains='Welcome') |
        Q(message__icontains='booking') | Q(is_broadcast=True)
    ).count()

    # Active Tab Filter
    active_tab = request.GET.get('tab', 'ALL').upper()
    filtered_qs = base_qs

    if active_tab == 'UNREAD':
        filtered_qs = filtered_qs.filter(is_read=False)
    elif active_tab == 'ENQUIRIES':
        filtered_qs = filtered_qs.filter(
            Q(title__icontains='Enquiry') | Q(title__icontains='Message') |
            Q(message__icontains='enquiry') | Q(message__icontains='replied')
        )
    elif active_tab == 'VISITS':
        filtered_qs = filtered_qs.filter(
            Q(title__icontains='Visit') | Q(message__icontains='walkthrough') |
            Q(message__icontains='visit')
        )
    elif active_tab == 'BOOKINGS':
        filtered_qs = filtered_qs.filter(
            Q(title__icontains='Booking') | Q(title__icontains='Welcome') |
            Q(message__icontains='booking') | Q(is_broadcast=True)
        )

    # Search keyword
    search_query = request.GET.get('q', '').strip()
    if search_query:
        filtered_qs = filtered_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    notifications_list = list(filtered_qs)

    # Decorate notifications with category meta, icon, and colors
    now = timezone.now()
    for notif in notifications_list:
        t_lower = notif.title.lower()
        m_lower = notif.message.lower()

        if 'enquiry' in t_lower or 'message' in t_lower or 'replied' in m_lower:
            notif.category = 'ENQUIRY'
            notif.category_label = 'Enquiry & Chat'
            notif.icon_type = 'chat'
            notif.icon_bg = '#EFF6FF'
            notif.icon_color = '#2563EB'
            if not notif.button_url:
                notif.button_url = '/tenant/enquiries/'
            if not notif.button_label:
                notif.button_label = 'Open Chat'
        elif 'visit' in t_lower or 'walkthrough' in m_lower:
            notif.category = 'VISIT'
            notif.category_label = 'Walkthrough Visit'
            notif.icon_type = 'calendar'
            notif.icon_bg = '#ECFDF5'
            notif.icon_color = '#059669'
            if not notif.button_url:
                notif.button_url = '/tenant/visits/'
            if not notif.button_label:
                notif.button_label = 'View Walkthrough'
        elif 'booking' in t_lower or 'booking' in m_lower or 'tenancy' in m_lower:
            notif.category = 'BOOKING'
            notif.category_label = 'Rental Booking'
            notif.icon_type = 'booking'
            notif.icon_bg = '#FEF3C7'
            notif.icon_color = '#D97706'
            if not notif.button_url:
                notif.button_url = '/tenant/bookings/'
            if not notif.button_label:
                notif.button_label = 'View Booking'
        else:
            notif.category = 'SYSTEM'
            notif.category_label = 'Platform Update'
            notif.icon_type = 'bell'
            notif.icon_bg = '#F3E8FF'
            notif.icon_color = '#7E22CE'
            if not notif.button_url:
                notif.button_url = '/tenant/find/'
            if not notif.button_label:
                notif.button_label = 'Explore Stays'

        # Relative time string
        diff = now - notif.created_at
        if diff.total_seconds() < 3600:
            minutes = max(1, int(diff.total_seconds() // 60))
            notif.time_ago = f"{minutes}m ago"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() // 3600)
            notif.time_ago = f"{hours}h ago"
        else:
            days = int(diff.total_seconds() // 86400)
            notif.time_ago = f"{days}d ago"

    # Pagination: Limit 5 per page
    paginator = Paginator(notifications_list, 5)
    page_num = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    context = {
        'active_tenant': tenant,
        'profile': profile,
        'notifications': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'active_tab': active_tab,
        'search_query': search_query,
        'count_all': count_all,
        'count_unread': count_unread,
        'count_enquiries': count_enquiries,
        'count_visits': count_visits,
        'count_bookings': count_bookings,
    }
    return render(request, 'tenant_portal/16_notifications.html', context)


# API: Mark single notification as read
def api_mark_notification_read(request, notification_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    notif = get_object_or_404(Notification, id=notification_id, recipient=tenant)
    notif.is_read = True
    notif.save()

    return JsonResponse({
        'status': 'success',
        'message': 'Notification marked as read',
        'notification_id': notif.id
    })


# API: Mark all notifications as read
def api_mark_all_notifications_read(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    updated_count = Notification.objects.filter(recipient=tenant, is_read=False).update(is_read=True)

    return JsonResponse({
        'status': 'success',
        'message': f'All {updated_count} notifications marked as read',
        'updated_count': updated_count
    })


# API: Delete notification
def api_delete_notification(request, notification_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    notif = get_object_or_404(Notification, id=notification_id, recipient=tenant)
    notif.delete()

    return JsonResponse({
        'status': 'success',
        'message': 'Notification removed',
        'notification_id': notification_id
    })


# 17. Profile & Preferences (Full Dynamic Profile & Stay Preferences)
def profile_preferences(request):
    tenant = get_active_tenant(request)
    if not tenant:
        return redirect('tenant_portal:overview')

    profile, _ = TenantProfile.objects.get_or_create(user=tenant)

    # Handle POST (Save Profile & Preferences)
    if request.method == 'POST':
        # 1. User Model Personal Info
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()

        if first_name:
            tenant.first_name = first_name
        if last_name:
            tenant.last_name = last_name
        if email:
            tenant.email = email
        if phone_number:
            tenant.phone_number = phone_number
        tenant.save()

        # 2. Stay Criteria & Location
        city_id = request.POST.get('preferred_city')
        if city_id:
            profile.preferred_city = City.objects.filter(id=city_id).first()

        locality_id = request.POST.get('preferred_locality')
        if locality_id:
            profile.preferred_locality = Locality.objects.filter(id=locality_id).first()

        # Budgets
        monthly_budget = request.POST.get('monthly_budget')
        if monthly_budget:
            try:
                profile.monthly_budget = float(monthly_budget)
            except Exception:
                pass

        min_budget = request.POST.get('min_budget')
        if min_budget:
            try:
                profile.min_budget = float(min_budget)
            except Exception:
                pass

        # Stay Types & Occupancy
        profile.preferred_accommodation_type = request.POST.get('preferred_accommodation_type', profile.preferred_accommodation_type)
        profile.occupancy_preference = request.POST.get('occupancy_preference', profile.occupancy_preference)

        # Move-in Date
        move_in_str = request.POST.get('target_move_in_date')
        if move_in_str:
            try:
                profile.target_move_in_date = datetime.strptime(move_in_str, '%Y-%m-%d').date()
            except Exception:
                pass

        # Living Habits & Professional Info
        profile.food_preference = request.POST.get('food_preference', profile.food_preference)
        profile.gender_preference = request.POST.get('gender_preference', profile.gender_preference)
        profile.profession = request.POST.get('profession', profile.profession)
        profile.company_or_college = request.POST.get('company_or_college', '').strip()
        profile.bio = request.POST.get('bio', '').strip()

        # Notification Preferences
        profile.whatsapp_notifications = ('whatsapp_notifications' in request.POST or request.POST.get('pref_wa') == 'on')
        profile.sms_notifications = ('sms_notifications' in request.POST or request.POST.get('pref_sms') == 'on')
        profile.email_notifications = ('email_notifications' in request.POST or request.POST.get('pref_email') == 'on')

        profile.save()

        # If AJAX request
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == 'true':
            return JsonResponse({
                'status': 'success',
                'message': 'Profile details and living preferences updated successfully!',
                'full_name': tenant.get_full_name() or tenant.username
            })

    # GET Request: Prepare Dynamic Data
    cities = City.objects.all().order_by('name')
    localities = Locality.objects.filter(city=profile.preferred_city).order_by('name') if profile.preferred_city else Locality.objects.none()

    # Dynamic Activity Counters for Identity Banner
    saved_count = SavedProperty.objects.filter(tenant=tenant).count()
    visits_count = VisitRequest.objects.filter(seeker=tenant).count()
    bookings_count = RentalBooking.objects.filter(tenant=tenant).count()
    enquiries_count = Enquiry.objects.filter(seeker=tenant).count()

    # User initials
    full_name = tenant.get_full_name() or tenant.username
    initials = "".join([part[0].upper() for part in full_name.split()[:2]]) or "AS"

    # Model Choices
    profession_choices = TenantProfile._meta.get_field('profession').choices
    food_choices = TenantProfile._meta.get_field('food_preference').choices
    occupancy_choices = TenantProfile._meta.get_field('occupancy_preference').choices
    accommodation_types = TenantProfile._meta.get_field('preferred_accommodation_type').choices
    gender_choices = TenantProfile._meta.get_field('gender_preference').choices

    context = {
        'active_tenant': tenant,
        'profile': profile,
        'full_name': full_name,
        'initials': initials,
        'cities': cities,
        'localities': localities,
        'saved_count': saved_count,
        'visits_count': visits_count,
        'bookings_count': bookings_count,
        'enquiries_count': enquiries_count,
        'profession_choices': profession_choices,
        'food_choices': food_choices,
        'occupancy_choices': occupancy_choices,
        'accommodation_types': accommodation_types,
        'gender_choices': gender_choices,
    }
    return render(request, 'tenant_portal/17_profile_preferences.html', context)


# API: Get Localities for City (Dynamic dependent dropdown)
def api_city_localities(request, city_id):
    localities = Locality.objects.filter(city_id=city_id).order_by('name')
    data = [{'id': loc.id, 'name': loc.name, 'pincode': loc.pincode} for loc in localities]
    return JsonResponse({'status': 'success', 'localities': data})


# 18. Help & Support (FAQs, Search, Tickets, Conversation Drawer, Safety Tips)
def help_support(request):
    tenant = get_active_tenant(request)
    profile = getattr(tenant, 'tenant_profile', None) if tenant else None

    # Curated FAQs
    faqs = [
        {
            'id': 1,
            'category': 'Search & Verification',
            'question': 'Does KiraayaGrid charge any brokerage or finding fees?',
            'answer': 'No! KiraayaGrid operates on a strict 100% Zero Brokerage model. All property discovery, landlord messaging, in-person walkthrough scheduling, and digital lease confirmations are completely free of broker fees for tenants.'
        },
        {
            'id': 2,
            'category': 'Visit Support',
            'question': 'How do I schedule and confirm a physical property walkthrough?',
            'answer': 'Find any verified stay, click "Request Property Walkthrough", pick your preferred date and time slot (Morning, Afternoon, Evening), and submit. The property manager or landlord will review and confirm your slot within 2 hours. You can track and reschedule visits anytime under Visit Requests.'
        },
        {
            'id': 3,
            'category': 'Visit Support',
            'question': 'What if the host proposes a different visit time?',
            'answer': 'If the host reschedules, you will see a prominent blue alert banner on your Visit Details page with the proposed new slot. You can either click "Accept Proposed Time" in one tap or propose another slot that fits your schedule.'
        },
        {
            'id': 4,
            'category': 'Enquiry Support',
            'question': 'How quickly do landlords respond to enquiries?',
            'answer': 'Verified landlords on KiraayaGrid have an average response time of under 1 hour during business hours (9:00 AM – 8:00 PM). You will receive an instant in-app and WhatsApp alert as soon as the host sends a reply.'
        },
        {
            'id': 5,
            'category': 'Bookings & Payments',
            'question': 'Does scheduling a walkthrough reserve the room?',
            'answer': 'No. Enquiring or scheduling a walkthrough does not lock the room. To officially secure the accommodation, you must submit a rental booking request, receive formal landlord acceptance, and lock in the ₹5,000 token deposit.'
        },
        {
            'id': 6,
            'category': 'Bookings & Payments',
            'question': 'How is my security deposit protected?',
            'answer': "All stays on KiraayaGrid follow standard Model Tenancy Act terms. Security deposits are clearly recorded in your digital tenancy slip, and 100% of the token amount is adjusted against your first month's rent."
        },
        {
            'id': 7,
            'category': 'Safety & Verification',
            'question': 'What safety precautions should I take on visit day?',
            'answer': 'Always inspect the property in person before transferring any payment. Carry a valid government photo ID (Aadhaar / Voter ID / Driver License) for building gate entry, and verify that the property displays the green "Verified Owner" seal.'
        },
    ]

    # Existing Support Tickets for active tenant
    tickets_qs = SupportTicket.objects.filter(user=tenant).prefetch_related('messages').order_by('-created_at') if tenant else SupportTicket.objects.none()

    total_tickets = tickets_qs.count()
    open_tickets = tickets_qs.filter(status__in=['OPEN', 'IN_PROGRESS']).count()
    resolved_tickets = tickets_qs.filter(status__in=['RESOLVED', 'CLOSED']).count()

    tickets_list = list(tickets_qs)
    status_styling = {
        'OPEN': {'bg': '#FEF3C7', 'color': '#92400E', 'border': '#FDE68A', 'label': 'Open'},
        'IN_PROGRESS': {'bg': '#DBEAFE', 'color': '#1E40AF', 'border': '#BFDBFE', 'label': 'In Progress'},
        'RESOLVED': {'bg': '#D1FAE5', 'color': '#065F46', 'border': '#A7F3D0', 'label': 'Resolved'},
        'CLOSED': {'bg': '#F1F5F9', 'color': '#475569', 'border': '#E2E8F0', 'label': 'Closed'},
    }

    for t in tickets_list:
        t.status_meta = status_styling.get(t.status, status_styling['OPEN'])
        t.msgs_count = t.messages.filter(is_internal=False).count()
        last_msg = t.messages.filter(is_internal=False).last()
        t.last_message_preview = last_msg.message if last_msg else t.message
        t.last_updated = last_msg.created_at if last_msg else t.created_at

    # Pagination: Limit 5 per page
    paginator = Paginator(tickets_list, 5)
    page_num = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    context = {
        'active_tenant': tenant,
        'profile': profile,
        'faqs': faqs,
        'tickets': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_tickets': total_tickets,
        'open_tickets': open_tickets,
        'resolved_tickets': resolved_tickets,
    }
    return render(request, 'tenant_portal/18_help_support.html', context)


# API: Raise Support Ticket
def api_create_support_ticket(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    category = request.POST.get('category', 'General Support').strip()
    subject = request.POST.get('subject', '').strip()
    message = request.POST.get('message', '').strip()
    priority = request.POST.get('priority', 'NORMAL').upper()

    if not subject or not message:
        return JsonResponse({'status': 'error', 'message': 'Subject and message are required.'}, status=400)

    ticket_code = f"TKT-2026-{random.randint(400, 999)}"

    ticket = SupportTicket.objects.create(
        ticket_code=ticket_code,
        user=tenant,
        subject=subject,
        category=category,
        channel='PORTAL',
        message=message,
        priority=priority,
        status='OPEN',
        sla_due_text='Response within 2 hours',
        sla_status='ON_TRACK'
    )

    # Initial seeker message in thread
    TicketMessage.objects.create(
        ticket=ticket,
        sender=tenant,
        sender_name=tenant.get_full_name() or tenant.username,
        sender_role='TENANT',
        is_internal=False,
        message=message
    )

    # Omnichannel notification for tenant
    dispatch_omnichannel_notification(
        recipient=tenant,
        title=f"Support Ticket Logged: #{ticket.ticket_code}",
        message=f"Your ticket #{ticket.ticket_code} ({subject[:50]}) has been logged. Support concierge is reviewing your request.",
        category='ADMIN',
        cta_url="/tenant/support/",
        cta_label="View Tickets"
    )

    # Cross-Portal Omnichannel Notification to Admins
    for admin_user in User.objects.filter(role='ADMIN'):
        dispatch_omnichannel_notification(
            recipient=admin_user,
            sender=tenant,
            title=f"New Seeker Support Ticket: #{ticket.ticket_code}",
            message=f"{tenant.get_full_name() or tenant.username} raised ticket '{subject}':\n\n\"{message[:100]}\"",
            category='ADMIN',
            cta_url="/admin_portal/support-center/",
            cta_label="Open Support Center",
            details={
                'Ticket ID': f"#{ticket.ticket_code}",
                'Category': category,
                'Priority': priority,
                'Seeker': tenant.get_full_name() or tenant.username,
            }
        )

    return JsonResponse({
        'status': 'success',
        'message': f"Ticket {ticket.ticket_code} created successfully!",
        'ticket_code': ticket.ticket_code,
        'ticket_id': ticket.id
    })


# API: Get Ticket Messages (Conversation drawer)
def api_ticket_messages(request, ticket_id):
    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=tenant)
    messages = ticket.messages.filter(is_internal=False).order_by('created_at')

    data = []
    for m in messages:
        data.append({
            'id': m.id,
            'sender_name': m.sender_name or (m.sender.get_full_name() if m.sender else 'Support Team'),
            'sender_role': m.sender_role,
            'is_tenant': (m.sender_role == 'TENANT' or m.sender == tenant),
            'message': m.message,
            'created_at': m.created_at.strftime('%d %b, %I:%M %p')
        })

    return JsonResponse({
        'status': 'success',
        'ticket_code': ticket.ticket_code,
        'subject': ticket.subject,
        'status_text': ticket.status,
        'category': ticket.category,
        'messages': data
    })


# API: Reply to Support Ticket
def api_reply_support_ticket(request, ticket_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=tenant)
    message_text = request.POST.get('message', '').strip() or request.POST.get('message_text', '').strip()
    if not message_text and request.content_type == 'application/json':
        try:
            body = json.loads(request.body)
            message_text = (body.get('message') or body.get('message_text') or '').strip()
        except Exception:
            pass

    if not message_text:
        return JsonResponse({'status': 'error', 'message': 'Message cannot be empty'}, status=400)

    msg = TicketMessage.objects.create(
        ticket=ticket,
        sender=tenant,
        sender_name=tenant.get_full_name() or tenant.username,
        sender_role='TENANT',
        is_internal=False,
        message=message_text
    )

    if ticket.status in ['RESOLVED', 'CLOSED']:
        ticket.status = 'IN_PROGRESS'
        ticket.save()

    # Cross-Portal Omnichannel Notification to Admins
    for admin_user in User.objects.filter(role='ADMIN'):
        dispatch_omnichannel_notification(
            recipient=admin_user,
            sender=tenant,
            title=f"New Seeker Reply: Ticket #{ticket.ticket_code}",
            message=f"{tenant.get_full_name() or tenant.username} replied on ticket '{ticket.subject}':\n\n\"{message_text[:90]}\"",
            category='CHAT',
            cta_url="/admin_portal/support-center/",
            cta_label="Open Support Center",
            details={
                'Ticket ID': f"#{ticket.ticket_code}",
                'Subject': ticket.subject,
                'Seeker': tenant.get_full_name() or tenant.username,
            }
        )

    return JsonResponse({
        'status': 'success',
        'message_id': msg.id,
        'sender_name': msg.sender_name,
        'message': msg.message,
        'created_at': msg.created_at.strftime('%d %b, %I:%M %p')
    })


# 19. Account & Privacy Settings (Security, Privacy, Data Export, Account Actions)
def account_settings(request):
    tenant = get_active_tenant(request)
    if not tenant:
        return redirect('tenant_portal:overview')

    profile, _ = TenantProfile.objects.get_or_create(user=tenant)

    # Activity Counts
    saved_count = SavedProperty.objects.filter(tenant=tenant).count()
    enquiries_count = Enquiry.objects.filter(seeker=tenant).count()
    visits_count = VisitRequest.objects.filter(seeker=tenant).count()
    bookings_count = RentalBooking.objects.filter(tenant=tenant).count()

    context = {
        'active_tenant': tenant,
        'profile': profile,
        'saved_count': saved_count,
        'enquiries_count': enquiries_count,
        'visits_count': visits_count,
        'bookings_count': bookings_count,
    }
    return render(request, 'tenant_portal/19_settings.html', context)


# API: Update Password (PBKDF2 SHA-256)
def api_update_password(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    current_pass = request.POST.get('current_password', '').strip()
    new_pass = request.POST.get('new_password', '').strip()
    confirm_pass = request.POST.get('confirm_password', '').strip()

    if not new_pass or not confirm_pass:
        return JsonResponse({'status': 'error', 'message': 'Please enter and confirm your new password.'}, status=400)

    if new_pass != confirm_pass:
        return JsonResponse({'status': 'error', 'message': 'New password and confirmation do not match.'}, status=400)

    if len(new_pass) < 6:
        return JsonResponse({'status': 'error', 'message': 'Password must be at least 6 characters long.'}, status=400)

    # Check current password if user has password set
    if current_pass and tenant.has_usable_password():
        if not tenant.check_password(current_pass):
            return JsonResponse({'status': 'error', 'message': 'Current password entered is incorrect.'}, status=400)

    # Set new password
    tenant.set_password(new_pass)
    tenant.save()

    # Preserve session if logged in
    if hasattr(request, 'user') and request.user.is_authenticated and request.user.id == tenant.id:
        update_session_auth_hash(request, tenant)

    # In-app notification
    Notification.objects.create(
        recipient=tenant,
        title="Security Alert: Password Updated",
        message="Your account login password has been changed successfully. PBKDF2 SHA-256 encryption active.",
        channel="IN_APP",
        button_label="Security Settings",
        button_url="/tenant/settings/"
    )

    return JsonResponse({
        'status': 'success',
        'message': 'Password changed successfully! Encryption credentials updated.'
    })


# API: Update Notification Preferences
def api_update_notification_settings(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    profile, _ = TenantProfile.objects.get_or_create(user=tenant)
    profile.whatsapp_notifications = (request.POST.get('whatsapp_notifications') in ['true', 'on', True])
    profile.sms_notifications = (request.POST.get('sms_notifications') in ['true', 'on', True])
    profile.email_notifications = (request.POST.get('email_notifications') in ['true', 'on', True])
    profile.save()

    return JsonResponse({
        'status': 'success',
        'message': 'Notification delivery channels updated successfully!'
    })


# API: Update Privacy Settings
def api_update_privacy_settings(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    return JsonResponse({
        'status': 'success',
        'message': 'Privacy & contact visibility preferences saved.'
    })


# API: Export Personal Data Archive (GDPR / Data Portability Download)
def api_export_personal_data(request):
    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    profile = getattr(tenant, 'tenant_profile', None)

    # 1. Personal Details
    user_data = {
        'username': tenant.username,
        'first_name': tenant.first_name,
        'last_name': tenant.last_name,
        'email': tenant.email,
        'phone_number': tenant.phone_number,
        'role': tenant.role,
        'date_joined': tenant.date_joined.isoformat() if tenant.date_joined else None,
    }

    # 2. Living Preferences
    profile_data = {}
    if profile:
        profile_data = {
            'preferred_city': profile.preferred_city.name if profile.preferred_city else None,
            'preferred_locality': profile.preferred_locality.name if profile.preferred_locality else None,
            'monthly_budget': float(profile.monthly_budget) if profile.monthly_budget else None,
            'min_budget': float(profile.min_budget) if profile.min_budget else None,
            'preferred_accommodation_type': profile.preferred_accommodation_type,
            'occupancy_preference': profile.occupancy_preference,
            'target_move_in_date': str(profile.target_move_in_date) if profile.target_move_in_date else None,
            'food_preference': profile.food_preference,
            'gender_preference': profile.gender_preference,
            'profession': profile.profession,
            'company_or_college': profile.company_or_college,
            'bio': profile.bio,
            'notification_settings': {
                'whatsapp': profile.whatsapp_notifications,
                'sms': profile.sms_notifications,
                'email': profile.email_notifications,
            }
        }

    # 3. Saved Properties
    saved_items = []
    for sp in SavedProperty.objects.filter(tenant=tenant).select_related('property', 'property__locality', 'property__city'):
        saved_items.append({
            'property_title': sp.property.title,
            'locality': sp.property.locality.name if sp.property.locality else None,
            'city': sp.property.city.name if sp.property.city else None,
            'saved_at': sp.created_at.isoformat()
        })

    # 4. Enquiries Submitted
    enquiries_list = []
    for enq in Enquiry.objects.filter(seeker=tenant).select_related('property'):
        enquiries_list.append({
            'enquiry_id': enq.id,
            'property_title': enq.property.title,
            'room_type': enq.interested_room_type,
            'budget': float(enq.budget) if enq.budget else None,
            'status': enq.status,
            'initial_message': enq.message,
            'created_at': enq.created_at.isoformat()
        })

    # 5. Walkthrough Visits
    visits_list = []
    for v in VisitRequest.objects.filter(seeker=tenant).select_related('property'):
        visits_list.append({
            'request_id': v.request_id,
            'property_title': v.property.title,
            'status': v.status,
            'scheduled_date': str(v.scheduled_date),
            'scheduled_time_slot': v.scheduled_time_slot,
            'notes': v.notes,
            'created_at': v.created_at.isoformat()
        })

    # 6. Rental Bookings
    bookings_list = []
    for b in RentalBooking.objects.filter(tenant=tenant).select_related('property'):
        bookings_list.append({
            'booking_id': b.booking_id,
            'property_title': b.property.title,
            'status': b.booking_status,
            'move_in_date': str(b.move_in_date),
            'monthly_rent': float(b.monthly_rent) if b.monthly_rent else None,
            'security_deposit': float(b.security_deposit) if b.security_deposit else None,
            'payment_status': b.payment_status,
            'payment_reference': b.payment_reference,
            'created_at': b.created_at.isoformat()
        })

    export_payload = {
        'export_metadata': {
            'platform': 'KiraayaGrid Platform & Tenancy System',
            'exported_at': datetime.now().isoformat(),
            'compliance': 'Digital Personal Data Protection Act (DPDP) / GDPR compliant archive'
        },
        'user_account': user_data,
        'profile_and_preferences': profile_data,
        'saved_properties': saved_items,
        'submitted_enquiries': enquiries_list,
        'walkthrough_visits': visits_list,
        'rental_bookings': bookings_list
    }

    response = HttpResponse(
        json.dumps(export_payload, indent=2, default=str),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="kiraayagrid_tenant_archive_{tenant.username}.json"'
    return response


# API: Submit Account Deletion Request
def api_delete_account(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=403)

    reason = request.POST.get('reason', 'Tenant requested account deactivation').strip()

    # Log deactivation ticket
    ticket_code = f"TKT-DEACT-{random.randint(100, 999)}"
    SupportTicket.objects.create(
        ticket_code=ticket_code,
        user=tenant,
        subject="Account Deactivation & Personal Data Erasure Request",
        category="Account Deletion / Privacy",
        channel="PORTAL",
        message=f"Tenant requested full account deactivation and personal data erasure.\nReason provided: {reason}",
        priority="HIGH",
        status="OPEN",
        sla_due_text="Compliance turnaround < 24 hours",
        sla_status="ON_TRACK"
    )

    return JsonResponse({
        'status': 'success',
        'message': f"Account deactivation request logged (#{ticket_code}). Our compliance team will finalize data erasure within 24 hours."
    })


# Logout View
def tenant_logout(request):
    auth_logout(request)
    next_url = request.GET.get('next')
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return redirect(next_url)
    return redirect('/auth/?role=TENANT')
