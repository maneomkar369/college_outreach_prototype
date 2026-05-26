# College Outreach Prototype — Quick Start Guide

## Step 1 — Install dependencies
```bash
pip install -r requirements.txt
```

## Step 2 — Get your free API keys

### EmailJS (Email — 200/month free)
1. Sign up: https://www.emailjs.com/
2. Go to Account → API Keys to get Public and Private Keys
3. Create an Email Service and Template in the dashboard

### Twilio (SMS + Voice — $15.50 free trial credit)
1. Sign up: https://www.twilio.com/try-twilio
2. Get Account SID + Auth Token from: https://console.twilio.com
3. Your free number is shown on the console dashboard
4. **Verify test numbers** (trial only):
   Console → Phone Numbers → Manage → Verified Caller IDs → Add New

### WhatsApp (PyWhatKit — Free Browser Automation)
1. PyWhatKit uses WhatsApp Web to send messages for free.
2. Ensure you have Google Chrome (or default browser) installed and logged into WhatsApp Web.
3. No API tokens or Meta approval required.
4. Keep the browser open during the campaign.

## Step 3 — Configure .env
```bash
cp .env.example .env
# Edit .env and fill in your API keys
nano .env
```

## Step 4 — Add your contacts CSV
Edit `data/sample_contacts.csv` or point to your own file.
Required columns: `name`, `email` or `phone`
Optional columns: `course`, `city`

## Step 5 — Run
```bash
python main.py
```

---

## Free Tier Summary

| Channel   | Service       | Free Limit                    | Who Gets Messages        |
|-----------|---------------|-------------------------------|--------------------------|
| Email     | EmailJS       | 200 emails/month              | Any valid email address  |
| SMS       | Twilio Trial  | ~160 SMS from $15.50 credit   | Verified numbers only    |
| WhatsApp  | PyWhatKit     | Unlimited sends               | Any valid WhatsApp number|
| Voice     | Twilio Trial  | ~100 min from $15.50 credit   | Verified numbers only    |

## Upgrading to Production

| Service   | Upgrade Cost  | Removes Restriction           |
|-----------|---------------|-------------------------------|
| EmailJS   | $15.00/mo     | 10,000 emails/month           |
| Twilio    | Add $20 credit| Call/SMS any number           |
| WhatsApp  | Meta Official | Use Meta Cloud API for prod   |
| MSG91     | Pay-per-use   | Full DLT-compliant India SMS  |

---

## Output Files
- `logs/campaign_YYYYMMDD_HHMMSS.log` — Full execution log
- `logs/results_campaign_X_YYYYMMDD.json` — Delivery results JSON

