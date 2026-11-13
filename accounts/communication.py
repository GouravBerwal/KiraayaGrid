import os
import re
import urllib.parse
import threading
import datetime
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


def clean_phone_number(phone):
    """Extracts 10-digit mobile number suitable for Indian telco & WhatsApp (+91)."""
    if not phone:
        return ''
    digits = ''.join(c for c in str(phone) if c.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    return digits


def generate_whatsapp_link(phone_number, text_content):
    """
    Generates a 1-click WhatsApp deep-link for instant desktop/mobile chat.
    E.g. https://api.whatsapp.com/send?phone=919876543210&text=...
    """
    clean_phone = clean_phone_number(phone_number)
    if not clean_phone or len(clean_phone) != 10:
        return None
    encoded_text = urllib.parse.quote(text_content.strip())
    return f"https://api.whatsapp.com/send?phone=91{clean_phone}&text={encoded_text}"


def send_email_async(to_email, recipient_name, subject, message_text, cta_url=None, cta_label=None, category='NOTIFICATION', details=None):
    """
    Asynchronously sends an Apple-grade branded HTML email to recipient's inbox.
    Non-blocking (executes in daemon thread so UI responds sub-100ms).
    """
    if not to_email or '@' not in to_email:
        return

    def _worker():
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        full_cta_url = cta_url
        if cta_url and not cta_url.startswith('http'):
            full_cta_url = f"{site_url.rstrip('/')}/{cta_url.lstrip('/')}"

        button_html = ""
        if full_cta_url and cta_label:
            button_html = f"""
            <div style="margin: 28px 0; text-align: center;">
              <a href="{full_cta_url}" style="display: inline-block; background: #0284C7; color: #FFFFFF; font-size: 14px; font-weight: 700; text-decoration: none; padding: 13px 28px; border-radius: 10px; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.35); letter-spacing: 0.2px;">
                {cta_label} &rarr;
              </a>
            </div>
            """

        details_html = ""
        if details and isinstance(details, dict):
            rows = "".join(f"<tr><td style='padding: 6px 12px; color: #64748B; font-size: 13px; font-weight: 600;'>{k}:</td><td style='padding: 6px 12px; color: #0F172A; font-size: 13px; font-weight: 700;'>{v}</td></tr>" for k, v in details.items())
            details_html = f"""
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 14px 16px; margin: 20px 0;">
              <table style="width: 100%; border-collapse: collapse;">{rows}</table>
            </div>
            """

        category_badges = {
            'CHAT': ('💬 Direct Message', '#ECFDF5', '#047857', '#A7F3D0'),
            'VISIT': ('🔑 Walkthrough Visit Update', '#EFF6FF', '#1D4ED8', '#BFDBFE'),
            'BOOKING': ('🎉 Tenancy & Booking Update', '#FDF2F8', '#BE185D', '#FBCFE8'),
            'ADMIN': ('📢 KiraayaGrid Official Notice', '#FFFBEB', '#B45309', '#FDE68A'),
            'KYC': ('🛡️ Verification Status', '#F0FDF4', '#15803D', '#BBF7D0'),
        }
        badge_text, bg_col, text_col, border_col = category_badges.get(category.upper(), ('🔔 KiraayaGrid Alert', '#F1F5F9', '#334155', '#CBD5E1'))
        formatted_message = message_text.replace('\n', '<br>')

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="margin: 0; padding: 24px; background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1E293B;">
  <div style="max-width: 560px; margin: 0 auto; background: #FFFFFF; border-radius: 16px; border: 1px solid #E2E8F0; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.06);">
    <!-- Header -->
    <div style="background: #0F172A; padding: 26px 32px; text-align: center;">
      <div style="font-size: 24px; font-weight: 800; color: #FFFFFF; letter-spacing: -0.5px;">
        Kiraaya<span style="color: #38BDF8;">Grid</span>
      </div>
      <div style="color: #94A3B8; font-size: 11.5px; margin-top: 4px; letter-spacing: 0.5px;">
        Direct Living · 100% Zero Brokerage
      </div>
    </div>

    <!-- Body -->
    <div style="padding: 32px 28px;">
      <div style="display: inline-block; background: {bg_col}; color: {text_col}; font-size: 11px; font-weight: 700; padding: 4px 12px; border-radius: 9999px; border: 1px solid {border_col}; margin-bottom: 18px; text-transform: uppercase; letter-spacing: 0.5px;">
        {badge_text}
      </div>
      <h2 style="font-size: 19px; font-weight: 700; color: #0F172A; margin: 0 0 10px 0;">Hello {recipient_name},</h2>
      <div style="font-size: 14.5px; line-height: 1.6; color: #334155; margin: 0 0 16px 0;">
        {formatted_message}
      </div>

      {details_html}

      {button_html}
    </div>

    <!-- Footer -->
    <div style="background: #F8FAFC; padding: 20px 28px; text-align: center; font-size: 12px; color: #94A3B8; border-top: 1px solid #E2E8F0; line-height: 1.6;">
      <strong>KiraayaGrid Platform Notifications</strong><br>
      Zero Brokerage · Direct Host Connection · Verified Spaces<br>
      Reply to this email or reach us at <a href="mailto:support.kiraayagrid@gmail.com" style="color: #0284C7; text-decoration: none;">support.kiraayagrid@gmail.com</a>
    </div>
  </div>
</body>
</html>
"""
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'KiraayaGrid <support.kiraayagrid@gmail.com>')
        try:
            send_mail(
                subject=subject,
                message=message_text,
                from_email=from_email,
                recipient_list=[to_email],
                html_message=html_content,
                fail_silently=False
            )
            print(f"[LIVE EMAIL SUCCESS] Sent '{subject}' to {to_email}")
        except Exception as e:
            print(f"[LIVE EMAIL ERROR] {e} -> Recipient: {to_email}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def send_whatsapp_async(phone_number, recipient_name, subject, message_text, cta_url=None):
    """
    Asynchronously formats and logs/dispatches WhatsApp message.
    Also handles Meta WhatsApp Cloud API if credentials are provided in settings/env.
    """
    clean_phone = clean_phone_number(phone_number)
    if not clean_phone or len(clean_phone) != 10:
        return

    def _worker():
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        full_cta_url = cta_url
        if cta_url and not cta_url.startswith('http'):
            full_cta_url = f"{site_url.rstrip('/')}/{cta_url.lstrip('/')}"

        wa_formatted = (
            f"🏡 *KiraayaGrid Alert*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Hello *{recipient_name}*,\n\n"
            f"📌 *{subject}*\n\n"
            f"{message_text}\n\n"
        )
        if full_cta_url:
            wa_formatted += f"🔗 *Open in Portal:* {full_cta_url}\n"
        wa_formatted += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"_100% Verified · Zero Brokerage_\n"
            f"KiraayaGrid Support: support.kiraayagrid@gmail.com"
        )

        # 1. Print formatted WhatsApp terminal dispatch log
        print(f"\n=======================================================\n[WHATSAPP DISPATCH] To +91 {clean_phone}:\n{wa_formatted}\n=======================================================\n")

        # 2. Meta WhatsApp Cloud API Integration (if configured)
        wa_token = getattr(settings, 'WHATSAPP_API_TOKEN', os.getenv('WHATSAPP_API_TOKEN', ''))
        wa_phone_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', os.getenv('WHATSAPP_PHONE_NUMBER_ID', ''))
        if wa_token and wa_phone_id:
            try:
                import requests
                api_url = f"https://graph.facebook.com/v19.0/{wa_phone_id}/messages"
                headers = {
                    "Authorization": f"Bearer {wa_token}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": f"91{clean_phone}",
                    "type": "text",
                    "text": {"preview_url": True, "body": wa_formatted}
                }
                resp = requests.post(api_url, json=payload, headers=headers, timeout=10)
                print(f"[WHATSAPP CLOUD API] Status {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"[WHATSAPP CLOUD API ERROR] {e}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def dispatch_omnichannel_notification(recipient=None, title="", message="", sender=None, category='NOTIFICATION', cta_url=None, cta_label=None, details=None, email_override=None, phone_override=None, name_override=None):
    """
    Single unified entrypoint for cross-channel notifications:
    1. In-App Notification (Database row)
    2. Real-time Gmail SMTP Email (support.kiraayagrid@gmail.com)
    3. WhatsApp Message / 1-Click WhatsApp Link
    """
    from admin_portal.models import Notification

    recipient_name = name_override or (recipient.get_full_name() or recipient.username if recipient else "Resident")
    recipient_email = email_override or (getattr(recipient, 'email', '') if recipient else '')
    recipient_phone = phone_override or (getattr(recipient, 'phone_number', '') or getattr(recipient, 'phone', '') if recipient else '')

    # 1. In-App Notification Record (if recipient is provided or broadcast)
    notif = None
    try:
        notif = Notification.objects.create(
            sender=sender,
            recipient=recipient,
            title=title,
            message=message,
            channel='OMNICHANNEL',
            button_label=cta_label or 'View Details',
            button_url=cta_url or '/',
            status='SENT'
        )
    except Exception as e:
        print(f"[NOTIFICATION DB ERROR] {e}")

    # 2. Real-Time Gmail Dispatch
    if recipient_email:
        send_email_async(
            to_email=recipient_email,
            recipient_name=recipient_name,
            subject=title,
            message_text=message,
            cta_url=cta_url,
            cta_label=cta_label,
            category=category,
            details=details
        )

    # 3. Real-Time WhatsApp Dispatch
    if recipient_phone:
        send_whatsapp_async(
            phone_number=recipient_phone,
            recipient_name=recipient_name,
            subject=title,
            message_text=message,
            cta_url=cta_url
        )

    # Return WhatsApp 1-click link so UI can also display a "Chat on WhatsApp" button if desired
    wa_link = generate_whatsapp_link(recipient_phone, f"Hi {recipient_name}, regarding KiraayaGrid: {title} - {message}")
    return {
        'notification_id': notif.id if notif else None,
        'email_sent': bool(recipient_email),
        'whatsapp_sent': bool(recipient_phone),
        'whatsapp_link': wa_link
    }
