-- ==============================================================
-- ROOMSETU / AANGAN - OWNER PORTAL COMPLETE DATABASE SCRIPT
-- Compatible with MySQL Workbench & MySQL 8.0+
-- Database: grahvia
-- Generated: 2026-11-06
-- ==============================================================

CREATE DATABASE IF NOT EXISTS `grahvia` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `grahvia`;

SET FOREIGN_KEY_CHECKS = 0;

-- -------------------------------------------------------------
-- 1. OWNER ROOMS TABLE (Screen 03, 04, 07, 09)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `owner_portal_room` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `room_number` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `room_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `max_occupancy` int unsigned NOT NULL,
  `total_beds` int unsigned NOT NULL,
  `occupied_beds` int unsigned NOT NULL,
  `available_beds` int unsigned NOT NULL,
  `monthly_rent` decimal(10,2) NOT NULL,
  `security_deposit` decimal(10,2) NOT NULL,
  `bathroom_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ac_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `furnishing` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `amenities` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `cover_photo` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `property_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `owner_portal_room_property_id_idx` (`property_id`),
  CONSTRAINT `owner_portal_room_property_id_fk` FOREIGN KEY (`property_id`) REFERENCES `admin_portal_property` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 2. INDIVIDUAL BEDS TABLE (Screen 04 - Bed Availability Grid)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `owner_portal_bed` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `bed_number` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `bed_position` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `tenant_name` varchar(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `occupied_since` date DEFAULT NULL,
  `monthly_rent` decimal(10,2) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `room_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `owner_portal_bed_room_id_idx` (`room_id`),
  CONSTRAINT `owner_portal_bed_room_id_fk` FOREIGN KEY (`room_id`) REFERENCES `owner_portal_room` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 3. PROPERTY PHOTOS GALLERY (Screen 03 Tab 8, Screen 09 Wizard)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `owner_portal_propertyphoto` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `photo_url` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `photo_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `caption` varchar(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_cover` tinyint(1) NOT NULL DEFAULT 0,
  `sort_order` int unsigned NOT NULL DEFAULT 1,
  `created_at` datetime(6) NOT NULL,
  `property_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `owner_portal_photo_property_id_idx` (`property_id`),
  CONSTRAINT `owner_portal_photo_property_id_fk` FOREIGN KEY (`property_id`) REFERENCES `admin_portal_property` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 4. SEEKER ENQUIRIES TABLE (Screen 05, 06)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `owner_portal_enquiry` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `seeker_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `seeker_phone` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `seeker_email` varchar(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `interested_room_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `budget` decimal(10,2) NOT NULL,
  `preferred_move_in` date DEFAULT NULL,
  `message` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `property_id` bigint NOT NULL,
  `seeker_id` bigint DEFAULT NULL,
  `room_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `owner_portal_enquiry_property_id_idx` (`property_id`),
  KEY `owner_portal_enquiry_seeker_id_idx` (`seeker_id`),
  KEY `owner_portal_enquiry_room_id_idx` (`room_id`),
  CONSTRAINT `owner_portal_enquiry_property_id_fk` FOREIGN KEY (`property_id`) REFERENCES `admin_portal_property` (`id`) ON DELETE CASCADE,
  CONSTRAINT `owner_portal_enquiry_room_id_fk` FOREIGN KEY (`room_id`) REFERENCES `owner_portal_room` (`id`) ON DELETE SET NULL,
  CONSTRAINT `owner_portal_enquiry_seeker_id_fk` FOREIGN KEY (`seeker_id`) REFERENCES `accounts_user` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 5. ENQUIRY MESSAGES THREAD (Screen 06 Conversation)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `owner_portal_enquirymessage` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `sender_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `message_text` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_read` tinyint(1) NOT NULL DEFAULT 0,
  `created_at` datetime(6) NOT NULL,
  `enquiry_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `owner_portal_enquiry_msg_idx` (`enquiry_id`),
  CONSTRAINT `owner_portal_enquiry_msg_fk` FOREIGN KEY (`enquiry_id`) REFERENCES `owner_portal_enquiry` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 6. BOOKING & VISIT REQUESTS (Screen 07, 08)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `owner_portal_visitrequest` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `request_id` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `seeker_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `seeker_phone` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `seeker_email` varchar(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `request_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'VISIT',
  `scheduled_date` date NOT NULL,
  `scheduled_time_slot` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PENDING',
  `notes` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_reply` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `property_id` bigint NOT NULL,
  `room_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `request_id_uniq` (`request_id`),
  KEY `owner_portal_visit_property_id_idx` (`property_id`),
  KEY `owner_portal_visit_room_id_idx` (`room_id`),
  CONSTRAINT `owner_portal_visit_property_id_fk` FOREIGN KEY (`property_id`) REFERENCES `admin_portal_property` (`id`) ON DELETE CASCADE,
  CONSTRAINT `owner_portal_visit_room_id_fk` FOREIGN KEY (`room_id`) REFERENCES `owner_portal_room` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 7. OWNER SUBSCRIPTIONS (Screen 11)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `owner_portal_subscription` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `plan_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `valid_until` date DEFAULT NULL,
  `monthly_price` decimal(10,2) NOT NULL DEFAULT 0.00,
  `featured_listings_count` int unsigned NOT NULL DEFAULT 0,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `owner_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `owner_subscription_owner_id_uniq` (`owner_id`),
  CONSTRAINT `owner_portal_sub_owner_fk` FOREIGN KEY (`owner_id`) REFERENCES `accounts_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 8. INVOICES & BILLING HISTORY (Screen 11)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `owner_portal_invoice` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `invoice_number` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `plan_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `gst_amount` decimal(10,2) NOT NULL DEFAULT 0.00,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PAID',
  `billing_date` date NOT NULL,
  `invoice_pdf_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `owner_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `invoice_number_uniq` (`invoice_number`),
  KEY `owner_portal_invoice_owner_id_idx` (`owner_id`),
  CONSTRAINT `owner_portal_inv_owner_fk` FOREIGN KEY (`owner_id`) REFERENCES `accounts_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 9. DRAFT LISTINGS (Part 2: 15-Step Wizard Autosave)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `owner_portal_draftlisting` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `current_step` int unsigned NOT NULL DEFAULT 1,
  `title` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `property_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `form_data` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_submitted` tinyint(1) NOT NULL DEFAULT 0,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `owner_id` bigint NOT NULL,
  `submitted_property_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `owner_portal_draft_owner_idx` (`owner_id`),
  KEY `owner_portal_draft_prop_idx` (`submitted_property_id`),
  CONSTRAINT `owner_portal_draft_prop_fk` FOREIGN KEY (`submitted_property_id`) REFERENCES `admin_portal_property` (`id`) ON DELETE SET NULL,
  CONSTRAINT `owner_portal_draft_owner_fk` FOREIGN KEY (`owner_id`) REFERENCES `accounts_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;

-- ==============================================================
-- 10. REALISTIC PRODUCTION SEED DATA
-- ==============================================================

-- 10.1 Ensure Arjun Mehta Owner exists
INSERT INTO `accounts_user` (
  `password`, `is_superuser`, `username`, `first_name`, `last_name`,
  `email`, `is_staff`, `is_active`, `date_joined`, `phone_number`, `role`,
  `admin_sub_role`, `is_verified_owner`, `created_at`, `updated_at`
) VALUES (
  'pbkdf2_sha256$870000$dummy$placeholder', 0, 'arjun_mehta', 'Arjun', 'Mehta',
  'arjun.mehta@aangan.in', 0, 1, NOW(), '+91 99887 76655', 'OWNER',
  NULL, 1, NOW(), NOW()
) ON DUPLICATE KEY UPDATE 
  `first_name` = 'Arjun',
  `last_name` = 'Mehta',
  `email` = 'arjun.mehta@aangan.in',
  `is_verified_owner` = 1;

-- 10.2 Ensure City & Localities exist
INSERT INTO `admin_portal_city` (`name`, `state`, `tier`, `is_active`, `created_at`)
VALUES ('Bengaluru', 'Karnataka', 'TIER_1', 1, NOW())
ON DUPLICATE KEY UPDATE `state` = 'Karnataka';

-- 10.3 Insert Properties for Arjun Mehta
INSERT INTO `admin_portal_property` (
  `owner_id`, `title`, `property_type`, `gender_category`,
  `address_line`, `city_id`, `locality_id`, `pincode`, `total_rooms`,
  `status`, `electricity_bill_url`, `created_at`, `updated_at`
)
SELECT u.id, 'The Courtyard House', 'CO_LIVING', 'CO_ED', '4th Cross, 5th Block, Koramangala', c.id, 1, '560034', 12, 'APPROVED', 'https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=600', NOW(), NOW()
FROM `accounts_user` u, `admin_portal_city` c
WHERE u.username = 'arjun_mehta' AND c.name = 'Bengaluru'
AND NOT EXISTS (SELECT 1 FROM `admin_portal_property` WHERE title = 'The Courtyard House' AND owner_id = u.id);

INSERT INTO `admin_portal_property` (
  `owner_id`, `title`, `property_type`, `gender_category`,
  `address_line`, `city_id`, `locality_id`, `pincode`, `total_rooms`,
  `status`, `electricity_bill_url`, `created_at`, `updated_at`
)
SELECT u.id, 'Olive Living', 'PG', 'CO_ED', '12th Main, HAL 2nd Stage, Indiranagar', c.id, 2, '560038', 10, 'APPROVED', 'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600', NOW(), NOW()
FROM `accounts_user` u, `admin_portal_city` c
WHERE u.username = 'arjun_mehta' AND c.name = 'Bengaluru'
AND NOT EXISTS (SELECT 1 FROM `admin_portal_property` WHERE title = 'Olive Living' AND owner_id = u.id);

INSERT INTO `admin_portal_property` (
  `owner_id`, `title`, `property_type`, `gender_category`,
  `address_line`, `city_id`, `locality_id`, `pincode`, `total_rooms`,
  `status`, `electricity_bill_url`, `created_at`, `updated_at`
)
SELECT u.id, 'The Fern Residency', 'HOSTEL', 'CO_ED', 'Sector 3, 27th Main, HSR Layout', c.id, 3, '560102', 6, 'PENDING', 'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600', NOW(), NOW()
FROM `accounts_user` u, `admin_portal_city` c
WHERE u.username = 'arjun_mehta' AND c.name = 'Bengaluru'
AND NOT EXISTS (SELECT 1 FROM `admin_portal_property` WHERE title = 'The Fern Residency' AND owner_id = u.id);

-- 10.4 Insert Rooms
INSERT INTO `owner_portal_room` (
  `property_id`, `room_number`, `room_type`, `max_occupancy`,
  `total_beds`, `occupied_beds`, `available_beds`, `monthly_rent`, `security_deposit`,
  `bathroom_type`, `ac_type`, `furnishing`, `amenities`, `cover_photo`, `is_active`,
  `created_at`, `updated_at`
)
SELECT p.id, '101', 'DOUBLE', 2, 2, 2, 0, 14500.00, 29000.00, 'ATTACHED', 'AC', 'Fully Furnished', 'WiFi, AC, Geyser, Wardrobe, Study Table', 'https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=600', 1, NOW(), NOW()
FROM `admin_portal_property` p WHERE p.title = 'The Courtyard House'
AND NOT EXISTS (SELECT 1 FROM `owner_portal_room` r WHERE r.property_id = p.id AND r.room_number = '101');

INSERT INTO `owner_portal_room` (
  `property_id`, `room_number`, `room_type`, `max_occupancy`,
  `total_beds`, `occupied_beds`, `available_beds`, `monthly_rent`, `security_deposit`,
  `bathroom_type`, `ac_type`, `furnishing`, `amenities`, `cover_photo`, `is_active`,
  `created_at`, `updated_at`
)
SELECT p.id, '102', 'DOUBLE', 2, 2, 1, 1, 14500.00, 29000.00, 'ATTACHED', 'AC', 'Fully Furnished', 'WiFi, AC, Geyser, Wardrobe', 'https://images.unsplash.com/photo-1595526114035-0d45ed16cfbf?w=600', 1, NOW(), NOW()
FROM `admin_portal_property` p WHERE p.title = 'The Courtyard House'
AND NOT EXISTS (SELECT 1 FROM `owner_portal_room` r WHERE r.property_id = p.id AND r.room_number = '102');

INSERT INTO `owner_portal_room` (
  `property_id`, `room_number`, `room_type`, `max_occupancy`,
  `total_beds`, `occupied_beds`, `available_beds`, `monthly_rent`, `security_deposit`,
  `bathroom_type`, `ac_type`, `furnishing`, `amenities`, `cover_photo`, `is_active`,
  `created_at`, `updated_at`
)
SELECT p.id, '201', 'SINGLE', 1, 1, 0, 1, 16000.00, 32000.00, 'ATTACHED', 'AC', 'Fully Furnished', 'WiFi, AC, TV, Geyser, Work Desk', 'https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=600', 1, NOW(), NOW()
FROM `admin_portal_property` p WHERE p.title = 'Olive Living'
AND NOT EXISTS (SELECT 1 FROM `owner_portal_room` r WHERE r.property_id = p.id AND r.room_number = '201');

-- 10.5 Insert Individual Beds
INSERT INTO `owner_portal_bed` (
  `room_id`, `bed_number`, `bed_position`, `status`,
  `tenant_name`, `occupied_since`, `monthly_rent`, `created_at`, `updated_at`
)
SELECT r.id, 'Bed A', 'Window Side', 'OCCUPIED', 'Rohan Kapoor', '2026-11-01', 14500.00, NOW(), NOW()
FROM `owner_portal_room` r JOIN `admin_portal_property` p ON r.property_id = p.id
WHERE p.title = 'The Courtyard House' AND r.room_number = '101'
AND NOT EXISTS (SELECT 1 FROM `owner_portal_bed` b WHERE b.room_id = r.id AND b.bed_number = 'Bed A');

INSERT INTO `owner_portal_bed` (
  `room_id`, `bed_number`, `bed_position`, `status`,
  `tenant_name`, `occupied_since`, `monthly_rent`, `created_at`, `updated_at`
)
SELECT r.id, 'Bed B', 'Door Side', 'OCCUPIED', 'Karthik V.', '2026-10-15', 14500.00, NOW(), NOW()
FROM `owner_portal_room` r JOIN `admin_portal_property` p ON r.property_id = p.id
WHERE p.title = 'The Courtyard House' AND r.room_number = '101'
AND NOT EXISTS (SELECT 1 FROM `owner_portal_bed` b WHERE b.room_id = r.id AND b.bed_number = 'Bed B');

INSERT INTO `owner_portal_bed` (
  `room_id`, `bed_number`, `bed_position`, `status`,
  `tenant_name`, `occupied_since`, `monthly_rent`, `created_at`, `updated_at`
)
SELECT r.id, 'Bed A', 'Window Side', 'OCCUPIED', 'Ankit S.', '2026-10-20', 14500.00, NOW(), NOW()
FROM `owner_portal_room` r JOIN `admin_portal_property` p ON r.property_id = p.id
WHERE p.title = 'The Courtyard House' AND r.room_number = '102'
AND NOT EXISTS (SELECT 1 FROM `owner_portal_bed` b WHERE b.room_id = r.id AND b.bed_number = 'Bed A');

INSERT INTO `owner_portal_bed` (
  `room_id`, `bed_number`, `bed_position`, `status`,
  `tenant_name`, `occupied_since`, `monthly_rent`, `created_at`, `updated_at`
)
SELECT r.id, 'Bed B', 'Door Side', 'AVAILABLE', NULL, NULL, 14500.00, NOW(), NOW()
FROM `owner_portal_room` r JOIN `admin_portal_property` p ON r.property_id = p.id
WHERE p.title = 'The Courtyard House' AND r.room_number = '102'
AND NOT EXISTS (SELECT 1 FROM `owner_portal_bed` b WHERE b.room_id = r.id AND b.bed_number = 'Bed B');

-- 10.6 Insert Seeker Enquiries
INSERT INTO `owner_portal_enquiry` (
  `property_id`, `room_id`, `seeker_name`, `seeker_phone`,
  `seeker_email`, `interested_room_type`, `budget`, `preferred_move_in`,
  `message`, `status`, `created_at`, `updated_at`
)
SELECT p.id, r.id, 'Ananya Sharma', '+91 98201 23456', 'ananya.sharma@example.com', 'Single occupancy', 16000.00, '2026-11-11', 'Looking for a quiet room with strong WiFi near Koramangala 5th block.', 'NEW', NOW(), NOW()
FROM `admin_portal_property` p
LEFT JOIN `owner_portal_room` r ON r.property_id = p.id AND r.room_number = '101'
WHERE p.title = 'The Courtyard House'
AND NOT EXISTS (SELECT 1 FROM `owner_portal_enquiry` e WHERE e.property_id = p.id AND e.seeker_name = 'Ananya Sharma');

INSERT INTO `owner_portal_enquiry` (
  `property_id`, `room_id`, `seeker_name`, `seeker_phone`,
  `seeker_email`, `interested_room_type`, `budget`, `preferred_move_in`,
  `message`, `status`, `created_at`, `updated_at`
)
SELECT p.id, r.id, 'Karthik Rao', '+91 98112 34567', 'karthik.rao@example.com', 'Twin sharing', 12000.00, '2026-11-14', 'Working at Embassy Golf Links, needed twin sharing room with food.', 'NEW', NOW(), NOW()
FROM `admin_portal_property` p
LEFT JOIN `owner_portal_room` r ON r.property_id = p.id AND r.room_number = '201'
WHERE p.title = 'Olive Living'
AND NOT EXISTS (SELECT 1 FROM `owner_portal_enquiry` e WHERE e.property_id = p.id AND e.seeker_name = 'Karthik Rao');

-- 10.7 Insert Visit Requests
INSERT INTO `owner_portal_visitrequest` (
  `request_id`, `property_id`, `room_id`, `seeker_name`,
  `seeker_phone`, `seeker_email`, `request_type`, `scheduled_date`,
  `scheduled_time_slot`, `status`, `notes`, `owner_reply`, `created_at`, `updated_at`
)
SELECT 'VIS-2026-071', p.id, r.id, 'Rohan Kapoor', '+91 99334 55667', 'rohan.kapoor@example.com', 'VISIT', '2026-11-07', 'Tomorrow · 11:00 AM', 'ACCEPTED', 'Requested a quick walkthrough of the terrace and gym.', 'Looking forward to meeting you Rohan!', NOW(), NOW()
FROM `admin_portal_property` p
LEFT JOIN `owner_portal_room` r ON r.property_id = p.id AND r.room_number = '101'
WHERE p.title = 'The Courtyard House'
ON DUPLICATE KEY UPDATE `status` = 'ACCEPTED';

INSERT INTO `owner_portal_visitrequest` (
  `request_id`, `property_id`, `room_id`, `seeker_name`,
  `seeker_phone`, `seeker_email`, `request_type`, `scheduled_date`,
  `scheduled_time_slot`, `status`, `notes`, `owner_reply`, `created_at`, `updated_at`
)
SELECT 'VIS-2026-082', p.id, r.id, 'Ishita Shah', '+91 97445 66778', 'ishita.shah@example.com', 'VISIT', '2026-11-08', 'Sunday · 2:30 PM', 'ACCEPTED', 'Will be accompanied by her brother for verification.', 'Confirmed slot for Sunday afternoon.', NOW(), NOW()
FROM `admin_portal_property` p
LEFT JOIN `owner_portal_room` r ON r.property_id = p.id AND r.room_number = '201'
WHERE p.title = 'Olive Living'
ON DUPLICATE KEY UPDATE `status` = 'ACCEPTED';

-- 10.8 Insert Subscription & Invoices
INSERT INTO `owner_portal_subscription` (
  `owner_id`, `plan_name`, `is_active`, `valid_until`, `monthly_price`, `featured_listings_count`, `created_at`, `updated_at`
)
SELECT u.id, 'Aangan Standard', 1, '2027-05-15', 0.00, 1, NOW(), NOW()
FROM `accounts_user` u WHERE u.username = 'arjun_mehta'
ON DUPLICATE KEY UPDATE `plan_name` = 'Aangan Standard';

INSERT INTO `owner_portal_invoice` (
  `owner_id`, `invoice_number`, `plan_name`, `amount`, `gst_amount`, `status`, `billing_date`, `invoice_pdf_url`, `created_at`
)
SELECT u.id, 'INV-2026-089', 'Owner Verification & Onboarding', 0.00, 0.00, 'PAID', '2026-10-15', '/media/invoices/INV-2026-089.pdf', NOW()
FROM `accounts_user` u WHERE u.username = 'arjun_mehta'
ON DUPLICATE KEY UPDATE `amount` = 0.00;

-- 10.9 Insert Gallery Photos
INSERT INTO `owner_portal_propertyphoto` (
  `property_id`, `photo_url`, `photo_type`, `caption`, `is_cover`, `sort_order`, `created_at`
)
SELECT p.id, 'https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=800', 'COVER', 'Courtyard House Exterior & Entrance', 1, 1, NOW()
FROM `admin_portal_property` p WHERE p.title = 'The Courtyard House'
AND NOT EXISTS (SELECT 1 FROM `owner_portal_propertyphoto` ph WHERE ph.property_id = p.id AND ph.photo_type = 'COVER');
