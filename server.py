"""
OutreachOS — Flask API Server
Run: python server.py
Serves the dashboard at http://localhost:5000
"""

import os
import sys
import json
import csv
import io
import time
import queue
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv, set_key, dotenv_values

load_dotenv()

BASE_DIR   = Path(__file__).parent
DASHBOARD  = BASE_DIR / "dashboard"
DATA_DIR   = BASE_DIR / "data"
LOG_DIR    = BASE_DIR / "logs"
ENV_FILE   = BASE_DIR / ".env"
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

app = Flask(__name__, static_folder=str(DASHBOARD), static_url_path="")
CORS(app)

# ── In-memory state ────────────────────────────────────
contacts_store: list[dict] = []
results_store:  list[dict] = []
campaign_lock   = threading.Lock()
campaign_running = False

# ── Import services (graceful fallback) ────────────────
try:
    from services.email_service    import send_emails
    from services.sms_service      import send_sms
    from services.whatsapp_service import send_whatsapp_messages
    from services.voice_service    import make_voice_calls
    SERVICES_OK = True
except Exception as e:
    print(f"[WARN] Services not fully loaded: {e}")
    SERVICES_OK = False

# ── Serve Dashboard ────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(str(DASHBOARD), "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(str(DASHBOARD), path)

# ── Contacts ───────────────────────────────────────────
@app.route("/api/contacts", methods=["GET"])
def get_contacts():
    return jsonify({"contacts": contacts_store, "total": len(contacts_store)})


@app.route("/api/contacts", methods=["POST"])
def add_contact():
    data = request.json or {}
    contact = {
        "name":   data.get("name", "").strip(),
        "email":  data.get("email", "").strip(),
        "phone":  data.get("phone", "").strip(),
        "course": data.get("course", "").strip(),
        "city":   data.get("city", "").strip(),
    }
    if not contact["name"]:
        return jsonify({"error": "Name is required"}), 400
    contacts_store.append(contact)
    return jsonify({"success": True, "contact": contact, "total": len(contacts_store)})


@app.route("/api/contacts/<int:idx>", methods=["DELETE"])
def delete_contact(idx):
    if 0 <= idx < len(contacts_store):
        removed = contacts_store.pop(idx)
        return jsonify({"success": True, "removed": removed})
    return jsonify({"error": "Index out of range"}), 404


@app.route("/api/contacts/bulk-delete", methods=["POST"])
def bulk_delete():
    data = request.json or {}
    idxs = set(data.get("indices", []))
    global contacts_store
    contacts_store = [c for i, c in enumerate(contacts_store) if i not in idxs]
    return jsonify({"success": True, "remaining": len(contacts_store)})


@app.route("/api/contacts/upload", methods=["POST"])
def upload_csv():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["file"]
    if not f.filename.endswith(".csv"):
        return jsonify({"error": "Only CSV files accepted"}), 400
    text = f.read().decode("utf-8", errors="replace")
    rows = _parse_csv(text)
    contacts_store.clear()
    contacts_store.extend(rows)
    return jsonify({"success": True, "loaded": len(rows), "contacts": rows})


@app.route("/api/contacts/load-sample", methods=["POST"])
def load_sample_contacts():
    sample_path = DATA_DIR / "sample_contacts.csv"
    if not sample_path.exists():
        sample_path = BASE_DIR / "data" / "sample_contacts.csv"
    if not sample_path.exists():
        return jsonify({"error": "Sample contacts file not found at " + str(sample_path)}), 404
    try:
        with open(sample_path, encoding="utf-8") as f:
            text = f.read()
        rows = _parse_csv(text)
        contacts_store.clear()
        contacts_store.extend(rows)
        return jsonify({"success": True, "loaded": len(rows), "contacts": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/contacts/export", methods=["GET"])
def export_contacts():
    if not contacts_store:
        return jsonify({"error": "No contacts"}), 400
    keys = ["name", "email", "phone", "course", "city"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(contacts_store)
    csv_data = buf.getvalue()
    return Response(csv_data, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=contacts_export.csv"})


def _parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text.strip()))
    rows = []
    for row in reader:
        cleaned = {k.strip().lower().replace(" ", "_"): v.strip() for k, v in row.items()}
        rows.append({
            "name":   cleaned.get("name", ""),
            "email":  cleaned.get("email", ""),
            "phone":  cleaned.get("phone", ""),
            "course": cleaned.get("course", ""),
            "city":   cleaned.get("city", ""),
        })
    return [r for r in rows if any(r.values())]


# ── Settings ────────────────────────────────────────────
SETTING_KEYS = [
    "EMAILJS_SERVICE_ID", "EMAILJS_TEMPLATE_ID", "EMAILJS_PUBLIC_KEY",
    "EMAILJS_PRIVATE_KEY", "EMAILJS_FROM_NAME", "EMAILJS_REPLY_TO",
    "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER",
    "VERIFIED_TEST_NUMBERS", "WHATSAPP_API_TOKEN", "WHATSAPP_PHONE_NUMBER_ID",
    "COLLEGE_NAME", "COLLEGE_PHONE", "COLLEGE_WEBSITE", "ADMISSION_YEAR",
]


@app.route("/api/settings", methods=["GET"])
def get_settings():
    vals = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}
    data = {k: vals.get(k, os.getenv(k, "")) for k in SETTING_KEYS}
    # Mask secrets in response
    for secret_key in ["EMAILJS_PRIVATE_KEY", "EMAILJS_PUBLIC_KEY", "TWILIO_AUTH_TOKEN",
                        "WHATSAPP_API_TOKEN", "EMAILJS_SERVICE_ID"]:
        v = data.get(secret_key, "")
        if v:
            data[secret_key] = v[:4] + "••••••" + v[-2:] if len(v) > 6 else "••••••"
    return jsonify(data)


@app.route("/api/settings", methods=["POST"])
def save_settings():
    data = request.json or {}
    if not ENV_FILE.exists():
        ENV_FILE.touch()
    for key, value in data.items():
        if key in SETTING_KEYS and "••" not in str(value):  # don't overwrite masked values
            set_key(str(ENV_FILE), key, str(value))
    load_dotenv(override=True)
    return jsonify({"success": True, "message": "Settings saved to .env"})


@app.route("/api/settings/raw", methods=["POST"])
def save_settings_raw():
    """Save all settings including secrets (no masking check)."""
    data = request.json or {}
    if not ENV_FILE.exists():
        ENV_FILE.touch()
    for key, value in data.items():
        if key in SETTING_KEYS:
            set_key(str(ENV_FILE), key, str(value))
    load_dotenv(override=True)
    return jsonify({"success": True})


# ── Campaign ────────────────────────────────────────────
@app.route("/api/campaign/run", methods=["POST"])
def run_campaign():
    global campaign_running, results_store
    if campaign_running:
        return jsonify({"error": "Campaign already running"}), 409

    data    = request.json or {}
    channels = data.get("channels", ["email", "sms", "whatsapp", "voice"])
    limit    = data.get("limit")
    delay    = float(data.get("delay", 0.5))

    targets = contacts_store[:int(limit)] if limit else contacts_store[:]
    if not targets:
        return jsonify({"error": "No contacts loaded"}), 400

    results_store = []
    q: queue.Queue = queue.Queue()

    def worker():
        global campaign_running, results_store
        campaign_running = True
        all_results = []
        total = len(targets) * len(channels)
        done  = 0

        q.put({"type": "start", "total": total, "contacts": len(targets), "channels": channels})

        channel_fn_map = {
            "email":     send_emails,
            "sms":       send_sms,
            "whatsapp":  send_whatsapp_messages,
            "voice":     make_voice_calls,
        }

        for ch in channels:
            q.put({"type": "channel_start", "channel": ch})
            fn = channel_fn_map.get(ch)
            if not fn:
                done += len(targets)
                continue

            try:
                # Run one contact at a time and stream each result
                for contact in targets:
                    try:
                        batch_result = fn([contact], delay_seconds=delay)
                    except Exception as e:
                        batch_result = [{
                            "contact": contact.get("name", "?"),
                            "email": contact.get("email", ""),
                            "phone": contact.get("phone", ""),
                            "channel": ch,
                            "status": "error",
                            "reason": str(e)
                        }]
                    all_results.extend(batch_result)
                    done += 1
                    pct = round(done / total * 100)
                    q.put({"type": "progress", "done": done, "total": total, "pct": pct,
                           "result": batch_result[0] if batch_result else {}})
                    time.sleep(delay)
            except Exception as e:
                q.put({"type": "error", "message": str(e), "channel": ch})

        results_store = all_results
        # Save JSON log
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = LOG_DIR / f"results_campaign_{ts_str}.json"
        with open(log_path, "w") as f:
            json.dump(all_results, f, indent=2, default=str)

        sent    = sum(1 for r in all_results if r.get("status") in ("sent", "dialed"))
        skipped = sum(1 for r in all_results if r.get("status") == "skipped")
        failed  = sum(1 for r in all_results if r.get("status") == "error")
        q.put({"type": "done", "sent": sent, "skipped": skipped, "failed": failed,
               "total": len(all_results), "log_file": str(log_path)})
        campaign_running = False

    def event_stream():
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        while True:
            try:
                msg = q.get(timeout=120)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                yield "data: {\"type\":\"ping\"}\n\n"
                if not campaign_running:
                    break

    return Response(stream_with_context(event_stream()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/campaign/status", methods=["GET"])
def campaign_status():
    return jsonify({"running": campaign_running})


# ── Results ─────────────────────────────────────────────
@app.route("/api/results", methods=["GET"])
def get_results():
    return jsonify({"results": results_store, "total": len(results_store)})


@app.route("/api/results/export", methods=["GET"])
def export_results():
    if not results_store:
        return jsonify({"error": "No results"}), 400
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        json.dumps(results_store, indent=2, default=str),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename=results_{ts_str}.json"}
    )


@app.route("/api/logs", methods=["GET"])
def list_logs():
    logs = sorted(LOG_DIR.glob("results_campaign_*.json"), reverse=True)[:20]
    return jsonify([{"name": l.name, "size": l.stat().st_size,
                     "modified": datetime.fromtimestamp(l.stat().st_mtime).isoformat()} for l in logs])


@app.route("/api/logs/<name>", methods=["GET"])
def get_log(name):
    log_path = LOG_DIR / name
    if not log_path.exists():
        return jsonify({"error": "Not found"}), 404
    with open(log_path) as f:
        return jsonify(json.load(f))


# ── Health ──────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "services_loaded": SERVICES_OK,
        "contacts": len(contacts_store),
        "campaign_running": campaign_running,
        "env_exists": ENV_FILE.exists(),
        "college": os.getenv("COLLEGE_NAME", "Not set"),
    })


if __name__ == "__main__":
    print("\n🎓 OutreachOS API Server")
    print("   Dashboard → http://localhost:5000")
    print("   API Base  → http://localhost:5000/api\n")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
