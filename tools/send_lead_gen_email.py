"""Send lead gen offer email with AnyVision signature."""

import base64
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from googleapiclient.discovery import build
from google_auth import get_google_credentials

project_root = Path(__file__).parent.parent

# Read signature
sig_html = (project_root / "email-signature.html").read_text(encoding="utf-8")
start = sig_html.find("<!-- Signature Start -->")
end = sig_html.find("<!-- Signature End -->") + len("<!-- Signature End -->")
sig = sig_html[start:end]

body_html = """<p>Hi Ian,</p>

<p>Hope you're doing well.</p>

<p>I wanted to reach out because I think there's a real opportunity for your business to generate more qualified leads on autopilot.</p>

<p>At <strong>AnyVision Media</strong>, we build custom <strong>AI-powered lead generation workflows</strong> that do the heavy lifting for you. Here's what that looks like in practice:</p>

<ul style="color:#333;font-size:14px;line-height:1.8;">
  <li><strong>Automated prospecting</strong> &mdash; we scrape and qualify leads from Google Maps, LinkedIn, and industry directories based on your ideal customer profile</li>
  <li><strong>Smart outreach sequences</strong> &mdash; personalised email and WhatsApp campaigns that adapt based on engagement</li>
  <li><strong>CRM integration</strong> &mdash; every lead lands in your pipeline, scored and ready for your sales team</li>
  <li><strong>Real-time reporting</strong> &mdash; a live dashboard so you always know what's working</li>
</ul>

<p>We've helped businesses across South Africa consistently fill their pipeline without hiring extra sales reps or spending hours on manual outreach.</p>

<p>Would you be open to a quick 15-minute call this week to see if this could work for you? No pressure at all &mdash; happy to walk you through a live demo of how it works.</p>

<p>Looking forward to hearing from you.</p>

<p>Warm regards,</p>"""

full_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif;font-size:14px;line-height:1.6;color:#333;">
{body_html}
<br>
{sig}
</body>
</html>"""

text_body = """Hi Ian,

Hope you're doing well.

I wanted to reach out because I think there's a real opportunity for your business to generate more qualified leads on autopilot.

At AnyVision Media, we build custom AI-powered lead generation workflows that do the heavy lifting for you:

- Automated prospecting - we scrape and qualify leads from Google Maps, LinkedIn, and industry directories based on your ideal customer profile
- Smart outreach sequences - personalised email and WhatsApp campaigns that adapt based on engagement
- CRM integration - every lead lands in your pipeline, scored and ready for your sales team
- Real-time reporting - a live dashboard so you always know what's working

We've helped businesses across South Africa consistently fill their pipeline without hiring extra sales reps or spending hours on manual outreach.

Would you be open to a quick 15-minute call this week to see if this could work for you? No pressure at all - happy to walk you through a live demo of how it works.

Looking forward to hearing from you.

Warm regards,
Ian
Founder - AnyVision Media
ian@anyvisionmedia.com
www.anyvisionmedia.com
"""

msg = MIMEMultipart("alternative")
msg["To"] = "ianimmelman89@gmail.com"
msg["Subject"] = "Automate Your Lead Generation with AI"
msg.attach(MIMEText(text_body, "plain"))
msg.attach(MIMEText(full_html, "html"))

raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

print("Authenticating...")
creds = get_google_credentials()
gmail = build("gmail", "v1", credentials=creds)

print("Sending email to ianimmelman89@gmail.com...")
result = gmail.users().messages().send(userId="me", body={"raw": raw}).execute()
print(f"Sent! Message ID: {result['id']}")
