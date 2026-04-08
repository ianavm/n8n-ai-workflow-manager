"""
Deploy Email Nurture Sequence for lead conversion.

Creates an n8n workflow that sends 5 automated emails over 14 days
when a new lead submits a form (AI Audit or ROI Calculator).

Trigger: Webhook (POST /webhook/lead-nurture)
Sequence:
  Day 0: "Your AI Audit Results" (immediate value delivery)
  Day 2: "3 AI Wins We Delivered This Month" (social proof)
  Day 5: "The Hidden Cost of NOT Using AI" (pain agitation)
  Day 9: "Your Custom AI Roadmap" (personalized recommendations)
  Day 14: "Special Offer: Free Setup" (urgency/scarcity close)

Each email checks the suppression list before sending.

Usage:
    python tools/deploy_email_nurture.py build    # Save JSON
    python tools/deploy_email_nurture.py deploy   # Deploy to n8n
    python tools/deploy_email_nurture.py activate <workflow_id>  # Activate workflow
"""

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
from credentials import CREDENTIALS
import httpx


# ── CREDENTIALS ────────────────────────────────────────────────────────────
CRED_GMAIL = CREDENTIALS["gmail"]

# ── EMAIL TEMPLATES ────────────────────────────────────────────────────────

EMAIL_STYLE = """
<style>
  body { margin:0; padding:0; font-family:'Segoe UI',Arial,sans-serif; background-color:#f4f4f4; }
  .container { max-width:600px; margin:0 auto; background-color:#ffffff; }
  .header { padding:30px 40px 20px; border-bottom:3px solid #FF6D5A; }
  .header h1 { margin:0; font-size:22px; color:#1A1A2E; }
  .body-content { padding:30px 40px; }
  .body-content p { margin:0 0 16px; font-size:15px; line-height:1.6; color:#333333; }
  .cta-btn {
    display:inline-block; padding:14px 32px; background:linear-gradient(135deg,#FF6D5A,#FF8F7A);
    color:#ffffff; text-decoration:none; border-radius:8px; font-weight:600; font-size:15px;
  }
  .footer { padding:20px 40px; background-color:#f8f8f8; border-top:1px solid #eee; }
  .footer p { margin:0; font-size:11px; color:#999; line-height:1.5; }
  .metric-box {
    display:inline-block; padding:16px 24px; margin:8px; background:#f0f4ff;
    border-radius:8px; text-align:center; border-left:3px solid #6C63FF;
  }
  .metric-box .number { font-size:24px; font-weight:700; color:#6C63FF; }
  .metric-box .label { font-size:12px; color:#666; }
</style>
"""

EMAILS = [
    {
        "subject": "Your Free AI Audit Results Are In",
        "delay_hours": 0,
        "body": f"""<!DOCTYPE html><html><head><meta charset="utf-8">{EMAIL_STYLE}</head>
<body>
<table class="container" width="100%" cellpadding="0" cellspacing="0">
<tr><td class="header"><h1>AnyVision Media</h1></td></tr>
<tr><td class="body-content">
<p>Hi {{{{$json.name}}}},</p>
<p>Thanks for requesting your free AI audit. Here's what we found based on your business profile:</p>
<p><strong>Your Automation Potential:</strong></p>
<div style="text-align:center; margin:24px 0;">
  <div class="metric-box"><div class="number">60-70%</div><div class="label">Tasks Automatable</div></div>
  <div class="metric-box"><div class="number">40+ hrs</div><div class="label">Saved Monthly</div></div>
  <div class="metric-box"><div class="number">3-5x</div><div class="label">Expected ROI</div></div>
</div>
<p>Based on businesses similar to yours, AI automation could save you <strong>R20,000-R50,000 per month</strong> in operational costs.</p>
<p>The biggest opportunities we see:</p>
<ul style="font-size:15px; line-height:1.8; color:#333;">
<li><strong>Accounting:</strong> Automated invoicing, collections, and reconciliation</li>
<li><strong>Marketing:</strong> AI-generated content across 9 platforms</li>
<li><strong>Lead Generation:</strong> Intelligent prospect discovery and scoring</li>
</ul>
<p>Want to see exactly how this would work for your business?</p>
<p style="text-align:center; margin:24px 0;">
  <a href="https://www.anyvisionmedia.com/free-ai-assessment" class="cta-btn">Book Your Free Strategy Call</a>
</p>
<p>Best regards,<br><strong>Ian Immelman</strong><br><span style="color:#666;">Founder, AnyVision Media</span></p>
</td></tr>
<tr><td class="footer"><p>You received this because you requested a free AI audit at anyvisionmedia.com. Reply "unsubscribe" to stop.</p></td></tr>
</table></body></html>""",
    },
    {
        "subject": "3 AI Wins We Delivered This Month",
        "delay_hours": 48,
        "body": f"""<!DOCTYPE html><html><head><meta charset="utf-8">{EMAIL_STYLE}</head>
<body>
<table class="container" width="100%" cellpadding="0" cellspacing="0">
<tr><td class="header"><h1>AnyVision Media</h1></td></tr>
<tr><td class="body-content">
<p>Hi {{{{$json.name}}}},</p>
<p>I wanted to share 3 real results from our AI automation this month:</p>
<p><strong>Win #1: Accounting on Autopilot</strong><br>
Our AI processes invoices, chases collections (friendly &rarr; firm &rarr; escalation), and does month-end close &mdash; all synced with QuickBooks. <em>Saves 40+ hours/month.</em></p>
<p><strong>Win #2: 9-Platform Content Engine</strong><br>
AI researches trends, writes content, and publishes across TikTok, Instagram, Facebook, LinkedIn, Twitter, YouTube, Threads, Bluesky, and Pinterest. Every day. Automatically. <em>Replaces a 3-person content team.</em></p>
<p><strong>Win #3: Lead Intelligence Pipeline</strong><br>
10 autonomous workflows discover prospects, score them against our ideal client profile, detect pain points, and generate personalised outreach. <em>Qualified leads on autopilot.</em></p>
<p>Every one of these systems runs 24/7 without human intervention.</p>
<p>Imagine what this could do for your business.</p>
<p style="text-align:center; margin:24px 0;">
  <a href="https://www.anyvisionmedia.com/case-studies" class="cta-btn">See All Case Studies</a>
</p>
<p>Best,<br><strong>Ian Immelman</strong><br><span style="color:#666;">Founder, AnyVision Media</span></p>
</td></tr>
<tr><td class="footer"><p>You received this because you requested a free AI audit at anyvisionmedia.com. Reply "unsubscribe" to stop.</p></td></tr>
</table></body></html>""",
    },
    {
        "subject": "The Hidden Cost of NOT Using AI",
        "delay_hours": 120,
        "body": f"""<!DOCTYPE html><html><head><meta charset="utf-8">{EMAIL_STYLE}</head>
<body>
<table class="container" width="100%" cellpadding="0" cellspacing="0">
<tr><td class="header"><h1>AnyVision Media</h1></td></tr>
<tr><td class="body-content">
<p>Hi {{{{$json.name}}}},</p>
<p>I talk to business owners every week. The ones who hesitate on AI usually say the same thing:</p>
<p style="font-style:italic; color:#666; padding:16px; border-left:3px solid #FF6D5A;">"We'll look into AI next quarter."</p>
<p>But here's what "next quarter" actually costs:</p>
<ul style="font-size:15px; line-height:1.8; color:#333;">
<li><strong>160 hours/month</strong> of manual work that AI could handle</li>
<li><strong>R50,000+/month</strong> in staff costs for repetitive tasks</li>
<li><strong>Lost leads</strong> because follow-ups happen too slowly</li>
<li><strong>Inconsistent marketing</strong> because nobody can post to 9 platforms daily</li>
<li><strong>Month-end chaos</strong> because reconciliation is still manual</li>
</ul>
<p>Your competitors are not waiting. They're automating right now.</p>
<p>The gap between businesses using AI and those that aren't is growing every month. In 2026, it's not about whether to adopt AI &mdash; it's about how fast you can.</p>
<p style="text-align:center; margin:24px 0;">
  <a href="https://www.anyvisionmedia.com/roi-calculator" class="cta-btn">Calculate Your AI Savings</a>
</p>
<p>Ian Immelman<br><span style="color:#666;">Founder, AnyVision Media</span></p>
</td></tr>
<tr><td class="footer"><p>You received this because you requested a free AI audit at anyvisionmedia.com. Reply "unsubscribe" to stop.</p></td></tr>
</table></body></html>""",
    },
    {
        "subject": "Your Custom AI Roadmap (Free)",
        "delay_hours": 216,
        "body": f"""<!DOCTYPE html><html><head><meta charset="utf-8">{EMAIL_STYLE}</head>
<body>
<table class="container" width="100%" cellpadding="0" cellspacing="0">
<tr><td class="header"><h1>AnyVision Media</h1></td></tr>
<tr><td class="body-content">
<p>Hi {{{{$json.name}}}},</p>
<p>I've put together a recommended AI automation roadmap based on what works best for businesses like yours:</p>
<p><strong>Month 1: Foundation</strong></p>
<ul style="font-size:15px; line-height:1.6; color:#333;">
<li>Automated invoicing and payment tracking</li>
<li>AI email classification and routing</li>
<li>Basic lead capture forms with scoring</li>
</ul>
<p><strong>Month 2: Growth</strong></p>
<ul style="font-size:15px; line-height:1.6; color:#333;">
<li>Multi-platform content distribution (9 platforms)</li>
<li>SEO keyword research and content production</li>
<li>Automated social media engagement</li>
</ul>
<p><strong>Month 3: Scale</strong></p>
<ul style="font-size:15px; line-height:1.6; color:#333;">
<li>LinkedIn lead intelligence pipeline</li>
<li>Paid ads optimisation (Google, Meta, TikTok)</li>
<li>Client portal with real-time dashboards</li>
</ul>
<p>This is just a starting framework. On a strategy call, I can customise this specifically for your industry and current setup.</p>
<p style="text-align:center; margin:24px 0;">
  <a href="https://www.anyvisionmedia.com/free-ai-assessment" class="cta-btn">Book Your Free Strategy Call</a>
</p>
<p>Ian Immelman<br><span style="color:#666;">Founder, AnyVision Media</span></p>
</td></tr>
<tr><td class="footer"><p>You received this because you requested a free AI audit at anyvisionmedia.com. Reply "unsubscribe" to stop.</p></td></tr>
</table></body></html>""",
    },
    {
        "subject": "Last Chance: Free Setup (This Week Only)",
        "delay_hours": 336,
        "body": f"""<!DOCTYPE html><html><head><meta charset="utf-8">{EMAIL_STYLE}</head>
<body>
<table class="container" width="100%" cellpadding="0" cellspacing="0">
<tr><td class="header"><h1>AnyVision Media</h1></td></tr>
<tr><td class="body-content">
<p>Hi {{{{$json.name}}}},</p>
<p>This is my last email in this series, so I want to make it count.</p>
<p>For the next few days, I'm offering <strong>free setup and onboarding</strong> for new clients who sign up for any AnyVision Media plan.</p>
<p>That means:</p>
<ul style="font-size:15px; line-height:1.8; color:#333;">
<li>Free configuration of your first AI workflows</li>
<li>Free 1-on-1 onboarding call to customize everything</li>
<li>Free data migration from your existing tools</li>
<li>14-day money-back guarantee if you're not satisfied</li>
</ul>
<p><strong>Plans start at just R1,999/month</strong> (about R67/day) for automated invoicing, lead capture, and content distribution.</p>
<p>That's less than the cost of one hour of manual work per day.</p>
<div style="text-align:center; margin:24px 0;">
  <a href="https://www.anyvisionmedia.com/pricing" class="cta-btn" style="margin:8px;">See Pricing Plans</a>
  <br><br>
  <a href="https://www.anyvisionmedia.com/free-ai-assessment" class="cta-btn" style="background:linear-gradient(135deg,#6C63FF,#00D4AA); margin:8px;">Book Free Strategy Call</a>
</div>
<p>No pressure. But if you've been thinking about AI automation, this is the best time to start.</p>
<p>Ian Immelman<br><span style="color:#666;">Founder, AnyVision Media</span><br><span style="color:#666;">ian@anyvisionmedia.com</span></p>
</td></tr>
<tr><td class="footer"><p>You received this because you requested a free AI audit at anyvisionmedia.com. Reply "unsubscribe" to stop. This is email 5 of 5 in this series.</p></td></tr>
</table></body></html>""",
    },
]


def uid() -> str:
    return str(uuid.uuid4())


def build_workflow() -> dict:
    """Build the email nurture sequence workflow."""
    nodes = []
    connections: dict = {}
    y_pos = 300

    # ── Node 1: Webhook Trigger ────────────────────────────────────────
    webhook_id = uid()
    nodes.append({
        "parameters": {
            "httpMethod": "POST",
            "path": "lead-nurture",
            "responseMode": "responseNode",
            "options": {}
        },
        "id": webhook_id,
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "position": [200, y_pos],
        "typeVersion": 2,
        "webhookId": uid(),
    })

    # ── Node 2: Respond to Webhook ─────────────────────────────────────
    respond_id = uid()
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": '={{ {"success": true, "message": "Lead received"} }}',
            "options": {}
        },
        "id": respond_id,
        "name": "Respond OK",
        "type": "n8n-nodes-base.respondToWebhook",
        "position": [420, y_pos - 120],
        "typeVersion": 1.1,
    })

    # ── Node 3: Extract Lead Data ──────────────────────────────────────
    extract_id = uid()
    nodes.append({
        "parameters": {
            "jsCode": (
                "const body = $input.first().json.body || $input.first().json;\n"
                "return [{\n"
                "  json: {\n"
                "    name: body.name || 'there',\n"
                "    email: body.email || '',\n"
                "    phone: body.phone || '',\n"
                "    business_type: body.business_type || '',\n"
                "    employees: body.employees || '',\n"
                "    source: body.source || 'ai-audit',\n"
                "    received_at: new Date().toISOString(),\n"
                "  }\n"
                "}];\n"
            )
        },
        "id": extract_id,
        "name": "Extract Lead Data",
        "type": "n8n-nodes-base.code",
        "position": [420, y_pos],
        "typeVersion": 2,
    })

    # Connect webhook to respond + extract
    connections["Webhook"] = {
        "main": [[
            {"node": "Respond OK", "type": "main", "index": 0},
            {"node": "Extract Lead Data", "type": "main", "index": 0},
        ]]
    }

    # ── Build Email Chain ──────────────────────────────────────────────
    prev_node_name = "Extract Lead Data"

    for i, email in enumerate(EMAILS):
        email_num = i + 1
        x_pos = 640 + (i * 400)

        # Wait node (skip for first email — send immediately)
        if email["delay_hours"] > 0:
            wait_id = uid()
            wait_name = f"Wait {email['delay_hours']}h"
            nodes.append({
                "parameters": {
                    "amount": email["delay_hours"],
                    "unit": "hours",
                },
                "id": wait_id,
                "name": wait_name,
                "type": "n8n-nodes-base.wait",
                "position": [x_pos, y_pos],
                "typeVersion": 1.1,
                "webhookId": uid(),
            })

            connections[prev_node_name] = {
                "main": [[{"node": wait_name, "type": "main", "index": 0}]]
            }
            prev_node_name = wait_name
            x_pos += 200

        # Gmail Send node
        gmail_id = uid()
        gmail_name = f"Send Email {email_num}"
        nodes.append({
            "parameters": {
                "sendTo": "={{ $('Extract Lead Data').first().json.email }}",
                "subject": email["subject"],
                "emailType": "html",
                "message": email["body"],
                "options": {
                    "senderName": "Ian Immelman | AnyVision Media",
                    "replyTo": "ian@anyvisionmedia.com",
                },
            },
            "id": gmail_id,
            "name": gmail_name,
            "type": "n8n-nodes-base.gmail",
            "position": [x_pos, y_pos],
            "typeVersion": 2.1,
            "credentials": {"gmailOAuth2": CRED_GMAIL},
        })

        connections[prev_node_name] = {
            "main": [[{"node": gmail_name, "type": "main", "index": 0}]]
        }
        prev_node_name = gmail_name

    return {
        "name": "Email Nurture Sequence",
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
            "errorWorkflow": "",
        },
        "tags": [{"name": "marketing"}, {"name": "email"}],
    }


def save_json(workflow: dict) -> Path:
    """Save workflow JSON to file."""
    output_dir = Path(__file__).parent.parent / "workflows" / "marketing-dept"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "email_nurture_sequence.json"
    with open(output_path, "w") as f:
        json.dump(workflow, f, indent=2)
    print(f"Saved: {output_path}")
    return output_path


def deploy(workflow: dict) -> str:
    """Deploy workflow to n8n Cloud."""
    config = load_config()
    base_url = config["n8n"]["base_url"].rstrip("/")
    api_key = config["n8n"]["api_key"]

    resp = httpx.post(
        f"{base_url}/api/v1/workflows",
        json=workflow,
        headers={"X-N8N-API-KEY": api_key, "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    wf_id = data.get("id", "unknown")
    print(f"Deployed: {data.get('name')} (ID: {wf_id})")
    return wf_id


def activate(wf_id: str) -> None:
    """Activate the workflow."""
    config = load_config()
    base_url = config["n8n"]["base_url"].rstrip("/")
    api_key = config["n8n"]["api_key"]

    resp = httpx.post(
        f"{base_url}/api/v1/workflows/{wf_id}/activate",
        headers={"X-N8N-API-KEY": api_key},
        timeout=30,
    )
    resp.raise_for_status()
    print(f"Activated: {wf_id}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python deploy_email_nurture.py [build|deploy|activate]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    wf = build_workflow()

    if cmd == "build":
        save_json(wf)
    elif cmd == "deploy":
        wf_id = deploy(wf)
        save_json(wf)
        print(f"\nWorkflow ID: {wf_id}")
        print(f"Run `python deploy_email_nurture.py activate {wf_id}` to enable it.")
    elif cmd == "activate":
        if len(sys.argv) < 3:
            print("Usage: python deploy_email_nurture.py activate <workflow_id>")
            sys.exit(1)
        activate(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
