"""
WhatsApp Service — Meta Cloud API (Primary) & PyWhatKit Fallback
Uses Meta Cloud API if tokens are found in .env, otherwise falls back to browser automation.
"""
import os
import time
import logging
import httpx

try:
    import pywhatkit
except Exception as e:
    pywhatkit = None
    print(f"Warning: Could not import pywhatkit ({e}).")

logger = logging.getLogger(__name__)


def get_verified_numbers() -> list[str]:
    raw = os.getenv("VERIFIED_TEST_NUMBERS", "")
    return [n.strip().replace("+", "") for n in raw.split(",") if n.strip()]


def normalize_phone(phone: str) -> str:
    """Strip non-digits and ensure country code with plus sign."""
    digits = "".join(c for c in phone if c.isdigit())
    if not digits.startswith("91") and len(digits) == 10:
        digits = "91" + digits
    if digits and not digits.startswith("+"):
        return "+" + digits
    return digits


def send_whatsapp_messages(contacts: list[dict], delay_seconds: float = 1.5) -> list[dict]:
    api_token = os.getenv("WHATSAPP_API_TOKEN", "").strip()
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    
    # Use Cloud API if we have credentials (even dummies) to avoid GUI automation issues
    use_cloud_api = bool(api_token and phone_id)

    if not use_cloud_api and pywhatkit is None:
        logger.error("No Cloud API credentials and pywhatkit is unavailable. WhatsApp disabled.")
        return [
            {"contact": c.get("name", "Unknown"), "phone": c.get("phone", ""), 
             "channel": "whatsapp", "status": "error", "reason": "No valid WhatsApp method available"} 
            for c in contacts
        ]

    verified = get_verified_numbers()
    results = []

    college_name = os.getenv("COLLEGE_NAME", "DIEMS")
    default_message = f"Hello from {college_name}! We are excited to share our latest admission updates."

    for i, contact in enumerate(contacts, 1):
        phone = normalize_phone(contact.get("phone", ""))
        name  = contact.get("name", "Contact")

        if not phone:
            results.append({"contact": name, "channel": "whatsapp",
                            "status": "skipped", "reason": "no phone"})
            continue

        # Check if number is in VERIFIED_TEST_NUMBERS to prevent spam
        check_phone = phone.replace("+", "")
        if verified and check_phone not in verified:
            results.append({
                "contact": name, "phone": phone, "channel": "whatsapp",
                "status": "skipped",
                "reason": "Test mode: number not in VERIFIED_TEST_NUMBERS",
            })
            logger.warning(f"WhatsApp skipped (unverified): {phone}")
            continue

        message_text = f"Hi {name},\n{default_message}"

        if use_cloud_api:
            try:
                logger.info(f"[{i}/{len(contacts)}] Cloud API: Sending message to {phone}...")
                url = f"https://graph.facebook.com/v17.0/{phone_id}/messages"
                headers = {
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": check_phone,
                    "type": "text",
                    "text": {"preview_url": False, "body": message_text}
                }
                resp = httpx.post(url, headers=headers, json=payload, timeout=10.0)
                
                if resp.status_code in (200, 201):
                    msg_id = resp.json().get("messages", [{}])[0].get("id", "api_sent")
                    results.append({"contact": name, "phone": phone, "channel": "whatsapp",
                                    "status": "sent", "message_id": msg_id})
                    logger.info(f"[{i}/{len(contacts)}] WhatsApp sent → {phone}")
                else:
                    results.append({"contact": name, "phone": phone, "channel": "whatsapp",
                                    "status": "error", "reason": f"HTTP {resp.status_code}: {resp.text}"})
                    logger.error(f"WhatsApp API Error for {phone}: {resp.text}")
            except Exception as e:
                results.append({"contact": name, "phone": phone, "channel": "whatsapp",
                                "status": "error", "reason": str(e)})
                logger.error(f"WhatsApp exception for {phone}: {e}")
                
        else:
            try:
                logger.info(f"[{i}/{len(contacts)}] PyWhatKit: Scheduling message to {phone}...")
                pywhatkit.sendwhatmsg_instantly(
                    phone_no=phone, 
                    message=message_text,
                    wait_time=15, 
                    tab_close=True, 
                    close_time=3
                )
                results.append({"contact": name, "phone": phone, "channel": "whatsapp",
                                "status": "sent", "message_id": "pywhatkit_sent"})
                logger.info(f"[{i}/{len(contacts)}] WhatsApp sent → {phone}")
            except Exception as e:
                results.append({"contact": name, "phone": phone, "channel": "whatsapp",
                                "status": "error", "reason": str(e)})
                logger.error(f"WhatsApp exception for {phone}: {e}")

        time.sleep(delay_seconds)

    return results
