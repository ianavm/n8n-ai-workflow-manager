"""Send an email with the AnyVision Media signature."""

import base64
import sys
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from googleapiclient.discovery import build
from google_auth import get_google_credentials

project_root = Path(__file__).parent.parent

# Read the signature HTML
signature_html = (project_root / "email-signature.html").read_text(encoding="utf-8")

# Extract just the signature table (between the comment markers)
start = signature_html.find("<!-- Signature Start -->")
end = signature_html.find("<!-- Signature End -->") + len("<!-- Signature End -->")
signature_block = signature_html[start:end]

# --- Email config ---
recipient = sys.argv[1] if len(sys.argv) > 1 else "ian@botar.co.za"
subject = sys.argv[2] if len(sys.argv) > 2 else "Email Signature Preview"
body_html = sys.argv[3] if len(sys.argv) > 3 else "<p>This is a test email.</p>"
body_text = sys.argv[4] if len(sys.argv) > 4 else "This is a test email."

# Build the full HTML email
html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif;font-size:14px;line-height:1.6;color:#333;">
{body_html}
<br>
{signature_block}
</body>
</html>"""

text_body = f"{body_text}\n\n--\nIan\nFounder - AnyVision Media\nian@anyvisionmedia.com\nwww.anyvisionmedia.com\n"

# Compose the message
message = MIMEMultipart("alternative")
message["To"] = recipient
message["Subject"] = subject
message.attach(MIMEText(text_body, "plain"))
message.attach(MIMEText(html_body, "html"))

raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

# Authenticate and send
print("Authenticating with Gmail API...")
creds = get_google_credentials()
gmail = build("gmail", "v1", credentials=creds)

print(f"Sending test email to {message['To']}...")
result = gmail.users().messages().send(userId="me", body={"raw": raw}).execute()
print(f"Sent! Message ID: {result['id']}")
