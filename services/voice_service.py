"""
Voice Call Service — Twilio Trial Account
Trial: can only call verified numbers. Uses TTS (no hosted TwiML needed).
"""
import os
import time
import logging
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Say, Pause, Gather
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
    raw = os.getenv("VERIFIED_TEST_NUMBERS", "")
    return [normalize_phone(n) for n in raw.split(",") if n.strip()]


def build_twiml(contact: dict) -> str:
    """Generate TTS voice script for the contact."""
    name    = contact.get("name", "Student")
    course  = contact.get("course", "your chosen program")
    college = os.getenv("COLLEGE_NAME", "Our College")
    website = os.getenv("COLLEGE_WEBSITE", "yourcollege.edu.in")

    response = VoiceResponse()

    response.say(
        f"Hello, {name}. This is a message from {college}.",
        voice="Polly.Aditi",
        language="en-IN",
    )
    response.pause(length=1)
    response.say(
        f"We are pleased to inform you that admissions for {course} "
        f"are now open. Seats are limited.",
        voice="Polly.Aditi",
        language="en-IN",
    )
    response.pause(length=1)

    gather = Gather(num_digits=1, timeout=5)
    gather.say(
        "Press 1 to know more about the program. Press 9 to opt out of future calls.",
        voice="Polly.Aditi",
        language="en-IN",
    )
    response.append(gather)

    response.say(
        f"Please visit {website} to apply online. Thank you and have a great day. Goodbye!",
        voice="Polly.Aditi",
        language="en-IN",
    )
    response.hangup()
    return str(response)


def make_voice_calls(contacts: list[dict], delay_seconds: float = 3.0) -> list[dict]:
    """
    Make outbound voice calls to contacts.
    On trial, only calls verified numbers.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("TWILIO_FROM_NUMBER", "")

    if not all([account_sid, auth_token, from_number]):
        raise ValueError("Twilio credentials missing in .env")

    client   = Client(account_sid, auth_token)
    verified = get_verified_numbers()
    results  = []

    for i, contact in enumerate(contacts, 1):
        phone = normalize_phone(contact.get("phone", ""))
        name  = contact.get("name", "Contact")

        if not phone:
            results.append({"contact": name, "channel": "voice",
                            "status": "skipped", "reason": "no phone"})
            continue

        if verified and phone not in verified:
            results.append({
                "contact": name, "phone": phone, "channel": "voice",
                "status": "skipped",
                "reason": "Trial: number not in VERIFIED_TEST_NUMBERS",
            })
            logger.warning(f"Voice skipped (unverified): {phone}")
            continue

        twiml = build_twiml(contact)
        try:
            call = client.calls.create(
                twiml=twiml,
                to=phone,
                from_=from_number,
                machine_detection="DetectMessageEnd",
            )
            results.append({
                "contact": name, "phone": phone, "channel": "voice",
                "status": "dialed", "call_sid": call.sid,
            })
            logger.info(f"[{i}/{len(contacts)}] Call dialed → {phone} | SID: {call.sid}")
        except TwilioRestException as e:
            results.append({"contact": name, "phone": phone, "channel": "voice",
                            "status": "error", "reason": str(e)})
            logger.error(f"Voice error for {phone}: {e}")

        time.sleep(delay_seconds)   # longer delay for voice — calls take time

    return results
