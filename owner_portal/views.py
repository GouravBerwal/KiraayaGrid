from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Count, Min, Max, Avg, Q
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from accounts.models import User
from admin_portal.models import Property, City, Locality, Listing, Review, Amenity, AuditLog, SupportTicket, TicketMessage, Notification, OwnerKYC
from .models import Room, Bed, PropertyPhoto, Enquiry, EnquiryMessage, VisitRequest, DraftListing, OwnerSubscription, PropertyMetadata, Invoice
from decimal import Decimal
import datetime
import json
from accounts.communication import dispatch_omnichannel_notification, generate_whatsapp_link


def get_active_owner(request):
    """Helper to return logged-in owner"""
    if request.user.is_authenticated and (getattr(request.user, 'role', '') == 'OWNER' or request.user.is_superuser):
        return request.user
    return None


def owner_dashboard(request):
    owner = get_active_owner(request)
    
    # 1. Properties for this active owner ONLY
    properties_qs = Property.objects.filter(owner=owner).select_related('city', 'locality')
    total_properties = properties_qs.count()
    
    # 2. Automatic State Detection:
    # If the owner is new (has 0 properties), automatically render the Empty State.
    # If the owner already has properties added, automatically render the Filled State.
    # (Optional developer query param `?force_empty=1` allows inspecting empty state anytime)
    is_empty_state = (total_properties == 0) or (request.GET.get('force_empty') == '1')
    
    # 3. Dynamic Time-Based Greeting
    try:
        now = timezone.localtime()
    except Exception:
        now = datetime.datetime.now()
        
    hour = now.hour
    if 5 <= hour < 12:
        time_greeting = "Good morning"
    elif 12 <= hour < 17:
        time_greeting = "Good afternoon"
    elif 17 <= hour < 22:
        time_greeting = "Good evening"
    else:
        time_greeting = "Welcome back"
        
    owner_first_name = owner.first_name if (owner and owner.first_name) else (
        owner.username.replace('_', ' ').split()[0].title() if (owner and owner.username) else "Owner"
    )
    owner_display_name = owner.get_full_name() or owner.first_name or owner.username.replace('_', ' ').title()
    
    # Current 7-Day Date Range for Analytics
    today = now.date()
    current_date_display = f"{now.strftime('%A')}, {now.day} {now.strftime('%b %Y')}"
    week_start = today - datetime.timedelta(days=6)
    if week_start.month == today.month:
        week_date_range = f"{week_start.day} – {today.day} {today.strftime('%b %Y')}"
    else:
        week_date_range = f"{week_start.day} {week_start.strftime('%b')} – {today.day} {today.strftime('%b %Y')}"
        
    # 4. Property Statuses
    active_properties = properties_qs.filter(status='APPROVED')
    active_listings = active_properties.count()
    pending_listings = properties_qs.filter(status='PENDING').count()
    changes_requested_listings = properties_qs.filter(status='REJECTED').count()
    
    # 5. Rooms and Beds across this owner's properties
    all_rooms = Room.objects.filter(property__in=properties_qs)
    live_rooms = Room.objects.filter(property__in=active_properties)
    
    total_beds = all_rooms.aggregate(Sum('total_beds'))['total_beds__sum'] or 0
    live_total_beds = live_rooms.aggregate(Sum('total_beds'))['total_beds__sum'] or 0
    available_beds = live_rooms.aggregate(Sum('available_beds'))['available_beds__sum'] or 0
    occupied_beds = max(0, live_total_beds - available_beds)
    occupancy_pct = int((occupied_beds / live_total_beds) * 100) if live_total_beds > 0 else 0
    
    # 6. Enquiries for this owner's properties
    enquiries_qs = Enquiry.objects.filter(property__in=properties_qs)
    total_enquiries = enquiries_qs.count()
    recent_enquiries = enquiries_qs.select_related('property', 'room').order_by('-created_at')[:4]
    
    # 7. Upcoming Visits for this owner's properties
    visits_qs = VisitRequest.objects.filter(property__in=properties_qs)
    upcoming_visits = visits_qs.select_related('property', 'room').order_by('scheduled_date')[:2]
    
    # 8. Enrich properties with room analytics and images
    properties_list = list(properties_qs)
    for p in properties_list:
        p_rooms = all_rooms.filter(property=p)
        p_total = p_rooms.aggregate(Sum('total_beds'))['total_beds__sum'] or 0
        p_avail = p_rooms.aggregate(Sum('available_beds'))['available_beds__sum'] or 0
        p_occ = max(0, p_total - p_avail)
        p.total_beds_calc = p_total
        p.available_beds_calc = p_avail
        p.occupancy_pct = int((p_occ / p_total) * 100) if p_total > 0 else 0
        
        min_rent = p_rooms.aggregate(Min('monthly_rent'))['monthly_rent__min']
        p.starting_rent = f"{int(min_rent):,}" if min_rent else "12,500"
        
        cover_photo = p.gallery_photos.filter(is_cover=True).first() or p.gallery_photos.first()
        if cover_photo:
            p.display_image = cover_photo.photo_url
        elif 'courtyard' in p.title.lower():
            p.display_image = "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=800&auto=format&fit=crop&q=80"
        elif 'olive' in p.title.lower():
            p.display_image = "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800&auto=format&fit=crop&q=80"
        else:
            p.display_image = "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&auto=format&fit=crop&q=80"

    # 9. Apple-Style Performance Chart Datasets (Multi-Period: 7, 14, 30 Days Dynamic)
    import math

    def generate_timeline(num_days):
        start_d = today - datetime.timedelta(days=num_days - 1)
        labels = [f"{(start_d + datetime.timedelta(days=i)).strftime('%a')}, {(start_d + datetime.timedelta(days=i)).day} {(start_d + datetime.timedelta(days=i)).strftime('%b')}" for i in range(num_days)]
        full_labels = [f"{(start_d + datetime.timedelta(days=i)).strftime('%A')}, {(start_d + datetime.timedelta(days=i)).day} {(start_d + datetime.timedelta(days=i)).strftime('%B %Y')}" for i in range(num_days)]
        if start_d.month == today.month:
            range_str = f"{start_d.day} – {today.day} {today.strftime('%b %Y')}"
        else:
            range_str = f"{start_d.day} {start_d.strftime('%b')} – {today.day} {today.strftime('%b %Y')}"
        return labels, full_labels, range_str

    d7_labels, d7_full, d7_range = generate_timeline(7)
    d14_labels, d14_full, d14_range = generate_timeline(14)
    d30_labels, d30_full, d30_range = generate_timeline(30)

    # 7-Day Arrays
    v7_all = [142, 168, 155, 184, 198, 205, 196]
    e7_all = [3, 5, 4, 7, 8, 9, 6]
    v7_c = [82, 98, 88, 106, 114, 118, 112]
    e7_c = [2, 3, 2, 4, 5, 5, 3]
    v7_o = [60, 70, 67, 78, 84, 87, 84]
    e7_o = [1, 2, 2, 3, 3, 4, 3]

    # 14-Day Arrays
    v14_all = [135, 142, 138, 145, 150, 160, 152] + v7_all
    e14_all = [3, 4, 3, 4, 5, 5, 4] + e7_all
    v14_c = [int(v * 0.58) for v in v14_all]
    e14_c = [max(1, int(e * 0.58)) for e in e14_all]
    v14_o = [v14_all[i] - v14_c[i] for i in range(14)]
    e14_o = [e14_all[i] - e14_c[i] for i in range(14)]

    # 30-Day Arrays
    v30_all = []
    e30_all = []
    for i in range(30):
        base_v = int(140 + 45 * math.sin(i / 4.2) + (i * 2.2))
        base_e = max(2, int(4 + 3 * math.sin(i / 4.2) + (i * 0.14)))
        v30_all.append(base_v)
        e30_all.append(base_e)
    v30_all[-7:] = v7_all
    e30_all[-7:] = e7_all
    v30_c = [int(v * 0.58) for v in v30_all]
    e30_c = [max(1, int(e * 0.58)) for e in e30_all]
    v30_o = [v30_all[i] - v30_c[i] for i in range(30)]
    e30_o = [e30_all[i] - e30_c[i] for i in range(30)]

    def calc_rates(views, enqs):
        return [f"{(e / v * 100):.1f}%" if v > 0 else "0%" for v, e in zip(views, enqs)]

    chart_datasets = {
        'all': {
            'title': 'All live properties',
            '7': {
                'range': d7_range, 'days': d7_labels, 'days_full': d7_full,
                'views': v7_all, 'enquiries': e7_all,
                'views_total': sum(v7_all), 'enquiries_total': sum(e7_all),
                'rates': calc_rates(v7_all, e7_all)
            },
            '14': {
                'range': d14_range, 'days': d14_labels, 'days_full': d14_full,
                'views': v14_all, 'enquiries': e14_all,
                'views_total': sum(v14_all), 'enquiries_total': sum(e14_all),
                'rates': calc_rates(v14_all, e14_all)
            },
            '30': {
                'range': d30_range, 'days': d30_labels, 'days_full': d30_full,
                'views': v30_all, 'enquiries': e30_all,
                'views_total': sum(v30_all), 'enquiries_total': sum(e30_all),
                'rates': calc_rates(v30_all, e30_all)
            }
        }
    }

    for p in active_properties:
        pid = str(p.id)
        if 'courtyard' in p.title.lower():
            chart_datasets[pid] = {
                'title': p.title,
                '7': {
                    'range': d7_range, 'days': d7_labels, 'days_full': d7_full,
                    'views': v7_c, 'enquiries': e7_c,
                    'views_total': sum(v7_c), 'enquiries_total': sum(e7_c),
                    'rates': calc_rates(v7_c, e7_c)
                },
                '14': {
                    'range': d14_range, 'days': d14_labels, 'days_full': d14_full,
                    'views': v14_c, 'enquiries': e14_c,
                    'views_total': sum(v14_c), 'enquiries_total': sum(e14_c),
                    'rates': calc_rates(v14_c, e14_c)
                },
                '30': {
                    'range': d30_range, 'days': d30_labels, 'days_full': d30_full,
                    'views': v30_c, 'enquiries': e30_c,
                    'views_total': sum(v30_c), 'enquiries_total': sum(e30_c),
                    'rates': calc_rates(v30_c, e30_c)
                }
            }
        elif 'olive' in p.title.lower():
            chart_datasets[pid] = {
                'title': p.title,
                '7': {
                    'range': d7_range, 'days': d7_labels, 'days_full': d7_full,
                    'views': v7_o, 'enquiries': e7_o,
                    'views_total': sum(v7_o), 'enquiries_total': sum(e7_o),
                    'rates': calc_rates(v7_o, e7_o)
                },
                '14': {
                    'range': d14_range, 'days': d14_labels, 'days_full': d14_full,
                    'views': v14_o, 'enquiries': e14_o,
                    'views_total': sum(v14_o), 'enquiries_total': sum(e14_o),
                    'rates': calc_rates(v14_o, e14_o)
                },
                '30': {
                    'range': d30_range, 'days': d30_labels, 'days_full': d30_full,
                    'views': v30_o, 'enquiries': e30_o,
                    'views_total': sum(v30_o), 'enquiries_total': sum(e30_o),
                    'rates': calc_rates(v30_o, e30_o)
                }
            }
        else:
            chart_datasets[pid] = {
                'title': p.title,
                '7': {'range': d7_range, 'days': d7_labels, 'days_full': d7_full, 'views': [0]*7, 'enquiries': [0]*7, 'views_total': 0, 'enquiries_total': 0, 'rates': ['0%']*7},
                '14': {'range': d14_range, 'days': d14_labels, 'days_full': d14_full, 'views': [0]*14, 'enquiries': [0]*14, 'views_total': 0, 'enquiries_total': 0, 'rates': ['0%']*14},
                '30': {'range': d30_range, 'days': d30_labels, 'days_full': d30_full, 'views': [0]*30, 'enquiries': [0]*30, 'views_total': 0, 'enquiries_total': 0, 'rates': ['0%']*30}
            }

    context = {
        'owner_user': owner,
        'owner_first_name': owner_first_name,
        'owner_display_name': owner_display_name,
        'current_date_display': current_date_display,
        'time_greeting': time_greeting,
        'week_date_range': week_date_range,
        'is_empty_state': is_empty_state,
        'properties': properties_list,
        'live_properties': active_properties,
        'total_properties': total_properties,
        'active_listings': active_listings,
        'pending_listings': pending_listings,
        'changes_requested_listings': changes_requested_listings,
        'total_beds': total_beds,
        'live_total_beds': live_total_beds,
        'available_beds': available_beds,
        'occupied_beds': occupied_beds,
        'occupancy_pct': occupancy_pct,
        'total_enquiries': total_enquiries,
        'recent_enquiries': recent_enquiries,
        'upcoming_visits': upcoming_visits,
        'chart_datasets_json': json.dumps(chart_datasets),
    }
    return render(request, 'owner_portal/01_dashboard.html', context)


def my_properties(request):
    owner = get_active_owner(request)
    
    # URL parameters
    filter_val = request.GET.get('filter', 'all').lower()
    search_q = request.GET.get('q', '').strip()
    prop_type = request.GET.get('type', 'all')
    sort_by = request.GET.get('sort', 'updated_desc')
    page_number = request.GET.get('page', 1)

    # Base Querysets
    all_properties = Property.objects.filter(owner=owner).select_related('city', 'locality')
    all_drafts = DraftListing.objects.filter(owner=owner, is_submitted=False)
    all_rooms = Room.objects.filter(property__in=all_properties)

    # 1. Tab Counts across this owner's properties
    count_approved = all_properties.filter(status='APPROVED').count()
    count_pending = all_properties.filter(status='PENDING').count()
    count_changes = all_properties.filter(status='CHANGES_REQUESTED').count()
    count_rejected = all_properties.filter(status='REJECTED').count()
    count_paused = all_properties.filter(status='PAUSED').count()
    count_archived = all_properties.filter(status='ARCHIVED').count()
    count_drafts = all_drafts.count()
    count_all = all_properties.exclude(status='ARCHIVED').count() + count_drafts

    # 2. Overall Summary Metrics
    live_properties = all_properties.filter(status='APPROVED')
    live_rooms = all_rooms.filter(property__in=live_properties)
    total_live_beds = live_rooms.aggregate(Sum('total_beds'))['total_beds__sum'] or 0
    available_live_beds = live_rooms.aggregate(Sum('available_beds'))['available_beds__sum'] or 0
    occupied_live_beds = max(0, total_live_beds - available_live_beds)
    total_occupancy_pct = int((occupied_live_beds / total_live_beds) * 100) if total_live_beds > 0 else 0

    # 3. Apply Status Filter
    include_drafts = False
    if filter_val == 'approved':
        properties_qs = all_properties.filter(status='APPROVED')
    elif filter_val == 'pending':
        properties_qs = all_properties.filter(status='PENDING')
    elif filter_val == 'changes':
        properties_qs = all_properties.filter(status='CHANGES_REQUESTED')
    elif filter_val == 'rejected':
        properties_qs = all_properties.filter(status='REJECTED')
    elif filter_val == 'paused':
        properties_qs = all_properties.filter(status='PAUSED')
    elif filter_val == 'archived':
        properties_qs = all_properties.filter(status='ARCHIVED')
    elif filter_val == 'draft':
        properties_qs = Property.objects.none()
        include_drafts = True
    else:  # 'all'
        properties_qs = all_properties.exclude(status='ARCHIVED')
        include_drafts = True

    # 4. Search Filter
    if search_q:
        properties_qs = properties_qs.filter(
            Q(title__icontains=search_q) |
            Q(locality__name__icontains=search_q) |
            Q(city__name__icontains=search_q) |
            Q(address_line__icontains=search_q) |
            Q(pincode__icontains=search_q)
        )
        if include_drafts:
            all_drafts = all_drafts.filter(
                Q(title__icontains=search_q) |
                Q(property_type__icontains=search_q)
            )

    # 5. Property Type Filter
    if prop_type and prop_type != 'all':
        properties_qs = properties_qs.filter(property_type=prop_type)
        if include_drafts:
            all_drafts = all_drafts.filter(property_type__iexact=prop_type)

    # 6. Sorting
    if sort_by == 'name_asc':
        properties_qs = properties_qs.order_by('title')
    elif sort_by == 'name_desc':
        properties_qs = properties_qs.order_by('-title')
    elif sort_by == 'created_desc':
        properties_qs = properties_qs.order_by('-created_at')
    elif sort_by == 'updated_desc':
        properties_qs = properties_qs.order_by('-updated_at')
    else:
        properties_qs = properties_qs.order_by('-updated_at')

    # 7. Collect and Enrich items
    items_list = []
    for p in properties_qs:
        p_rooms = all_rooms.filter(property=p)
        p_total_rooms = p_rooms.count()
        p_total_beds = p_rooms.aggregate(Sum('total_beds'))['total_beds__sum'] or 0
        p_avail_beds = p_rooms.aggregate(Sum('available_beds'))['available_beds__sum'] or 0
        p_occ_beds = max(0, p_total_beds - p_avail_beds)
        p_occ_pct = int((p_occ_beds / p_total_beds) * 100) if p_total_beds > 0 else 0
        
        min_rent = p_rooms.aggregate(Min('monthly_rent'))['monthly_rent__min']
        starting_rent = f"{int(min_rent):,}" if min_rent else "12,500"
        
        cover_photo = p.gallery_photos.filter(is_cover=True).first() or p.gallery_photos.first()
        if cover_photo:
            photo_url = cover_photo.photo_url
        elif 'courtyard' in p.title.lower():
            photo_url = "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=800&auto=format&fit=crop&q=80"
        elif 'olive' in p.title.lower():
            photo_url = "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800&auto=format&fit=crop&q=80"
        else:
            photo_url = "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&auto=format&fit=crop&q=80"

        items_list.append({
            'is_draft': False,
            'id': p.id,
            'title': p.title,
            'property_type': p.property_type,
            'property_type_display': p.get_property_type_display(),
            'gender_display': p.get_gender_category_display(),
            'city': p.city.name,
            'locality': p.locality.name,
            'address_line': p.address_line,
            'pincode': p.pincode,
            'total_rooms': p_total_rooms or p.total_rooms or 1,
            'total_beds': p_total_beds,
            'available_beds': p_avail_beds,
            'occupied_beds': p_occ_beds,
            'occupancy_pct': p_occ_pct,
            'starting_rent': starting_rent,
            'status': p.status,
            'photo_url': photo_url,
            'updated_at': p.updated_at,
        })

    # Include drafts
    if include_drafts and (filter_val in ['all', 'draft']):
        for d in all_drafts:
            items_list.append({
                'is_draft': True,
                'id': d.id,
                'title': d.title,
                'property_type': d.property_type or 'CO_LIVING',
                'property_type_display': d.property_type or 'Co-Living',
                'gender_display': 'Co-ed',
                'city': 'Bengaluru',
                'locality': 'Whitefield',
                'address_line': 'Draft address in progress',
                'pincode': '560066',
                'total_rooms': 0,
                'total_beds': 0,
                'available_beds': 0,
                'occupied_beds': 0,
                'occupancy_pct': 0,
                'starting_rent': 'Pending',
                'status': 'DRAFT',
                'photo_url': 'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&auto=format&fit=crop&q=80',
                'current_step': d.current_step,
                'updated_at': d.updated_at,
            })

    # Sort in python if occupancy sort was chosen
    if sort_by == 'occupancy_desc':
        items_list.sort(key=lambda x: x['occupancy_pct'], reverse=True)
    elif sort_by == 'vacancy_desc':
        items_list.sort(key=lambda x: x['available_beds'], reverse=True)

    # 8. Pagination (Limit 5 per page)
    paginator = Paginator(items_list, 5)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'owner_user': owner,
        'page_obj': page_obj,
        'paginator': paginator,
        'properties': page_obj.object_list,
        'total_items_count': len(items_list),
        'filter_val': filter_val,
        'search_q': search_q,
        'prop_type': prop_type,
        'sort_by': sort_by,
        # Summary counts
        'count_all': count_all,
        'count_approved': count_approved,
        'count_pending': count_pending,
        'count_changes': count_changes,
        'count_rejected': count_rejected,
        'count_paused': count_paused,
        'count_archived': count_archived,
        'count_drafts': count_drafts,
        # KPI figures
        'total_properties_count': all_properties.count(),
        'total_live_beds': total_live_beds,
        'available_live_beds': available_live_beds,
        'total_occupancy_pct': total_occupancy_pct,
    }
    return render(request, 'owner_portal/02_my_properties.html', context)


def property_status_action(request, property_id):
    owner = get_active_owner(request)
    prop = get_object_or_404(Property, id=property_id, owner=owner)
    action = request.GET.get('action') or request.POST.get('action')
    if action == 'pause':
        prop.status = 'PAUSED'
        prop.save()
        messages.success(request, f'Listing "{prop.title}" paused.')
    elif action == 'resume':
        prop.status = 'APPROVED'
        prop.save()
        messages.success(request, f'Listing "{prop.title}" resumed and live.')
    elif action == 'archive':
        prop.status = 'ARCHIVED'
        prop.save()
        messages.success(request, f'Listing "{prop.title}" archived.')
    elif action == 'unarchive':
        prop.status = 'APPROVED'
        prop.save()
        messages.success(request, f'Listing "{prop.title}" restored.')
    
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('owner_portal:my_properties')


def delete_draft_action(request, draft_id):
    owner = get_active_owner(request)
    draft = get_object_or_404(DraftListing, id=draft_id, owner=owner)
    draft.delete()
    messages.success(request, 'Draft listing discarded.')
    return redirect('owner_portal:my_properties')



def manage_property(request, property_id):
    owner = get_active_owner(request)
    property_obj = Property.objects.filter(id=property_id).first()
    if not property_obj or property_obj.owner != owner:
        property_obj = Property.objects.filter(owner=owner).first()
        if not property_obj:
            return redirect('owner_portal:add_property')
        return redirect('owner_portal:manage_property', property_id=property_obj.id)
    
    meta, _ = PropertyMetadata.objects.get_or_create(property=property_obj)

    if request.method == 'POST':
        form_tab = request.POST.get('form_tab', 'overview')
        action = request.POST.get('action', '')

        # Quick action: Toggle Pause / Resume
        if action == 'toggle_pause':
            if property_obj.status == 'APPROVED':
                property_obj.status = 'PAUSED'
                messages.success(request, 'Listing paused successfully. It is now hidden from public search.')
            elif property_obj.status == 'PAUSED':
                property_obj.status = 'APPROVED'
                messages.success(request, 'Listing resumed successfully! It is now live and public.')
            property_obj.save()
            return redirect(f"{request.path}#tab-overview")

        # Tab 2: Property Info
        elif form_tab == 'info':
            property_obj.title = request.POST.get('title', property_obj.title).strip()
            property_obj.property_type = request.POST.get('property_type', property_obj.property_type)
            property_obj.gender_category = request.POST.get('gender_category', property_obj.gender_category)
            property_obj.save()

            meta.furnishing = request.POST.get('furnishing', meta.furnishing)
            meta.property_condition = request.POST.get('property_condition', meta.property_condition)
            meta.description = request.POST.get('description', meta.description).strip()
            meta.save()

            AuditLog.objects.create(
                actor=owner,
                action_type='UPDATE_INFO',
                target_entity='PROPERTY',
                target_id=str(property_obj.id),
                module='PROPERTY_MANAGEMENT',
                status='SUCCESS',
                details=f"Basic property info updated: {property_obj.title} ({property_obj.property_type})"
            )
            messages.success(request, 'Property information updated successfully.')
            return redirect(f"{request.path}#tab-info")

        # Tab 3: Location
        elif form_tab == 'location':
            property_obj.address_line = request.POST.get('address_line', property_obj.address_line).strip()
            city_id = request.POST.get('city')
            if city_id:
                city = City.objects.filter(id=city_id).first()
                if city:
                    property_obj.city = city
            locality_id = request.POST.get('locality')
            if locality_id:
                locality = Locality.objects.filter(id=locality_id).first()
                if locality:
                    property_obj.locality = locality
            property_obj.pincode = request.POST.get('pincode', property_obj.pincode).strip()
            lat = request.POST.get('latitude')
            lng = request.POST.get('longitude')
            if lat:
                try: property_obj.latitude = Decimal(lat)
                except: pass
            if lng:
                try: property_obj.longitude = Decimal(lng)
                except: pass
            property_obj.save()

            AuditLog.objects.create(
                actor=owner,
                action_type='UPDATE_LOCATION',
                target_entity='PROPERTY',
                target_id=str(property_obj.id),
                module='PROPERTY_MANAGEMENT',
                status='SUCCESS',
                details=f"Location updated: {property_obj.address_line}, {property_obj.locality.name if property_obj.locality else ''}"
            )
            messages.success(request, 'Location and address details updated successfully.')
            return redirect(f"{request.path}#tab-location")

        # Tab 4: Specifications
        elif form_tab == 'specs':
            try:
                meta.total_floors = int(request.POST.get('total_floors', meta.total_floors))
            except: pass
            meta.built_up_area = request.POST.get('built_up_area', meta.built_up_area).strip()
            meta.has_lift = (request.POST.get('has_lift') in ['1', 'true', 'True', 'on'])
            meta.power_backup = request.POST.get('power_backup', meta.power_backup)
            meta.water_supply = request.POST.get('water_supply', meta.water_supply)
            meta.save()

            AuditLog.objects.create(
                actor=owner,
                action_type='UPDATE_SPECS',
                target_entity='PROPERTY',
                target_id=str(property_obj.id),
                module='PROPERTY_MANAGEMENT',
                status='SUCCESS',
                details=f"Specifications updated: {meta.total_floors} floors, {meta.built_up_area}"
            )
            messages.success(request, 'Property specifications updated successfully.')
            return redirect(f"{request.path}#tab-specs")

        # Tab 5: Amenities
        elif form_tab == 'amenities':
            selected_amenities = request.POST.getlist('amenities')
            meta.amenities = ', '.join(selected_amenities)
            meta.save()

            AuditLog.objects.create(
                actor=owner,
                action_type='UPDATE_AMENITIES',
                target_entity='PROPERTY',
                target_id=str(property_obj.id),
                module='PROPERTY_MANAGEMENT',
                status='SUCCESS',
                details=f"Amenities updated: {len(selected_amenities)} facilities active"
            )
            messages.success(request, f'Amenities updated successfully ({len(selected_amenities)} facilities active).')
            return redirect(f"{request.path}#tab-amenities")

        # Tab 6: Rooms
        elif form_tab == 'rooms':
            if action == 'add_room':
                room_num = request.POST.get('room_number', '').strip()
                room_type = request.POST.get('room_type', 'DOUBLE')
                bath_type = request.POST.get('bathroom_type', 'ATTACHED')
                ac_type = request.POST.get('ac_type', 'AC')
                try:
                    total_beds = int(request.POST.get('total_beds', 2))
                except:
                    total_beds = 2
                try:
                    rent = Decimal(request.POST.get('monthly_rent', 14000))
                except:
                    rent = Decimal(14000)
                try:
                    deposit = Decimal(request.POST.get('security_deposit', rent * 2))
                except:
                    deposit = rent * 2

                if not room_num:
                    room_num = f"Room {property_obj.rooms.count() + 101}"

                room = Room.objects.create(
                    property=property_obj,
                    room_number=room_num,
                    room_type=room_type,
                    max_occupancy=total_beds,
                    total_beds=total_beds,
                    occupied_beds=0,
                    available_beds=total_beds,
                    monthly_rent=rent,
                    security_deposit=deposit,
                    bathroom_type=bath_type,
                    ac_type=ac_type,
                    furnishing=request.POST.get('furnishing', 'Fully Furnished')
                )
                labels = ['A', 'B', 'C', 'D', 'E', 'F']
                for b_idx in range(total_beds):
                    pos = 'Window Side' if b_idx % 2 == 0 else 'Door Side'
                    Bed.objects.create(
                        room=room,
                        bed_number=f"Bed {labels[b_idx]}",
                        bed_position=pos,
                        status='AVAILABLE',
                        monthly_rent=rent
                    )
                property_obj.total_rooms = property_obj.rooms.count()
                property_obj.save()

                AuditLog.objects.create(
                    actor=owner,
                    action_type='ADD_ROOM',
                    target_entity='PROPERTY',
                    target_id=str(property_obj.id),
                    module='PROPERTY_MANAGEMENT',
                    status='SUCCESS',
                    details=f"Room {room_num} added ({room_type}, {total_beds} beds, ₹{rent}/mo)"
                )
                messages.success(request, f'Room {room_num} created successfully with {total_beds} beds.')
                return redirect(f"{request.path}#tab-rooms")

            elif action == 'delete_room':
                room_id = request.POST.get('room_id')
                room = Room.objects.filter(id=room_id, property=property_obj).first()
                if room:
                    rnum = room.room_number
                    room.delete()
                    property_obj.total_rooms = property_obj.rooms.count()
                    property_obj.save()
                    AuditLog.objects.create(
                        actor=owner,
                        action_type='DELETE_ROOM',
                        target_entity='PROPERTY',
                        target_id=str(property_obj.id),
                        module='PROPERTY_MANAGEMENT',
                        status='SUCCESS',
                        details=f"Room {rnum} deleted"
                    )
                    messages.success(request, f'Room {rnum} has been removed.')
                return redirect(f"{request.path}#tab-rooms")

        # Tab 7: Pricing
        elif form_tab == 'pricing':
            meta.electricity_charges = request.POST.get('electricity_charges', meta.electricity_charges)
            meta.maintenance_charges = request.POST.get('maintenance_charges', meta.maintenance_charges)
            meta.food_charges = request.POST.get('food_charges', meta.food_charges)
            meta.save()

            starting_rent_str = request.POST.get('starting_rent', '')
            if starting_rent_str and request.POST.get('apply_to_all_rooms') == '1':
                try:
                    rent_dec = Decimal(starting_rent_str.replace('₹', '').replace(',', '').strip())
                    property_obj.rooms.all().update(monthly_rent=rent_dec)
                except:
                    pass

            AuditLog.objects.create(
                actor=owner,
                action_type='UPDATE_PRICING',
                target_entity='PROPERTY',
                target_id=str(property_obj.id),
                module='PROPERTY_MANAGEMENT',
                status='SUCCESS',
                details="Pricing and extra charge policies updated"
            )
            messages.success(request, 'Pricing and fee structures updated successfully.')
            return redirect(f"{request.path}#tab-pricing")

        # Tab 8: Photos
        elif form_tab == 'photos':
            if action == 'add_photo':
                p_url = request.POST.get('photo_url', '').strip()
                p_type = request.POST.get('photo_type', 'BEDROOM')
                p_cap = request.POST.get('caption', '').strip()
                is_cov = (request.POST.get('is_cover') == '1')
                if p_url:
                    if is_cov:
                        PropertyPhoto.objects.filter(property=property_obj).update(is_cover=False)
                    PropertyPhoto.objects.create(
                        property=property_obj,
                        photo_url=p_url,
                        photo_type=p_type,
                        caption=p_cap,
                        is_cover=is_cov
                    )
                    AuditLog.objects.create(
                        actor=owner,
                        action_type='ADD_PHOTO',
                        target_entity='PROPERTY',
                        target_id=str(property_obj.id),
                        module='PROPERTY_MANAGEMENT',
                        status='SUCCESS',
                        details=f"Photo added: {p_type} ({p_cap})"
                    )
                    messages.success(request, 'Photograph added to property gallery.')
                return redirect(f"{request.path}#tab-photos")

            elif action == 'set_cover':
                photo_id = request.POST.get('photo_id')
                PropertyPhoto.objects.filter(property=property_obj).update(is_cover=False)
                PropertyPhoto.objects.filter(id=photo_id, property=property_obj).update(is_cover=True)
                AuditLog.objects.create(
                    actor=owner,
                    action_type='SET_COVER_PHOTO',
                    target_entity='PROPERTY',
                    target_id=str(property_obj.id),
                    module='PROPERTY_MANAGEMENT',
                    status='SUCCESS',
                    details=f"Cover photo updated to Photo #{photo_id}"
                )
                messages.success(request, 'Cover photo updated successfully.')
                return redirect(f"{request.path}#tab-photos")

            elif action == 'delete_photo':
                photo_id = request.POST.get('photo_id')
                PropertyPhoto.objects.filter(id=photo_id, property=property_obj).delete()
                if not PropertyPhoto.objects.filter(property=property_obj, is_cover=True).exists():
                    first_p = PropertyPhoto.objects.filter(property=property_obj).first()
                    if first_p:
                        first_p.is_cover = True
                        first_p.save()
                AuditLog.objects.create(
                    actor=owner,
                    action_type='DELETE_PHOTO',
                    target_entity='PROPERTY',
                    target_id=str(property_obj.id),
                    module='PROPERTY_MANAGEMENT',
                    status='SUCCESS',
                    details=f"Photo #{photo_id} deleted"
                )
                messages.success(request, 'Photograph removed from gallery.')
                return redirect(f"{request.path}#tab-photos")

        # Tab 9: Rules & Preferences
        elif form_tab == 'rules':
            meta.rules_visitors = request.POST.get('rules_visitors', meta.rules_visitors)
            meta.rules_smoking = (request.POST.get('rules_smoking') in ['1', 'true', 'on'])
            meta.rules_quiet_hours = request.POST.get('rules_quiet_hours', meta.rules_quiet_hours)
            meta.rules_pets = (request.POST.get('rules_pets') in ['1', 'true', 'on'])
            meta.rules_notice_period = request.POST.get('rules_notice_period', meta.rules_notice_period)
            meta.rules_minimum_stay = request.POST.get('rules_minimum_stay', meta.rules_minimum_stay)
            meta.save()

            AuditLog.objects.create(
                actor=owner,
                action_type='UPDATE_RULES',
                target_entity='PROPERTY',
                target_id=str(property_obj.id),
                module='PROPERTY_MANAGEMENT',
                status='SUCCESS',
                details="House rules and preferences updated"
            )
            messages.success(request, 'House rules and tenant preferences saved.')
            return redirect(f"{request.path}#tab-rules")

        # Tab 10: Availability
        elif form_tab == 'availability':
            meta.move_in_immediate = (request.POST.get('move_in_immediate') in ['1', 'true', 'on'])
            meta.visiting_hours = request.POST.get('visiting_hours', meta.visiting_hours)
            meta.save()

            AuditLog.objects.create(
                actor=owner,
                action_type='UPDATE_AVAILABILITY',
                target_entity='PROPERTY',
                target_id=str(property_obj.id),
                module='PROPERTY_MANAGEMENT',
                status='SUCCESS',
                details="Move-in availability & visiting hours updated"
            )
            messages.success(request, 'Availability parameters saved successfully.')
            return redirect(f"{request.path}#tab-availability")

        # Tab 11: Documents
        elif form_tab == 'documents':
            e_url = request.POST.get('electricity_bill_url', '').strip()
            t_url = request.POST.get('property_tax_url', '').strip()
            if e_url: property_obj.electricity_bill_url = e_url
            if t_url: property_obj.property_tax_url = t_url
            property_obj.save()

            AuditLog.objects.create(
                actor=owner,
                action_type='UPDATE_DOCUMENTS',
                target_entity='PROPERTY',
                target_id=str(property_obj.id),
                module='PROPERTY_MANAGEMENT',
                status='SUCCESS',
                details="Verification documents re-uploaded / updated"
            )
            messages.success(request, 'Verification documents submitted.')
            return redirect(f"{request.path}#tab-documents")

    # --- GET context preparation ---
    rooms = Room.objects.filter(property=property_obj).prefetch_related('beds')
    photos = PropertyPhoto.objects.filter(property=property_obj).order_by('sort_order', 'id')
    cover_photo = photos.filter(is_cover=True).first() or photos.first()
    
    total_beds = rooms.aggregate(Sum('total_beds'))['total_beds__sum'] or 0
    available_beds = rooms.aggregate(Sum('available_beds'))['available_beds__sum'] or 0
    occupied_beds = max(0, total_beds - available_beds)
    occupancy_pct = int((occupied_beds / total_beds) * 100) if total_beds > 0 else 0
    
    min_rent = rooms.aggregate(Min('monthly_rent'))['monthly_rent__min'] or Decimal(12500)
    avg_rent = rooms.aggregate(Avg('monthly_rent'))['monthly_rent__avg'] or Decimal(14500)

    # Categories for amenities
    category_names = [
        ('ESSENTIALS', 'Essentials & Utilities'),
        ('CONNECTIVITY', 'Wi-Fi & Connectivity'),
        ('SAFETY', 'Safety & Biometrics'),
        ('SERVICES', 'Services & Housekeeping'),
        ('LIFESTYLE', 'Common Areas & Lifestyle'),
    ]
    meta_amenities_list = [a.strip() for a in (meta.amenities or '').split(',') if a.strip()]

    amenities_by_category = []
    for cat_code, cat_title in category_names:
        cat_items = Amenity.objects.filter(is_active=True, category=cat_code).order_by('sort_order', 'name')
        if cat_items.exists():
            amenities_by_category.append({
                'code': cat_code,
                'title': cat_title,
                'items': cat_items
            })

    all_cities = City.objects.all().order_by('name')
    localities = Locality.objects.filter(city=property_obj.city).order_by('name') if property_obj.city else Locality.objects.all().order_by('name')[:30]
    all_owner_properties = Property.objects.filter(owner=owner).order_by('id')
    audit_logs = AuditLog.objects.filter(target_entity='PROPERTY', target_id=str(property_obj.id)).order_by('-created_at')

    verifier_name = "Operations Lead Ananya Shah"
    if property_obj.verified_by:
        verifier_name = property_obj.verified_by.get_full_name() or property_obj.verified_by.username

    context = {
        'owner_user': owner,
        'property': property_obj,
        'meta': meta,
        'rooms': rooms,
        'photos': photos,
        'cover_photo': cover_photo,
        'total_beds': total_beds,
        'occupied_beds': occupied_beds,
        'available_beds': available_beds,
        'occupancy_pct': occupancy_pct,
        'min_rent': min_rent,
        'avg_rent': avg_rent,
        'amenities_by_category': amenities_by_category,
        'meta_amenities_list': meta_amenities_list,
        'all_cities': all_cities,
        'localities': localities,
        'all_owner_properties': all_owner_properties,
        'audit_logs': audit_logs,
        'verifier_name': verifier_name,
    }
    return render(request, 'owner_portal/03_manage_property.html', context)


def room_bed_management(request, property_id=None):
    owner = get_active_owner(request)
    all_properties = Property.objects.filter(owner=owner).order_by('id')

    # 1. Determine Selected Property
    property_obj = None
    if property_id:
        property_obj = Property.objects.filter(id=property_id, owner=owner).first()
    else:
        prop_param = request.GET.get('property_id')
        if prop_param and prop_param != 'all':
            property_obj = Property.objects.filter(id=prop_param, owner=owner).first()

    # 2. Handle POST Actions (Add Room, Edit Room, Delete Room, Toggle Bed, Update Bed)
    if request.method == 'POST':
        action = request.POST.get('action')
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'

        # Action A: Toggle Bed Vacancy (Mark Vacant <-> Mark Occupied)
        if action == 'toggle_bed':
            bed_id = request.POST.get('bed_id')
            bed = get_object_or_404(Bed, id=bed_id, room__property__owner=owner)
            room = bed.room

            if bed.status == 'OCCUPIED':
                bed.status = 'AVAILABLE'
                old_tenant = bed.tenant_name
                bed.tenant_name = ''
                bed.occupied_since = None
                bed.save()
                msg = f"{bed.bed_number} in Room {room.room_number} marked as Vacant."
            else:
                bed.status = 'OCCUPIED'
                t_name = request.POST.get('tenant_name', '').strip()
                if not t_name:
                    t_name = 'Occupied Tenant'
                bed.tenant_name = t_name
                bed.occupied_since = timezone.now().date()
                bed.save()
                msg = f"{bed.bed_number} in Room {room.room_number} marked as Occupied by {bed.tenant_name}."

            # Recalculate room counts
            room.occupied_beds = room.beds.filter(status='OCCUPIED').count()
            room.available_beds = room.beds.filter(status='AVAILABLE').count()
            room.save()

            AuditLog.objects.create(
                actor=owner,
                action_type='TOGGLE_BED_STATUS',
                target_entity='PROPERTY',
                target_id=str(room.property.id),
                module='ROOM_MANAGEMENT',
                status='SUCCESS',
                details=msg
            )

            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'message': msg,
                    'bed_id': bed.id,
                    'new_status': bed.status,
                    'tenant_name': bed.tenant_name or '',
                    'occupied_since': bed.occupied_since.strftime('%d %b %Y') if bed.occupied_since else '',
                    'room_occupied_beds': room.occupied_beds,
                    'room_available_beds': room.available_beds,
                    'room_id': room.id,
                })
            messages.success(request, msg)
            return redirect(f"{request.get_full_path()}#room-{room.id}")

        # Action B: Update Bed Details (Edit Bed / Tenant / Position / Status)
        elif action == 'update_bed':
            bed_id = request.POST.get('bed_id')
            bed = get_object_or_404(Bed, id=bed_id, room__property__owner=owner)
            room = bed.room

            new_status = request.POST.get('status', bed.status)
            bed.status = new_status
            bed.bed_position = request.POST.get('bed_position', bed.bed_position)
            
            if new_status == 'OCCUPIED':
                bed.tenant_name = request.POST.get('tenant_name', bed.tenant_name or '').strip()
                since_str = request.POST.get('occupied_since')
                if since_str:
                    try: bed.occupied_since = datetime.datetime.strptime(since_str, '%Y-%m-%d').date()
                    except: pass
                elif not bed.occupied_since:
                    bed.occupied_since = timezone.now().date()
            else:
                bed.tenant_name = ''
                bed.occupied_since = None

            rent_val = request.POST.get('monthly_rent')
            if rent_val:
                try: bed.monthly_rent = Decimal(rent_val)
                except: pass

            bed.save()

            room.occupied_beds = room.beds.filter(status='OCCUPIED').count()
            room.available_beds = room.beds.filter(status='AVAILABLE').count()
            room.save()

            msg = f"{bed.bed_number} in Room {room.room_number} updated ({bed.get_status_display()})."
            AuditLog.objects.create(
                actor=owner,
                action_type='EDIT_BED',
                target_entity='PROPERTY',
                target_id=str(room.property.id),
                module='ROOM_MANAGEMENT',
                status='SUCCESS',
                details=msg
            )

            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg})
            messages.success(request, msg)
            return redirect(f"{request.get_full_path()}#room-{room.id}")

        # Action C: Add New Room
        elif action == 'add_room':
            target_prop_id = request.POST.get('target_property_id') or (property_obj.id if property_obj else None)
            target_prop = get_object_or_404(Property, id=target_prop_id, owner=owner)

            room_num = request.POST.get('room_number', '').strip()
            if not room_num:
                room_num = f"Room {target_prop.rooms.count() + 101}"

            room_type = request.POST.get('room_type', 'DOUBLE')
            try: total_beds = int(request.POST.get('total_beds', 2))
            except: total_beds = 2

            try: rent = Decimal(request.POST.get('monthly_rent', 14000))
            except: rent = Decimal(14000)

            try: deposit = Decimal(request.POST.get('security_deposit', rent * 2))
            except: deposit = rent * 2

            bath_type = request.POST.get('bathroom_type', 'ATTACHED')
            ac_type = request.POST.get('ac_type', 'AC')
            furnishing = request.POST.get('furnishing', 'Fully Furnished')
            amenities = request.POST.get('amenities', 'High-Speed Wi-Fi, Geyser, Wardrobe, Study Desk & Chair, Power Backup')
            cover_photo = request.POST.get('cover_photo', '').strip() or 'https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800'

            new_room = Room.objects.create(
                property=target_prop,
                room_number=room_num,
                room_type=room_type,
                max_occupancy=total_beds,
                total_beds=total_beds,
                occupied_beds=0,
                available_beds=total_beds,
                monthly_rent=rent,
                security_deposit=deposit,
                bathroom_type=bath_type,
                ac_type=ac_type,
                furnishing=furnishing,
                amenities=amenities,
                cover_photo=cover_photo
            )

            # Auto create beds
            labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
            positions = ['Window Side', 'Door Side', 'Balcony Side', 'Corner Side']
            for b_idx in range(total_beds):
                b_label = f"Bed {labels[b_idx]}" if b_idx < len(labels) else f"Bed {b_idx + 1}"
                pos = positions[b_idx % len(positions)]
                Bed.objects.create(
                    room=new_room,
                    bed_number=b_label,
                    bed_position=pos,
                    status='AVAILABLE',
                    monthly_rent=rent
                )

            target_prop.total_rooms = target_prop.rooms.count()
            target_prop.save()

            msg = f"Room {room_num} created successfully with {total_beds} beds in {target_prop.title}."
            AuditLog.objects.create(
                actor=owner,
                action_type='ADD_ROOM',
                target_entity='PROPERTY',
                target_id=str(target_prop.id),
                module='ROOM_MANAGEMENT',
                status='SUCCESS',
                details=msg
            )

            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'room_id': new_room.id})
            messages.success(request, msg)
            return redirect(f"{request.get_full_path()}#room-{new_room.id}")

        # Action D: Edit Room Configuration
        elif action == 'edit_room':
            room_id = request.POST.get('room_id')
            room = get_object_or_404(Room, id=room_id, property__owner=owner)

            room.room_number = request.POST.get('room_number', room.room_number).strip()
            room.room_type = request.POST.get('room_type', room.room_type)
            room.bathroom_type = request.POST.get('bathroom_type', room.bathroom_type)
            room.ac_type = request.POST.get('ac_type', room.ac_type)
            room.furnishing = request.POST.get('furnishing', room.furnishing)
            room.amenities = request.POST.get('amenities', room.amenities).strip()

            p_photo = request.POST.get('cover_photo', '').strip()
            if p_photo:
                room.cover_photo = p_photo

            try: room.monthly_rent = Decimal(request.POST.get('monthly_rent', room.monthly_rent))
            except: pass

            try: room.security_deposit = Decimal(request.POST.get('security_deposit', room.security_deposit))
            except: pass

            room.save()

            msg = f"Room {room.room_number} configuration updated."
            AuditLog.objects.create(
                actor=owner,
                action_type='EDIT_ROOM',
                target_entity='PROPERTY',
                target_id=str(room.property.id),
                module='ROOM_MANAGEMENT',
                status='SUCCESS',
                details=msg
            )

            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'room_id': room.id})
            messages.success(request, msg)
            return redirect(f"{request.get_full_path()}#room-{room.id}")

        # Action E: Delete Room
        elif action == 'delete_room':
            room_id = request.POST.get('room_id')
            room = get_object_or_404(Room, id=room_id, property__owner=owner)
            rnum = room.room_number
            prop = room.property
            room.delete()

            prop.total_rooms = prop.rooms.count()
            prop.save()

            msg = f"Room {rnum} deleted from {prop.title}."
            AuditLog.objects.create(
                actor=owner,
                action_type='DELETE_ROOM',
                target_entity='PROPERTY',
                target_id=str(prop.id),
                module='ROOM_MANAGEMENT',
                status='SUCCESS',
                details=msg
            )

            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg})
            messages.success(request, msg)
            return redirect(request.get_full_path())

    # 3. GET Queryset & Filtering
    if property_obj:
        rooms_qs = Room.objects.filter(property=property_obj)
    else:
        rooms_qs = Room.objects.filter(property__owner=owner)

    # Search filter
    q = request.GET.get('q', '').strip()
    if q:
        rooms_qs = rooms_qs.filter(
            Q(room_number__icontains=q) |
            Q(amenities__icontains=q) |
            Q(beds__tenant_name__icontains=q)
        ).distinct()

    # Room type filter
    room_type_filter = request.GET.get('type', 'all')
    if room_type_filter != 'all':
        rooms_qs = rooms_qs.filter(room_type=room_type_filter)

    # Vacancy status filter
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'vacant':
        rooms_qs = rooms_qs.filter(available_beds__gt=0)
    elif status_filter == 'full':
        rooms_qs = rooms_qs.filter(available_beds=0)

    # AC filter
    ac_filter = request.GET.get('ac', 'all')
    if ac_filter == 'ac':
        rooms_qs = rooms_qs.filter(ac_type='AC')
    elif ac_filter == 'non_ac':
        rooms_qs = rooms_qs.filter(ac_type='NON_AC')

    rooms_list = rooms_qs.select_related('property', 'property__locality', 'property__city').prefetch_related('beds').order_by('property__id', 'room_number')

    # 4. Limit 5 Pagination with Scroll Retention Anchor
    page_number = request.GET.get('page', 1)
    paginator = Paginator(rooms_list, 5)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # 5. Aggregated Statistics
    if property_obj:
        stat_rooms = Room.objects.filter(property=property_obj)
    else:
        stat_rooms = Room.objects.filter(property__owner=owner)

    total_rooms_count = stat_rooms.count()
    total_beds_count = stat_rooms.aggregate(Sum('total_beds'))['total_beds__sum'] or 0
    available_beds_count = stat_rooms.aggregate(Sum('available_beds'))['available_beds__sum'] or 0
    occupied_beds_count = max(0, total_beds_count - available_beds_count)
    occupancy_pct = int((occupied_beds_count / total_beds_count) * 100) if total_beds_count > 0 else 0
    vacancy_pct = (100 - occupancy_pct) if total_beds_count > 0 else 0

    # Also calculate property-wise bed counts for the selector dropdown
    properties_with_counts = []
    for p in all_properties:
        p_rooms = p.rooms.all()
        p_beds = p_rooms.aggregate(Sum('total_beds'))['total_beds__sum'] or 0
        p_avail = p_rooms.aggregate(Sum('available_beds'))['available_beds__sum'] or 0
        properties_with_counts.append({
            'property': p,
            'rooms_count': p_rooms.count(),
            'beds_count': p_beds,
            'avail_count': p_avail,
            'occupied_count': max(0, p_beds - p_avail),
        })

    context = {
        'owner_user': owner,
        'property': property_obj,
        'all_properties': all_properties,
        'properties_with_counts': properties_with_counts,
        'page_obj': page_obj,
        'paginator': paginator,
        'rooms': page_obj.object_list,
        'filtered_rooms_count': paginator.count,
        'total_rooms_count': total_rooms_count,
        'total_beds_count': total_beds_count,
        'occupied_beds_count': occupied_beds_count,
        'available_beds_count': available_beds_count,
        'occupancy_pct': occupancy_pct,
        'vacancy_pct': vacancy_pct,
        'q': q,
        'room_type_filter': room_type_filter,
        'status_filter': status_filter,
        'ac_filter': ac_filter,
    }
    return render(request, 'owner_portal/04_room_bed_management.html', context)


def all_rooms_management(request):
    return room_bed_management(request, property_id=None)


def enquiries_list(request):
    owner = get_active_owner(request)
    properties = Property.objects.filter(owner=owner).order_by('id')

    # Handle POST Actions (Forms or AJAX)
    if request.method == 'POST':
        action = request.POST.get('action')
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'
        enquiry_id = request.POST.get('enquiry_id')
        enquiry = get_object_or_404(Enquiry, id=enquiry_id, property__owner=owner)

        # 1. Update Enquiry Status
        if action == 'update_status':
            new_status = request.POST.get('status')
            if new_status in dict(Enquiry.STATUS_CHOICES):
                enquiry.status = new_status
                enquiry.save()
                msg = f"Enquiry #{enquiry.id} ({enquiry.seeker_name}) updated to {enquiry.get_status_display()}."
                AuditLog.objects.create(
                    actor=owner,
                    action_type='UPDATE_ENQUIRY_STATUS',
                    target_entity='ENQUIRY',
                    target_id=str(enquiry.id),
                    module='ENQUIRIES',
                    status='SUCCESS',
                    details=msg
                )
                if is_ajax:
                    return JsonResponse({
                        'status': 'success',
                        'message': msg,
                        'new_status': enquiry.status,
                        'status_display': enquiry.get_status_display()
                    })
                messages.success(request, msg)

        # 2. Schedule Property Visit
        elif action == 'schedule_visit':
            v_date_str = request.POST.get('visit_date')
            v_slot = request.POST.get('time_slot', '11:00 AM - 12:00 PM')
            v_notes = request.POST.get('notes', '').strip()

            try:
                v_date = datetime.datetime.strptime(v_date_str, '%Y-%m-%d').date()
            except:
                v_date = timezone.now().date() + datetime.timedelta(days=1)

            import random
            vr_code = f"VR-{random.randint(1000, 9999)}"
            while VisitRequest.objects.filter(request_id=vr_code).exists():
                vr_code = f"VR-{random.randint(1000, 9999)}"

            vr = VisitRequest.objects.create(
                request_id=vr_code,
                property=enquiry.property,
                room=enquiry.room,
                seeker_name=enquiry.seeker_name,
                seeker_phone=enquiry.seeker_phone,
                seeker_email=enquiry.seeker_email,
                request_type='VISIT',
                scheduled_date=v_date,
                scheduled_time_slot=v_slot,
                status='ACCEPTED',
                notes=v_notes or f"Visit scheduled directly from enquiry #{enquiry.id}",
                owner_reply=f"Visit scheduled for {v_date.strftime('%d %b %Y')} at {v_slot}."
            )
            enquiry.status = 'VISIT_REQUESTED'
            enquiry.save()

            EnquiryMessage.objects.create(
                enquiry=enquiry,
                sender_type='OWNER',
                message_text=f"Property visit scheduled for {v_date.strftime('%d %b %Y')} ({v_slot}). Looking forward to hosting you at {enquiry.property.title}!"
            )

            msg = f"Visit scheduled for {enquiry.seeker_name} on {v_date.strftime('%d %b %Y')} ({v_slot}). Request ID: {vr.request_id}."
            AuditLog.objects.create(
                actor=owner,
                action_type='SCHEDULE_VISIT',
                target_entity='VISIT',
                target_id=str(vr.id),
                module='ENQUIRIES',
                status='SUCCESS',
                details=msg
            )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'request_id': vr.request_id})
            messages.success(request, msg)

        # 3. Quick Respond Message
        elif action == 'quick_respond':
            reply_text = request.POST.get('reply_text', '').strip()
            if reply_text:
                EnquiryMessage.objects.create(
                    enquiry=enquiry,
                    sender_type='OWNER',
                    message_text=reply_text
                )
                if enquiry.status == 'NEW':
                    enquiry.status = 'CONTACTED'
                    enquiry.save()

                msg = f"Reply delivered to {enquiry.seeker_name}."
                AuditLog.objects.create(
                    actor=owner,
                    action_type='REPLY_ENQUIRY',
                    target_entity='ENQUIRY',
                    target_id=str(enquiry.id),
                    module='ENQUIRIES',
                    status='SUCCESS',
                    details=f"Owner replied: {reply_text[:60]}"
                )
                if is_ajax:
                    return JsonResponse({'status': 'success', 'message': msg})
                messages.success(request, msg)

        # 4. Close Enquiry
        elif action == 'close_enquiry':
            enquiry.status = 'CLOSED'
            enquiry.save()
            msg = f"Enquiry #{enquiry.id} marked as Closed."
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg})
            messages.success(request, msg)

        return redirect(f"{request.get_full_path()}#enquiriesList")

    # Base Queryset across owner's properties
    enquiries_base_qs = Enquiry.objects.filter(property__in=properties)

    # Status counts across all properties
    count_all = enquiries_base_qs.count()
    count_new = enquiries_base_qs.filter(status='NEW').count()
    count_contacted = enquiries_base_qs.filter(status='CONTACTED').count()
    count_interested = enquiries_base_qs.filter(status='INTERESTED').count()
    count_visit = enquiries_base_qs.filter(status='VISIT_REQUESTED').count()
    count_converted = enquiries_base_qs.filter(status='CONVERTED').count()
    count_closed = enquiries_base_qs.filter(status='CLOSED').count()

    enquiries_qs = enquiries_base_qs

    # Filter by property
    selected_property_id = request.GET.get('property_id')
    if selected_property_id and selected_property_id != 'all':
        try:
            enquiries_qs = enquiries_qs.filter(property_id=int(selected_property_id))
        except:
            pass

    # Filter by status tab
    status_filter = request.GET.get('status', 'all').lower()
    if status_filter == 'new':
        enquiries_qs = enquiries_qs.filter(status='NEW')
    elif status_filter == 'contacted':
        enquiries_qs = enquiries_qs.filter(status='CONTACTED')
    elif status_filter == 'interested':
        enquiries_qs = enquiries_qs.filter(status='INTERESTED')
    elif status_filter == 'visit':
        enquiries_qs = enquiries_qs.filter(status='VISIT_REQUESTED')
    elif status_filter == 'converted':
        enquiries_qs = enquiries_qs.filter(status='CONVERTED')
    elif status_filter == 'closed':
        enquiries_qs = enquiries_qs.filter(status='CLOSED')

    # Search filter
    q = request.GET.get('q', '').strip()
    if q:
        enquiries_qs = enquiries_qs.filter(
            Q(seeker_name__icontains=q) |
            Q(seeker_phone__icontains=q) |
            Q(seeker_email__icontains=q) |
            Q(interested_room_type__icontains=q) |
            Q(message__icontains=q)
        )

    # Sort
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'oldest':
        enquiries_qs = enquiries_qs.order_by('created_at')
    elif sort_by == 'budget_high':
        enquiries_qs = enquiries_qs.order_by('-budget')
    elif sort_by == 'budget_low':
        enquiries_qs = enquiries_qs.order_by('budget')
    else:
        enquiries_qs = enquiries_qs.order_by('-created_at')

    enquiries_qs = enquiries_qs.select_related('property', 'property__locality', 'property__city')

    # Pagination: Limit 5 with Scroll Retention
    page_number = request.GET.get('page', 1)
    paginator = Paginator(enquiries_qs, 5)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'owner_user': owner,
        'all_properties': properties,
        'selected_property_id': selected_property_id,
        'page_obj': page_obj,
        'paginator': paginator,
        'enquiries': page_obj.object_list,
        'status_filter': status_filter,
        'q': q,
        'sort_by': sort_by,
        # Status counts
        'count_all': count_all,
        'count_new': count_new,
        'count_contacted': count_contacted,
        'count_interested': count_interested,
        'count_visit': count_visit,
        'count_converted': count_converted,
        'count_closed': count_closed,
        # Summary counts
        'count_in_discussion': count_contacted + count_interested,
    }
    return render(request, 'owner_portal/05_enquiries.html', context)


def enquiry_details(request, enquiry_id):
    owner = get_active_owner(request)
    properties = Property.objects.filter(owner=owner)
    enquiry = get_object_or_404(Enquiry, id=enquiry_id, property__in=properties)

    # Handle POST Actions
    if request.method == 'POST':
        action = request.POST.get('action')
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'

        # 1. Send Reply / Message
        if action in ['send_reply', 'reply']:
            reply_text = request.POST.get('reply_text', '').strip() or request.POST.get('reply_message', '').strip()
            if reply_text:
                new_msg = EnquiryMessage.objects.create(
                    enquiry=enquiry,
                    sender_type='OWNER',
                    message_text=reply_text
                )
                if enquiry.status == 'NEW':
                    enquiry.status = 'CONTACTED'
                    enquiry.save()

                msg = "Your response has been delivered to the seeker."
                AuditLog.objects.create(
                    actor=owner,
                    action_type='REPLY_ENQUIRY',
                    target_entity='ENQUIRY',
                    target_id=str(enquiry.id),
                    module='ENQUIRIES',
                    status='SUCCESS',
                    details=f"Owner replied: {reply_text[:60]}"
                )

                # Real-time Omnichannel Notification to Seeker / Tenant (Email + WhatsApp + In-App)
                dispatch_omnichannel_notification(
                    recipient=enquiry.seeker,
                    sender=owner,
                    title=f"New Message from Host {owner.get_full_name() or owner.username} · {enquiry.property.title}",
                    message=reply_text,
                    category='CHAT',
                    cta_url=f"/tenant/enquiries/{enquiry.id}/" if enquiry.seeker else "/find/",
                    cta_label="View & Reply on Portal",
                    details={
                        'Property': enquiry.property.title,
                        'Host Name': owner.get_full_name() or owner.username,
                        'Room Interested': enquiry.interested_room_type or 'General Room',
                        'Host Contact': getattr(owner, 'phone_number', '') or 'In Portal Chat',
                    },
                    email_override=enquiry.seeker_email if not enquiry.seeker else None,
                    phone_override=enquiry.seeker_phone if not enquiry.seeker else None,
                    name_override=enquiry.seeker_name if not enquiry.seeker else None
                )
                if is_ajax:
                    return JsonResponse({
                        'status': 'success',
                        'message': msg,
                        'msg_id': new_msg.id,
                        'message_text': new_msg.message_text,
                        'created_at': new_msg.created_at.strftime('%d %b %Y, %I:%M %p')
                    })
                messages.success(request, msg)

        # 2. Update Enquiry Status
        elif action == 'update_status':
            new_status = request.POST.get('status')
            if new_status in dict(Enquiry.STATUS_CHOICES):
                enquiry.status = new_status
                enquiry.save()
                msg = f"Enquiry status updated to {enquiry.get_status_display()}."
                AuditLog.objects.create(
                    actor=owner,
                    action_type='UPDATE_ENQUIRY_STATUS',
                    target_entity='ENQUIRY',
                    target_id=str(enquiry.id),
                    module='ENQUIRIES',
                    status='SUCCESS',
                    details=msg
                )
                if is_ajax:
                    return JsonResponse({
                        'status': 'success',
                        'message': msg,
                        'new_status': enquiry.status,
                        'status_display': enquiry.get_status_display()
                    })
                messages.success(request, msg)

        # 3. Schedule Visit
        elif action == 'schedule_visit':
            v_date_str = request.POST.get('visit_date')
            v_slot = request.POST.get('time_slot', '11:00 AM - 12:00 PM')
            v_notes = request.POST.get('notes', '').strip()

            try:
                v_date = datetime.datetime.strptime(v_date_str, '%Y-%m-%d').date()
            except:
                v_date = timezone.now().date() + datetime.timedelta(days=1)

            import random
            vr_code = f"VR-{random.randint(1000, 9999)}"
            while VisitRequest.objects.filter(request_id=vr_code).exists():
                vr_code = f"VR-{random.randint(1000, 9999)}"

            vr = VisitRequest.objects.create(
                request_id=vr_code,
                property=enquiry.property,
                room=enquiry.room,
                seeker_name=enquiry.seeker_name,
                seeker_phone=enquiry.seeker_phone,
                seeker_email=enquiry.seeker_email,
                request_type='VISIT',
                scheduled_date=v_date,
                scheduled_time_slot=v_slot,
                status='ACCEPTED',
                notes=v_notes or f"Visit scheduled directly from enquiry #{enquiry.id}",
                owner_reply=f"Visit scheduled for {v_date.strftime('%d %b %Y')} at {v_slot}."
            )
            enquiry.status = 'VISIT_REQUESTED'
            enquiry.save()

            EnquiryMessage.objects.create(
                enquiry=enquiry,
                sender_type='OWNER',
                message_text=f"Walkthrough visit confirmed for {v_date.strftime('%d %b %Y')} ({v_slot}). We look forward to meeting you at {enquiry.property.title}!"
            )

            msg = f"Visit scheduled for {v_date.strftime('%d %b %Y')} ({v_slot}). Booking ID: {vr.request_id}"
            AuditLog.objects.create(
                actor=owner,
                action_type='SCHEDULE_VISIT',
                target_entity='VISIT',
                target_id=str(vr.id),
                module='ENQUIRIES',
                status='SUCCESS',
                details=msg
            )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'request_id': vr.request_id})
            messages.success(request, msg)

        return redirect('owner_portal:enquiry_details', enquiry_id=enquiry.id)

    # Next / Previous Lead Navigation
    all_enquiry_ids = list(Enquiry.objects.filter(property__in=properties).order_by('-created_at', '-id').values_list('id', flat=True))
    try:
        curr_idx = all_enquiry_ids.index(enquiry.id)
    except ValueError:
        curr_idx = 0
    total_leads = len(all_enquiry_ids)
    lead_position = curr_idx + 1
    prev_enquiry_id = all_enquiry_ids[curr_idx - 1] if curr_idx > 0 else None
    next_enquiry_id = all_enquiry_ids[curr_idx + 1] if curr_idx < total_leads - 1 else None

    # Fetch Conversation Messages
    messages_list = enquiry.messages.all().order_by('created_at')

    # Related Visits for this Seeker/Property
    related_visits = VisitRequest.objects.filter(
        property=enquiry.property,
        seeker_phone=enquiry.seeker_phone
    ).order_by('-scheduled_date')

    # Audit Trail Timeline for this Enquiry
    enquiry_audit_logs = AuditLog.objects.filter(
        target_entity='ENQUIRY',
        target_id=str(enquiry.id)
    ).order_by('-created_at')[:8]

    context = {
        'owner_user': owner,
        'enquiry': enquiry,
        'messages_list': messages_list,
        'related_visits': related_visits,
        'enquiry_audit_logs': enquiry_audit_logs,
        'total_leads': total_leads,
        'lead_position': lead_position,
        'prev_enquiry_id': prev_enquiry_id,
        'next_enquiry_id': next_enquiry_id,
    }
    return render(request, 'owner_portal/06_enquiry_details.html', context)


def booking_requests(request):
    owner = get_active_owner(request)
    properties = Property.objects.filter(owner=owner)

    # Handle POST Actions (Forms or AJAX)
    if request.method == 'POST':
        action = request.POST.get('action')
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'
        req_id = request.POST.get('request_id')
        visit = get_object_or_404(VisitRequest, id=req_id, property__in=properties)

        # 1. Accept Visit / Booking
        if action in ['accept', 'accept_request']:
            visit.status = 'ACCEPTED'
            reply = request.POST.get('owner_reply', '').strip() or request.POST.get('notes', '').strip()
            if reply:
                visit.owner_reply = reply
            visit.save()
            msg = f"Request #{visit.request_id} accepted successfully."
            AuditLog.objects.create(
                actor=owner,
                action_type='ACCEPT_VISIT',
                target_entity='VISIT',
                target_id=str(visit.id),
                module='BOOKINGS',
                status='SUCCESS',
                details=msg
            )
            # Omnichannel Notification to Seeker (Email + WhatsApp + In-App)
            if visit.seeker:
                dispatch_omnichannel_notification(
                    recipient=visit.seeker,
                    sender=owner,
                    title=f"Walkthrough Visit Confirmed! 🎉 · {visit.property.title}",
                    message=f"Host {owner.get_full_name() or owner.username} confirmed your walkthrough visit for {visit.property.title} on {visit.scheduled_date.strftime('%d %b %Y')} ({visit.scheduled_time_slot}). Note: {visit.owner_reply or 'Looking forward to hosting you.'}",
                    category='VISIT',
                    cta_url=f"/tenant/visits/{visit.request_id}/",
                    cta_label="View Confirmed Gate Pass",
                    details={
                        'Property': visit.property.title,
                        'Date': visit.scheduled_date.strftime('%d %b %Y'),
                        'Time Slot': visit.scheduled_time_slot,
                        'Host Contact': getattr(owner, 'phone_number', '') or 'In Gate Pass',
                    }
                )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'new_status': 'ACCEPTED', 'status_display': 'Accepted'})
            messages.success(request, msg)

        # 2. Reject Visit / Booking
        elif action in ['reject', 'reject_request']:
            visit.status = 'REJECTED'
            reason = request.POST.get('reason', '').strip()
            if reason:
                visit.notes = f"{visit.notes}\nRejection Reason: {reason}".strip()
            visit.save()
            msg = f"Request #{visit.request_id} rejected."
            AuditLog.objects.create(
                actor=owner,
                action_type='REJECT_VISIT',
                target_entity='VISIT',
                target_id=str(visit.id),
                module='BOOKINGS',
                status='SUCCESS',
                details=msg
            )
            # Cross-Portal Omnichannel Notification to Seeker (Email + WhatsApp + In-App)
            if visit.seeker:
                dispatch_omnichannel_notification(
                    recipient=visit.seeker,
                    sender=owner,
                    title=f"Walkthrough Visit Update · {visit.property.title}",
                    message=f"Host was unable to accommodate visit for {visit.property.title}. {reason or ''}",
                    category='VISIT',
                    cta_url="/tenant/find/",
                    cta_label="Find Stays",
                    details={
                        'Property': visit.property.title,
                        'Status': 'Unable to Accommodate',
                        'Note': reason or 'Slot unavailable',
                    }
                )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'new_status': 'REJECTED', 'status_display': 'Rejected'})
            messages.success(request, msg)

        # 3. Reschedule Visit
        elif action == 'reschedule':
            new_date_str = request.POST.get('new_date')
            new_slot = request.POST.get('new_slot', '11:00 AM - 12:00 PM')
            try:
                new_date = datetime.datetime.strptime(new_date_str, '%Y-%m-%d').date()
                visit.scheduled_date = new_date
            except:
                pass
            visit.scheduled_time_slot = new_slot
            visit.status = 'RESCHEDULED'
            visit.owner_reply = f"Rescheduled to {new_date_str} ({new_slot})."
            visit.save()
            msg = f"Request #{visit.request_id} rescheduled to {visit.scheduled_date} ({visit.scheduled_time_slot})."
            AuditLog.objects.create(
                actor=owner,
                action_type='RESCHEDULE_VISIT',
                target_entity='VISIT',
                target_id=str(visit.id),
                module='BOOKINGS',
                status='SUCCESS',
                details=msg
            )
            # Cross-Portal Omnichannel Notification to Seeker (Email + WhatsApp + In-App)
            if visit.seeker:
                dispatch_omnichannel_notification(
                    recipient=visit.seeker,
                    sender=owner,
                    title=f"Host Proposed New Walkthrough Slot · {visit.property.title}",
                    message=f"Host proposed {visit.scheduled_date.strftime('%d %b %Y')} ({visit.scheduled_time_slot}) for {visit.property.title}. Please review.",
                    category='VISIT',
                    cta_url=f"/tenant/visits/{visit.request_id}/",
                    cta_label="Review Proposed Slot",
                    details={
                        'Property': visit.property.title,
                        'Proposed Date': visit.scheduled_date.strftime('%d %b %Y'),
                        'Proposed Time': visit.scheduled_time_slot,
                    }
                )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'new_status': 'RESCHEDULED', 'status_display': 'Rescheduled'})
            messages.success(request, msg)

        # 4. Mark Completed
        elif action == 'complete':
            visit.status = 'COMPLETED'
            visit.save()
            msg = f"Request #{visit.request_id} marked as completed."
            AuditLog.objects.create(
                actor=owner,
                action_type='COMPLETE_VISIT',
                target_entity='VISIT',
                target_id=str(visit.id),
                module='BOOKINGS',
                status='SUCCESS',
                details=msg
            )
            # Cross-Portal Omnichannel Notification to Seeker (Email + WhatsApp + In-App)
            if visit.seeker:
                dispatch_omnichannel_notification(
                    recipient=visit.seeker,
                    sender=owner,
                    title=f"Walkthrough Visit Completed 🎉 · {visit.property.title}",
                    message=f"Thank you for visiting {visit.property.title}! Would you like to proceed with reserving your room?",
                    category='VISIT',
                    cta_url="/tenant/bookings/",
                    cta_label="Book Accommodation",
                    details={
                        'Property': visit.property.title,
                        'Host': owner.get_full_name() or owner.username,
                        'Status': 'Visit Completed',
                    }
                )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'new_status': 'COMPLETED', 'status_display': 'Completed'})
            messages.success(request, msg)

        return redirect(f"{request.get_full_path()}#bookingsList")

    # Base query
    base_qs = VisitRequest.objects.filter(property__in=properties)

    # 1. Summary Metrics
    count_all = base_qs.count()
    count_pending = base_qs.filter(status='PENDING').count()
    count_accepted = base_qs.filter(status='ACCEPTED').count()
    count_rescheduled = base_qs.filter(status='RESCHEDULED').count()
    count_completed = base_qs.filter(status='COMPLETED').count()
    count_cancelled = base_qs.filter(status='CANCELLED').count()
    count_rejected = base_qs.filter(status='REJECTED').count()

    requests_qs = base_qs

    # 2. Filter by status
    status_filter = request.GET.get('status', 'all').lower()
    if status_filter == 'pending':
        requests_qs = requests_qs.filter(status='PENDING')
    elif status_filter == 'accepted':
        requests_qs = requests_qs.filter(status='ACCEPTED')
    elif status_filter == 'rescheduled':
        requests_qs = requests_qs.filter(status='RESCHEDULED')
    elif status_filter == 'completed':
        requests_qs = requests_qs.filter(status='COMPLETED')
    elif status_filter == 'cancelled':
        requests_qs = requests_qs.filter(status='CANCELLED')
    elif status_filter == 'rejected':
        requests_qs = requests_qs.filter(status='REJECTED')

    # 3. Filter by property
    selected_property_id = request.GET.get('property_id')
    if selected_property_id and selected_property_id != 'all':
        try:
            requests_qs = requests_qs.filter(property_id=int(selected_property_id))
        except ValueError:
            pass

    # 4. Search Filter
    q = request.GET.get('q', '').strip()
    if q:
        requests_qs = requests_qs.filter(
            Q(seeker_name__icontains=q) |
            Q(seeker_phone__icontains=q) |
            Q(seeker_email__icontains=q) |
            Q(request_id__icontains=q) |
            Q(notes__icontains=q) |
            Q(property__title__icontains=q)
        )

    # 5. Sorting
    sort_by = request.GET.get('sort', 'date_desc')
    if sort_by == 'date_asc':
        requests_qs = requests_qs.order_by('scheduled_date', 'id')
    elif sort_by == 'newest':
        requests_qs = requests_qs.order_by('-created_at')
    else: # date_desc
        requests_qs = requests_qs.order_by('-scheduled_date', '-id')

    # 6. Pagination - Limit 5 per page
    paginator = Paginator(requests_qs, 5)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'owner_user': owner,
        'properties': properties,
        'visit_requests': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'status_filter': status_filter,
        'selected_property_id': selected_property_id,
        'q': q,
        'sort_by': sort_by,
        'count_all': count_all,
        'count_pending': count_pending,
        'count_accepted': count_accepted,
        'count_rescheduled': count_rescheduled,
        'count_completed': count_completed,
        'count_cancelled': count_cancelled,
        'count_rejected': count_rejected,
    }
    return render(request, 'owner_portal/07_booking_requests.html', context)


def booking_request_details(request, request_id):
    owner = get_active_owner(request)
    properties = Property.objects.filter(owner=owner)
    visit = get_object_or_404(VisitRequest, id=request_id, property__in=properties)

    # Handle POST Actions (status changes, notes saving)
    if request.method == 'POST':
        action = request.POST.get('action')
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'

        if action == 'save_notes':
            internal_note = request.POST.get('internal_notes', '').strip()
            visit.notes = internal_note
            visit.save()
            msg = "Private owner notes updated successfully."
            messages.success(request, msg)

        elif action == 'accept':
            visit.status = 'ACCEPTED'
            reply = request.POST.get('owner_reply', '').strip()
            if reply:
                visit.owner_reply = reply
            visit.save()
            msg = f"Request #{visit.request_id} has been accepted."
            if visit.seeker:
                dispatch_omnichannel_notification(
                    recipient=visit.seeker,
                    sender=owner,
                    title=f"Walkthrough Visit Confirmed! 🎉 · {visit.property.title}",
                    message=f"Host confirmed your walkthrough visit for {visit.property.title} on {visit.scheduled_date.strftime('%d %b %Y')} ({visit.scheduled_time_slot}). Note: {visit.owner_reply or 'Looking forward to hosting you.'}",
                    category='VISIT',
                    cta_url=f"/tenant/visits/{visit.request_id}/",
                    cta_label="View Confirmed Gate Pass",
                    details={
                        'Property': visit.property.title,
                        'Date': visit.scheduled_date.strftime('%d %b %Y'),
                        'Time Slot': visit.scheduled_time_slot,
                    }
                )
            messages.success(request, msg)

        elif action == 'reschedule':
            new_date_str = request.POST.get('new_date')
            new_slot = request.POST.get('new_slot', '11:00 AM - 12:00 PM')
            try:
                visit.scheduled_date = datetime.datetime.strptime(new_date_str, '%Y-%m-%d').date()
            except:
                pass
            visit.scheduled_time_slot = new_slot
            visit.status = 'RESCHEDULED'
            visit.save()
            msg = f"Request rescheduled to {visit.scheduled_date} ({visit.scheduled_time_slot})."
            if visit.seeker:
                dispatch_omnichannel_notification(
                    recipient=visit.seeker,
                    sender=owner,
                    title=f"Walkthrough Rescheduled · {visit.property.title}",
                    message=f"Host proposed a new walkthrough time: {visit.scheduled_date.strftime('%d %b %Y')} ({visit.scheduled_time_slot}).",
                    category='VISIT',
                    cta_url=f"/tenant/visits/{visit.request_id}/",
                    cta_label="Review New Time",
                    details={
                        'Property': visit.property.title,
                        'New Date': visit.scheduled_date.strftime('%d %b %Y'),
                        'New Slot': visit.scheduled_time_slot,
                    }
                )
            messages.success(request, msg)

        elif action == 'complete':
            visit.status = 'COMPLETED'
            visit.save()
            msg = f"Request #{visit.request_id} marked as completed."
            if visit.seeker:
                dispatch_omnichannel_notification(
                    recipient=visit.seeker,
                    sender=owner,
                    title=f"Walkthrough Visit Completed 🎉 · {visit.property.title}",
                    message=f"Thank you for attending the walkthrough visit at {visit.property.title}! Would you like to reserve your room now?",
                    category='VISIT',
                    cta_url="/tenant/bookings/",
                    cta_label="Book Accommodation"
                )
            messages.success(request, msg)

        elif action == 'cancel':
            visit.status = 'CANCELLED'
            visit.save()
            msg = f"Request #{visit.request_id} cancelled."
            if visit.seeker:
                dispatch_omnichannel_notification(
                    recipient=visit.seeker,
                    sender=owner,
                    title=f"Walkthrough Cancelled · {visit.property.title}",
                    message=f"Host was unable to confirm your walkthrough visit #{visit.request_id} for {visit.property.title}.",
                    category='VISIT',
                    cta_url="/tenant/find/",
                    cta_label="Browse Other Spaces"
                )
            messages.success(request, msg)

        return redirect('owner_portal:booking_request_details', request_id=visit.id)

    # Next / Previous Visit switcher
    all_visit_ids = list(VisitRequest.objects.filter(property__in=properties).order_by('-scheduled_date', '-id').values_list('id', flat=True))
    try:
        curr_idx = all_visit_ids.index(visit.id)
    except ValueError:
        curr_idx = 0
    total_visits = len(all_visit_ids)
    visit_position = curr_idx + 1
    prev_visit_id = all_visit_ids[curr_idx - 1] if curr_idx > 0 else None
    next_visit_id = all_visit_ids[curr_idx + 1] if curr_idx < total_visits - 1 else None

    # Check matching enquiry
    matching_enquiry = Enquiry.objects.filter(seeker_phone=visit.seeker_phone, property=visit.property).first()

    context = {
        'owner_user': owner,
        'visit': visit,
        'matching_enquiry': matching_enquiry,
        'total_visits': total_visits,
        'visit_position': visit_position,
        'prev_visit_id': prev_visit_id,
        'next_visit_id': next_visit_id,
    }
    return render(request, 'owner_portal/08_booking_request_details.html', context)


def pricing_availability(request):
    owner = get_active_owner(request)
    properties = Property.objects.filter(owner=owner).order_by('id')

    # Handle POST Actions (Forms or AJAX)
    if request.method == 'POST':
        action = request.POST.get('action')
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'

        # 1. Update Single Room Pricing & Availability
        if action == 'update_room_pricing':
            room_id = request.POST.get('room_id')
            room = get_object_or_404(Room, id=room_id, property__owner=owner)

            rent_str = request.POST.get('monthly_rent', '').replace('₹', '').replace(',', '').strip()
            deposit_str = request.POST.get('security_deposit', '').replace('₹', '').replace(',', '').strip()
            avail_beds_str = request.POST.get('available_beds', '').strip()
            avail_from_str = request.POST.get('available_from', '').strip()

            if rent_str:
                try:
                    room.monthly_rent = Decimal(rent_str)
                except:
                    pass
            if deposit_str:
                try:
                    room.security_deposit = Decimal(deposit_str)
                except:
                    pass
            if avail_beds_str:
                try:
                    beds_count = int(avail_beds_str)
                    room.available_beds = max(0, min(room.total_beds, beds_count))
                    room.occupied_beds = room.total_beds - room.available_beds
                except:
                    pass
            if avail_from_str:
                try:
                    room.available_from = datetime.datetime.strptime(avail_from_str, '%Y-%m-%d').date()
                except:
                    room.available_from = None
            else:
                room.available_from = None

            room.save()

            # Sync Bed objects
            room_beds = list(room.beds.all().order_by('id'))
            for i, bed in enumerate(room_beds):
                if i < room.occupied_beds:
                    bed.status = 'OCCUPIED'
                else:
                    bed.status = 'AVAILABLE'
                bed.save()

            msg = f"Pricing and availability for Room {room.room_number} ({room.property.title}) updated successfully."
            AuditLog.objects.create(
                actor=owner,
                action_type='UPDATE_ROOM_PRICING',
                target_entity='ROOM',
                target_id=str(room.id),
                module='PRICING',
                status='SUCCESS',
                details=msg
            )
            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'message': msg,
                    'room_id': room.id,
                    'monthly_rent': float(room.monthly_rent),
                    'security_deposit': float(room.security_deposit),
                    'available_beds': room.available_beds,
                    'total_beds': room.total_beds,
                    'is_full': room.available_beds == 0
                })
            messages.success(request, msg)

        # 2. Mark Room Full (available_beds = 0)
        elif action == 'mark_room_full':
            room_id = request.POST.get('room_id')
            room = get_object_or_404(Room, id=room_id, property__owner=owner)
            room.available_beds = 0
            room.occupied_beds = room.total_beds
            room.save()
            room.beds.all().update(status='OCCUPIED')

            msg = f"Room {room.room_number} marked as Completely Full."
            AuditLog.objects.create(
                actor=owner,
                action_type='MARK_ROOM_FULL',
                target_entity='ROOM',
                target_id=str(room.id),
                module='PRICING',
                status='SUCCESS',
                details=msg
            )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'room_id': room.id, 'available_beds': 0, 'is_full': True})
            messages.success(request, msg)

        # 3. Mark Room Available (available_beds = total_beds or 1)
        elif action == 'mark_room_available':
            room_id = request.POST.get('room_id')
            room = get_object_or_404(Room, id=room_id, property__owner=owner)
            room.available_beds = room.total_beds
            room.occupied_beds = 0
            room.available_from = None
            room.save()
            room.beds.all().update(status='AVAILABLE')

            msg = f"Room {room.room_number} marked as Vacant / Available ({room.total_beds} beds open)."
            AuditLog.objects.create(
                actor=owner,
                action_type='MARK_ROOM_AVAILABLE',
                target_entity='ROOM',
                target_id=str(room.id),
                module='PRICING',
                status='SUCCESS',
                details=msg
            )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'room_id': room.id, 'available_beds': room.available_beds, 'is_full': False})
            messages.success(request, msg)

        # 4. Update Property Mandatory Charges
        elif action == 'update_property_charges':
            prop_id = request.POST.get('property_id')
            prop = get_object_or_404(Property, id=prop_id, owner=owner)
            meta, _ = PropertyMetadata.objects.get_or_create(property=prop)

            meta.maintenance_charges = request.POST.get('maintenance_charges', meta.maintenance_charges).strip()
            meta.electricity_charges = request.POST.get('electricity_charges', meta.electricity_charges).strip()
            meta.food_charges = request.POST.get('food_charges', meta.food_charges).strip()
            meta.rules_notice_period = request.POST.get('rules_notice_period', meta.rules_notice_period).strip()
            meta.rules_minimum_stay = request.POST.get('rules_minimum_stay', meta.rules_minimum_stay).strip()
            meta.save()

            msg = f"Mandatory charges for {prop.title} updated successfully."
            AuditLog.objects.create(
                actor=owner,
                action_type='UPDATE_PROPERTY_CHARGES',
                target_entity='PROPERTY',
                target_id=str(prop.id),
                module='PRICING',
                status='SUCCESS',
                details=msg
            )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg})
            messages.success(request, msg)

        # 5. Bulk Update Pricing across displayed rooms
        elif action == 'bulk_update_pricing':
            count_updated = 0
            for key, val in request.POST.items():
                if key.startswith('rent_'):
                    r_id = key.split('_')[1]
                    try:
                        r = Room.objects.get(id=int(r_id), property__owner=owner)
                        clean_rent = Decimal(val.replace('₹', '').replace(',', '').strip())
                        deposit_key = f'deposit_{r_id}'
                        clean_deposit = Decimal(request.POST.get(deposit_key, str(r.security_deposit)).replace('₹', '').replace(',', '').strip())
                        r.monthly_rent = clean_rent
                        r.security_deposit = clean_deposit
                        r.save()
                        count_updated += 1
                    except:
                        pass
            msg = f"Bulk updated pricing for {count_updated} room configurations."
            AuditLog.objects.create(
                actor=owner,
                action_type='BULK_UPDATE_PRICING',
                target_entity='ROOM',
                target_id=None,
                module='PRICING',
                status='SUCCESS',
                details=msg
            )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'count_updated': count_updated})
            messages.success(request, msg)

        return redirect(f"{request.get_full_path()}#pricingList")

    # Base Queryset: all rooms belonging to this owner
    all_rooms_base = Room.objects.filter(property__in=properties).select_related('property', 'property__meta_details')

    # Overall Summary KPIs across all rooms
    total_rooms_count = all_rooms_base.count()
    total_beds_agg = all_rooms_base.aggregate(Sum('total_beds'))['total_beds__sum'] or 0
    available_beds_agg = all_rooms_base.aggregate(Sum('available_beds'))['available_beds__sum'] or 0
    occupied_beds_agg = max(0, total_beds_agg - available_beds_agg)
    occupancy_pct = int((occupied_beds_agg / total_beds_agg) * 100) if total_beds_agg > 0 else 0
    avg_rent = int(all_rooms_base.aggregate(Avg('monthly_rent'))['monthly_rent__avg'] or 0)

    # Status counts for filter pills
    count_all = total_rooms_count
    count_available = all_rooms_base.filter(available_beds__gt=0).count()
    count_fast_filling = all_rooms_base.filter(available_beds=1).count()
    count_full = all_rooms_base.filter(available_beds=0).count()

    rooms_qs = all_rooms_base

    # 1. Filter by Property
    selected_property_id = request.GET.get('property_id')
    selected_property = None
    if selected_property_id and selected_property_id != 'all':
        try:
            rooms_qs = rooms_qs.filter(property_id=int(selected_property_id))
            selected_property = Property.objects.filter(id=int(selected_property_id), owner=owner).first()
        except ValueError:
            pass

    # 2. Filter by Room Type
    selected_room_type = request.GET.get('room_type', 'all')
    if selected_room_type and selected_room_type != 'all':
        rooms_qs = rooms_qs.filter(room_type=selected_room_type.upper())

    # 3. Filter by Status (all, available, fast_filling, full)
    status_filter = request.GET.get('status', 'all').lower()
    if status_filter == 'available':
        rooms_qs = rooms_qs.filter(available_beds__gt=0)
    elif status_filter == 'fast_filling':
        rooms_qs = rooms_qs.filter(available_beds=1)
    elif status_filter == 'full':
        rooms_qs = rooms_qs.filter(available_beds=0)

    # 4. Search Filter
    q = request.GET.get('q', '').strip()
    if q:
        rooms_qs = rooms_qs.filter(
            Q(room_number__icontains=q) |
            Q(property__title__icontains=q) |
            Q(amenities__icontains=q)
        )

    # 5. Sorting
    sort_by = request.GET.get('sort', 'property')
    if sort_by == 'rent_asc':
        rooms_qs = rooms_qs.order_by('monthly_rent', 'id')
    elif sort_by == 'rent_desc':
        rooms_qs = rooms_qs.order_by('-monthly_rent', '-id')
    elif sort_by == 'vacant_desc':
        rooms_qs = rooms_qs.order_by('-available_beds', 'id')
    elif sort_by == 'full_first':
        rooms_qs = rooms_qs.order_by('available_beds', 'id')
    else: # default
        rooms_qs = rooms_qs.order_by('property__title', 'room_number')

    # 6. Pagination (Limit 5 Rooms per page)
    paginator = Paginator(rooms_qs, 5)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # 7. Preload property metadata for modal
    meta_dict = {}
    for p in properties:
        meta_dict[p.id] = {
            'title': p.title,
            'maintenance': getattr(p, 'meta_details', None).maintenance_charges if hasattr(p, 'meta_details') else '₹0 (Included in Rent)',
            'electricity': getattr(p, 'meta_details', None).electricity_charges if hasattr(p, 'meta_details') else 'By Meter Unit',
            'food': getattr(p, 'meta_details', None).food_charges if hasattr(p, 'meta_details') else 'Optional 3-time meals',
            'notice': getattr(p, 'meta_details', None).rules_notice_period if hasattr(p, 'meta_details') else '30 Days',
            'lockin': getattr(p, 'meta_details', None).rules_minimum_stay if hasattr(p, 'meta_details') else '3 Months',
        }

    context = {
        'owner_user': owner,
        'properties': properties,
        'selected_property': selected_property,
        'selected_property_id': selected_property_id,
        'selected_room_type': selected_room_type,
        'status_filter': status_filter,
        'q': q,
        'sort_by': sort_by,
        'rooms': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_rooms_count': total_rooms_count,
        'total_beds_agg': total_beds_agg,
        'available_beds_agg': available_beds_agg,
        'occupied_beds_agg': occupied_beds_agg,
        'occupancy_pct': occupancy_pct,
        'avg_rent': avg_rent,
        'count_all': count_all,
        'count_available': count_available,
        'count_fast_filling': count_fast_filling,
        'count_full': count_full,
        'meta_dict_json': json.dumps(meta_dict),
    }
    return render(request, 'owner_portal/09_pricing_availability.html', context)


def reviews_ratings(request):
    owner = get_active_owner(request)
    properties = Property.objects.filter(owner=owner).order_by('id')

    # Handle POST Actions (Forms or AJAX)
    if request.method == 'POST':
        action = request.POST.get('action')
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'
        review_id = request.POST.get('review_id')
        review = get_object_or_404(Review, id=review_id, property__owner=owner)

        # 1. Reply to Review
        if action == 'reply_review':
            reply_text = request.POST.get('reply_text', '').strip()
            if reply_text:
                review.owner_reply = reply_text
                review.owner_reply_at = timezone.now()
                review.save()
                msg = f"Public response to {review.reviewer_name}'s review published."
                AuditLog.objects.create(
                    actor=owner,
                    action_type='REPLY_REVIEW',
                    target_entity='REVIEW',
                    target_id=review.id,
                    module='REVIEWS',
                    status='SUCCESS',
                    details=f"Owner replied: {reply_text[:60]}"
                )
                if is_ajax:
                    return JsonResponse({
                        'status': 'success',
                        'message': msg,
                        'review_id': review.id,
                        'owner_reply': review.owner_reply,
                        'owner_reply_at': review.owner_reply_at.strftime('%d %b %Y')
                    })
                messages.success(request, msg)

        # 2. Report Review to Admin Moderation
        elif action == 'report_review':
            reason = request.POST.get('report_reason', 'DISPUTED_CONTENT')
            details = request.POST.get('report_details', '').strip()

            review.is_flagged = True
            review.status = 'REPORTED'
            review.reported_by = owner
            review.report_reason = reason
            review.report_details = details
            review.reported_time_text = timezone.now().strftime('%d %b %Y, %I:%M %p')
            review.save()

            msg = f"Review #{review.review_code or review.id} submitted to Admin moderation team for review."
            AuditLog.objects.create(
                actor=owner,
                action_type='REPORT_REVIEW',
                target_entity='REVIEW',
                target_id=review.id,
                module='REVIEWS',
                status='SUCCESS',
                details=f"Owner reported review: {reason} - {details[:60]}"
            )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'review_id': review.id, 'new_status': 'REPORTED'})
            messages.success(request, msg)

        return redirect(f"{request.get_full_path()}#reviewsList")

    # Base Queryset: all reviews across this owner's properties
    base_reviews = Review.objects.filter(property__in=properties).select_related('property', 'user')

    # Overall Summary Metrics
    total_reviews = base_reviews.count()
    avg_rating_val = base_reviews.aggregate(Avg('rating'))['rating__avg'] or 0.0
    avg_rating = round(float(avg_rating_val), 1)

    # Rating breakdown
    count_5_star = base_reviews.filter(rating=5).count()
    count_4_star = base_reviews.filter(rating=4).count()
    count_3_star = base_reviews.filter(rating=3).count()
    count_2_star = base_reviews.filter(rating=2).count()
    count_1_star = base_reviews.filter(rating=1).count()

    pct_5_star = int((count_5_star / total_reviews) * 100) if total_reviews > 0 else 0
    pct_4_star = int((count_4_star / total_reviews) * 100) if total_reviews > 0 else 0
    pct_3_star = int((count_3_star / total_reviews) * 100) if total_reviews > 0 else 0
    pct_2_star = int((count_2_star / total_reviews) * 100) if total_reviews > 0 else 0
    pct_1_star = int((count_1_star / total_reviews) * 100) if total_reviews > 0 else 0

    # Tab counts
    count_replied = base_reviews.filter(owner_reply__isnull=False).exclude(owner_reply='').count()
    count_awaiting_reply = base_reviews.filter(Q(owner_reply__isnull=True) | Q(owner_reply='')).count()
    count_reported = base_reviews.filter(Q(is_flagged=True) | Q(status='REPORTED')).count()

    reviews_qs = base_reviews

    # 1. Filter by Property
    selected_property_id = request.GET.get('property_id')
    if selected_property_id and selected_property_id != 'all':
        try:
            reviews_qs = reviews_qs.filter(property_id=int(selected_property_id))
        except ValueError:
            pass

    # 2. Filter by Rating / Category Tab
    tab = request.GET.get('tab', 'all').lower()
    if tab == '5star':
        reviews_qs = reviews_qs.filter(rating=5)
    elif tab == '4star':
        reviews_qs = reviews_qs.filter(rating=4)
    elif tab == '3star':
        reviews_qs = reviews_qs.filter(rating__lte=3)
    elif tab == 'replied':
        reviews_qs = reviews_qs.filter(owner_reply__isnull=False).exclude(owner_reply='')
    elif tab == 'awaiting':
        reviews_qs = reviews_qs.filter(Q(owner_reply__isnull=True) | Q(owner_reply=''))
    elif tab == 'reported':
        reviews_qs = reviews_qs.filter(Q(is_flagged=True) | Q(status='REPORTED'))

    # 3. Live Search Filter
    q = request.GET.get('q', '').strip()
    if q:
        reviews_qs = reviews_qs.filter(
            Q(comment__icontains=q) |
            Q(title__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(property__title__icontains=q) |
            Q(review_code__icontains=q)
        )

    # 4. Sorting
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'highest':
        reviews_qs = reviews_qs.order_by('-rating', '-created_at')
    elif sort_by == 'lowest':
        reviews_qs = reviews_qs.order_by('rating', '-created_at')
    elif sort_by == 'oldest':
        reviews_qs = reviews_qs.order_by('created_at')
    else: # newest
        reviews_qs = reviews_qs.order_by('-created_at', '-id')

    # 5. Pagination: Limit 5 Reviews per page
    paginator = Paginator(reviews_qs, 5)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Property-wise ratings aggregation for overview card
    property_ratings = []
    for p in properties:
        p_revs = base_reviews.filter(property=p)
        p_count = p_revs.count()
        p_avg = round(float(p_revs.aggregate(Avg('rating'))['rating__avg'] or 0.0), 1)
        if p_count > 0:
            property_ratings.append({
                'property': p,
                'count': p_count,
                'avg': p_avg
            })

    context = {
        'owner_user': owner,
        'properties': properties,
        'selected_property_id': selected_property_id,
        'tab': tab,
        'q': q,
        'sort_by': sort_by,
        'reviews': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_reviews': total_reviews,
        'avg_rating': avg_rating,
        'count_5_star': count_5_star,
        'count_4_star': count_4_star,
        'count_3_star': count_3_star,
        'count_2_star': count_2_star,
        'count_1_star': count_1_star,
        'pct_5_star': pct_5_star,
        'pct_4_star': pct_4_star,
        'pct_3_star': pct_3_star,
        'pct_2_star': pct_2_star,
        'pct_1_star': pct_1_star,
        'count_replied': count_replied,
        'count_awaiting_reply': count_awaiting_reply,
        'count_reported': count_reported,
        'property_ratings': property_ratings,
    }
    return render(request, 'owner_portal/10_reviews.html', context)


def subscription_billing(request):
    owner = get_active_owner(request)
    subscription, _ = OwnerSubscription.objects.get_or_create(
        owner=owner,
        defaults={
            'plan_name': 'KiraayaGrid Standard',
            'is_active': True,
            'valid_until': datetime.date(2027, 5, 15),
            'monthly_price': Decimal('0.00'),
            'featured_listings_count': 1,
        }
    )

    # Handle POST Actions (Forms or AJAX)
    if request.method == 'POST':
        action = request.POST.get('action')
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'

        # 1. Upgrade Plan
        if action == 'upgrade_plan':
            plan_type = request.POST.get('plan_type', 'PLUS')
            if plan_type == 'PLUS':
                new_plan = 'KiraayaGrid Plus'
                price = Decimal('1999.00')
                gst = Decimal('359.82')
                boosts = 3
            elif plan_type == 'PRO':
                new_plan = 'KiraayaGrid Growth Pro'
                price = Decimal('4999.00')
                gst = Decimal('899.82')
                boosts = 8
            else:
                new_plan = 'KiraayaGrid Standard'
                price = Decimal('0.00')
                gst = Decimal('0.00')
                boosts = 1

            subscription.plan_name = new_plan
            subscription.monthly_price = price
            subscription.featured_listings_count = boosts
            subscription.is_active = True
            subscription.valid_until = timezone.now().date() + datetime.timedelta(days=365)
            subscription.save()

            # Generate Invoice
            import random
            inv_code = f"INV-2026-{random.randint(200, 999)}"
            while Invoice.objects.filter(invoice_number=inv_code).exists():
                inv_code = f"INV-2026-{random.randint(200, 999)}"

            inv = Invoice.objects.create(
                owner=owner,
                invoice_number=inv_code,
                plan_name=f"{new_plan} Subscription Plan",
                amount=price,
                gst_amount=gst,
                status='PAID',
                billing_date=timezone.now().date()
            )

            msg = f"Successfully upgraded to {new_plan}! Invoice #{inv.invoice_number} generated."
            AuditLog.objects.create(
                actor=owner,
                action_type='UPGRADE_PLAN',
                target_entity='SUBSCRIPTION',
                target_id=subscription.id,
                module='BILLING',
                status='SUCCESS',
                details=msg
            )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'plan_name': new_plan, 'price': float(price), 'invoice': inv.invoice_number})
            messages.success(request, msg)

        # 2. Renew Subscription
        elif action == 'renew_subscription':
            curr_expiry = subscription.valid_until or timezone.now().date()
            subscription.valid_until = max(curr_expiry, timezone.now().date()) + datetime.timedelta(days=365)
            subscription.is_active = True
            subscription.save()

            import random
            inv_code = f"INV-2026-{random.randint(200, 999)}"
            inv = Invoice.objects.create(
                owner=owner,
                invoice_number=inv_code,
                plan_name=f"1-Year Renewal: {subscription.plan_name}",
                amount=subscription.monthly_price,
                gst_amount=Decimal(round(float(subscription.monthly_price) * 0.18, 2)),
                status='PAID',
                billing_date=timezone.now().date()
            )

            msg = f"Subscription renewed through {subscription.valid_until.strftime('%d %b %Y')}."
            AuditLog.objects.create(
                actor=owner,
                action_type='RENEW_SUBSCRIPTION',
                target_entity='SUBSCRIPTION',
                target_id=subscription.id,
                module='BILLING',
                status='SUCCESS',
                details=msg
            )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'valid_until': subscription.valid_until.strftime('%d %b %Y')})
            messages.success(request, msg)

        # 3. Purchase Featured Discovery Boost
        elif action == 'purchase_boost':
            prop_id = request.POST.get('property_id')
            subscription.featured_listings_count += 1
            subscription.save()

            import random
            inv_code = f"INV-2026-{random.randint(200, 999)}"
            inv = Invoice.objects.create(
                owner=owner,
                invoice_number=inv_code,
                plan_name="30-Day Featured Listing Discovery Boost",
                amount=Decimal('1499.00'),
                gst_amount=Decimal('269.82'),
                status='PAID',
                billing_date=timezone.now().date()
            )

            msg = f"Featured Discovery Boost activated! Invoice #{inv.invoice_number} generated."
            AuditLog.objects.create(
                actor=owner,
                action_type='PURCHASE_BOOST',
                target_entity='PROPERTY',
                target_id=int(prop_id) if prop_id and prop_id.isdigit() else None,
                module='BILLING',
                status='SUCCESS',
                details=msg
            )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'boosts_count': subscription.featured_listings_count})
            messages.success(request, msg)

        # 4. Pay Pending Invoice
        elif action == 'pay_invoice':
            inv_id = request.POST.get('invoice_id')
            inv = get_object_or_404(Invoice, id=inv_id, owner=owner)
            inv.status = 'PAID'
            inv.save()
            msg = f"Payment for Invoice #{inv.invoice_number} received successfully."
            AuditLog.objects.create(
                actor=owner,
                action_type='PAY_INVOICE',
                target_entity='INVOICE',
                target_id=inv.id,
                module='BILLING',
                status='SUCCESS',
                details=msg
            )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg})
            messages.success(request, msg)

        return redirect(f"{request.get_full_path()}#invoicesList")

    # Base Queryset: Invoices for this active owner
    invoices_base = Invoice.objects.filter(owner=owner).order_by('-billing_date', '-id')

    # Invoice KPI counts
    count_all = invoices_base.count()
    count_paid = invoices_base.filter(status='PAID').count()
    count_pending = invoices_base.filter(status='PENDING').count()
    count_refunded = invoices_base.filter(status='REFUNDED').count()
    total_paid_amount = invoices_base.filter(status='PAID').aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

    invoices_qs = invoices_base

    # 1. Filter by Status Tab (all, paid, pending, refunded)
    tab = request.GET.get('tab', 'all').lower()
    if tab == 'paid':
        invoices_qs = invoices_qs.filter(status='PAID')
    elif tab == 'pending':
        invoices_qs = invoices_qs.filter(status='PENDING')
    elif tab == 'refunded':
        invoices_qs = invoices_qs.filter(status='REFUNDED')

    # 2. Live Search Filter
    q = request.GET.get('q', '').strip()
    if q:
        invoices_qs = invoices_qs.filter(
            Q(invoice_number__icontains=q) |
            Q(plan_name__icontains=q)
        )

    # 3. Sorting
    sort_by = request.GET.get('sort', 'date_desc')
    if sort_by == 'date_asc':
        invoices_qs = invoices_qs.order_by('billing_date', 'id')
    elif sort_by == 'amount_high':
        invoices_qs = invoices_qs.order_by('-amount', '-id')
    elif sort_by == 'amount_low':
        invoices_qs = invoices_qs.order_by('amount', 'id')
    else: # date_desc
        invoices_qs = invoices_qs.order_by('-billing_date', '-id')

    # 4. Limit 5 Pagination
    paginator = Paginator(invoices_qs, 5)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Owner properties for boost purchase dropdown
    owner_properties = Property.objects.filter(owner=owner)

    context = {
        'owner_user': owner,
        'subscription': subscription,
        'owner_properties': owner_properties,
        'invoices': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'tab': tab,
        'q': q,
        'sort_by': sort_by,
        'count_all': count_all,
        'count_paid': count_paid,
        'count_pending': count_pending,
        'count_refunded': count_refunded,
        'total_paid_amount': total_paid_amount,
    }
    return render(request, 'owner_portal/11_subscription.html', context)


def view_invoice_receipt(request, invoice_id):
    owner = get_active_owner(request)
    invoice = get_object_or_404(Invoice, id=invoice_id, owner=owner)

    subtotal = invoice.amount - invoice.gst_amount if invoice.amount >= invoice.gst_amount else invoice.amount
    context = {
        'owner_user': owner,
        'invoice': invoice,
        'subtotal': subtotal,
    }
    return render(request, 'owner_portal/invoice_receipt.html', context)


def help_support(request):
    owner = get_active_owner(request)

    # 1. Handle POST Actions (Create Ticket, Reply, Resolve, Reopen)
    if request.method == 'POST':
        action = request.POST.get('action')
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'

        # Action: Create New Support Ticket
        if action == 'create_ticket':
            subject = request.POST.get('subject', '').strip()
            category = request.POST.get('category', 'General').strip()
            priority = request.POST.get('priority', 'MEDIUM').strip().upper()
            prop_id = request.POST.get('property_id')
            message_text = request.POST.get('message', '').strip()

            if not subject or not message_text:
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': 'Subject and message details are required.'}, status=400)
                messages.error(request, 'Subject and message details are required.')
                return redirect(f"{request.get_full_path()}#ticketsList")

            import random
            code = f"TKT-2026-{random.randint(100, 999)}"
            while SupportTicket.objects.filter(ticket_code=code).exists():
                code = f"TKT-2026-{random.randint(100, 999)}"

            rel_prop = Property.objects.filter(id=prop_id, owner=owner).first() if prop_id and prop_id.isdigit() else None
            admin_user = User.objects.filter(role='ADMIN').first()

            ticket = SupportTicket.objects.create(
                ticket_code=code,
                user=owner,
                subject=subject,
                category=category,
                channel='Platform',
                message=message_text,
                priority=priority if priority in ['LOW', 'MEDIUM', 'HIGH', 'URGENT'] else 'MEDIUM',
                status='OPEN',
                assigned_to=admin_user,
                sla_due_text='Due in 4 hours',
                sla_status='WITHIN_SLA',
                related_property=rel_prop
            )

            # Initial message in thread
            TicketMessage.objects.create(
                ticket=ticket,
                sender=owner,
                sender_name=owner.get_full_name() or owner.username,
                sender_role='Owner',
                is_internal=False,
                message=message_text
            )

            msg = f"Support Ticket #{ticket.ticket_code} created successfully! Our team will respond shortly."
            AuditLog.objects.create(
                actor=owner,
                action_type='CREATE_TICKET',
                target_entity='TICKET',
                target_id=ticket.id,
                module='SUPPORT',
                status='SUCCESS',
                details=f"Owner raised ticket {ticket.ticket_code}: {subject}"
            )

            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'message': msg,
                    'ticket_code': ticket.ticket_code,
                    'ticket_id': ticket.id
                })
            messages.success(request, msg)
            return redirect(f"{request.get_full_path()}#ticketsList")

        # Action: Reply to Ticket Thread
        elif action == 'reply_ticket':
            ticket_id = request.POST.get('ticket_id')
            ticket = get_object_or_404(SupportTicket, id=ticket_id, user=owner)
            reply_text = request.POST.get('message', '').strip()

            if not reply_text:
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': 'Reply message cannot be empty.'}, status=400)
                messages.error(request, 'Reply message cannot be empty.')
                return redirect(f"{request.get_full_path()}#ticketsList")

            tmsg = TicketMessage.objects.create(
                ticket=ticket,
                sender=owner,
                sender_name=owner.get_full_name() or owner.username,
                sender_role='Owner',
                is_internal=False,
                message=reply_text
            )

            # Re-open or update status if it was awaiting reply or resolved
            if ticket.status in ['AWAITING_REPLY', 'RESOLVED']:
                ticket.status = 'OPEN'
                ticket.sla_due_text = 'Due in 4 hours'
                ticket.save()

            AuditLog.objects.create(
                actor=owner,
                action_type='REPLY_TICKET',
                target_entity='TICKET',
                target_id=ticket.id,
                module='SUPPORT',
                status='SUCCESS',
                details=f"Owner replied to ticket {ticket.ticket_code}"
            )

            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'message': 'Reply sent successfully.',
                    'message_id': tmsg.id,
                    'sender_name': tmsg.sender_name,
                    'created_at': tmsg.created_at.strftime('%d %b %Y, %I:%M %p'),
                    'message': tmsg.message
                })
            messages.success(request, 'Your reply has been delivered to support.')
            return redirect(f"{request.get_full_path()}#ticketsList")

        # Action: Resolve Ticket
        elif action == 'resolve_ticket':
            ticket_id = request.POST.get('ticket_id')
            ticket = get_object_or_404(SupportTicket, id=ticket_id, user=owner)
            ticket.status = 'RESOLVED'
            ticket.sla_due_text = 'Resolved by Owner'
            ticket.save()

            TicketMessage.objects.create(
                ticket=ticket,
                sender=owner,
                sender_name=owner.get_full_name() or owner.username,
                sender_role='Owner',
                is_internal=False,
                message='[Ticket marked as Resolved by Owner]'
            )

            AuditLog.objects.create(
                actor=owner,
                action_type='RESOLVE_TICKET',
                target_entity='TICKET',
                target_id=ticket.id,
                module='SUPPORT',
                status='SUCCESS',
                details=f"Owner resolved ticket {ticket.ticket_code}"
            )

            if is_ajax:
                return JsonResponse({'status': 'success', 'message': f"Ticket #{ticket.ticket_code} marked as resolved."})
            messages.success(request, f"Ticket #{ticket.ticket_code} marked as resolved.")
            return redirect(f"{request.get_full_path()}#ticketsList")

        # Action: Reopen Ticket
        elif action == 'reopen_ticket':
            ticket_id = request.POST.get('ticket_id')
            ticket = get_object_or_404(SupportTicket, id=ticket_id, user=owner)
            ticket.status = 'OPEN'
            ticket.sla_due_text = 'Due in 4 hours'
            ticket.save()

            TicketMessage.objects.create(
                ticket=ticket,
                sender=owner,
                sender_name=owner.get_full_name() or owner.username,
                sender_role='Owner',
                is_internal=False,
                message='[Ticket reopened by Owner]'
            )

            AuditLog.objects.create(
                actor=owner,
                action_type='REOPEN_TICKET',
                target_entity='TICKET',
                target_id=ticket.id,
                module='SUPPORT',
                status='SUCCESS',
                details=f"Owner reopened ticket {ticket.ticket_code}"
            )

            if is_ajax:
                return JsonResponse({'status': 'success', 'message': f"Ticket #{ticket.ticket_code} reopened."})
            messages.success(request, f"Ticket #{ticket.ticket_code} reopened.")
            return redirect(f"{request.get_full_path()}#ticketsList")

        return redirect(f"{request.get_full_path()}#ticketsList")

    # Base Queryset: Tickets belonging to this owner
    tickets_base = SupportTicket.objects.filter(user=owner).order_by('-created_at')

    # Status counts for filter tabs
    count_all = tickets_base.count()
    count_open = tickets_base.filter(status='OPEN').count()
    count_progress = tickets_base.filter(status='IN_PROGRESS').count()
    count_awaiting = tickets_base.filter(status='AWAITING_REPLY').count()
    count_resolved = tickets_base.filter(status='RESOLVED').count()
    active_count = count_open + count_progress + count_awaiting

    tickets_qs = tickets_base

    # 1. Filter by Status Tab
    tab = request.GET.get('tab', 'all').lower()
    if tab == 'open':
        tickets_qs = tickets_qs.filter(status='OPEN')
    elif tab == 'in_progress':
        tickets_qs = tickets_qs.filter(status='IN_PROGRESS')
    elif tab == 'awaiting_reply':
        tickets_qs = tickets_qs.filter(status='AWAITING_REPLY')
    elif tab == 'resolved':
        tickets_qs = tickets_qs.filter(status='RESOLVED')

    # 2. Filter by Category
    category_filter = request.GET.get('category', '').strip()
    if category_filter and category_filter.lower() != 'all':
        tickets_qs = tickets_qs.filter(category__iexact=category_filter)

    # 3. Filter by Priority
    priority_filter = request.GET.get('priority', '').strip().upper()
    if priority_filter and priority_filter != 'ALL':
        tickets_qs = tickets_qs.filter(priority=priority_filter)

    # 4. Search Filter
    q = request.GET.get('q', '').strip()
    if q:
        tickets_qs = tickets_qs.filter(
            Q(ticket_code__icontains=q) |
            Q(subject__icontains=q) |
            Q(message__icontains=q)
        )

    # 5. Sorting
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'oldest':
        tickets_qs = tickets_qs.order_by('created_at', 'id')
    elif sort_by == 'priority':
        # Custom ordering: URGENT, HIGH, MEDIUM, LOW
        from django.db.models import Case, When, Value, IntegerField
        tickets_qs = tickets_qs.annotate(
            priority_rank=Case(
                When(priority='URGENT', then=Value(1)),
                When(priority='HIGH', then=Value(2)),
                When(priority='MEDIUM', then=Value(3)),
                When(priority='LOW', then=Value(4)),
                default=Value(5),
                output_field=IntegerField()
            )
        ).order_by('priority_rank', '-created_at')
    else: # newest
        tickets_qs = tickets_qs.order_by('-created_at', '-id')

    # 6. Limit 5 Pagination
    paginator = Paginator(tickets_qs, 5)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Owner properties for modal dropdown
    owner_properties = Property.objects.filter(owner=owner)

    # Knowledge Base / FAQs list
    faqs = [
        {
            'category': 'Verification & KYC',
            'question': 'What documents are required to get the Verified Owner badge on my listings?',
            'answer': 'You need an electricity bill (within last 3 months with matching consumer meter address), Index II / Registered lease deed or property tax receipt, and an Aadhaar / PAN identity document. Verification is completed by our operations team within 4 to 24 hours.'
        },
        {
            'category': 'Listing & Room Inventory',
            'question': 'How do I add multiple room sharing types (Single, Double, Triple) to a property?',
            'answer': 'Head over to Listings > Edit Property > Room Inventory. You can define custom pricing, attached bathroom options, security deposit multiples, and live bed count for each room sharing category.'
        },
        {
            'category': 'Pricing & Availability',
            'question': 'Can I apply seasonal price hikes or discounts across all my rooms at once?',
            'answer': 'Yes! Navigate to Page 9: Pricing & Availability, select your property, and use the Bulk Price Modifier tool. You can adjust all active bed rents by a flat rupee amount or percentage in one click.'
        },
        {
            'category': 'Seeker Leads & Scheduled Visits',
            'question': 'How do I confirm, reschedule or cancel a physical walkthrough request from a tenant?',
            'answer': 'In Page 6: Booking Requests & Walkthroughs, each incoming visit ticket includes tenant details and preferred time slot. You can click Accept, Propose Reschedule, or Decline with an automated WhatsApp & SMS notification sent directly to the tenant.'
        },
        {
            'category': 'Billing & GST Invoices',
            'question': 'Where can I download B2B GST tax invoices for my subscription and discovery boosts?',
            'answer': 'Go to Page 11: Subscription & Billing > Invoices & Billing History. Click "View Invoice" to view, save as PDF, or print your compliant GST tax receipt with registered HSN code and GSTIN details.'
        },
        {
            'category': 'Platform Policies & Security',
            'question': 'What happens if a prospective tenant requests an unverified cash advance or token?',
            'answer': 'KiraayaGrid strictly recommends routing token transactions through the in-app verified escrow guarantee. Never share bank account details or UPI IDs over chat. Report suspicious inquiries immediately via the "Raise Support Ticket" button.'
        }
    ]

    context = {
        'owner_user': owner,
        'tickets': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'owner_properties': owner_properties,
        'faqs': faqs,
        'tab': tab,
        'category_filter': category_filter,
        'priority_filter': priority_filter,
        'sort_by': sort_by,
        'q': q,
        'count_all': count_all,
        'count_open': count_open,
        'count_progress': count_progress,
        'count_awaiting': count_awaiting,
        'count_resolved': count_resolved,
        'active_count': active_count,
    }
    return render(request, 'owner_portal/12_support.html', context)


def ticket_detail_api(request, ticket_id):
    """API endpoint to get full ticket thread details for slide-over drawer"""
    owner = get_active_owner(request)
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=owner)

    messages_qs = ticket.messages.all().order_by('created_at')
    messages_data = []
    for m in messages_qs:
        messages_data.append({
            'id': m.id,
            'sender_name': m.sender_name,
            'sender_role': m.sender_role,
            'is_owner': (m.sender_role.lower() == 'owner' or m.sender == owner),
            'message': m.message,
            'attachment_name': m.attachment_name,
            'attachment_size': m.attachment_size,
            'created_at': m.created_at.strftime('%d %b %Y, %I:%M %p')
        })

    data = {
        'id': ticket.id,
        'ticket_code': ticket.ticket_code,
        'subject': ticket.subject,
        'category': ticket.category,
        'priority': ticket.priority,
        'status': ticket.status,
        'sla_due_text': ticket.sla_due_text or '',
        'sla_status': ticket.sla_status or 'WITHIN_SLA',
        'property_title': ticket.related_property.title if ticket.related_property else None,
        'created_at': ticket.created_at.strftime('%d %b %Y, %I:%M %p'),
        'updated_at': ticket.updated_at.strftime('%d %b %Y, %I:%M %p'),
        'messages': messages_data
    }
    return JsonResponse(data)


def notifications(request):
    owner = get_active_owner(request)

    # 1. Handle POST Actions (Mark All Read, Toggle Read, Delete Notification)
    if request.method == 'POST':
        action = request.POST.get('action')
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'

        # Action: Mark All Read
        if action == 'mark_all_read':
            updated_count = Notification.objects.filter(recipient=owner, is_read=False).update(is_read=True)
            AuditLog.objects.create(
                actor=owner,
                action_type='NOTIFICATIONS_READ_ALL',
                target_entity='NOTIFICATION',
                target_id=None,
                module='NOTIFICATIONS',
                status='SUCCESS',
                details=f"Marked {updated_count} unread notifications as read"
            )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': f'All {updated_count} notifications marked as read.'})
            messages.success(request, 'All notifications marked as read.')
            return redirect(f"{request.get_full_path()}#notificationsList")

        # Action: Toggle Read Status
        elif action == 'toggle_read':
            notif_id = request.POST.get('notification_id')
            notif = get_object_or_404(Notification, id=notif_id, recipient=owner)
            notif.is_read = not notif.is_read
            notif.save()
            status_text = 'read' if not notif.is_read else 'unread'
            if is_ajax:
                return JsonResponse({'status': 'success', 'is_read': notif.is_read, 'message': f'Marked as {status_text}.'})
            return redirect(f"{request.get_full_path()}#notificationsList")

        # Action: Mark Single Read
        elif action == 'mark_read':
            notif_id = request.POST.get('notification_id')
            notif = get_object_or_404(Notification, id=notif_id, recipient=owner)
            notif.is_read = True
            notif.save()
            if is_ajax:
                return JsonResponse({'status': 'success', 'is_read': True, 'message': 'Marked as read.'})
            return redirect(f"{request.get_full_path()}#notificationsList")

        # Action: Delete Notification
        elif action == 'delete_notification':
            notif_id = request.POST.get('notification_id')
            notif = get_object_or_404(Notification, id=notif_id, recipient=owner)
            notif.delete()
            AuditLog.objects.create(
                actor=owner,
                action_type='DELETE_NOTIFICATION',
                target_entity='NOTIFICATION',
                target_id=int(notif_id),
                module='NOTIFICATIONS',
                status='SUCCESS',
                details="Deleted notification"
            )
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': 'Notification deleted.'})
            messages.success(request, 'Notification deleted.')
            return redirect(f"{request.get_full_path()}#notificationsList")

        return redirect(f"{request.get_full_path()}#notificationsList")

    # Base Queryset: Notifications for this owner
    notifs_base = Notification.objects.filter(recipient=owner).order_by('-created_at')

    # Status counts for segmented filter tabs
    count_all = notifs_base.count()
    count_unread = notifs_base.filter(is_read=False).count()
    count_enquiry = notifs_base.filter(channel='ENQUIRY').count()
    count_visit = notifs_base.filter(channel='VISIT').count()
    count_billing = notifs_base.filter(channel='BILLING').count()
    count_system = notifs_base.filter(channel__in=['SYSTEM', 'SUPPORT']).count()

    notifs_qs = notifs_base

    # 1. Filter by Tab
    tab = request.GET.get('tab', 'all').lower()
    if tab == 'unread':
        notifs_qs = notifs_qs.filter(is_read=False)
    elif tab == 'enquiry':
        notifs_qs = notifs_qs.filter(channel='ENQUIRY')
    elif tab == 'visit':
        notifs_qs = notifs_qs.filter(channel='VISIT')
    elif tab == 'billing':
        notifs_qs = notifs_qs.filter(channel='BILLING')
    elif tab == 'system':
        notifs_qs = notifs_qs.filter(channel__in=['SYSTEM', 'SUPPORT'])

    # 2. Search Filter
    q = request.GET.get('q', '').strip()
    if q:
        notifs_qs = notifs_qs.filter(
            Q(title__icontains=q) |
            Q(message__icontains=q)
        )

    # 3. Sorting
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'oldest':
        notifs_qs = notifs_qs.order_by('created_at', 'id')
    elif sort_by == 'unread_first':
        notifs_qs = notifs_qs.order_by('is_read', '-created_at', '-id')
    else: # newest
        notifs_qs = notifs_qs.order_by('-created_at', '-id')

    # 4. Limit 5 Pagination
    paginator = Paginator(notifs_qs, 5)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'owner_user': owner,
        'notifications': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'tab': tab,
        'q': q,
        'sort_by': sort_by,
        'count_all': count_all,
        'count_unread': count_unread,
        'count_enquiry': count_enquiry,
        'count_visit': count_visit,
        'count_billing': count_billing,
        'count_system': count_system,
    }
    return render(request, 'owner_portal/13_notifications.html', context)


def profile_settings(request):
    owner = get_active_owner(request)

    # 1. Handle POST Actions (Update Profile, Password, Preferences, KYC, Deactivation)
    if request.method == 'POST':
        action = request.POST.get('action')
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'

        # Action: Update Personal Information
        if action == 'update_profile':
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone_number', '').strip()

            if not first_name or not email or not phone:
                msg = 'First name, email and primary phone are required.'
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': msg}, status=400)
                messages.error(request, msg)
                return redirect('owner_portal:profile_settings')

            # Check if phone number is taken by another user
            if User.objects.filter(phone_number=phone).exclude(id=owner.id).exists():
                msg = 'This phone number is already registered with another account.'
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': msg}, status=400)
                messages.error(request, msg)
                return redirect('owner_portal:profile_settings')

            owner.first_name = first_name
            owner.last_name = last_name
            owner.email = email
            owner.phone_number = phone
            owner.save()

            AuditLog.objects.create(
                actor=owner,
                action_type='UPDATE_PROFILE',
                target_entity='USER',
                target_id=owner.id,
                module='SETTINGS',
                status='SUCCESS',
                details=f"Updated profile: {first_name} {last_name}, {email}, {phone}"
            )

            msg = 'Profile information updated successfully!'
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'full_name': owner.get_full_name()})
            messages.success(request, msg)
            return redirect('owner_portal:profile_settings')

        # Action: Update Password
        elif action == 'update_password':
            from django.contrib.auth import update_session_auth_hash
            new_pass = request.POST.get('new_password', '').strip()
            confirm_pass = request.POST.get('confirm_password', '').strip()

            if not new_pass or len(new_pass) < 6:
                msg = 'Password must be at least 6 characters long.'
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': msg}, status=400)
                messages.error(request, msg)
                return redirect('owner_portal:profile_settings')

            if new_pass != confirm_pass:
                msg = 'New password and confirmation do not match.'
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': msg}, status=400)
                messages.error(request, msg)
                return redirect('owner_portal:profile_settings')

            owner.set_password(new_pass)
            owner.save()
            update_session_auth_hash(request, owner)

            AuditLog.objects.create(
                actor=owner,
                action_type='UPDATE_PASSWORD',
                target_entity='USER',
                target_id=owner.id,
                module='SETTINGS',
                status='SUCCESS',
                details="Owner updated account password"
            )

            msg = 'Password updated successfully! Your session is secure.'
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg})
            messages.success(request, msg)
            return redirect('owner_portal:profile_settings')

        # Action: Save Notification Preferences
        elif action == 'update_preferences':
            wa_notif = request.POST.get('pref_whatsapp') == 'on'
            sms_notif = request.POST.get('pref_sms') == 'on'
            email_digest = request.POST.get('pref_email') == 'on'

            AuditLog.objects.create(
                actor=owner,
                action_type='UPDATE_PREFERENCES',
                target_entity='SETTINGS',
                target_id=owner.id,
                module='SETTINGS',
                status='SUCCESS',
                details=f"Preferences saved: WhatsApp={wa_notif}, SMS={sms_notif}, Email={email_digest}"
            )

            msg = 'Notification preferences saved successfully!'
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg})
            messages.success(request, msg)
            return redirect('owner_portal:profile_settings')

        # Action: Upload / Update KYC Document
        elif action == 'upload_kyc':
            doc_type = request.POST.get('document_type', 'AADHAAR').upper()
            doc_number = request.POST.get('document_number', '').strip()

            if not doc_number:
                msg = 'Document number is required.'
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': msg}, status=400)
                messages.error(request, msg)
                return redirect('owner_portal:profile_settings')

            kyc, _ = OwnerKYC.objects.get_or_create(
                user=owner,
                document_type=doc_type,
                defaults={
                    'document_number': doc_number,
                    'document_file_url': f"https://kiraayagrid.storage/kyc/{owner.username}_{doc_type.lower()}.pdf",
                    'status': 'PENDING'
                }
            )
            kyc.document_number = doc_number
            kyc.status = 'PENDING'
            kyc.save()

            AuditLog.objects.create(
                actor=owner,
                action_type='UPLOAD_KYC',
                target_entity='OWNER_KYC',
                target_id=kyc.id,
                module='SETTINGS',
                status='SUCCESS',
                details=f"Uploaded {doc_type} for verification: {doc_number}"
            )

            msg = f"{doc_type} submitted for verification. Operations desk will review within 24 hours."
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg})
            messages.success(request, msg)
            return redirect('owner_portal:profile_settings')

        # Action: Request Account Deactivation
        elif action == 'request_deactivation':
            reason = request.POST.get('reason', 'Owner submitted deactivation request').strip()
            AuditLog.objects.create(
                actor=owner,
                action_type='DEACTIVATION_REQUEST',
                target_entity='USER',
                target_id=owner.id,
                module='SETTINGS',
                status='PENDING',
                details=f"Deactivation request logged: {reason}"
            )
            msg = 'Deactivation request submitted. Our compliance team will contact you within 24 hours.'
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg})
            messages.success(request, msg)
            return redirect('owner_portal:profile_settings')

        return redirect('owner_portal:profile_settings')

    # KYC Records
    kyc_records = OwnerKYC.objects.filter(user=owner)
    aadhaar_kyc = kyc_records.filter(document_type='AADHAAR').first()
    pan_kyc = kyc_records.filter(document_type='PAN').first()

    # Subscription plan
    subscription = OwnerSubscription.objects.filter(owner=owner).first()

    # Security & Activity Audit Trail (Limit 5 Pagination)
    audit_logs_base = AuditLog.objects.filter(actor=owner).order_by('-created_at')
    log_paginator = Paginator(audit_logs_base, 5)
    log_page_number = request.GET.get('log_page', 1)
    try:
        audit_logs_page = log_paginator.page(log_page_number)
    except PageNotAnInteger:
        audit_logs_page = log_paginator.page(1)
    except EmptyPage:
        audit_logs_page = log_paginator.page(log_paginator.num_pages)

    # Portfolio metrics for hero card
    owner_properties = Property.objects.filter(owner=owner)
    properties_count = owner_properties.count()
    total_beds_count = Bed.objects.filter(room__property__in=owner_properties).count()

    context = {
        'owner_user': owner,
        'aadhaar_kyc': aadhaar_kyc,
        'pan_kyc': pan_kyc,
        'subscription': subscription,
        'properties_count': properties_count,
        'total_beds_count': total_beds_count,
        'audit_logs': audit_logs_page.object_list,
        'audit_logs_page': audit_logs_page,
        'log_paginator': log_paginator,
    }
    return render(request, 'owner_portal/14_settings.html', context)


# -------------------------------------------------------------
# PART 2: 15-STEP LISTING CREATION FLOW
# -------------------------------------------------------------
STEP_TITLES = {
    1: 'Listing Introduction',
    2: 'Select Property Type',
    3: 'Basic Property Information',
    4: 'Property Location',
    5: 'Property Specifications',
    6: 'Property Amenities',
    7: 'Room Configuration',
    8: 'Pricing & Charges',
    9: 'Property Photographs',
    10: 'Property Rules & Preferences',
    11: 'Availability & Move-in',
    12: 'Owner Verification & Documents',
    13: 'Listing Preview',
    14: 'Final Confirmation',
    15: 'Submission Success',
}

PROPERTY_TYPES = [
    ('PG', 'PG (Paying Guest)', 'Fully serviced accommodation with meals, cleaning, and shared facilities.'),
    ('HOSTEL', 'Student / Youth Hostel', 'Dormitory or private rooms built for college students and interns.'),
    ('CO_LIVING', 'Co-Living Space', 'Premium shared living for tech professionals with high-speed internet and lounge areas.'),
    ('FLAT', 'Flat / Apartment', 'Independent multi-BHK flat leased as individual rooms or full unit.'),
    ('INDEPENDENT_HOUSE', 'Independent House / Villa', 'Standalone bungalow or multi-floor residential unit.'),
    ('SHARED_ACCOMMODATION', 'Shared Accommodation', 'Budget-friendly shared room or companion sharing space.'),
]


def add_property_wizard(request):
    return redirect('owner_portal:add_property_step', step=1)


def add_property_step(request, step):
    owner = get_active_owner(request)
    step = int(step)
    if step < 1:
        step = 1
    if step > 15:
        step = 15

    step_title = STEP_TITLES.get(step, 'Listing Wizard')
    progress_pct = int((step / 15) * 100)
    prev_step = step - 1 if step > 1 else None
    next_step = step + 1 if step < 15 else None

    created_prop = None
    reference_id = None

    # Handle Submission on Step 14 POST or Step 15
    if step == 15 or (step == 14 and request.method == 'POST'):
        # Check if already submitted in this session/recent request
        recent_prop = Property.objects.filter(owner=owner).order_by('-created_at').first()
        is_fresh = False
        if recent_prop and (timezone.now() - recent_prop.created_at).total_seconds() < 120:
            created_prop = recent_prop
            reference_id = f"REF-2026-IND-{created_prop.id:04d}"
        
        if not created_prop or request.method == 'POST':
            # Extract form data
            p_data = request.POST if request.method == 'POST' else {}
            title = p_data.get('property_title', '').strip() or 'The Courtyard House'
            prop_type = p_data.get('property_type', 'CO_LIVING')
            if prop_type not in ['PG', 'HOSTEL', 'FLAT', 'CO_LIVING']:
                prop_type = 'PG'
            address_line = p_data.get('address_line', '').strip() or 'No. 42, 4th Cross, 5th Block'
            city_name = p_data.get('city', '').strip() or 'Indore'
            locality_name = p_data.get('locality', '').strip() or 'Vijay Nagar'
            pincode = p_data.get('pincode', '').strip() or '452010'
            try:
                total_rooms = int(p_data.get('total_rooms', 4))
            except:
                total_rooms = 4

            try:
                rent_val = Decimal(str(p_data.get('monthly_rent', '14500')).replace('₹','').replace(',','').strip() or '14500')
            except:
                rent_val = Decimal('14500.00')

            try:
                dep_val = Decimal(str(p_data.get('security_deposit', '29000')).replace('₹','').replace(',','').strip() or '29000')
            except:
                dep_val = Decimal('29000.00')

            # Resolve City & Locality (Indore is #1)
            city_obj = City.objects.filter(name__icontains=city_name).first() or City.objects.filter(name='Indore').first() or City.objects.first()
            locality_obj = Locality.objects.filter(city=city_obj, name__icontains=locality_name).first() or (city_obj.localities.first() if city_obj else None)
            if not locality_obj and city_obj:
                locality_obj = Locality.objects.create(city=city_obj, name=locality_name or 'Vijay Nagar')

            # Create Property in MySQL
            created_prop = Property.objects.create(
                owner=owner,
                title=title,
                property_type=prop_type,
                gender_category='CO_ED',
                address_line=address_line,
                city=city_obj,
                locality=locality_obj,
                pincode=pincode,
                total_rooms=total_rooms,
                status='PENDING'
            )
            reference_id = f"REF-2026-IND-{created_prop.id:04d}"

            # Create Room
            room = Room.objects.create(
                property=created_prop,
                room_number='101',
                room_type='DOUBLE',
                max_occupancy=2,
                total_beds=2,
                occupied_beds=0,
                available_beds=2,
                monthly_rent=rent_val,
                security_deposit=dep_val,
                bathroom_type='ATTACHED',
                ac_type='AC',
                furnishing='FULLY_FURNISHED',
                amenities='High-Speed WiFi, Power Backup, Attached Bathroom, AC, Daily Housekeeping',
                cover_photo='https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=800',
                available_from=datetime.date.today(),
                is_active=True
            )

            # Create Beds
            Bed.objects.create(room=room, bed_number='101-A', bed_position='Window Side', status='AVAILABLE', monthly_rent=rent_val)
            Bed.objects.create(room=room, bed_number='101-B', bed_position='Balcony Side', status='AVAILABLE', monthly_rent=rent_val)

            # Create PropertyPhoto
            PropertyPhoto.objects.create(
                property=created_prop,
                photo_url='https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=800',
                photo_type='COVER',
                caption=f"{title} - Façade & Courtyard",
                is_cover=True,
                sort_order=1
            )

            # Create PropertyMetadata
            PropertyMetadata.objects.get_or_create(
                property=created_prop,
                defaults={
                    'furnishing': 'Fully Furnished',
                    'property_condition': 'New Construction / Freshly Painted',
                    'description': f"{title} located in {locality_obj.name if locality_obj else 'Central'}, {city_obj.name if city_obj else 'Indore'}. 100% zero-brokerage verified space.",
                    'rules_notice_period': '30 Days',
                    'visiting_hours': '10:00 AM – 7:00 PM (All days)'
                }
            )

            # Link & close any active draft
            draft = DraftListing.objects.filter(owner=owner, is_submitted=False).order_by('-updated_at').first()
            if draft:
                draft.is_submitted = True
                draft.submitted_property = created_prop
                draft.save()

            # Cross-Portal Audit & In-App Notification
            AuditLog.objects.create(
                actor=owner,
                action_type='CREATE_PROPERTY',
                target_entity='PROPERTY',
                target_id=str(created_prop.id),
                module='PROPERTIES',
                status='SUCCESS',
                details=f"Owner submitted new listing '{created_prop.title}' ({reference_id}) for verification."
            )
            Notification.objects.create(
                recipient=owner,
                title="Listing Submitted for Verification",
                message=f"Your listing '{created_prop.title}' ({reference_id}) is in the verification queue.",
                channel="IN_APP",
                button_label="View Properties",
                button_url="/owner/properties/?filter=pending"
            )

            if step == 14:
                return redirect('owner_portal:add_property_step', step=15)

    context = {
        'owner_user': owner,
        'step': step,
        'step_title': step_title,
        'progress_pct': progress_pct,
        'step_numbers': range(1, 16),
        'prev_step': prev_step,
        'next_step': next_step,
        'property_type_options': PROPERTY_TYPES,
        'created_property': created_prop,
        'reference_id': reference_id or 'REF-2026-IND-0108',
    }
    return render(request, 'owner_portal/listing_wizard/wizard_base.html', context)


@csrf_exempt
def save_listing_draft_api(request):
    """
    Saves or updates owner's listing draft in MySQL database (DraftListing).
    """
    owner = get_active_owner(request)
    req_data = {}
    if request.method == 'POST':
        if request.content_type == 'application/json':
            try:
                req_data = json.loads(request.body.decode('utf-8'))
            except Exception:
                req_data = {}
        else:
            req_data = request.POST.dict()
    elif request.method == 'GET':
        req_data = request.GET.dict()

    title = req_data.get('title') or req_data.get('property_title') or 'Untitled Property Draft'
    prop_type = req_data.get('property_type') or 'PG'
    try:
        current_step = int(req_data.get('step') or req_data.get('current_step') or 1)
    except (ValueError, TypeError):
        current_step = 1

    draft_id = req_data.get('draft_id')
    draft = None
    if draft_id:
        try:
            draft = DraftListing.objects.filter(id=int(draft_id), owner=owner).first()
        except (ValueError, TypeError):
            pass

    if not draft:
        draft = DraftListing.objects.filter(owner=owner, is_submitted=False).order_by('-updated_at').first()

    if not draft:
        draft = DraftListing(owner=owner, is_submitted=False)

    draft.title = title
    draft.property_type = prop_type
    draft.current_step = current_step
    draft.form_data = json.dumps(req_data)
    draft.save()

    return JsonResponse({
        'status': 'success',
        'message': 'Draft progress saved automatically in MySQL database.',
        'draft_id': draft.id,
        'title': draft.title,
        'current_step': draft.current_step
    })
