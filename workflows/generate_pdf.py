"""
Generate a colorful PDF from the WhatsApp Multi-Agent Onboarding Guide.
Uses xhtml2pdf to render styled HTML to PDF.
"""

import os
from xhtml2pdf import pisa

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PDF = os.path.join(OUTPUT_DIR, "agent_onboarding_guide.pdf")

# ── Brand colors ──
N8N_ORANGE = "#FF6D5A"
WHATSAPP_GREEN = "#25D366"
PHASE1_BLUE = "#2196F3"
PHASE2_PURPLE = "#9C27B0"
SETTINGS_AMBER = "#FF9800"
TROUBLESHOOT_RED = "#F44336"
LIVE_GREEN = "#4CAF50"
PENDING_YELLOW = "#FFC107"
TODO_RED = "#E53935"
BG_LIGHT = "#FAFAFA"
BORDER_GRAY = "#E0E0E0"

HTML_CONTENT = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
    @page {{
        size: A4;
        margin: 1.5cm 2cm;
        @frame footer {{
            -pdf-frame-content: page-footer;
            bottom: 0;
            margin-left: 2cm;
            margin-right: 2cm;
            height: 1cm;
        }}
    }}
    body {{
        font-family: Helvetica, Arial, sans-serif;
        font-size: 10pt;
        color: #333;
        line-height: 1.5;
    }}

    /* ── Title Banner ── */
    .title-banner {{
        background-color: {WHATSAPP_GREEN};
        color: white;
        padding: 20px 25px;
        border-radius: 8px;
        margin-bottom: 5px;
    }}
    .title-banner h1 {{
        font-size: 20pt;
        margin: 0 0 5px 0;
        color: white;
    }}
    .title-banner p {{
        margin: 2px 0;
        font-size: 10pt;
        color: #E8F5E9;
    }}

    /* ── Section Headers ── */
    .section-blue {{ background-color: {PHASE1_BLUE}; color: white; padding: 10px 15px; border-radius: 6px; margin-top: 20px; }}
    .section-purple {{ background-color: {PHASE2_PURPLE}; color: white; padding: 10px 15px; border-radius: 6px; margin-top: 20px; }}
    .section-amber {{ background-color: {SETTINGS_AMBER}; color: white; padding: 10px 15px; border-radius: 6px; margin-top: 20px; }}
    .section-red {{ background-color: {TROUBLESHOOT_RED}; color: white; padding: 10px 15px; border-radius: 6px; margin-top: 20px; }}
    .section-green {{ background-color: {LIVE_GREEN}; color: white; padding: 10px 15px; border-radius: 6px; margin-top: 20px; }}
    .section-gray {{ background-color: #607D8B; color: white; padding: 10px 15px; border-radius: 6px; margin-top: 20px; }}
    .section-blue h2, .section-purple h2, .section-amber h2, .section-red h2, .section-green h2, .section-gray h2 {{
        margin: 0;
        font-size: 14pt;
        color: white;
    }}

    /* ── Step Cards ── */
    .step-card {{
        border: 1.5px solid {BORDER_GRAY};
        border-left: 5px solid {PHASE1_BLUE};
        border-radius: 6px;
        padding: 12px 15px;
        margin: 12px 0;
        background: white;
    }}
    .step-card-purple {{
        border: 1.5px solid {BORDER_GRAY};
        border-left: 5px solid {PHASE2_PURPLE};
        border-radius: 6px;
        padding: 12px 15px;
        margin: 12px 0;
        background: white;
    }}
    .step-card h3, .step-card-purple h3 {{
        margin: 0 0 8px 0;
        font-size: 12pt;
        color: #333;
    }}
    .step-meta {{
        font-size: 9pt;
        color: #777;
        margin-bottom: 8px;
    }}

    /* ── Tables ── */
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 8px 0;
        font-size: 9pt;
    }}
    th {{
        background-color: #37474F;
        color: white;
        padding: 8px 10px;
        text-align: left;
        font-weight: bold;
    }}
    td {{
        padding: 6px 10px;
        border-bottom: 1px solid {BORDER_GRAY};
    }}
    tr:nth-child(even) td {{
        background-color: #F5F5F5;
    }}

    /* Status-specific table */
    .status-table td {{
        padding: 5px 10px;
    }}

    /* ── Status Badges ── */
    .badge-live {{
        background-color: {LIVE_GREEN};
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 8pt;
        font-weight: bold;
    }}
    .badge-pending {{
        background-color: {PENDING_YELLOW};
        color: #333;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 8pt;
        font-weight: bold;
    }}
    .badge-todo {{
        background-color: {TODO_RED};
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 8pt;
        font-weight: bold;
    }}

    /* ── Callout Boxes ── */
    .callout {{
        background-color: #E3F2FD;
        border-left: 4px solid {PHASE1_BLUE};
        padding: 10px 14px;
        margin: 10px 0;
        border-radius: 4px;
        font-size: 9pt;
    }}
    .callout-warn {{
        background-color: #FFF8E1;
        border-left: 4px solid {SETTINGS_AMBER};
        padding: 10px 14px;
        margin: 10px 0;
        border-radius: 4px;
        font-size: 9pt;
    }}
    .callout-success {{
        background-color: #E8F5E9;
        border-left: 4px solid {LIVE_GREEN};
        padding: 10px 14px;
        margin: 10px 0;
        border-radius: 4px;
        font-size: 9pt;
    }}
    .callout-danger {{
        background-color: #FFEBEE;
        border-left: 4px solid {TROUBLESHOOT_RED};
        padding: 10px 14px;
        margin: 10px 0;
        border-radius: 4px;
        font-size: 9pt;
    }}

    /* ── Action List ── */
    .action-item {{
        padding: 4px 0;
        font-size: 9.5pt;
    }}
    .check {{ color: {LIVE_GREEN}; font-weight: bold; }}
    .arrow {{ color: {PHASE1_BLUE}; }}

    /* ── Code/URL blocks ── */
    .code-block {{
        background-color: #263238;
        color: #B2FF59;
        padding: 10px 14px;
        border-radius: 4px;
        font-family: Courier, monospace;
        font-size: 8.5pt;
        margin: 8px 0;
        word-wrap: break-word;
    }}

    /* ── Flow Diagram ── */
    .flow-box {{
        border: 2px solid {BORDER_GRAY};
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0;
        text-align: center;
    }}
    .flow-waiting {{ border-color: {PENDING_YELLOW}; background: #FFFDE7; }}
    .flow-phase1 {{ border-color: {PHASE1_BLUE}; background: #E3F2FD; }}
    .flow-phase2 {{ border-color: {PHASE2_PURPLE}; background: #F3E5F5; }}
    .flow-arrow {{
        text-align: center;
        font-size: 14pt;
        color: #999;
        margin: 4px 0;
    }}

    /* ── Divider ── */
    hr {{
        border: none;
        border-top: 2px solid {BORDER_GRAY};
        margin: 15px 0;
    }}

    /* ── Footer ── */
    .footer {{
        font-size: 7.5pt;
        color: #999;
        text-align: center;
    }}

    /* ── Page break helper ── */
    .page-break {{
        page-break-before: always;
    }}
</style>
</head>
<body>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- TITLE BANNER                                           -->
<!-- ═══════════════════════════════════════════════════════ -->
<div class="title-banner">
    <h1>WhatsApp Multi-Agent System</h1>
    <h1 style="font-size: 14pt; font-weight: normal; margin-top: 0;">Agent Onboarding Guide</h1>
    <p><b>Workflow:</b> WhatsApp Multi-Agent System (Optimized) &nbsp;|&nbsp; <b>Platform:</b> n8n Cloud &nbsp;|&nbsp; <b>Industry:</b> Real Estate</p>
</div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- CURRENT STATUS                                         -->
<!-- ═══════════════════════════════════════════════════════ -->
<div class="section-green"><h2>Current Status</h2></div>

<table class="status-table">
    <tr><th>Component</th><th>Status</th><th>Notes</th></tr>
    <tr><td>n8n Cloud Instance</td><td><span class="badge-live">LIVE</span></td><td>Workflow deployed (36 nodes)</td></tr>
    <tr><td>Airtable Base + 4 Tables</td><td><span class="badge-live">LIVE</span></td><td>Agents, Message Log, Blocked, Errors</td></tr>
    <tr><td>Twilio Credential</td><td><span class="badge-live">LIVE</span></td><td>Connected in n8n</td></tr>
    <tr><td>OpenRouter (GPT-4)</td><td><span class="badge-live">LIVE</span></td><td>AI analysis ready</td></tr>
    <tr><td>Workflow Imported &amp; Configured</td><td><span class="badge-live">LIVE</span></td><td>All credentials mapped</td></tr>
    <tr><td>Agent 001 Record Created</td><td><span class="badge-live">LIVE</span></td><td>Waiting for phone # + token</td></tr>
    <tr><td>Facebook Business Verification</td><td><span class="badge-pending">PENDING</span></td><td>Under review by Meta</td></tr>
    <tr><td>Twilio WhatsApp Sandbox</td><td><span class="badge-todo">TODO</span></td><td>Manual &mdash; Twilio Console</td></tr>
    <tr><td>Meta Webhook &rarr; n8n</td><td><span class="badge-todo">TODO</span></td><td>2-minute setup once approved</td></tr>
    <tr><td>Agent Record: Phone + Token</td><td><span class="badge-todo">TODO</span></td><td>After Meta approves</td></tr>
</table>

<div class="callout">
    <b>Bottom line:</b> The system is fully built and deployed. Once Facebook approves your business, you're ~25 minutes away from going live.
</div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- PHASE 1                                                -->
<!-- ═══════════════════════════════════════════════════════ -->
<div class="section-blue"><h2>PHASE 1 &mdash; First-Time Setup (Do Once)</h2></div>
<p><i>Complete these steps in order after Facebook approves your business.</i></p>

<!-- Step 1 -->
<div class="step-card">
    <h3>Step 1 &mdash; Complete Facebook Business Verification</h3>
    <div class="step-meta">Time: Waiting on Meta &nbsp;&bull;&nbsp; Owner: You</div>
    <div class="action-item"><span class="check">&#10003;</span> Already submitted &mdash; no action needed</div>
    <div class="action-item"><span class="arrow">&#9658;</span> Wait for the approval email from Meta</div>
    <div class="action-item"><span class="arrow">&#9658;</span> Check: <b>business.facebook.com</b> &rarr; Business Settings &rarr; Business Info</div>
    <div class="callout-warn"><b>You are here.</b> Once this clears, move to Step 2.</div>
</div>

<!-- Step 2 -->
<div class="step-card">
    <h3>Step 2 &mdash; Set Up Twilio WhatsApp Sandbox</h3>
    <div class="step-meta">Time: ~5 minutes &nbsp;&bull;&nbsp; Owner: You</div>
    <table>
        <tr><th>#</th><th>Action</th><th>Details</th></tr>
        <tr><td><b>A</b></td><td>Go to <b>Twilio Console</b></td><td>&rarr; Messaging &rarr; Settings &rarr; WhatsApp Sandbox</td></tr>
        <tr><td><b>B</b></td><td>Send the join code</td><td>From your personal WhatsApp to the Twilio sandbox number</td></tr>
        <tr><td><b>C</b></td><td>Confirm connection</td><td>You'll see a green checkmark in Twilio</td></tr>
    </table>
    <div class="callout">This lets Twilio send WhatsApp messages on behalf of your agents.</div>
</div>

<!-- Step 3 -->
<div class="step-card">
    <h3>Step 3 &mdash; Grab Your 3 WhatsApp Values</h3>
    <div class="step-meta">Time: ~2 minutes &nbsp;&bull;&nbsp; Owner: You &nbsp;&bull;&nbsp; Where: developers.facebook.com &rarr; Your App &rarr; WhatsApp &rarr; Getting Started</div>
    <table>
        <tr><th>#</th><th>Value</th><th>Where to Find It</th><th>Example</th></tr>
        <tr><td><b>1</b></td><td><b>WhatsApp Business Account ID</b></td><td>Getting Started page, top section</td><td><code>123456789012345</code></td></tr>
        <tr><td><b>2</b></td><td><b>Phone Number ID</b></td><td>"From" dropdown on Getting Started</td><td><code>987654321098765</code></td></tr>
        <tr><td><b>3</b></td><td><b>Temporary Access Token</b></td><td>Click "Generate" on Getting Started</td><td><code>EAAx...</code></td></tr>
    </table>
    <div class="callout-success"><b>Copy all 3 values and share them with Claude.</b></div>
    <div class="callout-warn">The temporary token expires every 24 hours. Fine for testing. We'll set up a permanent System User token for production later.</div>
</div>

<div class="page-break"></div>

<!-- Step 4 -->
<div class="step-card">
    <h3>Step 4 &mdash; Claude Configures Everything (Automated)</h3>
    <div class="step-meta">Time: ~1 minute (automated) &nbsp;&bull;&nbsp; Owner: Claude</div>
    <p>Once you share the 3 values, Claude will:</p>
    <div class="action-item"><span class="check">&#10003;</span> Update agent_001 record in Airtable with your WhatsApp credentials</div>
    <div class="action-item"><span class="check">&#10003;</span> Verify the workflow is active and webhook URLs are live</div>
    <div class="action-item"><span class="check">&#10003;</span> Give you the webhook URL for the next step</div>
</div>

<!-- Step 5 -->
<div class="step-card">
    <h3>Step 5 &mdash; Connect Meta Webhook to n8n</h3>
    <div class="step-meta">Time: ~2 minutes &nbsp;&bull;&nbsp; Owner: You &nbsp;&bull;&nbsp; Where: developers.facebook.com &rarr; Your App &rarr; WhatsApp &rarr; Configuration</div>
    <table>
        <tr><th>#</th><th>Action</th><th>Value</th></tr>
        <tr><td><b>A</b></td><td>Open <b>Webhook</b> section</td><td>Click "Edit"</td></tr>
        <tr><td><b>B</b></td><td><b>Callback URL</b></td><td style="font-size: 8pt; font-family: Courier;">https://ianimmelman89.app.n8n.cloud/webhook/whatsapp-webhook</td></tr>
        <tr><td><b>C</b></td><td><b>Verify Token</b></td><td style="font-family: Courier;">whatsapp_multi_agent_verify</td></tr>
        <tr><td><b>D</b></td><td><b>Subscribe to</b></td><td>messages (checkbox)</td></tr>
        <tr><td><b>E</b></td><td>Click</td><td><b>"Verify and Save"</b></td></tr>
    </table>
    <div class="callout-success">If successful, Meta will show a green checkmark next to the webhook.</div>
</div>

<!-- Step 6 -->
<div class="step-card">
    <h3>Step 6 &mdash; Send a Test Message</h3>
    <div class="step-meta">Time: ~1 minute &nbsp;&bull;&nbsp; Owner: You</div>
    <div class="action-item"><span class="arrow">&#9658;</span> Open WhatsApp on your personal phone</div>
    <div class="action-item"><span class="arrow">&#9658;</span> Send <b>"Hello"</b> to the test number Meta gave you</div>
    <div class="action-item"><span class="arrow">&#9658;</span> Wait 5&ndash;10 seconds</div>
    <div class="action-item"><span class="check">&#10003;</span> You should receive an AI-powered response!</div>
    <div class="callout-success"><b>If you got a reply &mdash; the system is LIVE!</b></div>
</div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- PHASE 2                                                -->
<!-- ═══════════════════════════════════════════════════════ -->
<div class="section-purple"><h2>PHASE 2 &mdash; Onboarding Real Estate Agents (~2 min each)</h2></div>
<p><i>Once the system is live, adding each new agent is just a database row. No workflow changes needed.</i></p>

<!-- How It Works -->
<div class="step-card-purple">
    <h3>How It Works</h3>
    <div class="flow-box" style="background: #F5F5F5; text-align: left;">
        <div class="action-item"><span class="arrow">&#9658;</span> Client sends WhatsApp message</div>
        <div class="action-item"><span class="arrow">&#9658;</span> n8n receives it via webhook</div>
        <div class="action-item"><span class="arrow">&#9658;</span> Looks up agent by phone number in Airtable</div>
        <div class="action-item"><span class="arrow">&#9658;</span> GPT-4 analyzes the message + generates a reply</div>
        <div class="action-item"><span class="arrow">&#9658;</span> Sends response back via WhatsApp</div>
        <div class="action-item"><span class="arrow">&#9658;</span> Logs everything (message, response, timing)</div>
    </div>
    <div class="callout">Each agent gets their own WhatsApp number, AI settings, and conversation logs.<br/><b>Zero code changes. One Airtable row = one active agent.</b></div>
</div>

<!-- Step A -->
<div class="step-card-purple">
    <h3>Step A &mdash; Register a WhatsApp Number for the Agent</h3>
    <div class="step-meta">Where: developers.facebook.com &rarr; Your App &rarr; WhatsApp &rarr; Getting Started</div>
    <table>
        <tr><th>#</th><th>Action</th></tr>
        <tr><td>1</td><td>Click <b>"Add phone number"</b></td></tr>
        <tr><td>2</td><td>Enter the agent's business phone number (with country code)</td></tr>
        <tr><td>3</td><td>Verify via SMS or voice call</td></tr>
        <tr><td>4</td><td>Copy the new <b>Phone Number ID</b></td></tr>
    </table>
</div>

<div class="page-break"></div>

<!-- Step B -->
<div class="step-card-purple">
    <h3>Step B &mdash; Collect Agent Information</h3>
    <p>Share the following with Claude for each new agent:</p>
    <table>
        <tr><th>Field</th><th>Example (Real Estate)</th><th>Required?</th></tr>
        <tr><td><b>Full Name</b></td><td>Sarah Johnson</td><td><span class="check">YES</span></td></tr>
        <tr><td><b>Email</b></td><td>sarah@remax-capetown.co.za</td><td><span class="check">YES</span></td></tr>
        <tr><td><b>WhatsApp Number</b></td><td>+27821234567</td><td><span class="check">YES</span> (with + and country code)</td></tr>
        <tr><td><b>WhatsApp Business Account ID</b></td><td>123456789012345</td><td><span class="check">YES</span></td></tr>
        <tr><td><b>Phone Number ID</b></td><td>987654321098765</td><td><span class="check">YES</span> (from Step A)</td></tr>
        <tr><td><b>Access Token</b></td><td>EAAx...</td><td><span class="check">YES</span></td></tr>
        <tr><td><b>Company Name</b></td><td>RE/MAX Cape Town</td><td><span class="check">YES</span></td></tr>
        <tr><td><b>Region</b></td><td>South Africa</td><td><span class="check">YES</span></td></tr>
        <tr><td><b>Language</b></td><td>en</td><td><span class="check">YES</span> (ISO code)</td></tr>
        <tr><td><b>Timezone</b></td><td>Africa/Johannesburg</td><td><span class="check">YES</span> (IANA format)</td></tr>
    </table>
</div>

<!-- Step C -->
<div class="step-card-purple">
    <h3>Step C &mdash; Claude Creates the Agent Record (Automated)</h3>
    <div class="step-meta">Claude adds one row to the Agents table in Airtable.</div>
    <div class="action-item"><span class="check">&#10003;</span> Agent is immediately active</div>
    <div class="action-item"><span class="check">&#10003;</span> AI auto-reply is enabled by default</div>
    <div class="action-item"><span class="check">&#10003;</span> All messages are logged automatically</div>
    <div class="action-item"><span class="check">&#10003;</span> No workflow restart needed</div>
</div>

<!-- Step D -->
<div class="step-card-purple">
    <h3>Step D &mdash; Test the Agent's Number</h3>
    <div class="action-item"><span class="arrow">&#9658;</span> Send a WhatsApp message to the agent's number</div>
    <div class="action-item"><span class="arrow">&#9658;</span> Example: <i>"Hi, I'm looking for a 3-bedroom house in Sea Point"</i></div>
    <div class="action-item"><span class="arrow">&#9658;</span> Wait 5&ndash;10 seconds</div>
    <div class="action-item"><span class="check">&#10003;</span> AI should respond with helpful property-related info</div>
    <div class="callout-success"><b>Agent is live!</b> Repeat Steps A&ndash;D for each new real estate agent.</div>
</div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- OPTIONAL SETTINGS                                      -->
<!-- ═══════════════════════════════════════════════════════ -->
<div class="section-amber"><h2>Optional Settings (Per Agent)</h2></div>
<p><i>These have sensible defaults. Only change if needed.</i></p>

<table>
    <tr><th>Setting</th><th>Default</th><th>When to Change</th></tr>
    <tr><td><b>AI Model</b></td><td>GPT-4 (via OpenRouter)</td><td>Want cheaper/faster? Try gpt-3.5-turbo</td></tr>
    <tr><td><b>AI Temperature</b></td><td>0.7</td><td>Lower (0.3) = more precise. Higher (0.9) = more creative</td></tr>
    <tr><td><b>Max Response Length</b></td><td>300 chars</td><td>Increase for detailed property descriptions</td></tr>
    <tr><td><b>Auto-Reply</b></td><td>Enabled</td><td>Disable for manual-only agents</td></tr>
    <tr><td><b>Online Threshold</b></td><td>5 minutes</td><td>How long before "agent is away" kicks in</td></tr>
    <tr><td><b>Airtable Full Access</b></td><td>Yes</td><td>Restrict if agent shouldn't see all data</td></tr>
    <tr><td><b>Google Calendar ID</b></td><td>primary</td><td>Change if agent uses a separate calendar</td></tr>
</table>

<div class="callout">Tell Claude which settings to change and for which agent. It's a one-field update.</div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- TROUBLESHOOTING                                        -->
<!-- ═══════════════════════════════════════════════════════ -->
<div class="page-break"></div>
<div class="section-red"><h2>Troubleshooting</h2></div>

<div class="step-card" style="border-left-color: {TROUBLESHOOT_RED};">
    <h3>"I sent a message but got no reply"</h3>
    <table>
        <tr><th>Check</th><th>How</th></tr>
        <tr><td>Is the workflow active?</td><td>n8n dashboard &rarr; workflow should show green "Active"</td></tr>
        <tr><td>Is the agent record active?</td><td>Airtable &rarr; Agents &rarr; <code>is_active</code> = <code>true</code></td></tr>
        <tr><td>Is auto-reply on?</td><td>Airtable &rarr; Agents &rarr; <code>auto_reply</code> = <code>true</code></td></tr>
        <tr><td>Is the webhook connected?</td><td>Meta App &rarr; WhatsApp &rarr; Configuration &rarr; green checkmark</td></tr>
        <tr><td>Is the phone number correct?</td><td>Airtable &rarr; Agents &rarr; <code>whatsapp_number</code> matches exactly</td></tr>
    </table>
</div>

<div class="step-card" style="border-left-color: {TROUBLESHOOT_RED};">
    <h3>"Token expired" / "Unauthorized" errors</h3>
    <div class="action-item"><span class="arrow">&#9658;</span> Go to developers.facebook.com &rarr; Your App &rarr; WhatsApp &rarr; Getting Started</div>
    <div class="action-item"><span class="arrow">&#9658;</span> Click <b>"Generate"</b> for a new temporary token</div>
    <div class="action-item"><span class="arrow">&#9658;</span> Share the new token with Claude to update Airtable</div>
    <div class="callout-warn"><b>For production:</b> Set up a System User token (never expires) via Meta Business Settings &rarr; System Users &rarr; Generate Token</div>
</div>

<div class="step-card" style="border-left-color: {TROUBLESHOOT_RED};">
    <h3>"Group messages are being ignored"</h3>
    <div class="callout-success">This is <b>by design</b>. The workflow only processes direct (1-on-1) messages. Group messages are filtered out at Step 2 of the pipeline.</div>
</div>

<div class="step-card" style="border-left-color: {TROUBLESHOOT_RED};">
    <h3>"Agent shows as offline"</h3>
    <p>The system uses a 5-minute online threshold by default. The agent's app needs to ping the status webhook:</p>
    <div class="code-block">
        POST https://ianimmelman89.app.n8n.cloud/webhook/agent-status<br/>
        Body: {{ "agent_id": "agent_001", "status": "online" }}
    </div>
</div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- QUICK REFERENCE                                        -->
<!-- ═══════════════════════════════════════════════════════ -->
<div class="section-gray"><h2>Quick Reference</h2></div>

<h3 style="color: #37474F;">Airtable Tables</h3>
<table>
    <tr><th>Table</th><th>Purpose</th><th>ID</th></tr>
    <tr><td><b>Agents</b></td><td>Agent config + WhatsApp credentials</td><td><code>tblHCkr9weKQAHZoB</code></td></tr>
    <tr><td><b>Message Log</b></td><td>All processed messages</td><td><code>tbl72lkYHRbZHIK4u</code></td></tr>
    <tr><td><b>Blocked Messages</b></td><td>Filtered/blocked messages</td><td><code>tbluSD0m6zIAVmsGm</code></td></tr>
    <tr><td><b>Errors</b></td><td>System error tracking</td><td><code>tblM6CJi7pyWQWmeD</code></td></tr>
</table>

<h3 style="color: #37474F;">n8n Credentials</h3>
<table>
    <tr><th>Credential</th><th>Used By</th></tr>
    <tr><td>Whatsapp Multi Agent (Airtable)</td><td>11 Airtable nodes</td></tr>
    <tr><td>OpenRouter</td><td>AI Analysis node</td></tr>
    <tr><td>Twilio</td><td>Send WhatsApp node</td></tr>
    <tr><td>Header Auth account 2</td><td>Get Contact Info node</td></tr>
</table>

<h3 style="color: #37474F;">Key URLs</h3>
<table>
    <tr><th>URL</th><th>Purpose</th></tr>
    <tr><td style="font-family: Courier; font-size: 8pt;">https://ianimmelman89.app.n8n.cloud/webhook/whatsapp-webhook</td><td>Main message webhook</td></tr>
    <tr><td style="font-family: Courier; font-size: 8pt;">https://ianimmelman89.app.n8n.cloud/webhook/agent-status</td><td>Agent online/offline status</td></tr>
    <tr><td style="font-family: Courier; font-size: 8pt;">https://ianimmelman89.app.n8n.cloud/webhook/agent-register</td><td>Self-registration (extended version)</td></tr>
</table>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- VISUAL FLOW SUMMARY                                    -->
<!-- ═══════════════════════════════════════════════════════ -->
<div class="page-break"></div>
<div class="section-green"><h2>Full Onboarding Flow &mdash; Visual Summary</h2></div>
<br/>

<div class="flow-box flow-waiting">
    <b style="color: #F57F17; font-size: 12pt;">WAITING</b><br/>
    <span style="font-size: 10pt;">Facebook Business Verification</span>
</div>

<div class="flow-arrow">&darr;&nbsp;&nbsp;Approved!</div>

<div class="flow-box flow-phase1">
    <b style="color: {PHASE1_BLUE}; font-size: 12pt;">PHASE 1: First-Time Setup (~25 min)</b><br/><br/>
    <table style="margin: 0 auto; width: 80%; text-align: left;">
        <tr><td>Step 1</td><td><span class="check">&#10003;</span> Business verified</td></tr>
        <tr><td>Step 2</td><td>Twilio sandbox connected</td></tr>
        <tr><td>Step 3</td><td>3 WhatsApp values collected</td></tr>
        <tr><td>Step 4</td><td>Claude configures Airtable</td></tr>
        <tr><td>Step 5</td><td>Meta webhook &rarr; n8n</td></tr>
        <tr><td>Step 6</td><td>Test message sent &amp; replied</td></tr>
    </table>
</div>

<div class="flow-arrow">&darr;&nbsp;&nbsp;System is LIVE!</div>

<div class="flow-box flow-phase2">
    <b style="color: {PHASE2_PURPLE}; font-size: 12pt;">PHASE 2: Add Agents (~2 min each)</b><br/><br/>
    <table style="margin: 0 auto; width: 80%; text-align: left;">
        <tr><td>Step A</td><td>Register WhatsApp number in Meta</td></tr>
        <tr><td>Step B</td><td>Collect agent info (10 fields)</td></tr>
        <tr><td>Step C</td><td>Claude adds Airtable row</td></tr>
        <tr><td>Step D</td><td>Test message &rarr; AI replies</td></tr>
    </table>
    <br/>
    <b style="color: {PHASE2_PURPLE};">Repeat for each new real estate agent</b>
</div>

<br/><br/>

<hr/>
<div class="footer">
    WhatsApp Multi-Agent System (Optimized) &mdash; 36 nodes, n8n Cloud &nbsp;|&nbsp; Last updated: February 2026
</div>

<!-- Footer for page numbers -->
<div id="page-footer">
    <div class="footer">Agent Onboarding Guide &mdash; AnyVision Media</div>
</div>

</body>
</html>
"""


def generate_pdf():
    with open(OUTPUT_PDF, "w+b") as pdf_file:
        status = pisa.CreatePDF(HTML_CONTENT, dest=pdf_file)

    if status.err:
        print(f"ERROR: PDF generation failed with {status.err} errors")
        return False

    size_kb = os.path.getsize(OUTPUT_PDF) / 1024
    print(f"PDF generated successfully: {OUTPUT_PDF}")
    print(f"File size: {size_kb:.1f} KB")
    return True


if __name__ == "__main__":
    generate_pdf()
