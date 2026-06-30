import imaplib
import email
import json
import os
import time
import re
import html
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════
IMAP_SERVER = "imap.gmail.com"
EMAIL_ACCOUNT = "mechvec@gmail.com"
PASSWORD = "uwig gkbr jtnv axfb"
DATA_FILE = "trading_alerts.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)


def extract_clean_json(text_content):
    """Extracts JSON and handles messy email formatting."""
    try:
        text = html.unescape(text_content)
        text = text.replace('“', '"').replace('”', '"').replace("'", '"')
        text = re.sub(r'<[^>]*>', '', text)

        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            parsed = json.loads(json_str)
            if "ticker" in parsed:
                return parsed
    except Exception:
        return None
    return None


def check_email_alerts():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, PASSWORD)
        mail.select("inbox")

        # 🎯 THE FIX: Now it ONLY looks for emails with "TV_JSON" in the subject
        status, messages = mail.search(None, '(UNSEEN SUBJECT "TV_JSON")')

        if status != "OK" or not messages[0]:
            mail.logout()
            return

        for num in messages[0].split():
            status, data = mail.fetch(num, '(RFC822)')
            if status != "OK":
                continue

            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            body_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type in ["text/plain", "text/html"]:
                        body_text += part.get_payload(decode=True).decode(errors='ignore')
            else:
                body_text = msg.get_payload(decode=True).decode(errors='ignore')

            alert_data = extract_clean_json(body_text)

            if alert_data:
                alert_data["time_received"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                with open(DATA_FILE, "r") as f:
                    current_alerts = json.load(f)

                current_alerts.insert(0, alert_data)

                with open(DATA_FILE, "w") as f:
                    json.dump(current_alerts, f, indent=4)

                print(f"✅ Success! Dashboard Updated: {alert_data['ticker']} ({alert_data['action']})")
            else:
                print("⚠️ Found a 'TV_JSON' email, but couldn't read the payload.")

            # Use a slightly different IMAP flag command to ensure Gmail accepts it
            mail.store(num, '+FLAGS', '\\Seen')
            mail.store(num, '+FLAGS', '\\Deleted')  # Optional: Moves it to trash so it NEVER loops

        mail.expunge()  # Cleans up the inbox
        mail.logout()
    except Exception as e:
        print(f"Connection error: {e}")


print("📡 Engine Active. Waiting for emails with 'TV_JSON' in the subject...")
while True:
    check_email_alerts()
    time.sleep(5)