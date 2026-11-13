# KiraayaGrid 🏠

> Modern Accommodation Discovery and Property Management Marketplace connecting renters with verified PGs, hostels, flats, and co-living spaces across India.

---

## 📖 Overview

**KiraayaGrid** is an end-to-end accommodation platform built with **Python, Django, MySQL, HTML5, CSS3, and Vanilla JavaScript**. Designed with an Apple-grade UI inspired by Figma specifications, it offers zero brokerage accommodation discovery with dedicated, role-isolated portals for platform administrators, property owners/hosts, and tenants/residents.

---

## 🌟 Key Features

### 1. 🌐 Public Website
- **Modern Landing Page**: Dynamic search, trending cities (Indore #1 priority), curated stay collections, and founder spotlight.
- **Accommodation Explorer**: Multi-city search with filters for accommodation type (PG, Flat, Hostel, Co-living), budget range, sharing options, food preference, and amenities.
- **Neighborhood & City Pages**: City guides with localized accommodation listings.
- **Dedicated Host Onboarding**: "List Your Property" landing flow for prospective landlords.
- **Role-Based Authentication**: Unified authentication system with live username suggestions, email validation, and Google Firebase phone verification.

### 2. 🛡️ Admin Portal (Super Admin Exclusive)
- **Marketplace Overview**: Real-time platform metrics, active listings, tenant demand, and revenue charts.
- **Owner Verification**: Aadhaar/PAN KYC document verification with one-click approve/reject actions.
- **Property Moderation**: Audit listing specifications, floor plans, room photographs, and verify listings.
- **User Management**: Unified resident and owner directory with suspend/activate capabilities.
- **Reports & Complaints**: Dispute resolution engine for resident grievances.
- **Change Requests**: Moderate owner-requested changes to rent, deposits, and room inventory.
- **Master Catalogs**: Dynamic management of Cities, Localities, Landmarks, and Amenities.
- **Financial Analytics & Monetization**: Owner subscriptions, plan upgrades, and payment tracking.
- **Audit Logs & Security**: Comprehensive tracking of privileged staff actions and authentication logs.

### 3. 🏢 Owner Portal (Property Hosts)
- **Host Dashboard**: Property occupancy rates, rental earnings, active leads, and upcoming visits.
- **15-Step Listing Wizard**: Step-by-step Apple-grade listing creation with auto-saving drafts.
- **Room & Bed Inventory**: Room-by-room configuration and individual bed status tracking (Available, Reserved, Occupied).
- **Enquiry & Lead Management**: Receive direct enquiries from seekers with integrated messaging.
- **Visit Scheduling**: Manage physical visit requests (accept, reschedule, confirm).
- **Dynamic Pricing**: Adjust seasonal rent, token deposits, maintenance charges, and notice periods.
- **Subscription Management**: Starter, Professional, and Enterprise plans with invoice downloads.

### 4. 🏠 Tenant Portal (Residents & Seekers)
- **Tenant Dashboard**: Unified view of scheduled property visits, active enquiries, and booked stays.
- **Find Accommodation**: Real-time search with interactive filters and quick-view modals.
- **Saved Properties (Shortlist)**: Bookmark stays and compare pricing, amenities, and room sharing.
- **Enquiries & Chat**: Track response status from property hosts with notification badges.
- **Visit Management**: Confirm, reschedule, or cancel scheduled property visits.
- **Booking Management**: Reserve rooms, review agreement terms, and pay token deposits.
- **Profile & Preferences**: Set preferred city, monthly budget, sharing type, and food habits.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.12+ / Django 5+ / 6+
- **Database**: MySQL 8.0+ (PyMySQL driver)
- **Frontend**: Semantic HTML5, CSS3 (Custom Variables, Flexbox/Grid), Vanilla JavaScript (No heavy frameworks)
- **Authentication**: Django Auth + Google Firebase Phone OTP + Email SMTP verification
- **Styling**: Apple-grade Clean UI Design System (Figma-aligned)
- **Real-Time Communication**: Multi-channel alerts (Email SMTP & SMS/WhatsApp logs)

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- MySQL Server 8.0+
- Git

### 2. Clone the Repository
```bash
git clone https://github.com/GouravBerwal/KiraayaGrid.git
cd KiraayaGrid
```

### 3. Create and Activate Virtual Environment
```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your details:
```bash
cp .env.example .env
```

Ensure your MySQL database exists:
```sql
CREATE DATABASE grahvia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 6. Apply Database Migrations
```bash
python manage.py migrate
```

### 7. Create Super Admin Account
```bash
python manage.py createsuperuser
```

### 8. Run Development Server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your browser.

---

## 🧭 Portal URLs Reference

| Portal | URL | Default Role |
|---|---|---|
| **Public Website** | `http://127.0.0.1:8000/` | Guest / Public |
| **Authentication** | `http://127.0.0.1:8000/auth/` | All Users |
| **Admin Portal** | `http://127.0.0.1:8000/admin/` | Super Admin (`is_superuser=True`) |
| **Owner Workbench** | `http://127.0.0.1:8000/owner/dashboard/` | Property Owners (`role='OWNER'`) |
| **Tenant Portal** | `http://127.0.0.1:8000/tenant/dashboard/` | Tenants / Residents (`role='TENANT'`) |

---

## 🔒 Security & Access Control

- **Strict Superuser Gate**: Platform Admin routes are protected by `AdminSuperuserMiddleware`, strictly rejecting non-superuser access.
- **Role Isolation**: Dedicated middleware redirects users to their appropriate workbench based on verified role.
- **Protected Environment**: Secret keys, database credentials, and SMTP app passwords are strictly decoupled via `python-dotenv`.

---

## 👨‍💻 Author

**Gourav Berwal**
- GitHub: [@GouravBerwal](https://github.com/GouravBerwal)
- Email: gouravberwal003@gmail.com
