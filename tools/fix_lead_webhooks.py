"""Fix lead capture webhook workflows - correct Code node JS and Airtable mapping."""
import os, json, httpx, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / '.env')

base_url = os.environ['N8N_BASE_URL'].rstrip('/')
api_key = os.environ['N8N_API_KEY']
headers = {'X-N8N-API-KEY': api_key, 'Content-Type': 'application/json'}

CONTACT_JS = r"""
const raw = $input.first().json;
const d = raw.body || raw;
const now = new Date().toISOString();
const id = 'WEB-' + Math.random().toString(36).substring(2,10).toUpperCase();
const sourceMap = {'google':'Paid','meta':'Paid','facebook':'Paid','tiktok':'Paid','linkedin':'Social_LinkedIn','twitter':'Social_Twitter','instagram':'Social_IG'};
const utmSrc = (d.utm_source || '').toLowerCase();
const sourceChannel = sourceMap[utmSrc] || (utmSrc === 'organic' ? 'Organic' : 'Direct');
return [{json: {
  'Lead ID': id,
  'Contact Name': ((d.firstName||'') + ' ' + (d.lastName||'')).trim() || d.name || 'Unknown',
  'Email': d.email || '',
  'Phone': d.phone || '',
  'Company': d.company || '',
  'Source Channel': sourceChannel,
  'Source URL': d.page_url || '',
  'UTM Campaign': d.utm_campaign || '',
  'UTM Medium': d.utm_medium || '',
  'UTM Source': d.utm_source || '',
  'First Touch Content': d.interest || '',
  'Status': 'New',
  'Source System': 'SEO_Inbound',
  'Grade': 'Warm',
  'Notes': d.message || '',
  'Created At': now.split('T')[0],
}}];
"""

SEO_JS = r"""
const raw = $input.first().json;
const d = raw.body || raw;
const now = new Date().toISOString();
const id = 'SEO-' + Math.random().toString(36).substring(2,10).toUpperCase();
const sourceMap = {'google':'Paid','meta':'Paid','facebook':'Paid','tiktok':'Paid','linkedin':'Social_LinkedIn','twitter':'Social_Twitter','instagram':'Social_IG'};
const utmSrc = (d.utm_source || '').toLowerCase();
const sourceChannel = sourceMap[utmSrc] || (utmSrc === 'organic' ? 'Organic' : 'Direct');
return [{json: {
  'Lead ID': id,
  'Contact Name': d.name || 'Unknown',
  'Email': d.email || '',
  'Phone': d.phone || '',
  'Company': d.company || '',
  'Source Channel': sourceChannel,
  'Source URL': d.page_url || '',
  'UTM Campaign': d.utm_campaign || '',
  'UTM Medium': d.utm_medium || '',
  'UTM Source': d.utm_source || '',
  'Status': 'New',
  'Source System': 'SEO_Inbound',
  'Grade': 'Warm',
  'Notes': d.message || '',
  'Created At': now.split('T')[0],
}}];
"""

AIRTABLE_COLUMNS = {
    "mappingMode": "defineBelow",
    "value": {
        "Lead ID": '={{ $json["Lead ID"] }}',
        "Contact Name": '={{ $json["Contact Name"] }}',
        "Email": '={{ $json["Email"] }}',
        "Phone": '={{ $json["Phone"] }}',
        "Company": '={{ $json["Company"] }}',
        "Source Channel": '={{ $json["Source Channel"] }}',
        "Source URL": '={{ $json["Source URL"] }}',
        "UTM Campaign": '={{ $json["UTM Campaign"] }}',
        "UTM Medium": '={{ $json["UTM Medium"] }}',
        "UTM Source": '={{ $json["UTM Source"] }}',
        "First Touch Content": '={{ $json["First Touch Content"] }}',
        "Status": '={{ $json["Status"] }}',
        "Source System": '={{ $json["Source System"] }}',
        "Grade": '={{ $json["Grade"] }}',
        "Notes": '={{ $json["Notes"] }}',
        "Created At": '={{ $json["Created At"] }}',
    },
}

GMAIL_SUBJECT = '=NEW LEAD: {{ $json["Contact Name"] }} from {{ $json["Company"] }}'
GMAIL_HTML = '=<h2 style="color:#FF6D5A">New Lead!</h2><table border="1" cellpadding="8" style="border-collapse:collapse"><tr><td><b>Name</b></td><td>{{ $json["Contact Name"] }}</td></tr><tr><td><b>Email</b></td><td>{{ $json["Email"] }}</td></tr><tr><td><b>Company</b></td><td>{{ $json["Company"] }}</td></tr><tr><td><b>Notes</b></td><td>{{ $json["Notes"] }}</td></tr><tr><td><b>Source</b></td><td>{{ $json["UTM Source"] }} / {{ $json["UTM Medium"] }}</td></tr><tr><td><b>Page</b></td><td>{{ $json["Source URL"] }}</td></tr></table>'

workflows = [
    ("4MLgoxXNESR2PUHG", CONTACT_JS, "Contact Form"),
    ("7WdhKM5flilIEljF", SEO_JS, "SEO Lead Capture"),
]

for wf_id, code, label in workflows:
    r = httpx.get(f"{base_url}/api/v1/workflows/{wf_id}", headers=headers, timeout=15)
    wf = r.json()

    for n in wf["nodes"]:
        if n["name"] == "Format Lead Data":
            n["parameters"]["jsCode"] = code
        if n["type"] == "n8n-nodes-base.airtable":
            n["parameters"]["columns"] = AIRTABLE_COLUMNS
        if n["type"] == "n8n-nodes-base.gmail":
            n["parameters"]["subject"] = GMAIL_SUBJECT
            n["parameters"]["message"] = GMAIL_HTML

    r2 = httpx.put(
        f"{base_url}/api/v1/workflows/{wf_id}",
        headers=headers,
        json={"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"], "settings": wf.get("settings", {})},
        timeout=30,
    )
    print(f"{label}: update={r2.status_code}")

# Test
time.sleep(1)
r3 = httpx.post("https://ianimmelman89.app.n8n.cloud/webhook/website-contact-form", json={
    "email": "ian@anyvisionmedia.com", "firstName": "Webhook", "lastName": "Test",
    "company": "AVM Verify", "message": "Test - safe to delete", "interest": "strategy",
    "page_url": "https://www.anyvisionmedia.com", "utm_source": "test", "utm_medium": "test",
}, timeout=30)
print(f"\nWebhook test: {r3.status_code}")

time.sleep(4)

# Check execution
r4 = httpx.get(f"{base_url}/api/v1/executions", headers=headers,
               params={"workflowId": "4MLgoxXNESR2PUHG", "limit": 1}, timeout=15)
execs = r4.json().get("data", [])
if execs:
    print(f"Latest execution: {execs[0]['status']}")

# Check Airtable
token = os.environ["AIRTABLE_API_TOKEN"]
r5 = httpx.get("https://api.airtable.com/v0/apptjjBx34z9340tK/tblwOPTPY85Tcj7NJ",
               headers={"Authorization": f"Bearer {token}"}, params={"maxRecords": 5}, timeout=15)
records = r5.json().get("records", [])
print(f"Airtable Leads: {len(records)} records")
for rec in records:
    f = rec.get("fields", {})
    print(f'  {f.get("Contact Name","?")} | {f.get("Email","?")} | {f.get("Source Channel","?")}')
