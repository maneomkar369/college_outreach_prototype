"""
Email Service — EmailJS Free Tier (200 emails/month)
"""
import os
import time
import logging
import httpx
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

_template_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent.parent / "templates")
)


def render_email(contact: dict) -> tuple[str, str]:
    """Render subject and HTML body for a contact."""
    tmpl = _template_env.get_template("email_template.html")

    ctx = {
        "name":          contact.get("name", "Student"),
        "email":         contact.get("email", ""),
        "course":        contact.get("course", "your chosen program"),
        "city":          contact.get("city", "your city"),
        "college_name":  os.getenv("COLLEGE_NAME", "Our College"),
        "college_phone": os.getenv("COLLEGE_PHONE", "+91-XXXXXXXXXX"),
        "college_website": os.getenv("COLLEGE_WEBSITE", "https://yourcollege.edu.in"),
        "admission_year": os.getenv("ADMISSION_YEAR", "2025-26"),
    }
    subject = f"Admissions Open for {contact.get('course', 'your program')} — {ctx['college_name']}"
    return subject, tmpl.render(**ctx)


def send_emails(contacts: list[dict], delay_seconds: float = 0.5) -> list[dict]:
    """
    Send personalized emails to all contacts using EmailJS.
    delay_seconds: pause between sends to respect rate limits.
    Returns list of result dicts.
    """
    service_id = os.getenv("EMAILJS_SERVICE_ID", "")
    template_id = os.getenv("EMAILJS_TEMPLATE_ID", "")
    public_key = os.getenv("EMAILJS_PUBLIC_KEY", "")
    private_key = os.getenv("EMAILJS_PRIVATE_KEY", "")
    from_name = os.getenv("EMAILJS_FROM_NAME", "College Admissions")
    reply_to = os.getenv("EMAILJS_REPLY_TO", "your-email@gmail.com")

    if not service_id or not template_id or not public_key:
        raise ValueError("EMAILJS_SERVICE_ID, EMAILJS_TEMPLATE_ID, and EMAILJS_PUBLIC_KEY must be set in .env")

    results = []

    for i, contact in enumerate(contacts, 1):
        email = contact.get("email", "").strip()
        if not email:
            results.append({"contact": contact.get("name", "Unknown"), "channel": "email",
                            "status": "skipped", "reason": "no email"})
            continue

        subject, html_body = render_email(contact)

        payload = {
            "service_id": service_id,
            "template_id": template_id,
            "user_id": public_key,
            "accessToken": private_key,
            "template_params": {
                "to_email": email,
                "to_name": contact.get("name", "Student"),
                "from_name": from_name,
                "reply_to": reply_to,
                "subject": subject,
                "message": html_body
            }
        }

        try:
            response = httpx.post(
                "https://api.emailjs.com/api/v1.0/email/send",
                json=payload,
                timeout=10.0
            )
            # EmailJS returns 'OK' and 200 on success
            status = "sent" if response.status_code == 200 else "failed"
            results.append({
                "contact": contact.get("name", "Unknown"),
                "email": email,
                "channel": "email",
                "status": status,
                "message_id": f"EmailJS_{response.status_code}",
                "http_status": response.status_code,
            })
            if status == "sent":
                logger.info(f"[{i}/{len(contacts)}] Email {status} → {email}")
            else:
                logger.error(f"[{i}/{len(contacts)}] Email {status} → {email}: {response.text}")
                results[-1]["reason"] = response.text
        except Exception as e:
            results.append({"contact": contact.get("name", "Unknown"), "email": email,
                            "channel": "email", "status": "error", "reason": str(e)})
            logger.error(f"Email error for {email}: {e}")

        time.sleep(delay_seconds)

    return results
