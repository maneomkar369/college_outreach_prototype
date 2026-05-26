"""
College Outreach Prototype — Main Runner
=========================================
Run: python main.py

Menu-driven CLI that lets you:
  1. Load contacts from CSV
  2. Run any channel (email / SMS / WhatsApp / voice)
  3. Run all channels
  4. View results report
"""
import os
import sys
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from colorama import init, Fore, Style
from tabulate import tabulate

load_dotenv()
init(autoreset=True)  # colorama

# ── Logging ───────────────────────────────────────────────────────────────────
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"campaign_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ── Import services ───────────────────────────────────────────────────────────
from services.email_service     import send_emails
from services.sms_service       import send_sms
from services.whatsapp_service  import send_whatsapp_messages
from services.voice_service     import make_voice_calls


# ─── Contact Loader ───────────────────────────────────────────────────────────

def load_contacts(csv_path: str) -> list[dict]:
    import pandas as pd
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    contacts = df.to_dict(orient="records")
    print(f"{Fore.GREEN}✓ Loaded {len(contacts)} contacts from {csv_path}")
    return contacts


# ─── Report ───────────────────────────────────────────────────────────────────

def print_results(results: list[dict], title: str):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}{Style.RESET_ALL}")

    if not results:
        print("  No results.")
        return

    # Summary counts
    counts = {}
    for r in results:
        s = r.get("status", "unknown")
        counts[s] = counts.get(s, 0) + 1

    for status, count in counts.items():
        color = Fore.GREEN if status in ("sent", "dialed") else \
                Fore.YELLOW if status == "skipped" else Fore.RED
        print(f"  {color}{status.upper()}: {count}{Style.RESET_ALL}")

    # Detail table
    rows = []
    for r in results:
        reason = str(r.get("reason") or r.get("message_id") or r.get("message_sid") or r.get("call_sid") or "")
        # Strip ANSI codes and newlines to prevent tabulate formatting issues
        reason = re.sub(r'\x1b\[[0-9;]*m', '', reason).replace('\n', ' ').replace('\r', '').strip()
        # Truncate reason if too long
        if len(reason) > 50:
            reason = reason[:47] + "..."
            
        rows.append([
            r.get("contact", ""),
            r.get("email") or r.get("phone", ""),
            r.get("channel", ""),
            r.get("status", ""),
            reason
        ])

    print()
    print(tabulate(rows, headers=["Name", "Email/Phone", "Channel", "Status", "ID/Note"],
                   tablefmt="rounded_outline", maxcolwidths=[20, 28, 10, 10, 50]))


def save_results(results: list[dict], campaign_name: str):
    report_dir = Path("logs")
    fname = report_dir / f"results_{campaign_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(fname, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n{Fore.BLUE}📄 Full results saved to: {fname}")


# ─── Menu ─────────────────────────────────────────────────────────────────────

def print_banner():
    print(f"""
{Fore.BLUE}{Style.BRIGHT}╔══════════════════════════════════════════════════════╗
║     College Outreach Automation — Prototype v1.0      ║
║              Free API Tier Edition                     ║
╚══════════════════════════════════════════════════════╝{Style.RESET_ALL}
""")


def print_free_tier_info():
    print(f"""
{Fore.YELLOW}⚠  Free Tier Limits:{Style.RESET_ALL}
  • Email (EmailJS)    — 200 emails/month, any valid email
  • SMS (Twilio Trial) — verified numbers only (VERIFIED_TEST_NUMBERS in .env)
  • WhatsApp (PyWhatKit)— unlimited, uses WhatsApp Web via browser
  • Voice (Twilio)     — verified numbers only
""")


def main():
    print_banner()
    print_free_tier_info()

    # Load contacts
    csv_path = input(
        f"{Fore.CYAN}Enter CSV path [{Fore.WHITE}data/sample_contacts.csv{Fore.CYAN}]: {Style.RESET_ALL}"
    ).strip() or "data/sample_contacts.csv"

    if not Path(csv_path).exists():
        print(f"{Fore.RED}✗ File not found: {csv_path}")
        sys.exit(1)

    contacts = load_contacts(csv_path)

    # Optional: limit contacts for testing
    limit_input = input(
        f"{Fore.CYAN}How many contacts to process? [{Fore.WHITE}all{Fore.CYAN}]: {Style.RESET_ALL}"
    ).strip()
    if limit_input.isdigit():
        contacts = contacts[:int(limit_input)]
        print(f"{Fore.YELLOW}  Limiting to {len(contacts)} contacts.")

    print(f"""
{Fore.WHITE}{Style.BRIGHT}Choose channel:{Style.RESET_ALL}
  1. Email only       (EmailJS — any email address)
  2. SMS only         (Twilio — verified numbers only)
  3. WhatsApp only    (PyWhatKit — via WhatsApp Web)
  4. Voice only       (Twilio — verified numbers only)
  5. All channels     (email to all; SMS/WA/Voice to verified only)
  6. Exit
""")
    choice = input(f"{Fore.CYAN}Enter choice [1-6]: {Style.RESET_ALL}").strip()

    all_results = []
    campaign_name = f"campaign_{choice}"

    try:
        if choice == "1":
            print(f"\n{Fore.GREEN}▶ Sending emails...")
            results = send_emails(contacts)
            print_results(results, "Email Results")
            all_results.extend(results)

        elif choice == "2":
            print(f"\n{Fore.GREEN}▶ Sending SMS...")
            results = send_sms(contacts)
            print_results(results, "SMS Results")
            all_results.extend(results)

        elif choice == "3":
            print(f"\n{Fore.GREEN}▶ Sending WhatsApp messages...")
            results = send_whatsapp_messages(contacts)
            print_results(results, "WhatsApp Results")
            all_results.extend(results)

        elif choice == "4":
            print(f"\n{Fore.GREEN}▶ Making voice calls...")
            results = make_voice_calls(contacts)
            print_results(results, "Voice Call Results")
            all_results.extend(results)

        elif choice == "5":
            print(f"\n{Fore.GREEN}▶ Running all channels...")
            for label, fn in [
                ("Email",     lambda: send_emails(contacts)),
                ("SMS",       lambda: send_sms(contacts)),
                ("WhatsApp",  lambda: send_whatsapp_messages(contacts)),
                ("Voice",     lambda: make_voice_calls(contacts)),
            ]:
                print(f"\n  {Fore.YELLOW}── {label} ──{Style.RESET_ALL}")
                results = fn()
                print_results(results, f"{label} Results")
                all_results.extend(results)

        elif choice == "6":
            print("Goodbye!")
            return

        else:
            print(f"{Fore.RED}Invalid choice.")
            return

    except ValueError as e:
        print(f"\n{Fore.RED}✗ Configuration error: {e}")
        print(f"{Fore.YELLOW}  Make sure your .env file has the required API keys.")
        return
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Campaign interrupted by user.")

    # Save JSON report
    if all_results:
        save_results(all_results, campaign_name)

    print(f"\n{Fore.GREEN}{Style.BRIGHT}✓ Done! Log file: {log_file}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
