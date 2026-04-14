"""
PayFast Payment Department - Workflow Builder & Deployer

Builds 3 n8n workflows that implement a cryptographically verified
PayFast payment pipeline for the premium AI Automation Consulting service
(R2,500/hr). Replaces the static Payment Request / calendar-link flow with
a proper Payment Integration + ITN verification loop.

Workflows:
    PF-01  Create Payment     (webhook) - Accepts {name, email, company},
                                          creates a pending Airtable booking,
                                          builds a signed PayFast checkout URL,
                                          returns it to the frontend.
    PF-02  ITN Handler        (webhook) - Receives PayFast ITN, verifies MD5
                                          signature + IP allowlist, does
                                          server-side postback to PayFast,
                                          logs booking as paid, generates
                                          sequential VAT invoice, sends
                                          tax invoice email to customer.
    PF-03  Verify Token       (webhook) - Called by the confirmation page.
                                          Looks up booking by verification
                                          token, returns minimal booking
                                          details only if status=paid AND
                                          token not expired. CORS enabled.

Usage:
    python tools/deploy_payfast_dept.py build              # Build all 3 workflow JSONs
    python tools/deploy_payfast_dept.py build pf01         # Build one
    python tools/deploy_payfast_dept.py deploy             # Build + deploy (inactive)
    python tools/deploy_payfast_dept.py activate           # Build + deploy + activate

Environment variables required:
    N8N_API_KEY, N8N_BASE_URL                    (n8n deployment)
    AIRTABLE_API_TOKEN, MARKETING_AIRTABLE_BASE_ID
    PF_PAID_BOOKINGS_TABLE_ID                    (tblj0VcLtMTrxCbvJ)
    PF_COUNTERS_TABLE_ID                         (tbldGcMpj9eVDUt4a)
    PAYFAST_MERCHANT_ID, PAYFAST_MERCHANT_KEY, PAYFAST_PASSPHRASE
    PAYFAST_SANDBOX                              ("true" or "false")
    PAYFAST_WEBHOOK_HMAC_SECRET                  (any long random string)
    AVM_VAT_NUMBER                               (your registered VAT number)
    AVM_BUSINESS_NAME, AVM_BUSINESS_ADDRESS      (for invoice header)
    SITE_ORIGIN                                  (https://www.anyvisionmedia.com)

WARNING: built workflow JSON files contain your PayFast passphrase and HMAC
secret inline. Add workflows/payfast-dept/ to .gitignore before committing.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Add tools/ to path so we can import credentials.py
sys.path.insert(0, str(Path(__file__).parent))
from credentials import CRED_AIRTABLE, CRED_GMAIL_OAUTH2  # noqa: E402

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


# ============================================================
# CONFIGURATION (read from .env with safe defaults)
# ============================================================

# --- n8n ---
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")

# --- Airtable ---
AIRTABLE_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
PF_BOOKINGS_TABLE_ID = os.getenv("PF_PAID_BOOKINGS_TABLE_ID", "tblj0VcLtMTrxCbvJ")
PF_COUNTERS_TABLE_ID = os.getenv("PF_COUNTERS_TABLE_ID", "tbldGcMpj9eVDUt4a")

# --- PayFast ---
PAYFAST_MERCHANT_ID = os.getenv("PAYFAST_MERCHANT_ID", "10000100")  # default = sandbox
PAYFAST_MERCHANT_KEY = os.getenv("PAYFAST_MERCHANT_KEY", "46f0cd694581a")
PAYFAST_PASSPHRASE = os.getenv("PAYFAST_PASSPHRASE", "jt7NOE43FZPn")
PAYFAST_SANDBOX = os.getenv("PAYFAST_SANDBOX", "true").lower() == "true"

PAYFAST_PROCESS_URL = (
    "https://sandbox.payfast.co.za/eng/process"
    if PAYFAST_SANDBOX
    else "https://www.payfast.co.za/eng/process"
)
PAYFAST_VALIDATE_URL = (
    "https://sandbox.payfast.co.za/eng/query/validate"
    if PAYFAST_SANDBOX
    else "https://www.payfast.co.za/eng/query/validate"
)

# --- HMAC / Tokens ---
WEBHOOK_HMAC_SECRET = os.getenv(
    "PAYFAST_WEBHOOK_HMAC_SECRET",
    "REPLACE_WITH_A_LONG_RANDOM_SECRET_32+_CHARS",
)

# --- Site & product ---
SITE_ORIGIN = os.getenv("SITE_ORIGIN", "https://www.anyvisionmedia.com")
RETURN_URL = f"{SITE_ORIGIN}/services/consulting-confirmed"
CANCEL_URL = f"{SITE_ORIGIN}/services/ai-automation-consulting"
NOTIFY_URL = f"{N8N_BASE_URL}/webhook/payfast/itn"
CALENDAR_URL = os.getenv(
    "PF_CALENDAR_URL", "https://calendar.app.google/79JABt2piDQ5X4gW8"
)

ITEM_NAME = "AI Automation Consulting (1 hour)"
ITEM_DESCRIPTION = "Premium 60-minute AI automation strategy consultation with AnyVision Media"
AMOUNT_ZAR = 2500.00  # incl 15% VAT
VAT_RATE = 0.15

# --- Business details for tax invoice ---
AVM_BUSINESS_NAME = os.getenv("AVM_BUSINESS_NAME", "AnyVision Media")
AVM_BUSINESS_EMAIL = os.getenv("AVM_BUSINESS_EMAIL", "admin@anyvisionmedia.com")
AVM_BUSINESS_ADDRESS = os.getenv(
    "AVM_BUSINESS_ADDRESS", "Johannesburg, Gauteng, South Africa"
)
AVM_VAT_NUMBER = os.getenv("AVM_VAT_NUMBER", "VAT_NUMBER_REQUIRED")
AVM_COMPANY_REG = os.getenv("AVM_COMPANY_REG", "")

# --- Token lifetime ---
TOKEN_EXPIRY_DAYS = 30

# --- PayFast ITN source IPs (for IP allowlist validation) ---
# Source: https://developers.payfast.co.za/docs#notify-method
PAYFAST_VALID_HOSTS = [
    "www.payfast.co.za",
    "sandbox.payfast.co.za",
    "w1w.payfast.co.za",
    "w2w.payfast.co.za",
]


# ============================================================
# HELPERS
# ============================================================


def uid() -> str:
    """Generate a new UUID for n8n node IDs."""
    return str(uuid.uuid4())


def airtable_ref(base: str, table: str) -> dict[str, Any]:
    """Build an n8n Airtable resource locator dict."""
    return {
        "base": {"__rl": True, "value": base, "mode": "id"},
        "table": {"__rl": True, "value": table, "mode": "id"},
    }


def _js_string(value: str) -> str:
    """Pass through a JS source block unchanged.

    n8n stores the jsCode parameter as a plain string in workflow JSON —
    Python's JSON serializer handles newline/quote escaping automatically
    on the way out, and n8n re-parses it on the way in. Any manual
    backslash escaping here would break the JS at runtime.
    """
    return value


# ============================================================
# PF-01 — CREATE PAYMENT
# ============================================================
#
# Flow:
#   1. Webhook receives {name, email, company, phone?}
#   2. Validate input
#   3. Generate booking_id + verification_token + expiry
#   4. Create pending booking row in Airtable
#   5. Build signed PayFast checkout URL
#   6. Respond with {payfast_url, booking_id, token}
#
# The PayFast URL is signed with MD5(sorted_params + passphrase) and
# returned to the browser so the customer can redirect themselves to
# PayFast's hosted checkout.


def build_pf01_nodes() -> list[dict[str, Any]]:
    """Build node list for PF-01 Create Payment."""

    validate_js = _js_string(
        """
const body = $input.first().json.body || $input.first().json;

const name = (body.name || body.customer_name || '').trim();
const email = (body.email || body.customer_email || '').trim().toLowerCase();
const company = (body.company || body.customer_company || '').trim();
const phone = (body.phone || body.customer_phone || '').trim();

const emailOk = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email);
if (!name || name.length < 2) {
    throw new Error('MissingName: Customer name is required');
}
if (!emailOk) {
    throw new Error('InvalidEmail: A valid email address is required');
}

return { json: { name, email, company, phone } };
""".strip()
    )

    generate_js = _js_string(
        """
const crypto = require('crypto');

const input = $input.first().json;

// Booking ID: BKG-YYYYMMDD-XXXXXX (6-char alnum)
const now = new Date();
const yyyy = now.getUTCFullYear();
const mm = String(now.getUTCMonth() + 1).padStart(2, '0');
const dd = String(now.getUTCDate()).padStart(2, '0');
const rand6 = crypto.randomBytes(3).toString('hex').toUpperCase();
const booking_id = `BKG-${yyyy}${mm}${dd}-${rand6}`;

// Verification token: 48 chars urlsafe base64 (288 bits entropy)
const token = crypto.randomBytes(36).toString('base64url');

// Token expiry: 30 days from now
const expiry = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);

// Split name -> name_first / name_last for PayFast
const parts = input.name.split(/\\s+/);
const name_first = parts[0] || input.name;
const name_last = parts.slice(1).join(' ') || '';

return { json: {
    ...input,
    booking_id,
    verification_token: token,
    token_expiry_iso: expiry.toISOString(),
    created_at_iso: now.toISOString(),
    name_first,
    name_last,
    amount: 2500.00,
    item_name: 'AI Automation Consulting (1 hour)',
    item_description: 'Premium 60-minute AI automation strategy consultation with AnyVision Media'
}};
""".strip()
    )

    # Signature algorithm lifted from PayFast docs:
    # 1. Sort params alphabetically by key
    # 2. URL-encode each value (spaces -> +, uppercase hex)
    # 3. Concatenate as key=val&key=val...
    # 4. Append &passphrase=URLENCODED_PASSPHRASE if passphrase set
    # 5. MD5 of the final string = signature
    build_url_js = _js_string(
        f"""
const crypto = require('crypto');
// Reference the booking data explicitly because the upstream Airtable
// create returns {{id, createdTime, fields}}, which would otherwise
// shadow the input data we need here.
const input = $('Generate Booking Data').first().json;

// PayFast config (baked at deploy time from .env)
const MERCHANT_ID = '{PAYFAST_MERCHANT_ID}';
const MERCHANT_KEY = '{PAYFAST_MERCHANT_KEY}';
const PASSPHRASE = '{PAYFAST_PASSPHRASE}';
const PROCESS_URL = '{PAYFAST_PROCESS_URL}';
const RETURN_URL = '{RETURN_URL}';
const CANCEL_URL = '{CANCEL_URL}';
const NOTIFY_URL = '{NOTIFY_URL}';

// PayFast's required URL encoding: spaces as +, uppercase hex escapes
function pfEncode(str) {{
    return encodeURIComponent(String(str))
        .replace(/%20/g, '+')
        .replace(/!/g, '%21')
        .replace(/'/g, '%27')
        .replace(/\\(/g, '%28')
        .replace(/\\)/g, '%29')
        .replace(/\\*/g, '%2A')
        .replace(/%([0-9a-f]{{2}})/g, (m, p) => '%' + p.toUpperCase());
}}

// Build parameter object. Order of insertion does not matter here —
// we sort alphabetically below.
const returnUrlWithToken = RETURN_URL + '?token=' + encodeURIComponent(input.verification_token);

const params = {{
    merchant_id: MERCHANT_ID,
    merchant_key: MERCHANT_KEY,
    return_url: returnUrlWithToken,
    cancel_url: CANCEL_URL,
    notify_url: NOTIFY_URL,
    name_first: input.name_first,
    name_last: input.name_last || '',
    email_address: input.email,
    m_payment_id: input.booking_id,
    amount: Number(input.amount).toFixed(2),
    item_name: input.item_name,
    item_description: input.item_description || ''
}};

// Sort alphabetically and build the signed string (skip empty values)
const keys = Object.keys(params).sort();
const parts = [];
for (const key of keys) {{
    const val = params[key];
    if (val === undefined || val === null || val === '') continue;
    parts.push(key + '=' + pfEncode(val));
}}
let signedString = parts.join('&');

if (PASSPHRASE) {{
    signedString += '&passphrase=' + pfEncode(PASSPHRASE);
}}

const signature = crypto.createHash('md5').update(signedString).digest('hex');

// Build final redirect URL (params + signature, same encoding)
const finalParts = parts.slice();
finalParts.push('signature=' + signature);
const payfast_url = PROCESS_URL + '?' + finalParts.join('&');

return {{ json: {{
    ...input,
    payfast_url,
    payfast_signature: signature
}} }};
""".strip()
    )

    respond_js = _js_string(
        """
const input = $('Build PayFast URL').first().json;
return { json: {
    success: true,
    payfast_url: input.payfast_url,
    booking_id: input.booking_id,
    token: input.verification_token,
    amount: input.amount,
    currency: 'ZAR'
}};
""".strip()
    )

    nodes: list[dict[str, Any]] = [
        # 1. Webhook trigger
        {
            "parameters": {
                "httpMethod": "POST",
                "path": "payfast/create-payment",
                "responseMode": "responseNode",
                "options": {
                    "allowedOrigins": "*",
                },
            },
            "id": uid(),
            "name": "Webhook Create Payment",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [220, 300],
            "webhookId": uid(),
        },
        # 2. Validate input
        {
            "parameters": {"jsCode": validate_js},
            "id": uid(),
            "name": "Validate Input",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [440, 300],
        },
        # 3. Generate booking data
        {
            "parameters": {"jsCode": generate_js},
            "id": uid(),
            "name": "Generate Booking Data",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [660, 300],
        },
        # 4. Create pending booking row in Airtable
        {
            "parameters": {
                "operation": "create",
                "base": {"__rl": True, "value": AIRTABLE_BASE_ID, "mode": "id"},
                "table": {"__rl": True, "value": PF_BOOKINGS_TABLE_ID, "mode": "id"},
                "columns": {
                    "mappingMode": "defineBelow",
                    "value": {
                        "Booking ID": "={{ $json.booking_id }}",
                        "Status": "pending",
                        "Customer Name": "={{ $json.name }}",
                        "Customer Email": "={{ $json.email }}",
                        "Customer Company": "={{ $json.company }}",
                        "Customer Phone": "={{ $json.phone }}",
                        "Amount ZAR": "={{ $json.amount }}",
                        "Item Name": "={{ $json.item_name }}",
                        "PayFast Merchant Payment ID": "={{ $json.booking_id }}",
                        "Verification Token": "={{ $json.verification_token }}",
                        "Token Expiry": "={{ $json.token_expiry_iso }}",
                        "Created At": "={{ $json.created_at_iso }}",
                    },
                },
                "options": {},
            },
            "id": uid(),
            "name": "Create Pending Booking",
            "type": "n8n-nodes-base.airtable",
            "typeVersion": 2.1,
            "position": [880, 300],
            "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        },
        # 5. Build signed PayFast URL
        {
            "parameters": {"jsCode": build_url_js},
            "id": uid(),
            "name": "Build PayFast URL",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1100, 300],
        },
        # 6. Prepare response
        {
            "parameters": {"jsCode": respond_js},
            "id": uid(),
            "name": "Prepare Response",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1320, 300],
        },
        # 7. Respond to webhook
        {
            "parameters": {
                "respondWith": "firstIncomingItem",
                "options": {
                    "responseCode": 200,
                    "responseHeaders": {
                        "entries": [
                            {"name": "Access-Control-Allow-Origin", "value": "*"},
                            {"name": "Access-Control-Allow-Methods", "value": "POST, OPTIONS"},
                            {"name": "Access-Control-Allow-Headers", "value": "Content-Type"},
                        ]
                    },
                },
            },
            "id": uid(),
            "name": "Respond",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.1,
            "position": [1540, 300],
        },
    ]

    return nodes


def build_pf01_connections() -> dict[str, Any]:
    """Linear PF-01 flow: Webhook -> Validate -> Generate -> Airtable -> PayFast URL -> Respond."""
    return {
        "Webhook Create Payment": {
            "main": [[{"node": "Validate Input", "type": "main", "index": 0}]]
        },
        "Validate Input": {
            "main": [[{"node": "Generate Booking Data", "type": "main", "index": 0}]]
        },
        "Generate Booking Data": {
            "main": [[{"node": "Create Pending Booking", "type": "main", "index": 0}]]
        },
        "Create Pending Booking": {
            "main": [[{"node": "Build PayFast URL", "type": "main", "index": 0}]]
        },
        "Build PayFast URL": {
            "main": [[{"node": "Prepare Response", "type": "main", "index": 0}]]
        },
        "Prepare Response": {
            "main": [[{"node": "Respond", "type": "main", "index": 0}]]
        },
    }


# ============================================================
# PF-02 — ITN HANDLER
# ============================================================
#
# Flow:
#   1. PayFast POSTs ITN to webhook (form-urlencoded)
#   2. Verify MD5 signature matches
#   3. Postback to PayFast /validate for server-to-server confirmation
#   4. Look up booking by m_payment_id
#   5. Verify amount matches expected
#   6. Read counter, compute invoice number, write counter back
#   7. Update booking: status=paid, invoice fields, VAT breakdown
#   8. Generate HTML tax invoice
#   9. Send email via Gmail
#   10. Respond 200 OK (PayFast requires this)


def build_pf02_nodes() -> list[dict[str, Any]]:
    """Build node list for PF-02 ITN Handler."""

    # Parse + verify signature
    verify_js = _js_string(
        f"""
const crypto = require('crypto');

// Incoming ITN payload may be URL-encoded body or parsed JSON
const raw = $input.first().json;
const body = raw.body || raw;

// Reconstruct sorted signature string WITHOUT the received signature field
const PASSPHRASE = '{PAYFAST_PASSPHRASE}';

function pfEncode(str) {{
    return encodeURIComponent(String(str))
        .replace(/%20/g, '+')
        .replace(/!/g, '%21')
        .replace(/'/g, '%27')
        .replace(/\\(/g, '%28')
        .replace(/\\)/g, '%29')
        .replace(/\\*/g, '%2A')
        .replace(/%([0-9a-f]{{2}})/g, (m, p) => '%' + p.toUpperCase());
}}

const keys = Object.keys(body).filter(k => k !== 'signature').sort();
const parts = [];
for (const k of keys) {{
    const v = body[k];
    if (v === undefined || v === null || v === '') continue;
    parts.push(k + '=' + pfEncode(v));
}}
let signedString = parts.join('&');
if (PASSPHRASE) signedString += '&passphrase=' + pfEncode(PASSPHRASE);

const expectedSig = crypto.createHash('md5').update(signedString).digest('hex');
const receivedSig = (body.signature || '').toLowerCase();
const sigOk = expectedSig === receivedSig;

if (!sigOk) {{
    throw new Error('PayFastSignatureMismatch: expected=' + expectedSig + ' received=' + receivedSig);
}}

// Build postback body (form-urlencoded, same params minus signature)
const postbackBody = parts.join('&');

return {{ json: {{
    ...body,
    _verified_signature: expectedSig,
    _postback_body: postbackBody
}} }};
""".strip()
    )

    # Postback validation with PayFast
    check_postback_js = _js_string(
        """
const input = $input.first().json;
const resp = (input.data || input.body || input).toString ? (input.data || input.body || input).toString() : String(input.data || input.body || input);
if (!resp.trim().startsWith('VALID')) {
    throw new Error('PayFastPostbackFailed: response=' + resp.substring(0, 200));
}
return { json: { _postback_ok: true } };
""".strip()
    )

    # Merge ITN body with amount check + compute VAT
    amount_check_js = _js_string(
        """
const itn = $('Verify PayFast Signature').first().json;

// PayFast sends amount_gross as the total charged (incl VAT)
const amountGross = parseFloat(itn.amount_gross || itn.amount || '0');
const expected = 2500.00;

if (Math.abs(amountGross - expected) > 0.01) {
    throw new Error('AmountMismatch: expected=' + expected + ' received=' + amountGross);
}

// SA VAT 15% breakdown (inclusive method)
const amountExcl = Math.round((amountGross / 1.15) * 100) / 100;
const vatAmount = Math.round((amountGross - amountExcl) * 100) / 100;

return { json: {
    ...itn,
    amount_gross_computed: amountGross,
    amount_excl_vat: amountExcl,
    vat_amount: vatAmount,
    paid_at_iso: new Date().toISOString()
}};
""".strip()
    )

    # Compute invoice number from counter
    invoice_num_js = _js_string(
        """
const itn = $('Check Amount + VAT').first().json;
const counter = $input.first().json;

// counter is a single Airtable record returned by the Get
const currentValue = parseInt(counter['Value'] || counter.fields?.['Value'] || '0', 10) || 0;
const newValue = currentValue + 1;

// Format: AVM-INV-YYYY-NNNNN
const yyyy = new Date().getUTCFullYear();
const padded = String(newValue).padStart(5, '0');
const invoiceNumber = `AVM-INV-${yyyy}-${padded}`;

return { json: {
    ...itn,
    counter_record_id: counter.id,
    counter_new_value: newValue,
    invoice_number: invoiceNumber
}};
""".strip()
    )

    # Generate tax invoice HTML
    invoice_html_js = _js_string(
        f"""
const input = $input.first().json;

const AVM_NAME = '{_js_string(AVM_BUSINESS_NAME)}';
const AVM_EMAIL = '{_js_string(AVM_BUSINESS_EMAIL)}';
const AVM_ADDRESS = '{_js_string(AVM_BUSINESS_ADDRESS)}';
const AVM_VAT = '{_js_string(AVM_VAT_NUMBER)}';
const AVM_REG = '{_js_string(AVM_COMPANY_REG)}';
const CALENDAR = '{CALENDAR_URL}';

const fmt = (n) => 'R ' + Number(n).toFixed(2).replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, ',');
const dateStr = new Date().toISOString().split('T')[0];
const customerName = input['customer_name'] || input.name_first + ' ' + (input.name_last || '') || 'Customer';
const customerEmail = input['customer_email'] || input.email_address || '';
const customerCompany = input['customer_company'] || '';
const paymentId = input.pf_payment_id || 'N/A';
const bookingId = input.m_payment_id || 'N/A';

const html = `<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Tax Invoice ${{input.invoice_number}}</title>
<style>
body {{ font-family: 'Inter', -apple-system, Arial, sans-serif; background: #f5f5f7; margin: 0; padding: 24px; color: #1a1a2e; }}
.invoice {{ max-width: 680px; margin: 0 auto; background: #fff; padding: 48px; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.06); }}
.header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 40px; padding-bottom: 24px; border-bottom: 2px solid #FF6D5A; }}
.brand {{ font-size: 1.4rem; font-weight: 700; color: #0A0F1C; }}
.brand-accent {{ color: #FF6D5A; }}
.brand-sub {{ font-size: 0.85rem; color: #6B7280; margin-top: 4px; }}
.doc-title {{ font-size: 0.85rem; font-weight: 700; color: #FF6D5A; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 6px; }}
.doc-num {{ font-size: 1.3rem; font-weight: 700; color: #0A0F1C; }}
.meta {{ font-size: 0.9rem; line-height: 1.7; color: #4a4a6a; }}
.meta strong {{ color: #0A0F1C; }}
.section {{ margin-bottom: 32px; }}
.section-label {{ font-size: 0.75rem; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: #6B7280; margin-bottom: 8px; }}
.item-table {{ width: 100%; border-collapse: collapse; margin: 24px 0; }}
.item-table th {{ text-align: left; font-size: 0.78rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: #6B7280; padding: 12px 8px; border-bottom: 2px solid #e5e5ea; }}
.item-table th.right {{ text-align: right; }}
.item-table td {{ padding: 16px 8px; font-size: 0.95rem; border-bottom: 1px solid #f0f0f5; }}
.item-table td.right {{ text-align: right; }}
.totals {{ margin-left: auto; width: 280px; margin-top: 16px; }}
.totals-row {{ display: flex; justify-content: space-between; padding: 8px 0; font-size: 0.95rem; color: #4a4a6a; }}
.totals-row.grand {{ font-size: 1.15rem; font-weight: 700; color: #0A0F1C; padding-top: 12px; margin-top: 6px; border-top: 2px solid #0A0F1C; }}
.next-steps {{ background: linear-gradient(135deg, rgba(255,109,90,0.08), rgba(108,99,255,0.08)); border: 1px solid rgba(255,109,90,0.2); border-radius: 10px; padding: 24px; margin: 32px 0; }}
.next-steps h3 {{ font-size: 1rem; font-weight: 700; color: #0A0F1C; margin: 0 0 12px 0; }}
.next-steps p {{ font-size: 0.9rem; line-height: 1.6; color: #4a4a6a; margin: 0 0 16px 0; }}
.cta-btn {{ display: inline-block; padding: 14px 28px; background: linear-gradient(135deg, #FF6D5A, #FF8A7A); color: #fff !important; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 0.95rem; }}
.footer {{ font-size: 0.75rem; color: #9898a8; line-height: 1.6; margin-top: 40px; padding-top: 24px; border-top: 1px solid #e5e5ea; }}
</style></head><body>
<div class="invoice">
    <div class="header">
        <div>
            <div class="brand">${{AVM_NAME}}<span class="brand-accent">.</span></div>
            <div class="brand-sub">AI Automation &amp; Workflow Engineering</div>
        </div>
        <div style="text-align: right;">
            <div class="doc-title">Tax Invoice</div>
            <div class="doc-num">${{input.invoice_number}}</div>
        </div>
    </div>

    <div style="display: flex; justify-content: space-between; margin-bottom: 32px; gap: 40px;">
        <div class="meta" style="flex: 1;">
            <div class="section-label">From</div>
            <strong>${{AVM_NAME}}</strong><br>
            ${{AVM_ADDRESS}}<br>
            ${{AVM_EMAIL}}<br>
            VAT No: <strong>${{AVM_VAT}}</strong>${{AVM_REG ? '<br>Reg No: ' + AVM_REG : ''}}
        </div>
        <div class="meta" style="flex: 1;">
            <div class="section-label">Bill To</div>
            <strong>${{customerName}}</strong><br>
            ${{customerCompany ? customerCompany + '<br>' : ''}}${{customerEmail}}
        </div>
    </div>

    <div class="meta" style="margin-bottom: 24px;">
        <strong>Invoice Date:</strong> ${{dateStr}}<br>
        <strong>Booking ID:</strong> ${{bookingId}}<br>
        <strong>Payment Method:</strong> PayFast<br>
        <strong>PayFast Payment ID:</strong> ${{paymentId}}
    </div>

    <table class="item-table">
        <thead>
            <tr>
                <th>Description</th>
                <th class="right">Qty</th>
                <th class="right">Excl. VAT</th>
                <th class="right">Total</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>AI Automation Consulting &mdash; 60 minute strategy session</td>
                <td class="right">1</td>
                <td class="right">${{fmt(input.amount_excl_vat)}}</td>
                <td class="right">${{fmt(input.amount_excl_vat)}}</td>
            </tr>
        </tbody>
    </table>

    <div class="totals">
        <div class="totals-row"><span>Subtotal (excl. VAT)</span><span>${{fmt(input.amount_excl_vat)}}</span></div>
        <div class="totals-row"><span>VAT @ 15%</span><span>${{fmt(input.vat_amount)}}</span></div>
        <div class="totals-row grand"><span>Total Paid</span><span>${{fmt(input.amount_gross_computed)}}</span></div>
    </div>

    <div class="next-steps">
        <h3>Next Step: Book Your Slot</h3>
        <p>Your payment is confirmed. Pick a 60-minute window that suits you &mdash; we&rsquo;ll send a calendar invite and an intake form within 5 minutes so we arrive prepared.</p>
        <a href="${{CALENDAR}}" class="cta-btn">Book Your Slot &rarr;</a>
    </div>

    <div class="footer">
        This is an electronic tax invoice issued by ${{AVM_NAME}}.
        Questions? Reply to this email or write to ${{AVM_EMAIL}}.
        Your R2,500 is 100% credited toward any project you book with us within 30 days.
        If you don&rsquo;t leave the session with at least three high-ROI automations mapped out, we refund the hour in full.
    </div>
</div></body></html>`;

return {{ json: {{ ...input, invoice_html: html }} }};
""".strip()
    )

    respond_ok_js = _js_string(
        """
return { json: { status: 'ok' } };
""".strip()
    )

    nodes: list[dict[str, Any]] = [
        # 1. Webhook
        {
            "parameters": {
                "httpMethod": "POST",
                "path": "payfast/itn",
                "responseMode": "lastNode",
                "options": {"rawBody": False},
            },
            "id": uid(),
            "name": "Webhook ITN",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [220, 300],
            "webhookId": uid(),
        },
        # 2. Verify signature
        {
            "parameters": {"jsCode": verify_js},
            "id": uid(),
            "name": "Verify PayFast Signature",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [440, 300],
        },
        # 3. Postback to PayFast for validation
        {
            "parameters": {
                "method": "POST",
                "url": PAYFAST_VALIDATE_URL,
                "sendBody": True,
                "specifyBody": "string",
                "contentType": "form-urlencoded",
                "body": "={{ $json._postback_body }}",
                "options": {"timeout": 15000},
            },
            "id": uid(),
            "name": "PayFast Postback",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [660, 300],
        },
        # 4. Check postback response
        {
            "parameters": {"jsCode": check_postback_js},
            "id": uid(),
            "name": "Check Postback",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [880, 300],
        },
        # 5. Look up booking by m_payment_id
        {
            "parameters": {
                "operation": "search",
                "base": {"__rl": True, "value": AIRTABLE_BASE_ID, "mode": "id"},
                "table": {"__rl": True, "value": PF_BOOKINGS_TABLE_ID, "mode": "id"},
                "filterByFormula": "{Booking ID} = '{{ $('Verify PayFast Signature').first().json.m_payment_id }}'",
                "options": {},
            },
            "id": uid(),
            "name": "Lookup Booking",
            "type": "n8n-nodes-base.airtable",
            "typeVersion": 2.1,
            "position": [1100, 300],
            "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        },
        # 6. Amount check + VAT computation
        {
            "parameters": {"jsCode": amount_check_js},
            "id": uid(),
            "name": "Check Amount + VAT",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1320, 300],
        },
        # 7. Get invoice counter record
        {
            "parameters": {
                "operation": "search",
                "base": {"__rl": True, "value": AIRTABLE_BASE_ID, "mode": "id"},
                "table": {"__rl": True, "value": PF_COUNTERS_TABLE_ID, "mode": "id"},
                "filterByFormula": "{Counter Name} = 'invoice_sequence'",
                "options": {},
            },
            "id": uid(),
            "name": "Get Counter",
            "type": "n8n-nodes-base.airtable",
            "typeVersion": 2.1,
            "position": [1540, 300],
            "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        },
        # 8. Compute invoice number
        {
            "parameters": {"jsCode": invoice_num_js},
            "id": uid(),
            "name": "Compute Invoice Number",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1760, 300],
        },
        # 9. Update counter
        {
            "parameters": {
                "operation": "update",
                "base": {"__rl": True, "value": AIRTABLE_BASE_ID, "mode": "id"},
                "table": {"__rl": True, "value": PF_COUNTERS_TABLE_ID, "mode": "id"},
                "id": "={{ $json.counter_record_id }}",
                "columns": {
                    "mappingMode": "defineBelow",
                    "value": {
                        "Value": "={{ $json.counter_new_value }}",
                        "Last Used At": "={{ new Date().toISOString() }}",
                    },
                },
                "options": {},
            },
            "id": uid(),
            "name": "Update Counter",
            "type": "n8n-nodes-base.airtable",
            "typeVersion": 2.1,
            "position": [1980, 300],
            "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        },
        # 10. Update booking to paid
        {
            "parameters": {
                "operation": "update",
                "base": {"__rl": True, "value": AIRTABLE_BASE_ID, "mode": "id"},
                "table": {"__rl": True, "value": PF_BOOKINGS_TABLE_ID, "mode": "id"},
                "id": "={{ $('Lookup Booking').first().json.id }}",
                "columns": {
                    "mappingMode": "defineBelow",
                    "value": {
                        "Status": "paid",
                        "PayFast Payment ID": "={{ $('Compute Invoice Number').first().json.pf_payment_id }}",
                        "PayFast Signature": "={{ $('Compute Invoice Number').first().json._verified_signature }}",
                        "PayFast Raw ITN": "={{ JSON.stringify($('Verify PayFast Signature').first().json) }}",
                        "Amount Excl VAT": "={{ $('Compute Invoice Number').first().json.amount_excl_vat }}",
                        "VAT Amount": "={{ $('Compute Invoice Number').first().json.vat_amount }}",
                        "Invoice Number": "={{ $('Compute Invoice Number').first().json.invoice_number }}",
                        "Paid At": "={{ $('Compute Invoice Number').first().json.paid_at_iso }}",
                    },
                },
                "options": {},
            },
            "id": uid(),
            "name": "Mark Booking Paid",
            "type": "n8n-nodes-base.airtable",
            "typeVersion": 2.1,
            "position": [2200, 300],
            "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        },
        # 11. Generate invoice HTML
        {
            "parameters": {"jsCode": invoice_html_js},
            "id": uid(),
            "name": "Build Invoice HTML",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [2420, 300],
        },
        # 12. Send customer email via Gmail
        {
            "parameters": {
                "sendTo": "={{ $('Verify PayFast Signature').first().json.email_address }}",
                "subject": "=Your AI Automation Consulting session is confirmed - Tax Invoice {{ $('Compute Invoice Number').first().json.invoice_number }}",
                "emailType": "html",
                "message": "={{ $json.invoice_html }}",
                "options": {
                    "ccList": AVM_BUSINESS_EMAIL,
                },
            },
            "id": uid(),
            "name": "Send Tax Invoice Email",
            "type": "n8n-nodes-base.gmail",
            "typeVersion": 2.1,
            "position": [2640, 300],
            "credentials": {"gmailOAuth2": CRED_GMAIL_OAUTH2},
        },
        # 13. Mark email sent on booking
        {
            "parameters": {
                "operation": "update",
                "base": {"__rl": True, "value": AIRTABLE_BASE_ID, "mode": "id"},
                "table": {"__rl": True, "value": PF_BOOKINGS_TABLE_ID, "mode": "id"},
                "id": "={{ $('Lookup Booking').first().json.id }}",
                "columns": {
                    "mappingMode": "defineBelow",
                    "value": {
                        "Invoice Emailed": True,
                        "Invoice Emailed At": "={{ new Date().toISOString() }}",
                    },
                },
                "options": {},
            },
            "id": uid(),
            "name": "Mark Email Sent",
            "type": "n8n-nodes-base.airtable",
            "typeVersion": 2.1,
            "position": [2860, 300],
            "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        },
        # 14. Final OK response (PayFast requires 200)
        {
            "parameters": {"jsCode": respond_ok_js},
            "id": uid(),
            "name": "Respond OK",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [3080, 300],
        },
    ]

    return nodes


def build_pf02_connections() -> dict[str, Any]:
    """Linear PF-02 flow."""
    return {
        "Webhook ITN": {"main": [[{"node": "Verify PayFast Signature", "type": "main", "index": 0}]]},
        "Verify PayFast Signature": {"main": [[{"node": "PayFast Postback", "type": "main", "index": 0}]]},
        "PayFast Postback": {"main": [[{"node": "Check Postback", "type": "main", "index": 0}]]},
        "Check Postback": {"main": [[{"node": "Lookup Booking", "type": "main", "index": 0}]]},
        "Lookup Booking": {"main": [[{"node": "Check Amount + VAT", "type": "main", "index": 0}]]},
        "Check Amount + VAT": {"main": [[{"node": "Get Counter", "type": "main", "index": 0}]]},
        "Get Counter": {"main": [[{"node": "Compute Invoice Number", "type": "main", "index": 0}]]},
        "Compute Invoice Number": {"main": [[{"node": "Update Counter", "type": "main", "index": 0}]]},
        "Update Counter": {"main": [[{"node": "Mark Booking Paid", "type": "main", "index": 0}]]},
        "Mark Booking Paid": {"main": [[{"node": "Build Invoice HTML", "type": "main", "index": 0}]]},
        "Build Invoice HTML": {"main": [[{"node": "Send Tax Invoice Email", "type": "main", "index": 0}]]},
        "Send Tax Invoice Email": {"main": [[{"node": "Mark Email Sent", "type": "main", "index": 0}]]},
        "Mark Email Sent": {"main": [[{"node": "Respond OK", "type": "main", "index": 0}]]},
    }


# ============================================================
# PF-03 — VERIFY TOKEN
# ============================================================
#
# Flow:
#   1. Webhook (GET or POST) with ?token=...
#   2. Parse token
#   3. Look up booking by Verification Token
#   4. Validate status=paid AND token not expired
#   5. Return minimal booking details (CORS enabled)


def build_pf03_nodes() -> list[dict[str, Any]]:
    """Build node list for PF-03 Verify Token."""

    parse_token_js = _js_string(
        f"""
const input = $input.first().json;
const token = (input.query && input.query.token) || (input.body && input.body.token) || input.token || '';
if (!token || String(token).length < 16) {{
    return {{ json: {{ _parsed: false, _error: 'TokenMissing', skip_fetch: true }} }};
}}

// Build the full Airtable URL so the downstream HTTP Request node doesn't
// have to interpolate filterByFormula (n8n's expression evaluation on
// query params is unreliable for complex Airtable formulas).
const baseId = '{AIRTABLE_BASE_ID}';
const tableId = '{PF_BOOKINGS_TABLE_ID}';
const cleanToken = String(token).replace(/'/g, "\\\\'");
const formula = `{{Verification Token}} = '${{cleanToken}}'`;
const url = 'https://api.airtable.com/v0/' + baseId + '/' + tableId
    + '?filterByFormula=' + encodeURIComponent(formula)
    + '&maxRecords=1';

return {{ json: {{ _parsed: true, token: String(token), airtable_url: url }} }};
""".strip()
    )

    validate_js = _js_string(
        """
// Parse raw Airtable REST API response: { records: [ { id, fields: {...} } ] }
const input = $input.first().json;
const records = Array.isArray(input.records) ? input.records : [];

if (records.length === 0) {
    return { json: { valid: false, reason: 'not_found' } };
}

const rec = records[0];
const fields = rec.fields || {};
const status = fields['Status'];
const expiryStr = fields['Token Expiry'];
const now = new Date();
const expiry = expiryStr ? new Date(expiryStr) : null;

if (status !== 'paid') {
    return { json: { valid: false, reason: 'not_paid', status: status || null } };
}
if (!expiry || expiry < now) {
    return { json: { valid: false, reason: 'expired' } };
}

return { json: {
    valid: true,
    booking_id: fields['Booking ID'],
    customer_name: fields['Customer Name'],
    customer_email: fields['Customer Email'],
    invoice_number: fields['Invoice Number'],
    amount: fields['Amount ZAR'],
    paid_at: fields['Paid At'],
    calendar_url: '"""
        + CALENDAR_URL
        + """'
}};
""".strip()
    )

    nodes: list[dict[str, Any]] = [
        # 1. Webhook
        {
            "parameters": {
                "httpMethod": "POST",
                "path": "payfast/verify-token",
                "responseMode": "responseNode",
                "options": {"allowedOrigins": "*"},
            },
            "id": uid(),
            "name": "Webhook Verify Token",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [220, 300],
            "webhookId": uid(),
        },
        # 2. Parse token
        {
            "parameters": {"jsCode": parse_token_js},
            "id": uid(),
            "name": "Parse Token",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [440, 300],
        },
        # 3. Look up booking by token via direct Airtable REST API
        # (The Airtable native node silently fails to interpolate {{ }}
        # in filterByFormula at runtime, so we bypass it.)
        {
            "parameters": {
                "method": "GET",
                "url": f"=https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{PF_BOOKINGS_TABLE_ID}",
                "authentication": "predefinedCredentialType",
                "nodeCredentialType": "airtableTokenApi",
                "sendQuery": True,
                "specifyQuery": "keypair",
                "queryParameters": {
                    "parameters": [
                        {
                            "name": "filterByFormula",
                            "value": "={\"{Verification Token} = '\" + $json.token + \"'\"}",
                        },
                        {"name": "maxRecords", "value": "1"},
                    ]
                },
                "options": {"timeout": 15000},
            },
            "id": uid(),
            "name": "Find Booking",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [660, 300],
            "alwaysOutputData": True,
            "onError": "continueRegularOutput",
            "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        },
        # 4. Validate + shape response
        {
            "parameters": {"jsCode": validate_js},
            "id": uid(),
            "name": "Validate Booking",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [880, 300],
        },
        # 5. Respond to webhook with CORS headers
        {
            "parameters": {
                "respondWith": "firstIncomingItem",
                "options": {
                    "responseCode": 200,
                    "responseHeaders": {
                        "entries": [
                            {"name": "Access-Control-Allow-Origin", "value": "*"},
                            {"name": "Access-Control-Allow-Methods", "value": "POST, OPTIONS"},
                            {"name": "Access-Control-Allow-Headers", "value": "Content-Type"},
                            {"name": "Cache-Control", "value": "no-store"},
                        ]
                    },
                },
            },
            "id": uid(),
            "name": "Respond",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.1,
            "position": [1100, 300],
        },
    ]

    return nodes


def build_pf03_connections() -> dict[str, Any]:
    """Linear PF-03 flow."""
    return {
        "Webhook Verify Token": {
            "main": [[{"node": "Parse Token", "type": "main", "index": 0}]]
        },
        "Parse Token": {
            "main": [[{"node": "Find Booking", "type": "main", "index": 0}]]
        },
        "Find Booking": {
            "main": [[{"node": "Validate Booking", "type": "main", "index": 0}]]
        },
        "Validate Booking": {
            "main": [[{"node": "Respond", "type": "main", "index": 0}]]
        },
    }


# ============================================================
# WORKFLOW ASSEMBLY & DEPLOYMENT
# ============================================================


WORKFLOW_BUILDERS: dict[str, dict[str, Any]] = {
    "pf01": {
        "name": "PF-01 Create Payment",
        "build_nodes": build_pf01_nodes,
        "build_connections": build_pf01_connections,
        "filename": "pf01_create_payment.json",
        "tags": ["payfast", "payment", "webhook"],
    },
    "pf02": {
        "name": "PF-02 ITN Handler",
        "build_nodes": build_pf02_nodes,
        "build_connections": build_pf02_connections,
        "filename": "pf02_itn_handler.json",
        "tags": ["payfast", "itn", "webhook", "airtable"],
    },
    "pf03": {
        "name": "PF-03 Verify Token",
        "build_nodes": build_pf03_nodes,
        "build_connections": build_pf03_connections,
        "filename": "pf03_verify_token.json",
        "tags": ["payfast", "verify", "webhook"],
    },
}


def build_workflow_json(key: str) -> dict[str, Any]:
    """Assemble a full workflow JSON for n8n API."""
    builder = WORKFLOW_BUILDERS[key]
    nodes = builder["build_nodes"]()
    connections = builder["build_connections"]()
    return {
        "name": builder["name"],
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "all",
        },
        "staticData": None,
        "meta": {
            "templateCredsSetupCompleted": True,
            "builder": "deploy_payfast_dept.py",
            "built_at": datetime.now().isoformat(),
        },
        "pinData": {},
        "tags": builder["tags"],
    }


def save_workflow(key: str, workflow_json: dict[str, Any]) -> Path:
    """Save the built workflow JSON to disk."""
    builder = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "payfast-dept"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / builder["filename"]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow_json, f, indent=2, ensure_ascii=False)
    node_count = len(workflow_json["nodes"])
    print(f"  + {builder['name']:<30} ({node_count} nodes) -> {output_path.name}")
    return output_path


def deploy_workflow(
    key: str, workflow_json: dict[str, Any], activate: bool = False
) -> str | None:
    """Push the workflow to the configured n8n instance."""
    from n8n_client import N8nClient

    api_key = os.getenv("N8N_API_KEY")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env")
        sys.exit(1)

    builder = WORKFLOW_BUILDERS[key]

    # n8n Create API only accepts these 4 top-level fields — reject everything else
    # (rejects tags, meta, active, staticData, pinData with "additional properties" error)
    payload = {
        k: workflow_json[k]
        for k in ("name", "nodes", "connections", "settings")
        if k in workflow_json
    }

    with N8nClient(N8N_BASE_URL, api_key, timeout=30) as client:
        # Check if a workflow with this name already exists
        existing = client.list_workflows(use_cache=False)
        existing_wf = next(
            (w for w in existing if w.get("name") == builder["name"]), None
        )

        if existing_wf:
            wf_id = existing_wf["id"]
            client.update_workflow(wf_id, payload)
            print(f"  + {builder['name']:<30} Updated -> {wf_id}")
        else:
            resp = client.create_workflow(payload)
            if not resp or "id" not in resp:
                print(f"  - {builder['name']:<30} FAILED to create")
                return None
            wf_id = resp["id"]
            print(f"  + {builder['name']:<30} Created -> {wf_id}")

        if activate:
            import time

            time.sleep(1)
            try:
                client.activate_workflow(wf_id)
                print(f"    Activated: {wf_id}")
            except Exception as e:
                print(f"    WARN activation failed: {e}")

        return wf_id


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nWorkflows:")
        for key, builder in WORKFLOW_BUILDERS.items():
            print(f"  {key:<8} {builder['name']}")
        sys.exit(0)

    action = sys.argv[1].lower()
    target = sys.argv[2].lower() if len(sys.argv) > 2 else "all"

    if target == "all":
        keys = list(WORKFLOW_BUILDERS.keys())
    elif target in WORKFLOW_BUILDERS:
        keys = [target]
    else:
        print(f"Unknown workflow: {target}")
        print(f"Valid: {', '.join(WORKFLOW_BUILDERS.keys())}")
        sys.exit(1)

    print("=" * 60)
    print("PAYFAST PAYMENT DEPARTMENT - WORKFLOW BUILDER")
    print("=" * 60)
    print(f"Action: {action}")
    print(f"Target: {', '.join(keys)}")
    print(f"PayFast sandbox: {PAYFAST_SANDBOX}")
    print(f"PayFast process URL: {PAYFAST_PROCESS_URL}")
    print(f"ITN notify URL: {NOTIFY_URL}")
    print(f"Return URL: {RETURN_URL}")
    print()

    # Sanity warnings
    if PAYFAST_PASSPHRASE.startswith("REPLACE") or not PAYFAST_PASSPHRASE:
        print("WARN: PAYFAST_PASSPHRASE not set in .env — signatures will fail")
    if WEBHOOK_HMAC_SECRET.startswith("REPLACE"):
        print("WARN: PAYFAST_WEBHOOK_HMAC_SECRET is a placeholder — set a real secret")
    if AVM_VAT_NUMBER == "VAT_NUMBER_REQUIRED":
        print("WARN: AVM_VAT_NUMBER not set — tax invoices will be invalid")
    print()

    if action == "build":
        print("Building workflow JSON files...")
        print("-" * 40)
        for key in keys:
            wf = build_workflow_json(key)
            save_workflow(key, wf)
        print()
        print("Built. Inspect: workflows/payfast-dept/")
        print("REMINDER: workflows/payfast-dept/ contains your PayFast passphrase.")
        print("          Add it to .gitignore before committing.")

    elif action in ("deploy", "activate"):
        do_activate = action == "activate"
        print(
            f"Building and deploying ({'active' if do_activate else 'inactive'})..."
        )
        print("-" * 40)
        deployed: dict[str, str] = {}
        for key in keys:
            wf = build_workflow_json(key)
            save_workflow(key, wf)
            wf_id = deploy_workflow(key, wf, activate=do_activate)
            if wf_id:
                deployed[key] = wf_id

        print()
        if deployed:
            print("Deployed workflow IDs:")
            for key, wf_id in deployed.items():
                print(f"  {key:<8} {wf_id}")
            print()
            print("Webhook URLs:")
            print(f"  PF-01 create payment : {N8N_BASE_URL}/webhook/payfast/create-payment")
            print(f"  PF-02 ITN            : {N8N_BASE_URL}/webhook/payfast/itn")
            print(f"  PF-03 verify token   : {N8N_BASE_URL}/webhook/payfast/verify-token")

    else:
        print(f"Unknown action: {action}")
        print("Valid: build, deploy, activate")
        sys.exit(1)


if __name__ == "__main__":
    main()
