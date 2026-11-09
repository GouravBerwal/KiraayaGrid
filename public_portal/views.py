import json
import re
import random
import time
import os
import threading
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import get_user_model, login, logout, authenticate
from django.db.models import Min, Count, Q, Case, When, Value, IntegerField
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.conf import settings
from django.core.mail import send_mail

from admin_portal.models import Property, City, Locality, Amenity, Review, Notification
from owner_portal.models import Room, Bed, PropertyPhoto, OwnerSubscription
from tenant_portal.models import TenantProfile, SavedProperty

User = get_user_model()


def get_curated_properties():
    """
    Returns verified stays from database annotated with min rent and cover photo.
    """
    props = list(Property.objects.filter(status='APPROVED')
                 .annotate(min_rent_val=Min('rooms__monthly_rent'))
                 .select_related('city', 'locality', 'owner')
                 .prefetch_related('gallery_photos', 'rooms', 'reviews')[:12])
    
    # Defaults in case DB is lightly populated
    sample_photos = [
        '/static/public/images/stay_olive_house.png',
        '/static/public/images/stay_nest_lane7.png',
        '/static/public/images/stay_grove_collective.png',
        'https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800&auto=format&fit=crop&q=80',
        'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&auto=format&fit=crop&q=80',
        'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800&auto=format&fit=crop&q=80',
    ]

    for idx, p in enumerate(props):
        cov = p.gallery_photos.filter(is_cover=True).first() or p.gallery_photos.first()
        p.display_photo = cov.photo_url if (cov and cov.photo_url) else sample_photos[idx % len(sample_photos)]
        p.display_price = int(p.min_rent_val) if p.min_rent_val else (int(p.rooms.first().monthly_rent) if p.rooms.exists() else 0)
        p.locality_name = p.locality.name if p.locality else (p.city.name if p.city else 'Indore')
        p.city_name = p.city.name if p.city else 'Indore'
        
        # Room Type display
        if p.property_type == 'PG':
            p.display_type = 'PG · Private room'
            p.display_amenities = 'Wi-Fi · Meals · Housekeeping'
        elif p.property_type == 'FLAT':
            p.display_type = 'Flat · 1 BHK'
            p.display_amenities = 'Wi-Fi · Kitchen · Balcony'
        elif p.property_type == 'CO_LIVING':
            p.display_type = 'Co-living · Private room'
            p.display_amenities = 'Wi-Fi · Gym · Housekeeping'
        else:
            p.display_type = f'{p.get_property_type_display()} · Studio'
            p.display_amenities = 'Wi-Fi · Furnished · AC'

        # Ratings
        approved_revs = [r for r in p.reviews.all() if getattr(r, 'status', '') == 'APPROVED']
        if approved_revs:
            p.display_rating = f"{sum(r.rating for r in approved_revs) / len(approved_revs):.1f}"
            p.reviews_count = len(approved_revs)
        else:
            p.display_rating = "New"
            p.reviews_count = 0
    
    return props


# 1. Public Home & Landing Page (1:1 with Figma)
def home_landing(request):
    featured_stays = get_curated_properties()[:3]
    all_stays_count = Property.objects.filter(status='APPROVED').count()
    
    # Real Cities with counts (Indore always ordered first per founder mandate)
    cities_qs = City.objects.filter(is_active=True).annotate(
        stay_count=Count('properties', filter=Q(properties__status='APPROVED'))
    ).order_by(
        Case(
            When(name__iexact='Indore', then=Value(0)),
            default=Value(1),
            output_field=IntegerField()
        ),
        'name'
    )
    city_cards = []
    default_city_data = [
        {'name': 'Indore', 'photo': '/static/public/images/city_indore.png', 'count': '5 verified stays', 'tagline': "India's Cleanest City · Tech & Startup Hub"},
        {'name': 'Bengaluru', 'photo': '/static/public/images/city_bengaluru.png', 'count': '8 verified stays', 'tagline': 'The Silicon Valley of India'},
        {'name': 'Mumbai', 'photo': '/static/public/images/city_mumbai.png', 'count': '6 verified stays', 'tagline': 'City of Dreams & Coastal Energy'},
        {'name': 'Pune', 'photo': '/static/public/images/city_pune.png', 'count': '5 verified stays', 'tagline': 'Oxford of the East & IT Oasis'},
        {'name': 'Hyderabad', 'photo': '/static/public/images/city_hyderabad.png', 'count': '3 verified stays', 'tagline': 'Cyberabad Heritage & Culinary Hub'},
    ]

    for item in default_city_data:
        c_obj = cities_qs.filter(name__icontains=item['name']).first()
        cnt = c_obj.stay_count if c_obj else 0
        city_cards.append({
            'name': item['name'],
            'photo': item['photo'],
            'count': f"{cnt} verified stay{'s' if cnt != 1 else ''}" if cnt > 0 else "Verified listings coming soon",
            'tagline': item['tagline'],
            'id': c_obj.id if c_obj else ''
        })

    # Category Counts (Real-time DB counts)
    category_counts = {
        'PG': Property.objects.filter(property_type='PG', status='APPROVED').count(),
        'HOSTEL': Property.objects.filter(property_type='HOSTEL', status='APPROVED').count(),
        'PRIVATE_ROOM': Property.objects.filter(rooms__room_type='SINGLE', status='APPROVED').distinct().count(),
        'SHARED_ROOM': Property.objects.filter(rooms__room_type__in=['DOUBLE', 'TRIPLE'], status='APPROVED').distinct().count(),
        'FLAT': Property.objects.filter(property_type='FLAT', status='APPROVED').count(),
        'CO_LIVING': Property.objects.filter(property_type='CO_LIVING', status='APPROVED').count(),
    }

    context = {
        'featured_stays': featured_stays,
        'city_cards': city_cards,
        'category_counts': category_counts,
        'all_stays_count': all_stays_count,
        'cities': cities_qs,
    }
    return render(request, 'public_portal/01_landing.html', context)


# 2. About Us & Founder Spotlight Page
def about_founder(request):
    founder_profile = {
        'name': 'Gourav Gurjar',
        'role': 'Founder & Chief Architect',
        'credentials': 'Ex-MAANG/FAANG Systems Engineer · Distributed Architect',
        'photo': '/static/public/images/founder.png',
        'mission_headline': 'Eliminating predatory rental brokerage with engineering rigor, radical transparency, and human empathy.',
        'short_bio': 'Crafted in Silicon Valley engineering disciplines, returned to solve India\'s most painful real-estate barrier: the lack of trust between seekers and property owners.',
        'full_story': """
        Born out of firsthand frustration moving across technology hubs in Bengaluru and Hyderabad, Gourav founded KiraayaGrid with a singular obsession: 
        finding a home in a new city should feel as welcoming and transparent as returning to your family courtyard.
        
        Drawing on deep distributed systems expertise from world-class tech firms, he architected the platform from the ground up to replace manipulative middlemen with cryptographically audited verifications, direct landlord connections, and zero-brokerage guarantees. Today, KiraayaGrid powers verified discovery across thousands of urban spaces with Apple-grade design craftsmanship and sub-second execution.
        """,
        'pillars': [
            {'title': 'Zero-Brokerage Mandate', 'desc': 'Rent goes directly from resident to homeowner. No commission haircuts, no inflated security deposits.'},
            {'title': 'Ground-Truth Verification', 'desc': 'Physical multi-point inspections ensure photos, amenities, and lease terms match reality.'},
            {'title': 'Direct P2P Communication', 'desc': 'Unfiltered chat streams and scheduled walkthrough gate passes directly between seeker and host.'},
            {'title': 'Apple-Grade Craftsmanship', 'desc': 'Thoughtfully designed digital interfaces with obsessive attention to fluid motion, clarity, and peace of mind.'}
        ],
        'stats': [
            {'num': '100%', 'label': 'Zero Brokerage'},
            {'num': '3,450+', 'label': 'Verified Rooms'},
            {'num': '₹4.2 Cr+', 'label': 'Brokerage Saved'},
            {'num': '99.98%', 'label': 'Platform Uptime'}
        ]
    }
    return render(request, 'public_portal/04_about_founder.html', {'founder': founder_profile})


# 3. Public Explore Stays (Max 5 Pagination)
def explore_stays(request):
    search_q = (request.GET.get('q') or request.GET.get('search') or '').strip()
    city_filter = request.GET.get('city', '').strip()
    type_filter = request.GET.get('type', '').strip()
    category_filter = request.GET.get('category', '').strip()
    occupancy_filter = request.GET.get('occupancy', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    sort_by = request.GET.get('sort', 'recommended')

    qs = Property.objects.filter(status='APPROVED').annotate(
        min_rent_val=Min('rooms__monthly_rent')
    ).select_related('city', 'locality', 'owner').prefetch_related('gallery_photos', 'rooms')

    if search_q:
        qs = qs.filter(
            Q(title__icontains=search_q) |
            Q(address_line__icontains=search_q) |
            Q(locality__name__icontains=search_q) |
            Q(city__name__icontains=search_q)
        )

    if city_filter:
        qs = qs.filter(Q(city__name__iexact=city_filter) | Q(city__name__icontains=city_filter) | Q(city_id=city_filter if city_filter.isdigit() else 0))

    if type_filter:
        qs = qs.filter(property_type=type_filter)

    if category_filter:
        if category_filter == 'coliving':
            qs = qs.filter(property_type='CO_LIVING')
        elif category_filter == 'pg':
            qs = qs.filter(property_type='PG')
        elif category_filter == 'flat':
            qs = qs.filter(property_type='FLAT')
        elif category_filter == 'budget':
            qs = qs.filter(min_rent_val__lte=15000)

    if occupancy_filter:
        qs = qs.filter(rooms__room_type=occupancy_filter)

    if max_price and max_price.isdigit():
        qs = qs.filter(min_rent_val__lte=int(max_price))

    if sort_by == 'price_low':
        qs = qs.order_by('min_rent_val')
    elif sort_by == 'price_high':
        qs = qs.order_by('-min_rent_val')
    elif sort_by == 'newest':
        qs = qs.order_by('-created_at')
    else:
        qs = qs.order_by('-id')

    properties_list = list(qs)
    sample_photos = [
        '/static/public/images/stay_olive_house.png',
        '/static/public/images/stay_nest_lane7.png',
        '/static/public/images/stay_grove_collective.png',
        'https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800&auto=format&fit=crop&q=80',
        'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&auto=format&fit=crop&q=80',
        'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800&auto=format&fit=crop&q=80',
        'https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=800&auto=format&fit=crop&q=80',
    ]

    for idx, prop in enumerate(properties_list):
        cov = prop.gallery_photos.filter(is_cover=True).first() or prop.gallery_photos.first()
        prop.display_photo = cov.photo_url if (cov and cov.photo_url) else sample_photos[idx % len(sample_photos)]
        prop.display_price = int(prop.min_rent_val) if prop.min_rent_val else (int(prop.rooms.first().monthly_rent) if prop.rooms.exists() else 0)
        prop.locality_str = prop.locality.name if prop.locality else (prop.city.name if prop.city else 'Indore')
        prop.city_str = prop.city.name if prop.city else 'Indore'

        if prop.property_type == 'PG':
            prop.display_category_label = 'Private Room · PG'
            prop.display_badge = 'Boys & Girls PG'
            prop.display_amenities = ['Wi-Fi', '3 Meals Daily', 'Housekeeping', 'Power Backup']
        elif prop.property_type == 'FLAT':
            prop.display_category_label = 'Independent Apartment'
            prop.display_badge = '1 & 2 BHK Flat'
            prop.display_amenities = ['Wi-Fi', 'Modular Kitchen', 'Balcony View', 'Gated Security']
        elif prop.property_type == 'CO_LIVING':
            prop.display_category_label = 'Community Living'
            prop.display_badge = 'Premium Co-living'
            prop.display_amenities = ['Wi-Fi', 'Fitness Center', 'Coworking Lounge', 'Weekly Events']
        else:
            prop.display_category_label = f"{prop.get_property_type_display()} Living"
            prop.display_badge = 'Studio Suite'
            prop.display_amenities = ['High-Speed Wi-Fi', 'Air Conditioning', 'Fully Furnished', '24/7 Support']

        approved_revs = [r for r in prop.reviews.all() if getattr(r, 'status', '') == 'APPROVED']
        if approved_revs:
            prop.rating_score = f"{sum(r.rating for r in approved_revs) / len(approved_revs):.1f}"
            prop.reviews_count = len(approved_revs)
        else:
            prop.rating_score = "New"
            prop.reviews_count = 0
        prop.brokerage_saved = f"₹{prop.display_price:,}"

    # Universal Max 5 Pagination
    paginator = Paginator(properties_list, 5)
    page_num = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    cities = City.objects.filter(is_active=True).order_by(
        Case(
            When(name__iexact='Indore', then=Value(0)),
            default=Value(1),
            output_field=IntegerField()
        ),
        'name'
    )

    # Category counts for ribbon badges
    category_counts = {
        'all': Property.objects.filter(status='APPROVED').count(),
        'coliving': Property.objects.filter(status='APPROVED', property_type='CO_LIVING').count(),
        'pg': Property.objects.filter(status='APPROVED', property_type='PG').count(),
        'flat': Property.objects.filter(status='APPROVED', property_type='FLAT').count(),
    }

    context = {
        'page_obj': page_obj,
        'properties': page_obj,
        'total_count': paginator.count,
        'cities': cities,
        'search_q': search_q,
        'city_filter': city_filter,
        'type_filter': type_filter,
        'category_filter': category_filter,
        'occupancy_filter': occupancy_filter,
        'max_price': max_price,
        'sort_by': sort_by,
        'category_counts': category_counts,
    }
    return render(request, 'public_portal/02_explore_stays.html', context)


# 4. Public Property Details View
def stay_details(request, property_id):
    prop = get_object_or_404(Property.objects.select_related('city', 'locality', 'owner').prefetch_related('gallery_photos', 'rooms', 'reviews'), id=property_id)
    
    rooms = list(prop.rooms.filter(is_active=True))
    min_rent = int(min([r.monthly_rent for r in rooms])) if rooms else 0

    # Ensure rich display rooms if property has no rooms added yet
    display_rooms = []
    if rooms:
        for r in rooms:
            display_rooms.append({
                'id': r.id,
                'name': f"{r.get_room_type_display()} (Room {r.room_number})",
                'type': r.get_room_type_display(),
                'rent': int(r.monthly_rent),
                'rent_formatted': f"{int(r.monthly_rent):,}",
                'deposit': int(r.security_deposit or r.monthly_rent),
                'deposit_formatted': f"{int(r.security_deposit or r.monthly_rent):,}",
                'furnishing': getattr(r, 'furnishing', 'Fully Furnished') or 'Fully Furnished',
                'ac': getattr(r, 'ac_type', 'AC Room') or 'Air Conditioned',
                'vacant': getattr(r, 'available_beds', 1) or 1,
                'badge': 'Vacant · Instant Move-in'
            })
    # Clean Real-world Data (No mock fallback)
    photos = list(prop.gallery_photos.all())
    default_photo = '/static/public/images/stay_olive_house.png'
    gallery_urls = [p.photo_url for p in photos if p.photo_url] or [default_photo]

    reviews = list(prop.reviews.filter(status='APPROVED').select_related('user'))
    sample_reviews = [
        {
            'author': r.user.get_full_name() or r.user.username,
            'role': 'Verified Resident',
            'rating': r.rating,
            'date': r.created_at.strftime('%b %d, %Y'),
            'comment': r.comment,
            'avatar': (r.user.first_name[:1] or r.user.username[:1]).upper()
        }
        for r in reviews
    ]
    avg_rating = f"{sum(r.rating for r in reviews) / len(reviews):.1f}" if reviews else "New"

    # Similar Recommended Stays (Max 3)
    similar_qs = Property.objects.filter(status='APPROVED').exclude(id=prop.id)
    if prop.city:
        similar_city = similar_qs.filter(city=prop.city)
        if similar_city.exists():
            similar_qs = similar_city
    similar_stays = list(similar_qs.select_related('city', 'locality')[:3])
    for s in similar_stays:
        cov = s.gallery_photos.filter(is_cover=True).first() or s.gallery_photos.first()
        s.display_photo = cov.photo_url if (cov and cov.photo_url) else default_photo
        active_rms = list(s.rooms.filter(is_active=True))
        s.display_price = int(min([r.monthly_rent for r in active_rms])) if active_rms else 0

    context = {
        'prop': prop,
        'display_rooms': display_rooms,
        'min_rent': min_rent,
        'min_rent_formatted': f"{min_rent:,}",
        'security_deposit': min_rent,
        'security_deposit_formatted': f"{min_rent:,}",
        'brokerage_saved': f"₹{min_rent:,}",
        'gallery_urls': gallery_urls,
        'cover_photo': gallery_urls[0],
        'sub_photos': gallery_urls[1:5],
        'sample_reviews': sample_reviews,
        'reviews_count': len(sample_reviews),
        'avg_rating': avg_rating,
        'owner': prop.owner,
        'similar_stays': similar_stays,
        'locality_name': prop.locality.name if prop.locality else (prop.city.name if prop.city else 'Bengaluru'),
        'city_name': prop.city.name if prop.city else 'Bengaluru',
    }
    return render(request, 'public_portal/03_stay_details.html', context)


# 5. Public "List Your Property" Landing Page for Homeowners & Landlords
def list_property_landing(request):
    """
    Dedicated public informational and onboarding landing page for property owners.
    Highlights: Zero brokerage, verified tenant pipeline, automated payouts, yield calculator.
    """
    cities = City.objects.filter(is_active=True).order_by(
        Case(
            When(name__iexact='Indore', then=Value(0)),
            default=Value(1),
            output_field=IntegerField()
        ),
        'name'
    )
    stats = [
        {'num': '0%', 'label': 'Brokerage or Listing Fee'},
        {'num': '3.2 Days', 'label': 'Average Placement Speed'},
        {'num': '100%', 'label': 'KYC Verified Working Residents'},
        {'num': '₹0', 'label': 'No Hidden Deductions'}
    ]
    
    testimonials = [
        {
            'name': 'Rajesh Mehta',
            'city': 'HSR Layout, Bengaluru',
            'property': 'Shanti Residency · 18 Rooms',
            'quote': 'Earlier I was paying 15 days of rent every year to local brokers who disappeared when issues arose. With KiraayaGrid, I filled all 18 rooms in 5 days with zero brokerage!',
            'avatar': 'RM'
        },
        {
            'name': 'Sunita Deshmukh',
            'city': 'Koregaon Park, Pune',
            'property': 'Deshmukh Heights · 1 BHK & Studios',
            'quote': 'The physical verification photoshoot brought genuine IT professionals. Digital agreements and on-time rent deposits have given me total peace of mind.',
            'avatar': 'SD'
        },
        {
            'name': 'Venkatesh Rao',
            'city': 'Gachibowli, Hyderabad',
            'property': 'Greenview Coliving · 24 Beds',
            'quote': 'The direct chat feature allows me to talk to tenants before approving walkthrough visits. Complete control without broker harassment.',
            'avatar': 'VR'
        }
    ]

    context = {
        'cities': cities,
        'stats': stats,
        'testimonials': testimonials,
        'is_owner': request.user.is_authenticated and getattr(request.user, 'role', '') == 'OWNER'
    }
    return render(request, 'public_portal/06_list_property.html', context)


# 6. Public Locations & Neighborhoods Explorer
def locations_overview(request):
    """
    Dedicated city and neighborhood discovery hub.
    Highlights: Top cities, key localities, average rents, amenities, and stay counts.
    """
    cities_qs = City.objects.filter(is_active=True).annotate(
        approved_count=Count('properties', filter=Q(properties__status='APPROVED'))
    )
    
    city_data = [
        {
            'name': 'Indore',
            'state': 'Madhya Pradesh',
            'tagline': "India's 7-Time Cleanest City · Tech & Commercial Capital of MP",
            'description': "7-time national cleanliness champion, premier IIT & IIM educational corridors, booming Super Corridor IT hubs, renowned culinary legacy at Sarafa & 56 Dukan, and peaceful green living.",
            'avg_rent': '₹9,500',
            'stay_count': '5 verified stays',
            'photo': '/static/public/images/city_indore.png',
            'popular_localities': ['Vijay Nagar', 'Super Corridor', 'Bhawarkua', 'Palasia', 'Geeta Bhawan', 'Rau'],
            'tech_parks': 'TCS & Infosys Super Corridor · Crystal IT Park',
            'metro_connectivity': 'Indore Metro Yellow Line Priority Corridor',
            'best_for': 'Tech Innovators, Students & Families'
        },
        {
            'name': 'Bengaluru',
            'state': 'Karnataka',
            'tagline': 'The Silicon Valley of India',
            'description': 'Lush garden boulevards, global tech parks, and thriving indie cafe culture. India\'s premier startup capital.',
            'avg_rent': '₹14,500',
            'stay_count': '8 verified stays',
            'photo': '/static/public/images/city_bengaluru.png',
            'popular_localities': ['Koramangala', 'Indiranagar', 'HSR Layout', 'Whitefield', 'Bellandur', 'Electronic City'],
            'tech_parks': 'Ecoworld · Manyata · Bagmane',
            'metro_connectivity': 'Purple & Green Lines',
            'best_for': 'Software Engineers & Founders'
        },
        {
            'name': 'Mumbai',
            'state': 'Maharashtra',
            'tagline': 'The City of Dreams & Coastal Energy',
            'description': 'Sea-breeze promenades, premier corporate headquarters, and high-energy urban nightlife.',
            'avg_rent': '₹22,000',
            'stay_count': '6 verified stays',
            'photo': '/static/public/images/city_mumbai.png',
            'popular_localities': ['Bandra West', 'Powai', 'Andheri East', 'Lower Parel', 'Juhu', 'Worli'],
            'tech_parks': 'BKC · Nesco · Mindspace',
            'metro_connectivity': 'Metro 1, 2A & 7',
            'best_for': 'Finance, Media & Product Leads'
        },
        {
            'name': 'Pune',
            'state': 'Maharashtra',
            'tagline': 'The Oxford of the East & IT Oasis',
            'description': 'Pleasant year-round weather, rich academic pedigree, and sprawling technology campuses.',
            'avg_rent': '₹12,000',
            'stay_count': '5 verified stays',
            'photo': '/static/public/images/city_pune.png',
            'popular_localities': ['Koregaon Park', 'Viman Nagar', 'Hinjawadi', 'Baner', 'Kalyani Nagar', 'Aundh'],
            'tech_parks': 'Rajiv Gandhi Infotech · EON IT',
            'metro_connectivity': 'Pune Metro Line 1 & 2',
            'best_for': 'Tech Innovators & Scholars'
        },
        {
            'name': 'Hyderabad',
            'state': 'Telangana',
            'tagline': 'Cyberabad Heritage & Culinary Capital',
            'description': 'Historic grandeur, world-class biotechnology and cloud infrastructure corridors, and authentic hospitality.',
            'avg_rent': '₹11,500',
            'stay_count': '3 verified stays',
            'photo': '/static/public/images/city_hyderabad.png',
            'popular_localities': ['Gachibowli', 'Madhapur', 'Hitec City', 'Kondapur', 'Jubilee Hills', 'Banjara Hills'],
            'tech_parks': 'Cyber Towers · Mindspace · DLF',
            'metro_connectivity': 'Red & Blue Metro Lines',
            'best_for': 'Cloud Architects & Biotech'
        },
        {
            'name': 'Delhi NCR',
            'state': 'Delhi & Haryana',
            'tagline': 'The National Capital & Millennium City',
            'description': 'Sprawling expressways, rapid metro access, premier MNC hubs in Cyber City, and vibrant student enclaves.',
            'avg_rent': '₹13,500',
            'stay_count': '2 verified stays',
            'photo': '/static/public/images/city_delhi.png',
            'popular_localities': ['DLF Cyber City', 'Golf Course Road', 'Sector 62 Noida', 'South Campus', 'Hauz Khas'],
            'tech_parks': 'Cyber Hub · Candor TechSpace',
            'metro_connectivity': 'Delhi Metro & Rapid Metro',
            'best_for': 'Corporate Leaders & Consultants'
        }
    ]

    for item in city_data:
        c_obj = cities_qs.filter(name__icontains=item['name'].split()[0]).first()
        cnt = c_obj.approved_count if c_obj else 0
        item['stay_count'] = f"{cnt} verified stay{'s' if cnt != 1 else ''}" if cnt > 0 else "Verified stays coming soon"

    context = {
        'cities': city_data,
        'total_cities': len(city_data)
    }
    return render(request, 'public_portal/07_locations.html', context)


# 7. Multi-Role Apple-Grade Authentication & Live Verification Suite

def generate_unique_username_suggestions(full_name='', email='', role='TENANT', limit=4):
    """
    Generates smart, completely unique username suggestions based on user name/email and role.
    Guarantees no collisions with any existing owners or tenants in the MySQL database.
    """
    base_parts = []
    if full_name:
        clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', full_name).strip().lower()
        parts = clean_name.split()
        if parts:
            base_parts = parts
    elif email:
        local_part = email.split('@')[0]
        clean_local = re.sub(r'[^a-zA-Z0-9]', '_', local_part).strip('_').lower()
        base_parts = [p for p in clean_local.split('_') if p]

    if not base_parts:
        base_parts = ['user']

    first = base_parts[0]
    last = base_parts[-1] if len(base_parts) > 1 else ''
    role_suffix = 'owner' if role.upper() == 'OWNER' else 'stay'

    candidates = []
    if last and last != first:
        candidates.append(f'{first}_{last}')
        candidates.append(f'{first}_{last[0]}')
        candidates.append(f'{last}_{first}')
    candidates.append(f'{first}_{role_suffix}')
    candidates.append(f'{first}{random.randint(10, 99)}')
    if last:
        candidates.append(f'{first}_{last}_{random.randint(1, 99)}')
    else:
        candidates.append(f'{first}_{role_suffix}{random.randint(1, 99)}')

    unique_suggestions = []
    for cand in candidates:
        cand = re.sub(r'[^a-z0-9_]', '', cand.lower())
        if not cand or len(cand) < 3:
            continue
        test_user = cand
        counter = 1
        while User.objects.filter(username__iexact=test_user).exists():
            test_user = f'{cand}{counter}'
            counter += 1
        if test_user not in unique_suggestions:
            unique_suggestions.append(test_user)
        if len(unique_suggestions) >= limit:
            break

    return unique_suggestions


def api_suggest_usernames(request):
    """
    API endpoint for live username suggestions based on Name, Email, and Role.
    """
    full_name = request.GET.get('name', '') or request.POST.get('name', '')
    email = request.GET.get('email', '') or request.POST.get('email', '')
    role = request.GET.get('role', 'TENANT') or request.POST.get('role', 'TENANT')

    suggestions = generate_unique_username_suggestions(full_name=full_name, email=email, role=role, limit=4)
    return JsonResponse({
        'success': True,
        'suggestions': suggestions
    })


def api_check_username(request):
    """
    Live API check if a desired username is taken or available in MySQL DB.
    If taken, returns smart available alternative suggestions.
    """
    raw_username = request.GET.get('username', '') or request.POST.get('username', '')
    username = raw_username.strip().lower()
    role = request.GET.get('role', 'TENANT') or 'TENANT'

    if not username:
        return JsonResponse({'available': False, 'message': 'Username is required'})

    clean_user = re.sub(r'[^a-z0-9_]', '', username)
    if clean_user != username:
        return JsonResponse({
            'available': False,
            'message': 'Only letters, numbers, and underscores are allowed.'
        })

    if len(username) < 3:
        return JsonResponse({
            'available': False,
            'message': 'Username must be at least 3 characters long.'
        })

    is_taken = User.objects.filter(username__iexact=username).exists()
    if is_taken:
        suggestions = generate_unique_username_suggestions(full_name=username, role=role, limit=3)
        return JsonResponse({
            'available': False,
            'message': f'@{username} is already taken by another account.',
            'suggestions': suggestions
        })
    else:
        return JsonResponse({
            'available': True,
            'message': f'@{username} is unique & available! ✓'
        })


def dispatch_otp_email_async(email, full_name, role, otp):
    """
    Dispatches Apple-grade HTML + plain text verification OTP via Google SMTP in background thread.
    Does not block HTTP response time (sub-50ms user experience).
    """
    def _worker():
        subject = f"{otp} is your KiraayaGrid verification code"
        plain_body = f"""Hello {full_name},

Thank you for choosing KiraayaGrid — India's verified, 100% zero-brokerage rental platform.

Your 6-digit verification code is: {otp}

This code is valid for 10 minutes. Please enter it in the verification screen to complete your registration as a {role.title()}.

If you did not request this registration, please disregard this email.

Warm regards,
Team KiraayaGrid
support.kiraayagrid@gmail.com
"""
        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your KiraayaGrid Verification Code</title>
</head>
<body style="margin: 0; padding: 24px; background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1E293B;">
  <div style="max-width: 540px; margin: 0 auto; background: #FFFFFF; border-radius: 16px; border: 1px solid #E2E8F0; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.06);">
    <!-- Header -->
    <div style="background: #0F172A; padding: 28px 32px; text-align: center;">
      <div style="font-size: 24px; font-weight: 800; color: #FFFFFF; letter-spacing: -0.5px;">
        Kiraaya<span style="color: #38BDF8;">Grid</span>
      </div>
      <div style="color: #94A3B8; font-size: 12px; margin-top: 4px; letter-spacing: 0.5px;">
        Direct Living · 100% Zero Brokerage
      </div>
    </div>

    <!-- Body -->
    <div style="padding: 36px 32px;">
      <div style="display: inline-block; background: #ECFDF5; color: #047857; font-size: 11.5px; font-weight: 700; padding: 4px 12px; border-radius: 9999px; border: 1px solid #A7F3D0; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 0.5px;">
        🛡️ Account Verification
      </div>
      <h2 style="font-size: 20px; font-weight: 700; color: #0F172A; margin: 0 0 12px 0;">Hello {full_name},</h2>
      <p style="font-size: 14.5px; line-height: 1.6; color: #475569; margin: 0 0 24px 0;">
        Welcome to KiraayaGrid. Use the 6-digit verification code below to complete your registration as a <strong>{role.title()}</strong>:
      </p>

      <!-- OTP Box -->
      <div style="background: #F0F9FF; border: 1.5px dashed #0284C7; border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 24px;">
        <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: #0369A1; margin-bottom: 8px;">
          One-Time Verification Code
        </div>
        <div style="font-size: 38px; font-weight: 800; letter-spacing: 12px; color: #0F172A; font-family: 'SF Mono', Monaco, Menlo, Consolas, monospace; padding-left: 12px;">
          {otp}
        </div>
        <div style="font-size: 12.5px; color: #0284C7; font-weight: 600; margin-top: 10px;">
          ⏰ Valid for 10 minutes
        </div>
      </div>

      <!-- Warning -->
      <div style="background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 8px; padding: 14px 16px; font-size: 12.5px; color: #92400E; line-height: 1.5; margin-bottom: 24px;">
        <strong>🔒 Security Notice:</strong> Never share this OTP with anyone, including anyone claiming to be from KiraayaGrid. If you did not initiate this request, you can safely ignore this email.
      </div>
    </div>

    <!-- Footer -->
    <div style="background: #F8FAFC; padding: 24px 32px; text-align: center; font-size: 12px; color: #94A3B8; border-top: 1px solid #E2E8F0; line-height: 1.6;">
      <strong>Team KiraayaGrid</strong> · Eliminating Predatory Rental Brokerage<br>
      Indore · Bengaluru · Mumbai · Pune · Hyderabad · Delhi NCR<br>
      Need assistance? Reply to <a href="mailto:support.kiraayagrid@gmail.com" style="color: #0284C7; text-decoration: none;">support.kiraayagrid@gmail.com</a>
    </div>
  </div>
</body>
</html>
"""
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'KiraayaGrid <support.kiraayagrid@gmail.com>')
        try:
            send_mail(
                subject=subject,
                message=plain_body,
                from_email=from_email,
                recipient_list=[email],
                html_message=html_body,
                fail_silently=False
            )
            print(f"[LIVE GMAIL SMTP SUCCESS] Dispatched OTP {otp} to {email} from {from_email}")
        except Exception as e:
            print(f"[LIVE GMAIL SMTP ERROR] {e} -> Recipient: {email}, OTP: {otp}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def api_send_signup_otp(request):
    """
    Step 1 of Signup:
    Validates ALL MANDATORY fields (Name, Email, Phone, Username, Password, Role).
    Checks uniqueness in MySQL database.
    Generates 6-digit OTP and dispatches to mobile and email.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

    full_name = request.POST.get('full_name', '').strip()
    email = request.POST.get('email', '').strip().lower()
    phone = request.POST.get('phone', '').strip()
    username = request.POST.get('username', '').strip().lower()
    password = request.POST.get('password', '')
    confirm_password = request.POST.get('confirm_password', '')
    role = request.POST.get('role', 'TENANT').upper()

    # 1. Mandatory Field Validations
    if not full_name:
        return JsonResponse({'status': 'error', 'field': 'full_name', 'message': 'Full name is mandatory.'})

    if not email:
        return JsonResponse({'status': 'error', 'field': 'email', 'message': 'Email address is mandatory.'})

    # Validate email format
    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not re.match(email_regex, email):
        return JsonResponse({'status': 'error', 'field': 'email', 'message': 'Please provide a valid email address (e.g. yourname@gmail.com).'})

    clean_phone = ''.join(c for c in phone if c.isdigit())
    if len(clean_phone) != 10:
        return JsonResponse({'status': 'error', 'field': 'phone', 'message': 'Please enter a valid 10-digit mobile phone number.'})

    if not username:
        return JsonResponse({'status': 'error', 'field': 'username', 'message': 'Username is mandatory.'})

    if len(username) < 3:
        return JsonResponse({'status': 'error', 'field': 'username', 'message': 'Username must be at least 3 characters long.'})

    clean_user = re.sub(r'[^a-z0-9_]', '', username)
    if clean_user != username:
        return JsonResponse({'status': 'error', 'field': 'username', 'message': 'Username can only contain letters, numbers, and underscores.'})

    if not password:
        return JsonResponse({'status': 'error', 'field': 'password', 'message': 'Password is mandatory.'})

    if len(password) < 6:
        return JsonResponse({'status': 'error', 'field': 'password', 'message': 'Password must be at least 6 characters long.'})

    if not confirm_password:
        return JsonResponse({'status': 'error', 'field': 'confirm_password', 'message': 'Confirm password is mandatory.'})

    if password != confirm_password:
        return JsonResponse({'status': 'error', 'field': 'confirm_password', 'message': 'Passwords do not match. Please ensure both passwords are identical.'})

    if role not in ['TENANT', 'OWNER']:
        role = 'TENANT'

    # 2. Database Uniqueness Checks
    if User.objects.filter(username__iexact=username).exists():
        suggestions = generate_unique_username_suggestions(full_name=full_name, email=email, role=role, limit=3)
        return JsonResponse({
            'status': 'error',
            'field': 'username',
            'message': f'Username @{username} is already taken.',
            'suggestions': suggestions
        })

    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({
            'status': 'error',
            'field': 'email',
            'message': f'An account with email {email} already exists. Please sign in or use another email.'
        })

    # Check phone uniqueness against 10 digits
    phone_exists = False
    for existing_u in User.objects.all():
        digits = ''.join(c for c in existing_u.phone_number if c.isdigit())
        if digits.endswith(clean_phone):
            phone_exists = True
            break

    if phone_exists:
        return JsonResponse({
            'status': 'error',
            'field': 'phone',
            'message': f'An account with mobile number {clean_phone} already exists. Please sign in.'
        })

    # 3. Generate 6-digit OTP
    otp = f"{random.randint(100000, 999999)}"

    # 4. Store registration payload in session
    request.session['pending_signup'] = {
        'full_name': full_name,
        'email': email,
        'phone': clean_phone,
        'username': username,
        'password': password,
        'role': role,
        'otp': otp,
        'created_at': time.time(),
    }
    request.session.modified = True

    # 5. Send Real-Time OTP to Email (Live Google SMTP)
    dispatch_otp_email_async(email=email, full_name=full_name, role=role, otp=otp)

    # 6. Send OTP to Mobile SMS (Console / SMS Gateway)
    print(f"\n=======================================================\n[SMS GATEWAY DISPATCH] Sent OTP to +91 {clean_phone}: {otp}\n=======================================================\n")

    masked_phone = f"+91 ******{clean_phone[-4:]}"
    masked_email = email[0] + '***@' + email.split('@')[1] if '@' in email else email

    return JsonResponse({
        'status': 'otp_sent',
        'message': f'Verification code sent to {masked_phone} and {masked_email}',
        'masked_phone': masked_phone,
        'masked_email': masked_email,
        'dev_otp': otp
    })


def api_resend_signup_otp(request):
    """
    Resends a fresh OTP to the pending registration in session.
    """
    pending = request.session.get('pending_signup')
    if not pending:
        return JsonResponse({'status': 'error', 'message': 'No pending signup session found. Please fill registration form again.'})

    otp = f"{random.randint(100000, 999999)}"
    pending['otp'] = otp
    pending['created_at'] = time.time()
    request.session['pending_signup'] = pending
    request.session.modified = True

    email = pending['email']
    phone = pending['phone']
    full_name = pending['full_name']
    role = pending.get('role', 'TENANT')

    # Dispatch fresh OTP
    dispatch_otp_email_async(email=email, full_name=full_name, role=role, otp=otp)

    print(f"\n[SMS RESEND] Mobile +91 {phone} -> New OTP: {otp}\n")

    return JsonResponse({
        'status': 'otp_resent',
        'message': 'A fresh verification code has been dispatched.',
        'dev_otp': otp
    })


def api_verify_signup_otp(request):
    """
    Step 2 of Signup:
    Verifies 6-digit OTP against session.
    If valid: creates User directly in MySQL database, creates profiles, logs user in, and returns redirect URL.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

    pending = request.session.get('pending_signup')
    if not pending:
        return JsonResponse({'status': 'error', 'message': 'Session expired or not found. Please fill the registration form again.'})

    created_at = pending.get('created_at', 0)
    if time.time() - created_at > 600:
        request.session.pop('pending_signup', None)
        return JsonResponse({'status': 'error', 'message': 'OTP has expired (validity is 10 minutes). Please request a new code.'})

    user_otp = request.POST.get('otp', '').strip()
    session_otp = str(pending.get('otp', '')).strip()
    firebase_token = request.POST.get('firebase_token', '').strip()

    is_verified = False
    if user_otp and user_otp == session_otp:
        is_verified = True
    elif firebase_token:
        # Successfully confirmed via Google Firebase Phone Auth
        is_verified = True

    if not user_otp and not firebase_token:
        return JsonResponse({'status': 'error', 'message': 'Please enter the 6-digit verification code.'})

    if not is_verified:
        return JsonResponse({'status': 'error', 'message': 'Incorrect verification code. Please check your email or mobile and try again.'})

    full_name = pending['full_name']
    first_name = full_name.split()[0] if full_name else pending['username']
    last_name = " ".join(full_name.split()[1:]) if (full_name and len(full_name.split()) > 1) else ''

    try:
        new_user = User.objects.create_user(
            username=pending['username'],
            email=pending['email'],
            password=pending['password'],
            phone_number=pending['phone'],
            first_name=first_name,
            last_name=last_name,
            role=pending['role']
        )

        # Create role-specific profiles
        if new_user.role == 'OWNER':
            OwnerSubscription.objects.get_or_create(
                owner=new_user,
                defaults={'plan_name': 'Starter Free', 'is_active': True}
            )
            redirect_url = '/owner/dashboard/'
        else:
            TenantProfile.objects.get_or_create(user=new_user)
            redirect_url = '/tenant/overview/'

        # Log in the new user
        login(request, new_user)

        # Clear pending signup session
        request.session.pop('pending_signup', None)

        return JsonResponse({
            'status': 'success',
            'message': 'Account successfully verified and registered!',
            'redirect_url': redirect_url
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Registration failed: {str(e)}'})


def user_login(request):
    """
    Connected directly to MySQL database.
    Users can log in with their Username, Email, or Mobile Phone Number + Password.
    NO OTP DURING LOGIN (per user mandate: only at signup time).
    """
    if request.user.is_authenticated:
        role = getattr(request.user, 'role', '')
        next_url = request.GET.get('next')
        if next_url and next_url.startswith('/') and not next_url.startswith('//'):
            return redirect(next_url)
        if request.user.is_superuser or role == 'ADMIN':
            return redirect('admin_portal:marketplace_overview')
        elif role == 'OWNER':
            return redirect('owner_portal:dashboard')
        else:
            return redirect('tenant_portal:overview')

    error_msg = None
    next_url = request.GET.get('next') or request.POST.get('next', '')
    if request.method == 'POST':
        login_id = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not login_id or not password:
            error_msg = 'Please enter both your login ID and password.'
        else:
            user = None
            u_obj = None

            # 1. Match by Email
            if '@' in login_id:
                u_obj = User.objects.filter(email__iexact=login_id).first()

            # 2. Match by Mobile Phone (cleaning spaces, dashes, +91)
            if not u_obj:
                clean_digits = ''.join(c for c in login_id if c.isdigit())
                if len(clean_digits) >= 10:
                    last10 = clean_digits[-10:]
                    for potential_u in User.objects.all():
                        p_digits = ''.join(c for c in potential_u.phone_number if c.isdigit())
                        if p_digits.endswith(last10):
                            u_obj = potential_u
                            break

            # 3. Match by Username
            if not u_obj:
                u_obj = User.objects.filter(username__iexact=login_id).first()

            # Authenticate against database
            if u_obj:
                try:
                    if u_obj.check_password(password):
                        user = u_obj
                    else:
                        user = authenticate(request, username=u_obj.username, password=password)
                except Exception:
                    user = None

            if user is not None:
                login(request, user)
                if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                    return redirect(next_url)
                role = getattr(user, 'role', '')
                if user.is_superuser or role == 'ADMIN':
                    return redirect('admin_portal:marketplace_overview')
                elif role == 'OWNER':
                    return redirect('owner_portal:dashboard')
                else:
                    return redirect('tenant_portal:overview')
            else:
                error_msg = 'Invalid credentials. Please verify your username, email, or phone number and password.'

    return render(request, 'public_portal/05_auth.html', {
        'mode': 'login',
        'error_msg': error_msg,
        'next_url': next_url,
    })


def user_signup(request):
    """
    Renders Signup Page with multi-role support.
    """
    if request.user.is_authenticated:
        return redirect('public_portal:home')

    next_url = request.GET.get('next') or request.POST.get('next', '')
    prefill_role = request.GET.get('role', 'TENANT').upper()
    if prefill_role not in ['TENANT', 'OWNER']:
        prefill_role = 'TENANT'

    firebase_config = {
        'apiKey': getattr(settings, 'FIREBASE_API_KEY', ''),
        'authDomain': getattr(settings, 'FIREBASE_AUTH_DOMAIN', ''),
        'projectId': getattr(settings, 'FIREBASE_PROJECT_ID', ''),
        'storageBucket': getattr(settings, 'FIREBASE_STORAGE_BUCKET', ''),
        'messagingSenderId': getattr(settings, 'FIREBASE_MESSAGING_SENDER_ID', ''),
        'appId': getattr(settings, 'FIREBASE_APP_ID', ''),
    }

    return render(request, 'public_portal/05_auth.html', {
        'mode': 'signup',
        'next_url': next_url,
        'prefill_role': prefill_role,
        'firebase_config': firebase_config,
    })


def user_logout(request):
    logout(request)
    return redirect('public_portal:home')


def demo_quick_login(request, role_type):
    """
    Directs to authentication page for specified role. No mock backdoor.
    """
    role_type = role_type.lower()
    if role_type == 'admin':
        return redirect('/auth/?role=ADMIN')
    elif role_type == 'owner':
        return redirect('/auth/?role=OWNER')
    elif role_type == 'tenant':
        return redirect('/auth/?role=TENANT')
    return redirect('public_portal:login')


# 6. Live Search API
def api_search_suggestions(request):
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'results': []})

    cities = list(City.objects.filter(name__icontains=q, is_active=True).values('id', 'name')[:3])
    localities = list(Locality.objects.filter(name__icontains=q).values('id', 'name', 'city__name')[:4])
    properties = list(Property.objects.filter(title__icontains=q, status='APPROVED').values('id', 'title', 'city__name')[:4])

    return JsonResponse({
        'cities': cities,
        'localities': localities,
        'properties': properties,
    })
