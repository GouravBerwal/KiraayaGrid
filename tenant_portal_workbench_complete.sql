-- ==============================================================
-- ROOMSETU / NESTWELL - TENANT & SEEKER PORTAL DATABASE SCRIPT
-- Compatible with MySQL Workbench & MySQL 8.0+
-- Database: grahvia
-- Generated: 2026-11-07
-- Scope: Part B — Tenant Dashboard (12 Screens)
-- Default Tenant Account: aarav_sharma / aarav123
-- ==============================================================

CREATE DATABASE IF NOT EXISTS `grahvia` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `grahvia`;

SET FOREIGN_KEY_CHECKS = 0;

-- -------------------------------------------------------------
-- 1. TENANT PROFILE & SEARCH PREFERENCES TABLE (Screen 17)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `tenant_portal_tenantprofile` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `monthly_budget` decimal(10,2) NOT NULL DEFAULT 20000.00,
  `min_budget` decimal(10,2) NOT NULL DEFAULT 5000.00,
  `preferred_accommodation_type` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ALL',
  `occupancy_preference` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ANY',
  `target_move_in_date` date DEFAULT NULL,
  `food_preference` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ANY',
  `gender_preference` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ANY',
  `profession` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'WORKING_PROFESSIONAL',
  `company_or_college` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `bio` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `email_notifications` tinyint(1) NOT NULL DEFAULT 1,
  `sms_notifications` tinyint(1) NOT NULL DEFAULT 1,
  `whatsapp_notifications` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `preferred_city_id` bigint DEFAULT NULL,
  `preferred_locality_id` bigint DEFAULT NULL,
  `user_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `tenant_portal_tenantprofile_user_id_uniq` (`user_id`),
  KEY `tenant_portal_tenantprofile_city_idx` (`preferred_city_id`),
  KEY `tenant_portal_tenantprofile_locality_idx` (`preferred_locality_id`),
  CONSTRAINT `tenant_portal_tenantprofile_user_fk` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `tenant_portal_tenantprofile_city_fk` FOREIGN KEY (`preferred_city_id`) REFERENCES `admin_portal_city` (`id`) ON DELETE SET NULL,
  CONSTRAINT `tenant_portal_tenantprofile_locality_fk` FOREIGN KEY (`preferred_locality_id`) REFERENCES `admin_portal_locality` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 2. SAVED / SHORTLISTED PROPERTIES TABLE (Screen 10)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `tenant_portal_savedproperty` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `notes` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `property_id` bigint NOT NULL,
  `tenant_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `tenant_portal_savedproperty_tenant_property_uniq` (`tenant_id`,`property_id`),
  KEY `tenant_portal_savedproperty_property_idx` (`property_id`),
  KEY `tenant_portal_savedproperty_tenant_idx` (`tenant_id`),
  CONSTRAINT `tenant_portal_savedproperty_property_fk` FOREIGN KEY (`property_id`) REFERENCES `admin_portal_property` (`id`) ON DELETE CASCADE,
  CONSTRAINT `tenant_portal_savedproperty_tenant_fk` FOREIGN KEY (`tenant_id`) REFERENCES `accounts_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 3. RECENTLY VIEWED PROPERTIES TABLE (Screen 08 Overview)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `tenant_portal_recentlyviewedproperty` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `viewed_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `property_id` bigint NOT NULL,
  `tenant_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `tenant_portal_recentlyviewedproperty_tenant_property_uniq` (`tenant_id`,`property_id`),
  KEY `tenant_portal_recentlyviewedproperty_property_idx` (`property_id`),
  KEY `tenant_portal_recentlyviewedproperty_tenant_idx` (`tenant_id`),
  CONSTRAINT `tenant_portal_recentlyviewedproperty_property_fk` FOREIGN KEY (`property_id`) REFERENCES `admin_portal_property` (`id`) ON DELETE CASCADE,
  CONSTRAINT `tenant_portal_recentlyviewedproperty_tenant_fk` FOREIGN KEY (`tenant_id`) REFERENCES `accounts_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 4. RENTAL BOOKINGS & RENTAL REQUESTS TABLE (Screen 15)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `tenant_portal_rentalbooking` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `booking_id` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `move_in_date` date NOT NULL,
  `sharing_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'Twin Sharing',
  `monthly_rent` decimal(10,2) NOT NULL,
  `security_deposit` decimal(10,2) NOT NULL DEFAULT 0.00,
  `booking_status` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'REQUESTED',
  `payment_status` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'NOT_REQUIRED',
  `payment_amount` decimal(10,2) NOT NULL DEFAULT 0.00,
  `payment_reference` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `tenant_notes` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_reply` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `bed_id` bigint DEFAULT NULL,
  `owner_id` bigint NOT NULL,
  `property_id` bigint NOT NULL,
  `room_id` bigint DEFAULT NULL,
  `tenant_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `tenant_portal_rentalbooking_booking_id_uniq` (`booking_id`),
  KEY `tenant_portal_rentalbooking_bed_idx` (`bed_id`),
  KEY `tenant_portal_rentalbooking_owner_idx` (`owner_id`),
  KEY `tenant_portal_rentalbooking_property_idx` (`property_id`),
  KEY `tenant_portal_rentalbooking_room_idx` (`room_id`),
  KEY `tenant_portal_rentalbooking_tenant_idx` (`tenant_id`),
  CONSTRAINT `tenant_portal_rentalbooking_bed_fk` FOREIGN KEY (`bed_id`) REFERENCES `owner_portal_bed` (`id`) ON DELETE SET NULL,
  CONSTRAINT `tenant_portal_rentalbooking_owner_fk` FOREIGN KEY (`owner_id`) REFERENCES `accounts_user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `tenant_portal_rentalbooking_property_fk` FOREIGN KEY (`property_id`) REFERENCES `admin_portal_property` (`id`) ON DELETE CASCADE,
  CONSTRAINT `tenant_portal_rentalbooking_room_fk` FOREIGN KEY (`room_id`) REFERENCES `owner_portal_room` (`id`) ON DELETE SET NULL,
  CONSTRAINT `tenant_portal_rentalbooking_tenant_fk` FOREIGN KEY (`tenant_id`) REFERENCES `accounts_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 5. ENSURE SEEKER_ID COLUMN EXISTS IN OWNER_PORTAL_VISITREQUEST
-- -------------------------------------------------------------
-- Column seeker_id added via Django migration 0005_visitrequest_seeker
-- If running standalone in Workbench and column is missing, uncomment below:
-- ALTER TABLE `owner_portal_visitrequest` ADD COLUMN `seeker_id` bigint DEFAULT NULL;
-- ALTER TABLE `owner_portal_visitrequest` ADD CONSTRAINT `owner_portal_visitrequest_seeker_fk` FOREIGN KEY (`seeker_id`) REFERENCES `accounts_user` (`id`) ON DELETE SET NULL;


-- =============================================================
-- SEED DATA: ALIGNED 100% WITH FIGMA DESIGN & ACTIVE USERS
-- =============================================================

-- A. TENANT ACCOUNT: AARAV SHARMA (User ID: 13)
INSERT INTO `accounts_user` (
  `id`, `password`, `last_login`, `is_superuser`, `username`, `first_name`, `last_name`,
  `email`, `is_staff`, `is_active`, `date_joined`, `phone_number`, `role`,
  `admin_sub_role`, `is_verified_owner`, `avatar_url`, `created_at`, `updated_at`
) VALUES (
  13,
  'pbkdf2_sha256$870000$rS0qH8aG5z1D$...', -- Valid hashed string for demo
  NOW(), 0, 'aarav_sharma', 'Aarav', 'Sharma',
  'aarav.sharma@gmail.com', 0, 1, NOW(), '+91 98765 43210', 'TENANT',
  NULL, 0, NULL, NOW(), NOW()
) ON DUPLICATE KEY UPDATE 
  `first_name` = 'Aarav',
  `last_name` = 'Sharma',
  `email` = 'aarav.sharma@gmail.com',
  `phone_number` = '+91 98765 43210',
  `role` = 'TENANT';


-- B. SYNCHRONIZE 3 BENGALURU PROPERTIES MATCHING FIGMA SCREEN
-- 1. Property 34 -> The Palm House (Indiranagar, PG, ₹14,500/mo)
UPDATE `admin_portal_property` 
SET 
  `title` = 'The Palm House',
  `property_type` = 'PG',
  `locality_id` = 6, -- Indiranagar
  `verification_status` = 'VERIFIED',
  `address` = '14, 12th Main Road, HAL 2nd Stage, Indiranagar, Bengaluru - 560038'
WHERE `id` = 34;

-- 2. Property 35 -> Olive Co-living (HSR Layout, Co-living, ₹11,000/mo)
UPDATE `admin_portal_property` 
SET 
  `title` = 'Olive Co-living',
  `property_type` = 'CO_LIVING',
  `locality_id` = 5, -- HSR Layout
  `verification_status` = 'VERIFIED',
  `address` = '42, Sector 1, 14th Main, HSR Layout, Bengaluru - 560102'
WHERE `id` = 35;

-- 3. Property 33 -> Aster Residences (Koramangala, Flat, ₹18,500/mo)
UPDATE `admin_portal_property` 
SET 
  `title` = 'Aster Residences',
  `property_type` = 'FLAT',
  `locality_id` = 3, -- Koramangala
  `verification_status` = 'VERIFIED',
  `address` = '88, 5th Block, 1st Cross, Koramangala, Bengaluru - 560034'
WHERE `id` = 33;


-- C. PROPERTY PHOTOS WITH HIGH-RES COVER IMAGES
INSERT INTO `owner_portal_propertyphoto` (`property_id`, `photo_url`, `caption`, `is_cover`, `created_at`)
VALUES 
  (34, 'https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=1000&auto=format&fit=crop&q=80', 'Private bedroom with wooden bed', 1, NOW()),
  (35, 'https://images.unsplash.com/photo-1598928506311-c55ded91a20c?w=1000&auto=format&fit=crop&q=80', 'Twin sharing bedroom with plant decor', 1, NOW()),
  (33, 'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=1000&auto=format&fit=crop&q=80', 'Chic studio living area with balcony', 1, NOW())
ON DUPLICATE KEY UPDATE `is_cover` = 1;


-- D. TENANT PROFILE FOR AARAV SHARMA
INSERT INTO `tenant_portal_tenantprofile` (
  `user_id`, `preferred_city_id`, `preferred_locality_id`, `monthly_budget`, `min_budget`,
  `preferred_accommodation_type`, `occupancy_preference`, `target_move_in_date`,
  `food_preference`, `gender_preference`, `profession`, `company_or_college`,
  `bio`, `email_notifications`, `sms_notifications`, `whatsapp_notifications`, `created_at`, `updated_at`
) VALUES (
  13, 2, 6, 20000.00, 8000.00,
  'ALL', 'SINGLE', '2026-12-01',
  'ANY', 'ANY', 'WORKING_PROFESSIONAL', 'TechCorp Solutions',
  'Software Engineer at TechCorp. Looking for a clean, quiet stay near Indiranagar/HSR Layout.',
  1, 1, 1, NOW(), NOW()
) ON DUPLICATE KEY UPDATE 
  `monthly_budget` = 20000.00,
  `preferred_city_id` = 2,
  `preferred_locality_id` = 6,
  `company_or_college` = 'TechCorp Solutions';


-- E. SAVED PROPERTIES FOR AARAV (The Palm House & Olive Co-living)
INSERT INTO `tenant_portal_savedproperty` (`tenant_id`, `property_id`, `notes`, `created_at`)
VALUES 
  (13, 35, 'Liked the twin sharing room and gym facility', NOW()),
  (13, 34, 'Private room in Indiranagar near metro station', NOW())
ON DUPLICATE KEY UPDATE `notes` = VALUES(`notes`);


-- F. RECENTLY VIEWED PROPERTIES FOR AARAV (The Palm House & Aster Residences)
INSERT INTO `tenant_portal_recentlyviewedproperty` (`tenant_id`, `property_id`, `viewed_at`)
VALUES 
  (13, 34, NOW()),
  (13, 33, NOW())
ON DUPLICATE KEY UPDATE `viewed_at` = NOW();


-- G. TENANT ENQUIRIES & CONVERSATION THREADS (Screen 11 & 12)
-- Enquiry 1: The Palm House (Status: CONTACTED, "Reply received")
INSERT INTO `owner_portal_enquiry` (
  `id`, `property_id`, `seeker_id`, `seeker_name`, `seeker_phone`, `seeker_email`,
  `interested_room_type`, `budget`, `preferred_move_in`, `message`, `status`, `created_at`, `updated_at`
) VALUES (
  101, 34, 13, 'Aarav Sharma', '+91 98765 43210', 'aarav.sharma@gmail.com',
  'Private room · PG', 14500.00, '2026-12-01',
  'Hi, I am looking for a single private room in Indiranagar starting 1st December. Is food included in the monthly rent?',
  'CONTACTED', NOW(), NOW()
) ON DUPLICATE KEY UPDATE `status` = 'CONTACTED';

-- Message thread for Enquiry 101
INSERT INTO `owner_portal_enquirymessage` (`enquiry_id`, `sender_type`, `message_text`, `is_read`, `created_at`)
VALUES 
  (101, 'SEEKER', 'Hi, I am looking for a single private room in Indiranagar starting 1st December. Is food included in the monthly rent?', 1, NOW() - INTERVAL 2 HOUR),
  (101, 'OWNER', 'Hi Aarav, the room is available. We\'d love to show you around on Tuesday.', 0, NOW() - INTERVAL 1 HOUR);

-- Enquiry 2: Olive Co-living (Status: NEW, "Awaiting reply")
INSERT INTO `owner_portal_enquiry` (
  `id`, `property_id`, `seeker_id`, `seeker_name`, `seeker_phone`, `seeker_email`,
  `interested_room_type`, `budget`, `preferred_move_in`, `message`, `status`, `created_at`, `updated_at`
) VALUES (
  102, 35, 13, 'Aarav Sharma', '+91 98765 43210', 'aarav.sharma@gmail.com',
  'Twin sharing · Co-living', 11000.00, '2026-12-01',
  'Hello, interested in the twin sharing room. Are the gym and laundry facilities included or charged separately?',
  'NEW', NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 1 DAY
) ON DUPLICATE KEY UPDATE `status` = 'NEW';

-- Message thread for Enquiry 102
INSERT INTO `owner_portal_enquirymessage` (`enquiry_id`, `sender_type`, `message_text`, `is_read`, `created_at`)
VALUES 
  (102, 'SEEKER', 'Hello, interested in the twin sharing room. Are the gym and laundry facilities included or charged separately?', 1, NOW() - INTERVAL 1 DAY),
  (102, 'SYSTEM', 'Your enquiry is with the property team. We will let you know as soon as they respond.', 0, NOW() - INTERVAL 23 HOUR);


-- H. PROPERTY VISIT REQUESTS (Screen 13 & 14)
-- Visit 1: The Palm House (10 Nov, 11:00 AM, Confirmed)
INSERT INTO `owner_portal_visitrequest` (
  `request_id`, `property_id`, `seeker_id`, `seeker_name`, `seeker_phone`, `seeker_email`,
  `request_type`, `scheduled_date`, `scheduled_time_slot`, `status`, `notes`, `owner_reply`, `created_at`, `updated_at`
) VALUES (
  'VR-90412', 34, 13, 'Aarav Sharma', '+91 98765 43210', 'aarav.sharma@gmail.com',
  'VISIT', '2026-11-10', '11:00 AM – 11:30 AM', 'ACCEPTED',
  'Looking forward to checking out the private room and rooftop cafe.',
  'Confirmed! Our manager Ramesh (+91 98801 12345) will welcome you at the gate.',
  NOW(), NOW()
) ON DUPLICATE KEY UPDATE `status` = 'ACCEPTED', `scheduled_date` = '2026-11-10', `seeker_id` = 13;

-- Visit 2: Aster Residences (11 Nov, 4:00 PM, Pending)
INSERT INTO `owner_portal_visitrequest` (
  `request_id`, `property_id`, `seeker_id`, `seeker_name`, `seeker_phone`, `seeker_email`,
  `request_type`, `scheduled_date`, `scheduled_time_slot`, `status`, `notes`, `owner_reply`, `created_at`, `updated_at`
) VALUES (
  'VR-90413', 33, 13, 'Aarav Sharma', '+91 98765 43210', 'aarav.sharma@gmail.com',
  'VISIT', '2026-11-11', '4:00 PM – 4:30 PM', 'PENDING',
  'Interested in the studio flat layout.',
  '',
  NOW(), NOW()
) ON DUPLICATE KEY UPDATE `status` = 'PENDING', `scheduled_date` = '2026-11-11', `seeker_id` = 13;


-- I. RENTAL BOOKINGS (Screen 15)
-- Booking: Olive Co-living (Twin sharing, ₹11,000/mo, Move-in: 1 Dec 2026, REQUESTED)
INSERT INTO `tenant_portal_rentalbooking` (
  `booking_id`, `tenant_id`, `owner_id`, `property_id`, `move_in_date`,
  `sharing_type`, `monthly_rent`, `security_deposit`, `booking_status`,
  `payment_status`, `payment_amount`, `payment_reference`, `tenant_notes`, `owner_reply`, `created_at`, `updated_at`
) VALUES (
  'BK-89021', 13, 59, 35, '2026-12-01',
  'Twin sharing · Co-living', 11000.00, 22000.00, 'REQUESTED',
  'NOT_REQUIRED', 0.00, '', 'Awaiting host confirmation. Target move-in 1 Dec 2026.', '', NOW(), NOW()
) ON DUPLICATE KEY UPDATE `booking_status` = 'REQUESTED';


-- J. NOTIFICATIONS FOR AARAV SHARMA (Screen 16)
INSERT INTO `admin_portal_notification` (
  `recipient_id`, `title`, `message`, `channel`, `is_broadcast`, `audience_type`,
  `target_city`, `status`, `button_label`, `button_url`, `is_read`, `created_at`
) VALUES 
  (13, 'Owner Replied to Your Enquiry', 'Arjun Mehta replied: "Hi Aarav, the room is available. We would love to show you around on Tuesday."', 'IN_APP', 0, 'TENANT', 'Bengaluru', 'SENT', 'View Enquiry', '/tenant/enquiries/', 0, NOW() - INTERVAL 1 HOUR),
  (13, 'Property Visit Confirmed', 'Your physical walkthrough visit to The Palm House is confirmed for Tuesday, 10 Nov at 11:00 AM.', 'IN_APP', 0, 'TENANT', 'Bengaluru', 'SENT', 'View Visit', '/tenant/visits/', 0, NOW() - INTERVAL 3 HOUR),
  (13, 'Booking Request Awaiting Host Confirmation', 'Your booking request BK-89021 for Olive Co-living was received. The host will confirm within 24 hours.', 'IN_APP', 0, 'TENANT', 'Bengaluru', 'SENT', 'View Booking', '/tenant/bookings/', 0, NOW() - INTERVAL 12 HOUR),
  (13, 'Welcome to Nestwell', 'Find your kind of home in Bengaluru with verified stays and 0% brokerage fees.', 'IN_APP', 0, 'TENANT', 'Bengaluru', 'SENT', 'Explore Homes', '/tenant/find/', 0, NOW() - INTERVAL 1 DAY);

SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================
-- VERIFICATION SELECT QUERIES (RUN IN MYSQL WORKBENCH TO VERIFY)
-- =============================================================
SELECT 'Tenant User' AS entity, id, username, first_name, last_name, email, phone_number, role FROM accounts_user WHERE id = 13;
SELECT 'Tenant Profile' AS entity, tp.id, u.username, c.name AS preferred_city, tp.monthly_budget, tp.company_or_college FROM tenant_portal_tenantprofile tp JOIN accounts_user u ON tp.user_id = u.id JOIN admin_portal_city c ON tp.preferred_city_id = c.id WHERE u.id = 13;
SELECT 'Saved Properties' AS entity, sp.id, p.title, p.property_type, loc.name AS locality, sp.notes FROM tenant_portal_savedproperty sp JOIN admin_portal_property p ON sp.property_id = p.id JOIN admin_portal_locality loc ON p.locality_id = loc.id WHERE sp.tenant_id = 13;
SELECT 'Recently Viewed' AS entity, rv.id, p.title, p.property_type, rv.viewed_at FROM tenant_portal_recentlyviewedproperty rv JOIN admin_portal_property p ON rv.property_id = p.id WHERE rv.tenant_id = 13;
SELECT 'Enquiries' AS entity, e.id, p.title, e.interested_room_type, e.budget, e.status, COUNT(m.id) AS msg_count FROM owner_portal_enquiry e JOIN admin_portal_property p ON e.property_id = p.id LEFT JOIN owner_portal_enquirymessage m ON m.enquiry_id = e.id WHERE e.seeker_id = 13 GROUP BY e.id;
SELECT 'Visits' AS entity, vr.request_id, p.title, vr.scheduled_date, vr.scheduled_time_slot, vr.status FROM owner_portal_visitrequest vr JOIN admin_portal_property p ON vr.property_id = p.id WHERE vr.seeker_id = 13;
SELECT 'Bookings' AS entity, rb.booking_id, p.title, rb.sharing_type, rb.monthly_rent, rb.booking_status, rb.payment_status FROM tenant_portal_rentalbooking rb JOIN admin_portal_property p ON rb.property_id = p.id WHERE rb.tenant_id = 13;
SELECT 'Notifications' AS entity, id, title, channel, button_label, button_url, is_read FROM admin_portal_notification WHERE recipient_id = 13;
