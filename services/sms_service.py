"""
SMS Service — Twilio Trial Account
IMPORTANT: Trial accounts can only send to verified numbers.
Add numbers at: https://console.twilio.com/us1/develop/phone-numbers/manage/verified
"""
import os
import time
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)


def normalize_phone(phone: str) -> str:
    """Strip non-digits and ensure country code with plus sign."""
    digits = "".join(c for c in phone if c.isdigit())
    if not digits.startswith("91") and len(digits) == 10:
        digits = "91" + digits
    if digits and not digits.startswith("+"):
        return "+" + digits
    return digits


def get_verified_numbers() -> list[str]:
    """Load the list of verified test numbers from .env"""
    raw = os.getenv("VERIFIED_TEST_NUMBERS", "")
    return [normalize_phone(n) for n in raw.split(",") if n.strip()]


def build_sms_message(contact: dict) -> str:
    college = os.getenv("COLLEGE_NAME", "Our College")
    website = os.getenv("COLLEGE_WEBSITE", "https://yourcollege.edu.in")
    year    = os.getenv("ADMISSION_YEAR", "2025-26")
    return (
        f"Dear {contact.get('name', 'Student')}, "
        f"Admissions for {contact.get('course', 'your program')} at {college} "
        f"are now OPEN for {year}! Limited seats. "
        f"Apply: {website} | Reply STOP to opt out."
    )


def send_sms(contacts: list[dict], delay_seconds: float = 1.0) -> list[dict]:
    """
    Send SMS to contacts. On trial accounts, skips numbers not in verified list.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("TWILIO_FROM_NUMBER", "")

    if not all([account_sid, auth_token, from_number]):
        raise ValueError("TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER must be set")

    client = Client(account_sid, auth_token)
    verified = get_verified_numbers()
    results  = []

    for i, contact in enumerate(contacts, 1):
        phone = normalize_phone(contact.get("phone", ""))
        name  = contact.get("name", "Contact")

        if not phone:
            results.append({"contact": name, "channel": "sms",
                            "status": "skipped", "reason": "no phone"})
            continue

        # Trial account restriction
        if verified and phone not in verified:
            results.append({
                "contact": name, "phone": phone, "channel": "sms",
                "status": "skipped",
                "reason": f"Trial: {phone} not in VERIFIED_TEST_NUMBERS",
            })
            logger.warning(f"SMS skipped (unverified): {phone}")
            continue

        body = build_sms_message(contact)
        try:
            message = client.messages.create(
                body=body,
                from_=from_number,
                to=phone,
            )
            results.append({
                "contact": name, "phone": phone, "channel": "sms",
                "status": "sent", "message_sid": message.sid,
            })
            logger.info(f"[{i}/{len(contacts)}] SMS sent → {phone} | SID: {message.sid}")
        except TwilioRestException as e:
            results.append({"contact": name, "phone": phone, "channel": "sms",
                            "status": "error", "reason": str(e)})
            logger.error(f"SMS error for {phone}: {e}")

        time.sleep(delay_seconds)

    return results
