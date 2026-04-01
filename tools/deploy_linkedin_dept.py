"""
AVM LinkedIn Lead Intelligence - Multi-Agent Workflow Builder & Deployer

Builds and deploys 10 n8n workflows (LI-01 through LI-10) for LinkedIn
lead discovery, AI qualification, pain point detection, automation
opportunity mapping, outreach personalization, and CRM pipeline management.

Workflows:
    LI-01: Lead Orchestrator (parent, scheduled)
    LI-02: Lead Discovery & Collection (sub-workflow)
    LI-03: Data Enrichment (sub-workflow, AI)
    LI-04: ICP Scoring (sub-workflow, AI)
    LI-05: Pain Point Detection (sub-workflow, AI)
    LI-06: Automation Opportunity Mapping (sub-workflow, AI)
    LI-07: Outreach Personalization (sub-workflow, AI)
    LI-08: Lead Prioritization & QA (sub-workflow)
    LI-09: CRM Sync & Dashboard (sub-workflow)
    LI-10: Feedback & Learning Loop (webhook + scheduled, AI)

Usage:
    python tools/deploy_linkedin_dept.py build              # Build all JSONs
    python tools/deploy_linkedin_dept.py build li01          # Build LI-01 only
    python tools/deploy_linkedin_dept.py deploy              # Build + Deploy (inactive)
    python tools/deploy_linkedin_dept.py activate            # Build + Deploy + Activate
"""

import json
import sys
import uuid
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))
from credentials import CREDENTIALS


# ======================================================================
# CREDENTIAL CONSTANTS
# ======================================================================

CRED_OPENROUTER = CREDENTIALS["openrouter"]
CRED_AIRTABLE = CREDENTIALS["airtable"]
CRED_GMAIL = CREDENTIALS["gmail"]
CRED_TELEGRAM = CREDENTIALS["telegram"]


# ======================================================================
# AIRTABLE TABLE IDS (from .env, populated by setup script)
# ======================================================================

MARKETING_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")

TABLE_CAMPAIGNS = os.getenv("LI_TABLE_CAMPAIGNS", "REPLACE_AFTER_SETUP")
TABLE_LEADS = os.getenv("LI_TABLE_LEADS", "REPLACE_AFTER_SETUP")
TABLE_ENRICHMENT = os.getenv("LI_TABLE_ENRICHMENT", "REPLACE_AFTER_SETUP")
TABLE_SCORES = os.getenv("LI_TABLE_SCORES", "REPLACE_AFTER_SETUP")
TABLE_PAIN_POINTS = os.getenv("LI_TABLE_PAIN_POINTS", "REPLACE_AFTER_SETUP")
TABLE_OPPORTUNITIES = os.getenv("LI_TABLE_OPPORTUNITIES", "REPLACE_AFTER_SETUP")
TABLE_OUTREACH = os.getenv("LI_TABLE_OUTREACH", "REPLACE_AFTER_SETUP")
TABLE_PIPELINE = os.getenv("LI_TABLE_PIPELINE", "REPLACE_AFTER_SETUP")
TABLE_FEEDBACK = os.getenv("LI_TABLE_FEEDBACK", "REPLACE_AFTER_SETUP")
TABLE_AGENT_LOGS = os.getenv("LI_TABLE_AGENT_LOGS", "REPLACE_AFTER_SETUP")


# ======================================================================
# CONFIG
# ======================================================================

ALERT_EMAIL = os.getenv("SELFHEALING_ALERT_EMAIL", "ian@anyvisionmedia.com")
OPENROUTER_MODEL = "anthropic/claude-sonnet-4"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
OWNER_TELEGRAM_CHAT_ID = os.getenv("RE_OWNER_TELEGRAM_CHAT_ID", "REPLACE_AFTER_SETUP")


# ======================================================================
# HELPERS
# ======================================================================

def uid() -> str:
    """Generate UUID for node IDs."""
    return str(uuid.uuid4())


def airtable_ref(base_id: str, table_id: str) -> dict:
    """Build Airtable base/table reference dict for node parameters."""
    return {
        "base": {"__rl": True, "value": base_id, "mode": "id"},
        "table": {"__rl": True, "value": table_id, "mode": "id"},
    }


def build_workflow(name: str, nodes: list, connections: dict, **kwargs) -> dict:
    """Assemble a complete n8n workflow JSON."""
    return {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
    }


# ======================================================================
# COMMON NODE BUILDERS
# ======================================================================

def build_sticky_note(name: str, content: str, position: list,
                      width: int = 250, height: int = 160, color: int = 3) -> dict:
    """Build a Sticky Note node for canvas annotation.

    Colors: 1=yellow, 2=blue, 3=pink, 4=green, 5=purple, 6=red, 7=gray
    """
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": position,
        "parameters": {
            "content": content,
            "width": width,
            "height": height,
            "color": color,
        },
    }


def build_code_node(name: str, js_code: str, position: list) -> dict:
    """Build a Code node with JavaScript."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "parameters": {
            "jsCode": js_code,
        },
    }


def build_airtable_search(name: str, base_id: str, table_id: str, formula: str,
                           position: list, sort_field: str = None,
                           sort_desc: bool = False,
                           always_output: bool = False) -> dict:
    """Build an Airtable search node."""
    params = {
        "operation": "search",
        **airtable_ref(base_id, table_id),
        "filterByFormula": formula,
        "options": {},
    }
    if sort_field:
        params["sort"] = {
            "property": [{"field": sort_field, "direction": "desc" if sort_desc else "asc"}]
        }

    node = {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": position,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": params,
    }
    if always_output:
        node["alwaysOutputData"] = True
    return node


def build_airtable_create(name: str, base_id: str, table_id: str,
                           position: list, columns: list = None) -> dict:
    """Build an Airtable create node.

    If columns is provided, it sets explicit field mappings (defineBelow).
    Otherwise the node auto-maps all incoming JSON fields to Airtable columns.

    CRITICAL: The ``columns`` parameter with ``mappingMode`` is REQUIRED for
    Airtable v2.1 create.  Without it the API request body has no ``fields``
    key and Airtable returns "Could not find field 'fields'".
    """
    params = {
        "operation": "create",
        **airtable_ref(base_id, table_id),
        "columns": {
            "mappingMode": "autoMapInputData",
            "value": None,
        },
        "options": {},
    }
    if columns:
        params["columns"] = {
            "mappingMode": "defineBelow",
            "value": columns,
        }

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": position,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": params,
    }


def build_airtable_update(name: str, base_id: str, table_id: str,
                           position: list, matching_columns: list,
                           columns: list = None) -> dict:
    """Build an Airtable update node with matchingColumns."""
    params = {
        "operation": "update",
        **airtable_ref(base_id, table_id),
        "matchingColumns": matching_columns,
        "columns": {
            "mappingMode": "autoMapInputData",
            "value": None,
        },
        "options": {},
    }
    if columns:
        params["columns"] = {"mappingMode": "defineBelow", "value": columns}

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": position,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": params,
    }


def build_openrouter_ai(name: str, system_prompt: str, user_message_expr: str,
                         position: list, max_tokens: int = 1500,
                         temperature: float = 0.3) -> dict:
    """Build an HTTP Request node calling OpenRouter AI."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": position,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "parameters": {
            "method": "POST",
            "url": OPENROUTER_URL,
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "HTTP-Referer", "value": "https://www.anyvisionmedia.com"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": json.dumps({
                "model": OPENROUTER_MODEL,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "={{" + user_message_expr + "}}"},
                ],
            }),
            "options": {"timeout": 60000},
        },
    }


def build_telegram_send(name: str, chat_id_expr: str, message_expr: str,
                         position: list, parse_mode: str = "HTML") -> dict:
    """Build a Telegram sendMessage node."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": position,
        "credentials": {"telegramApi": CRED_TELEGRAM},
        "parameters": {
            "operation": "sendMessage",
            "chatId": chat_id_expr,
            "text": message_expr,
            "additionalFields": {
                "parse_mode": parse_mode,
            },
        },
    }


def build_gmail_send(name: str, to_expr: str, subject_expr: str,
                      body_expr: str, position: list,
                      is_html: bool = True) -> dict:
    """Build a Gmail send node."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": position,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "parameters": {
            "sendTo": to_expr,
            "subject": subject_expr,
            "emailType": "html" if is_html else "text",
            "message": body_expr,
            "options": {},
        },
    }


def build_if_node(name: str, condition_expr: str, position: list,
                   negate: bool = False) -> dict:
    """Build an If node (n8n v2.2 compatible).

    Uses version=2, typeValidation=strict, singleValue for unary boolean ops.
    Output 0 = true branch, Output 1 = false branch.
    """
    operation = "false" if negate else "true"
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": position,
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 2,
                },
                "conditions": [
                    {
                        "leftValue": condition_expr,
                        "operator": {
                            "type": "boolean",
                            "operation": operation,
                            "singleValue": True,
                        },
                    }
                ],
            },
        },
    }


def build_if_number_node(name: str, left_expr: str, right_value: int,
                          operation: str, position: list) -> dict:
    """Build an If node with numeric comparison (n8n v2.2).

    Operations: gt, gte, lt, lte, equals, notEquals
    """
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": position,
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 2,
                },
                "conditions": [
                    {
                        "leftValue": left_expr,
                        "rightValue": right_value,
                        "operator": {
                            "type": "number",
                            "operation": operation,
                        },
                    }
                ],
            },
        },
    }


def build_switch_node(name: str, field_expr: str, rules: list,
                       position: list) -> dict:
    """Build a Switch node for multi-way routing.

    Uses rules.values (NOT rules.rules) per Switch v3.2.
    """
    values = []
    for rule_value in rules:
        values.append({
            "conditions": {
                "conditions": [
                    {
                        "leftValue": field_expr,
                        "rightValue": rule_value,
                        "operator": {"type": "string", "operation": "equals"},
                    }
                ],
            },
        })
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": position,
        "parameters": {
            "rules": {"values": values},
        },
    }


def build_set_node(name: str, assignments: list, position: list) -> dict:
    """Build a Set node (v3.4) with variable assignments.

    assignments: list of dicts with {name, value, type} where type is
    'string', 'number', 'boolean'.
    """
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": position,
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": a["name"],
                        "value": a["value"],
                        "type": a.get("type", "string"),
                    }
                    for a in assignments
                ]
            },
            "includeOtherFields": True,
            "options": {},
        },
    }


def build_execute_workflow_trigger(name: str, position: list) -> dict:
    """Build an Execute Workflow Trigger node (sub-workflow entry point)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.executeWorkflowTrigger",
        "typeVersion": 1.1,
        "position": position,
        "parameters": {"inputSource": "passthrough"},
    }


def build_execute_workflow(name: str, workflow_id: str, position: list) -> dict:
    """Build an Execute Workflow node to call a sub-workflow."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.executeWorkflow",
        "typeVersion": 1.2,
        "position": position,
        "parameters": {
            "workflowId": {"__rl": True, "mode": "id", "value": workflow_id},
            "options": {},
        },
    }


def build_http_request(name: str, method: str, url: str, position: list,
                        auth_type: str = None, cred_type: str = None,
                        cred_ref: dict = None, body: dict = None,
                        headers: list = None) -> dict:
    """Build a generic HTTP Request node."""
    node = {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": position,
        "parameters": {
            "method": method,
            "url": url,
            "options": {"timeout": 30000},
        },
    }
    if auth_type and cred_type and cred_ref:
        node["parameters"]["authentication"] = auth_type
        node["parameters"]["nodeCredentialType"] = cred_type
        node["credentials"] = {cred_type: cred_ref}
    elif cred_ref:
        node["credentials"] = {"httpHeaderAuth": cred_ref}
    if headers:
        node["parameters"]["sendHeaders"] = True
        node["parameters"]["headerParameters"] = {"parameters": headers}
    if body:
        node["parameters"]["sendBody"] = True
        node["parameters"]["specifyBody"] = "json"
        node["parameters"]["jsonBody"] = (
            json.dumps(body) if isinstance(body, dict) else body
        )
    return node


def build_noop(name: str, position: list) -> dict:
    """Build a No Operation node (dead end)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": position,
        "parameters": {},
    }


def build_schedule_trigger(name: str, cron: str, position: list) -> dict:
    """Build a Schedule Trigger node (v1.2) with cron expression."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": position,
        "parameters": {
            "rule": {"interval": [{"field": "cronExpression", "expression": cron}]},
        },
    }


def build_manual_trigger(name: str, position: list) -> dict:
    """Build a Manual Trigger node (v1)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": position,
        "parameters": {},
    }


def build_webhook_trigger(name: str, path: str, position: list) -> dict:
    """Build a Webhook trigger node (v2)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": position,
        "webhookId": uid(),
        "parameters": {
            "path": path,
            "httpMethod": "POST",
            "responseMode": "lastNode",
        },
    }


def build_merge_node(name: str, position: list, mode: str = "append") -> dict:
    """Build a Merge node (v3) with configurable mode."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.merge",
        "typeVersion": 3,
        "position": position,
        "parameters": {"mode": mode},
    }


def build_split_in_batches(name: str, position: list,
                            batch_size: int = 1) -> dict:
    """Build a Split In Batches node (v3)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.splitInBatches",
        "typeVersion": 3,
        "position": position,
        "parameters": {"batchSize": batch_size, "options": {}},
    }


def build_wait_node(name: str, position: list, seconds: int = 3) -> dict:
    """Build a Wait node (v1.1) with configurable delay."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.wait",
        "typeVersion": 1.1,
        "position": position,
        "parameters": {
            "amount": seconds,
            "unit": "seconds",
        },
    }


def build_error_trigger(name: str, position: list) -> dict:
    """Build an Error Trigger node (v1)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.errorTrigger",
        "typeVersion": 1,
        "position": position,
        "parameters": {},
    }


def build_respond_to_webhook(name: str, position: list) -> dict:
    """Build a Respond to Webhook node (v1.1)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": position,
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ $json }}",
        },
    }


# ======================================================================
# AI SYSTEM PROMPTS
# ======================================================================

LI03_ENRICHMENT_PROMPT = r"""You are a business intelligence analyst for AnyVision Media, an AI automation agency in South Africa.

Given raw HTML content from a company website, extract structured business intelligence.

Extract These Fields:
1. company_description: 2-3 sentence summary of what the company does
2. key_services: array of main services/products offered
3. business_model: one of "B2B", "B2C", "B2B2C", "Marketplace", "SaaS", "Agency", "Retail", "Manufacturing", "Services", "Unknown"
4. employee_estimate: one of "1-10", "11-50", "51-200", "201-500", "500+"
5. tech_stack_hints: array of technologies detected (CMS, analytics, chat widgets, etc.)
6. has_blog: boolean
7. social_presence: object with boolean for each platform {linkedin, facebook, instagram, twitter, youtube}
8. digital_presence_score: 0-100 based on website quality, social links, blog, contact forms
9. website_quality_score: 0-100

Scoring Rubric for digital_presence_score:
- Has modern website: +20
- Has blog/content: +15
- Has 3+ social media links: +15
- Has contact form: +10
- Has chat widget: +10
- Has SSL (https): +10
- Has clear service pages: +10
- Has testimonials/case studies: +10

Output Format (JSON only, no markdown fences):
{"company_description":"...","key_services":[...],"business_model":"...","employee_estimate":"...","tech_stack_hints":[...],"has_blog":true,"social_presence":{"linkedin":true},"digital_presence_score":75,"website_quality_score":60}"""

LI04_ICP_SCORING_PROMPT = r"""You are an ICP (Ideal Customer Profile) scoring specialist for AnyVision Media, an AI workflow automation agency in South Africa.

AnyVision Media ICP:
- Decision-makers (CEO, COO, CTO, MD, Operations Director, Marketing Director) at SMBs
- Company size: 10-500 employees
- Industries: Professional services, real estate, e-commerce, healthcare admin, logistics, finance, hospitality, education
- Located in South Africa (Johannesburg/Gauteng preferred) or SADC region
- Shows signs of manual processes, scaling challenges, or tech adoption interest
- NOT: competitors (agencies, dev shops), job seekers, students, enterprise (5000+ employees)

Scoring Weights:
- Decision Maker Role (20%): CEO/MD/COO=20, Director/VP=16, Manager=12, Other=5
- Company Size Fit (15%): Sweet spot 20-200 employees=15, 10-20 or 200-500=10, outside=3
- Industry Fit (15%): Core industries=15, Adjacent=10, Poor fit=3
- Pain Indicators (20%): Strong signals=20, Moderate=12, Weak=5
- Automation Potential (20%): High=20, Medium=12, Low=5
- Engagement Likelihood (10%): Active LinkedIn presence=10, Moderate=6, Low=2

Red Flags (auto-disqualify or reduce score):
- Competitor (digital agency, automation company): DISQUALIFY
- Job seeker / "Open to Work": DISQUALIFY
- Student / intern: DISQUALIFY
- Enterprise (>5000 employees): reduce by 50%
- No company website: reduce by 20%
- Non-South African without SADC presence: reduce by 30%

Output Format (JSON only, no markdown fences):
{"total_score":78,"decision_maker_score":16,"company_size_score":15,"industry_score":12,"pain_indicator_score":15,"automation_potential_score":12,"engagement_likelihood_score":8,"confidence":0.82,"priority_band":"High","red_flags":[],"reasoning":"explanation","disqualified":false,"disqualify_reason":null}"""

LI05_PAIN_DETECTION_PROMPT = r"""You are a business operations analyst specializing in identifying automation opportunities for South African SMBs.

Given a lead's profile and their company's enrichment data, identify 3-7 likely operational pain points that AnyVision Media's AI automation services could address.

Pain Point Categories:
1. Manual_Processes: Repetitive data entry, manual reporting, paper-based workflows
2. Data_Silos: Disconnected systems, manual data transfer between platforms
3. Customer_Experience: Slow response times, inconsistent communication, no self-service
4. Reporting_Visibility: No real-time dashboards, manual report generation
5. Communication_Gaps: Internal miscommunication, missed follow-ups, no CRM
6. Scaling_Bottleneck: Processes that don't scale, hiring to solve process problems
7. Cost_Inefficiency: Overstaffing for admin tasks, duplicate tool subscriptions

Output (JSON only, no markdown fences):
{"pain_points":[{"pain_point":"description","category":"Manual_Processes","severity":8,"confidence":0.75,"evidence":"data suggesting this","automation_category":"workflow_automation"}],"summary":"overall pain assessment"}"""

LI06_OPPORTUNITY_MAPPING_PROMPT = r"""You are a solutions architect for AnyVision Media, an AI workflow automation agency in South Africa.

AnyVision Media Service Packages:
- Lite (R1,999/mo): 1 automated workflow, basic chatbot, email automation, monthly reporting
- Growth (R4,999/mo): 3 workflows, AI chatbot, CRM integration, social media automation
- Pro (R14,999/mo): Unlimited workflows, custom AI agents, full system integration
- Enterprise (R29,999/mo): Dedicated AI architect, custom development, white-label

AnyVision Media Capabilities:
- n8n workflow automation (any business process)
- AI chatbots (WhatsApp, website, Telegram)
- CRM setup and automation (Airtable, HubSpot)
- Document processing (invoices, contracts, compliance)
- Email management and classification
- Social media automation
- Reporting dashboards
- Lead generation automation
- Accounting automation

Output (JSON only, no markdown fences):
{"opportunities":[{"solution_name":"AI Email Triage","pain_points_addressed":["Communication_Gaps"],"roi_hypothesis":"Reduce email response time by 60%","suggested_package":"Growth_R4999","implementation_complexity":"Moderate","confidence":0.8}],"recommended_package":"Growth_R4999","estimated_monthly_value_to_client_zar":12000,"pitch_angle":"hook for this client"}"""

LI07_OUTREACH_PROMPT = r"""You are a B2B outreach copywriter for AnyVision Media, an AI automation agency in South Africa founded by Ian Immelman.

Tone Guidelines:
- Professional and conversational (NOT salesy or spammy)
- Value-first: lead with insight, not a pitch
- Specific: reference their company, role, or industry
- No buzzwords: avoid "synergy", "leverage", "revolutionize"
- South African English (organised, behaviour, colour)

Generate:
1. connection_message (STRICT MAX 300 characters including spaces): observation + pain point + soft CTA
2. follow_up_1 (max 500 chars): thank + insight + case study mention + soft CTA
3. follow_up_2 (max 500 chars): different angle + value offer (free audit, guide)
4. short_pitch (100-200 words): Problem -> Solution -> Proof -> CTA
5. email_draft: subject line + body (200-300 words), specific ROI mention, clear CTA
6. personalization_score (0-100)

Output (JSON only, no markdown fences):
{"connection_message":"...","follow_up_1":"...","follow_up_2":"...","short_pitch":"...","email_draft":{"subject":"...","body":"..."},"personalization_score":82}"""

LI10_LEARNING_PROMPT = r"""You are a sales intelligence analyst for AnyVision Media.

Analyze lead outcome records to identify patterns in successful vs lost leads.

Analyze:
1. Which ICP score ranges correlate with wins vs losses?
2. Which industries have highest conversion rates?
3. Which pain point categories lead to deals most often?
4. Which package tiers are most popular?
5. What outreach messages got the best response rates?
6. Are there any red flags to add to the ICP?
7. Are there scoring weight adjustments needed?

Output (JSON only, no markdown fences):
{"win_patterns":["pattern"],"loss_patterns":["pattern"],"icp_refinements":[{"field":"industry","suggestion":"Add hospitality","evidence":"3/5 wins"}],"scoring_adjustments":[{"weight":"pain_indicators","current":20,"suggested":25,"reasoning":"..."}],"top_performing_industries":["industry"],"recommended_actions":["action"],"summary":"executive summary"}"""


# ======================================================================
# JAVASCRIPT CODE NODE CONSTANTS
# ======================================================================

ERROR_HANDLER_CODE = r"""const error = $input.first().json;
const workflowName = error.workflow?.name || 'Unknown';
const errorMsg = error.execution?.error?.message || 'Unknown error';
const lastNode = error.execution?.lastNodeExecuted || 'Unknown';
const execUrl = error.execution?.url || '';
const now = new Date().toISOString();
return {
  json: {
    log_id: `ERR-${Date.now().toString(36)}`.toUpperCase(),
    workflow: workflowName,
    lead_id: '',
    action: 'Error',
    status: 'Failed',
    error_message: errorMsg.substring(0, 1000),
    input_summary: `Last node: ${lastNode}`,
    output_summary: `Execution: ${execUrl}`,
    tokens_used: 0,
    duration_ms: 0,
    execution_id: error.execution?.id || '',
    timestamp: now,
    telegram_message: `<b>LinkedIn Agent Error</b>\n\nWorkflow: ${workflowName}\nNode: ${lastNode}\nError: ${errorMsg.substring(0, 200)}\n\n<a href="${execUrl}">View Execution</a>`,
  }
};"""

LI01_LOAD_RATE_LIMITS_CODE = r"""const campaign = $input.first().json;
const f = campaign.fields || campaign;
const now = new Date().toISOString();
return {
  json: {
    campaign_id: f['Campaign Name'] || 'default',
    batch_size: parseInt(f['Batch Size'] || 50),
    daily_limit: parseInt(f['Daily Action Limit'] || 200),
    hourly_limit: parseInt(f['Hourly Rate Limit'] || 100),
    token_budget: parseInt(f['Token Budget Daily'] || 30000),
    icp_titles: JSON.parse(f['ICP Titles'] || '[]'),
    icp_industries: JSON.parse(f['ICP Industries'] || '[]'),
    icp_company_size: f['ICP Company Size'] || '10-500',
    icp_locations: JSON.parse(f['ICP Locations'] || '[]'),
    icp_keywords: JSON.parse(f['ICP Keywords'] || '[]'),
    red_flag_keywords: JSON.parse(f['Red Flag Keywords'] || '[]'),
    run_started_at: now,
  }
};"""

LI01_BUILD_SUMMARY_CODE = r"""const items = $input.all();
const now = new Date().toISOString();
const stats = {
  total_processed: items.length,
  run_completed_at: now,
  status: 'completed',
};
const msg = `<b>LinkedIn Lead Intelligence - Batch Complete</b>\n\nLeads processed: ${stats.total_processed}\nCompleted: ${now}\n\nCheck Airtable for details.`;
return {
  json: {
    ...stats,
    email_subject: 'LinkedIn Lead Intelligence - Weekly Summary',
    email_body: `<div style="font-family:Arial;max-width:600px"><div style="background:#FF6D5A;padding:15px"><h2 style="color:white;margin:0">LinkedIn Lead Intelligence</h2></div><div style="padding:20px"><p>Batch processing complete.</p><p><b>Leads processed:</b> ${stats.total_processed}</p><p><b>Completed:</b> ${now}</p><p>Review leads in Airtable.</p></div></div>`,
    telegram_message: msg,
  }
};"""

LI02_NORMALIZE_CODE = r"""const items = $input.all();
const results = [];
for (const item of items) {
  const d = item.json;
  const leadId = `LI-${Date.now().toString(36)}-${Math.random().toString(36).substr(2, 5)}`.toUpperCase();
  results.push({
    json: {
      lead_id: leadId,
      full_name: d.fullName || d.full_name || ((d.firstName || '') + ' ' + (d.lastName || '')).trim() || '',
      first_name: d.firstName || d.first_name || (d.fullName || d.full_name || '').split(' ')[0] || '',
      last_name: d.lastName || d.last_name || (d.fullName || d.full_name || '').split(' ').slice(1).join(' ') || '',
      title: d.title || d.headline || d.jobTitle || d.job_title || '',
      company_name: d.companyName || d.company || d.company_name || '',
      industry: d.industry || '',
      location: d.location || d.city || '',
      linkedin_url: d.linkedinUrl || d.linkedin_url || d.profileUrl || d.profile_url || '',
      email: d.email || '',
      phone: d.phone || '',
      company_website: d.companyUrl || d.company_website || d.website || '',
      company_linkedin: d.companyLinkedinUrl || d.company_linkedin || '',
      employee_count: String(d.employeeCount || d.employee_count || ''),
      source: d.source || 'CSV_Upload',
      source_metadata: JSON.stringify({imported_at: new Date().toISOString(), original_fields: Object.keys(d)}),
      status: 'New',
      created_at: new Date().toISOString(),
    }
  });
}
return results;"""

LI02_RATE_LIMIT_CODE = r"""const items = $input.all();
const config = $('Trigger').first().json;
const hourlyLimit = config.hourly_limit || 100;
const limited = items.slice(0, hourlyLimit);
return limited.map(item => ({json: item.json}));"""

LI03_BUILD_SEARCH_URL_CODE = r"""const lead = $input.first().json;
const company = lead.company_name || '';
const query = encodeURIComponent(company + ' official website');
return {
  json: {
    ...lead,
    search_url: `https://www.google.com/search?q=${query}&num=3`,
  }
};"""

LI03_PARSE_AI_RESPONSE_CODE = r"""const raw = $input.first().json;
let parsed = {};
try {
  const content = raw.choices[0].message.content;
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  parsed = JSON.parse(cleaned);
} catch (e) {
  parsed = {
    company_description: '',
    key_services: [],
    business_model: 'Unknown',
    employee_estimate: '',
    tech_stack_hints: [],
    has_blog: false,
    social_presence: {},
    digital_presence_score: 0,
    website_quality_score: 0,
    parse_error: e.message,
  };
}
const lead = $('Load Lead + Enrichment Data').first().json;
return {
  json: {
    ...lead,
    ...parsed,
    enrichment_id: `EN-${Date.now().toString(36)}`.toUpperCase(),
    enriched_at: new Date().toISOString(),
  }
};"""

LI04_BUILD_SCORING_CONTEXT_CODE = r"""const lead = $input.first().json;
const enrichment = $('Load Enrichment Data').first().json;
const config = $('Trigger').first().json;
const context = {
  lead: {
    full_name: lead.full_name || lead['Full Name'] || '',
    title: lead.title || lead['Title'] || '',
    company_name: lead.company_name || lead['Company Name'] || '',
    industry: lead.industry || lead['Industry'] || '',
    location: lead.location || lead['Location'] || '',
    linkedin_url: lead.linkedin_url || lead['LinkedIn URL'] || '',
    employee_count: lead.employee_count || lead['Employee Count'] || '',
  },
  enrichment: {
    company_description: enrichment.company_description || enrichment['Company Description'] || '',
    key_services: enrichment.key_services || enrichment['Key Services'] || '',
    business_model: enrichment.business_model || enrichment['Business Model'] || '',
    digital_presence_score: enrichment.digital_presence_score || enrichment['Digital Presence Score'] || 0,
    website_quality_score: enrichment.website_quality_score || enrichment['Website Quality Score'] || 0,
  },
  icp_config: {
    titles: config.icp_titles || [],
    industries: config.icp_industries || [],
    company_size: config.icp_company_size || '10-500',
  },
};
return {json: {scoring_context: JSON.stringify(context, null, 2), lead_id: lead.lead_id || lead['Lead ID'] || ''}};"""

LI04_PARSE_SCORE_CODE = r"""const raw = $input.first().json;
let parsed = {};
try {
  const content = raw.choices[0].message.content;
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  parsed = JSON.parse(cleaned);
} catch (e) {
  parsed = {total_score: 0, confidence: 0, priority_band: 'Low', red_flags: [], reasoning: 'Parse error: ' + e.message, disqualified: false};
}
const context = $('Build Scoring Context').first().json;
return {
  json: {
    score_id: `SC-${Date.now().toString(36)}`.toUpperCase(),
    lead_id: context.lead_id,
    score_type: 'ICP',
    ...parsed,
    scored_at: new Date().toISOString(),
  }
};"""

LI05_PARSE_PAIN_POINTS_CODE = r"""const raw = $input.first().json;
let parsed = {pain_points: [], summary: ''};
try {
  const content = raw.choices[0].message.content;
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  parsed = JSON.parse(cleaned);
} catch (e) {
  parsed = {pain_points: [], summary: 'Parse error: ' + e.message};
}
const lead = $('Loop Over Leads').first().json;
const leadId = lead.lead_id || lead['Lead ID'] || '';
const results = parsed.pain_points.map((pp, i) => ({
  json: {
    pain_point_id: `PP-${Date.now().toString(36)}-${i}`.toUpperCase(),
    lead_id: leadId,
    pain_point: pp.pain_point || '',
    category: pp.category || 'Manual_Processes',
    severity: pp.severity || 5,
    confidence: pp.confidence || 0.5,
    evidence: pp.evidence || '',
    automation_category: pp.automation_category || '',
    detected_at: new Date().toISOString(),
  }
}));
if (results.length === 0) {
  results.push({json: {lead_id: leadId, pain_point: 'No pain points detected', severity: 0, detected_at: new Date().toISOString()}});
}
return results;"""

LI06_PARSE_OPPORTUNITIES_CODE = r"""const raw = $input.first().json;
let parsed = {opportunities: [], recommended_package: '', pitch_angle: ''};
try {
  const content = raw.choices[0].message.content;
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  parsed = JSON.parse(cleaned);
} catch (e) {
  parsed = {opportunities: [], recommended_package: 'Growth_R4999', pitch_angle: 'Parse error', estimated_monthly_value_to_client_zar: 0};
}
const lead = $('Loop Over Leads').first().json;
const leadId = lead.lead_id || lead['Lead ID'] || '';
const results = parsed.opportunities.map((opp, i) => ({
  json: {
    opportunity_id: `OPP-${Date.now().toString(36)}-${i}`.toUpperCase(),
    lead_id: leadId,
    solution_name: opp.solution_name || '',
    pain_points_addressed: JSON.stringify(opp.pain_points_addressed || []),
    roi_hypothesis: opp.roi_hypothesis || '',
    suggested_package: opp.suggested_package || parsed.recommended_package || '',
    implementation_complexity: opp.implementation_complexity || 'Moderate',
    rank: i + 1,
    confidence: opp.confidence || 0.5,
    created_at: new Date().toISOString(),
  }
}));
if (results.length === 0) {
  results.push({json: {lead_id: leadId, solution_name: 'General consultation', created_at: new Date().toISOString()}});
}
return results;"""

LI07_BUILD_OUTREACH_CONTEXT_CODE = r"""const lead = $('Loop Over Leads').first().json;
const opps = $('Load Opportunities').all();
const pains = $('Load Pain Points').all();
const oppList = opps.map(o => {
  const d = o.json;
  return {
    solution: d.solution_name || d['Solution Name'] || '',
    package: d.suggested_package || d['Suggested Package'] || '',
    roi: d.roi_hypothesis || d['ROI Hypothesis'] || '',
  };
});
const painList = pains.map(p => {
  const d = p.json;
  return {
    pain: d.pain_point || d['Pain Point'] || '',
    category: d.category || d['Category'] || '',
    severity: d.severity || d['Severity'] || 5,
  };
});
const context = {
  lead: {
    full_name: lead.full_name || lead['Full Name'] || '',
    first_name: lead.first_name || lead['First Name'] || '',
    title: lead.title || lead['Title'] || '',
    company_name: lead.company_name || lead['Company Name'] || '',
    industry: lead.industry || lead['Industry'] || '',
    location: lead.location || lead['Location'] || '',
  },
  opportunities: oppList,
  pain_points: painList,
};
return {json: {outreach_context: JSON.stringify(context, null, 2), lead_id: lead.lead_id || lead['Lead ID'] || ''}};"""

LI07_VALIDATE_OUTREACH_CODE = r"""const raw = $input.first().json;
let parsed = {};
try {
  const content = raw.choices[0].message.content;
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  parsed = JSON.parse(cleaned);
} catch (e) {
  parsed = {connection_message: '', follow_up_1: '', follow_up_2: '', short_pitch: '', email_draft: {subject: '', body: ''}, personalization_score: 0};
}
let connMsg = (parsed.connection_message || '').substring(0, 300);
const lead = $('Loop Over Leads').first().json;
const leadId = lead.lead_id || lead['Lead ID'] || '';
return {
  json: {
    outreach_id: `OUT-${Date.now().toString(36)}`.toUpperCase(),
    lead_id: leadId,
    connection_message: connMsg,
    follow_up_1: (parsed.follow_up_1 || '').substring(0, 500),
    follow_up_2: (parsed.follow_up_2 || '').substring(0, 500),
    short_pitch: parsed.short_pitch || '',
    email_draft: parsed.email_draft?.body || '',
    email_subject: parsed.email_draft?.subject || '',
    status: 'Draft',
    personalization_score: parsed.personalization_score || 0,
    generated_at: new Date().toISOString(),
  }
};"""

LI08_CALCULATE_PRIORITY_CODE = r"""const items = $input.all();
const results = [];
for (const item of items) {
  const d = item.json;
  const icpScore = parseInt(d.icp_score || d['ICP Score'] || 0);
  const painAvg = parseFloat(d.avg_pain_severity || 5);
  const oppConfidence = parseFloat(d.avg_opp_confidence || 0.5);
  const outreachScore = parseInt(d.personalization_score || d['Personalization Score'] || 50);
  const finalScore = Math.round(
    icpScore * 0.40 +
    painAvg * 10 * 0.25 +
    oppConfidence * 100 * 0.20 +
    outreachScore * 0.15
  );
  results.push({
    json: {
      ...d,
      final_priority_score: Math.min(finalScore, 100),
    }
  });
}
return results;"""

LI08_QA_VALIDATION_CODE = r"""const lead = $input.first().json;
const issues = [];
if (!lead.full_name && !lead['Full Name']) issues.push('MISSING: full_name');
if (!lead.company_name && !lead['Company Name']) issues.push('MISSING: company_name');
if (!lead.linkedin_url && !lead['LinkedIn URL']) issues.push('MISSING: linkedin_url');
if (!lead.connection_message && !lead['Connection Message']) issues.push('MISSING: outreach');
const icpScore = parseInt(lead.icp_score || lead['ICP Score'] || 0);
const redFlags = lead.red_flags || lead['Red Flags'] || '';
if (icpScore > 80 && redFlags && redFlags.length > 2) {
  issues.push('CONTRADICTION: High ICP score with red flags');
}
const desc = lead.company_description || lead['Company Description'] || '';
if (desc.includes('I cannot') || desc.includes('As an AI') || desc.includes('I don\'t have')) {
  issues.push('HALLUCINATION: AI refusal in company description');
}
const connMsg = lead.connection_message || lead['Connection Message'] || '';
if (connMsg.length > 300) issues.push('VIOLATION: Connection message exceeds 300 chars');
const score = lead.final_priority_score || 0;
const disqualified = lead.disqualified === true;
let lane;
if (disqualified || score < 20) lane = 'Ignore';
else if (score < 45) lane = 'Nurture';
else if (score < 70 || issues.length > 0) lane = 'Manual_Review';
else lane = 'High_Priority';
return {
  json: {
    ...lead,
    qa_issues: issues,
    qa_passed: issues.length === 0,
    routing_lane: lane,
    qa_timestamp: new Date().toISOString(),
  }
};"""

LI09_BUILD_PIPELINE_CODE = r"""const lead = $input.first().json;
const pipelineId = `PL-${Date.now().toString(36)}`.toUpperCase();
const lane = lead.routing_lane || 'Awaiting_Review';
return {
  json: {
    pipeline_id: pipelineId,
    lead_id: lead.lead_id || lead['Lead ID'] || '',
    stage: lane === 'High_Priority' ? 'Approved' : 'Awaiting_Review',
    previous_stage: lead.status || 'Qualified',
    stage_changed_at: new Date().toISOString(),
    days_in_stage: 0,
    owner: 'Ian Immelman',
    notes: `Auto-qualified. ICP: ${lead.icp_score || lead['ICP Score'] || 0}, Priority: ${lead.final_priority_score || 0}`,
    next_action: lane === 'High_Priority' ? 'Send connection request' : 'Manual review required',
    next_action_date: new Date(Date.now() + 86400000).toISOString().split('T')[0],
  }
};"""

LI10_VALIDATE_FEEDBACK_CODE = r"""const input = $input.first().json;
const required = ['lead_id', 'outcome'];
const missing = required.filter(f => !input[f]);
if (missing.length > 0) {
  return {json: {valid: false, error: `Missing fields: ${missing.join(', ')}`}};
}
const validOutcomes = ['No_Reply','Replied_Positive','Replied_Negative','Meeting_Booked','Proposal_Sent','Deal_Won','Deal_Lost','Nurture'];
if (!validOutcomes.includes(input.outcome)) {
  return {json: {valid: false, error: `Invalid outcome: ${input.outcome}. Valid: ${validOutcomes.join(', ')}`}};
}
return {
  json: {
    valid: true,
    feedback_id: `FB-${Date.now().toString(36)}`.toUpperCase(),
    lead_id: input.lead_id,
    outcome: input.outcome,
    revenue_zar: parseFloat(input.revenue_zar || 0),
    package_sold: input.package_sold || '',
    feedback_notes: input.feedback_notes || '',
    icp_score_at_contact: parseInt(input.icp_score_at_contact || 0),
    priority_band_at_contact: input.priority_band_at_contact || '',
    recorded_at: new Date().toISOString(),
  }
};"""

LI10_PARSE_LEARNING_CODE = r"""const raw = $input.first().json;
let parsed = {};
try {
  const content = raw.choices[0].message.content;
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  parsed = JSON.parse(cleaned);
} catch (e) {
  parsed = {win_patterns: [], loss_patterns: [], summary: 'Parse error: ' + e.message};
}
return {
  json: {
    feedback_id: `LEARN-${Date.now().toString(36)}`.toUpperCase(),
    lead_id: 'SYSTEM',
    outcome: 'Nurture',
    learning_insights: JSON.stringify(parsed, null, 2),
    feedback_notes: parsed.summary || '',
    recorded_at: new Date().toISOString(),
    email_subject: 'LinkedIn Lead Intelligence - Monthly Learning Report',
    email_body: `<div style="font-family:Arial;max-width:600px"><div style="background:#FF6D5A;padding:15px"><h2 style="color:white;margin:0">Monthly Learning Report</h2></div><div style="padding:20px"><h3>Win Patterns</h3><ul>${(parsed.win_patterns||[]).map(p=>'<li>'+p+'</li>').join('')}</ul><h3>Loss Patterns</h3><ul>${(parsed.loss_patterns||[]).map(p=>'<li>'+p+'</li>').join('')}</ul><h3>Recommendations</h3><ul>${(parsed.recommended_actions||[]).map(p=>'<li>'+p+'</li>').join('')}</ul><p><b>Summary:</b> ${parsed.summary||''}</p></div></div>`,
  }
};"""

LI08_AGGREGATE_SCORES_CODE = r"""const lead = $input.first().json;
const leadId = lead.lead_id || lead['Lead ID'] || '';
const icpScore = parseInt(lead.icp_score || lead['ICP Score'] || lead.total_score || 0);
const painSeverity = parseFloat(lead.avg_pain_severity || lead['Avg Pain Severity'] || 5);
const oppConfidence = parseFloat(lead.avg_opp_confidence || lead['Avg Opp Confidence'] || 0.5);
const personalization = parseInt(lead.personalization_score || lead['Personalization Score'] || 50);
return {
  json: {
    ...lead,
    lead_id: leadId,
    icp_score: icpScore,
    avg_pain_severity: painSeverity,
    avg_opp_confidence: oppConfidence,
    personalization_score: personalization,
  }
};"""


# ======================================================================
# LI-01: LEAD ORCHESTRATOR
# ======================================================================

def build_li01_nodes() -> list:
    nodes = []
    # Sticky note
    nodes.append(build_sticky_note(
        "Note LI-01",
        "LI-01: Lead Orchestrator\nLoads campaign config, checks pause/limits, coordinates sub-workflows",
        [0, 100], 350, 120, 2,
    ))
    # Triggers
    nodes.append(build_schedule_trigger("Weekly Schedule", "0 5 * * 1", [220, 300]))
    nodes.append(build_manual_trigger("Manual Trigger", [220, 500]))
    # Load campaign
    nodes.append(build_airtable_search(
        "Load Campaign Config", MARKETING_BASE_ID, TABLE_CAMPAIGNS,
        "={Status}='Active'", [460, 400],
    ))
    # Check campaign exists
    nodes.append(build_if_node("Has Active Campaign?", "={{ $json.id !== undefined }}", [700, 400]))
    nodes.append(build_noop("No Campaign", [700, 600]))
    # Emergency pause check
    nodes.append(build_if_node("Emergency Pause?", "={{ $json['Emergency Pause'] === true }}", [940, 400]))
    # Paused notification
    nodes.append(build_code_node("System Paused", r"""return {json: {telegram_message: '<b>LinkedIn System PAUSED</b>\n\nEmergency pause is enabled. Disable in Airtable to resume.'}};""", [940, 600]))
    nodes.append(build_telegram_send("Telegram Pause Alert", OWNER_TELEGRAM_CHAT_ID, "={{ $json.telegram_message }}", [1180, 600]))
    # Load rate limits
    nodes.append(build_code_node("Load Rate Limits", LI01_LOAD_RATE_LIMITS_CODE, [1180, 400]))
    # Check daily limit
    nodes.append(build_airtable_search(
        "Check Daily Actions", MARKETING_BASE_ID, TABLE_AGENT_LOGS,
        "=AND({Timestamp}>TODAY(),{Status}='Success')", [1420, 400], always_output=True,
    ))
    nodes.append(build_if_number_node(
        "Under Daily Limit?",
        "={{ $('Check Daily Actions').all().length }}",
        200, "lt", [1660, 400],
    ))
    nodes.append(build_code_node(
        "Daily Limit Hit",
        r"""return {json: {telegram_message: '<b>LinkedIn Daily Limit Reached</b>\n\nActions today: ' + $('Check Daily Actions').all().length}};""",
        [1660, 600],
    ))
    nodes.append(build_telegram_send("Telegram Limit Alert", OWNER_TELEGRAM_CHAT_ID, "={{ $json.telegram_message }}", [1900, 600]))
    # Execute sub-workflows (placeholder IDs, replaced after deploy)
    nodes.append(build_execute_workflow("Run LI-02 Discovery", "REPLACE_LI02_ID", [1900, 400]))
    nodes.append(build_execute_workflow("Run LI-03 Enrichment", "REPLACE_LI03_ID", [2140, 400]))
    nodes.append(build_execute_workflow("Run LI-04 Scoring", "REPLACE_LI04_ID", [2380, 400]))
    nodes.append(build_execute_workflow("Run LI-05 Pain Detection", "REPLACE_LI05_ID", [2620, 400]))
    nodes.append(build_execute_workflow("Run LI-06 Opportunities", "REPLACE_LI06_ID", [2860, 400]))
    nodes.append(build_execute_workflow("Run LI-07 Outreach", "REPLACE_LI07_ID", [3100, 400]))
    nodes.append(build_execute_workflow("Run LI-08 Prioritization", "REPLACE_LI08_ID", [3340, 400]))
    nodes.append(build_execute_workflow("Run LI-09 CRM Sync", "REPLACE_LI09_ID", [3580, 400]))
    # Summary
    nodes.append(build_code_node("Build Summary", LI01_BUILD_SUMMARY_CODE, [3820, 400]))
    nodes.append(build_gmail_send(
        "Send Summary Email", ALERT_EMAIL,
        "={{ $json.email_subject }}", "={{ $json.email_body }}", [4060, 300],
    ))
    nodes.append(build_telegram_send(
        "Send Summary Telegram", OWNER_TELEGRAM_CHAT_ID,
        "={{ $json.telegram_message }}", [4060, 500],
    ))
    # Error handler
    nodes.append(build_error_trigger("Error Trigger", [220, 800]))
    nodes.append(build_code_node("Error Handler", ERROR_HANDLER_CODE, [460, 800]))
    nodes.append(build_airtable_create("Log Error", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [700, 800]))
    nodes.append(build_telegram_send("Telegram Error", OWNER_TELEGRAM_CHAT_ID, "={{ $json.telegram_message }}", [700, 1000]))
    return nodes


def build_li01_connections(nodes: list) -> dict:
    return {
        "Weekly Schedule": {"main": [[{"node": "Load Campaign Config", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Load Campaign Config", "type": "main", "index": 0}]]},
        "Load Campaign Config": {"main": [[{"node": "Has Active Campaign?", "type": "main", "index": 0}]]},
        "Has Active Campaign?": {"main": [
            [{"node": "Emergency Pause?", "type": "main", "index": 0}],
            [{"node": "No Campaign", "type": "main", "index": 0}],
        ]},
        "Emergency Pause?": {"main": [
            [{"node": "System Paused", "type": "main", "index": 0}],
            [{"node": "Load Rate Limits", "type": "main", "index": 0}],
        ]},
        "System Paused": {"main": [[{"node": "Telegram Pause Alert", "type": "main", "index": 0}]]},
        "Load Rate Limits": {"main": [[{"node": "Check Daily Actions", "type": "main", "index": 0}]]},
        "Check Daily Actions": {"main": [[{"node": "Under Daily Limit?", "type": "main", "index": 0}]]},
        "Under Daily Limit?": {"main": [
            [{"node": "Run LI-02 Discovery", "type": "main", "index": 0}],
            [{"node": "Daily Limit Hit", "type": "main", "index": 0}],
        ]},
        "Daily Limit Hit": {"main": [[{"node": "Telegram Limit Alert", "type": "main", "index": 0}]]},
        "Run LI-02 Discovery": {"main": [[{"node": "Run LI-03 Enrichment", "type": "main", "index": 0}]]},
        "Run LI-03 Enrichment": {"main": [[{"node": "Run LI-04 Scoring", "type": "main", "index": 0}]]},
        "Run LI-04 Scoring": {"main": [[{"node": "Run LI-05 Pain Detection", "type": "main", "index": 0}]]},
        "Run LI-05 Pain Detection": {"main": [[{"node": "Run LI-06 Opportunities", "type": "main", "index": 0}]]},
        "Run LI-06 Opportunities": {"main": [[{"node": "Run LI-07 Outreach", "type": "main", "index": 0}]]},
        "Run LI-07 Outreach": {"main": [[{"node": "Run LI-08 Prioritization", "type": "main", "index": 0}]]},
        "Run LI-08 Prioritization": {"main": [[{"node": "Run LI-09 CRM Sync", "type": "main", "index": 0}]]},
        "Run LI-09 CRM Sync": {"main": [[{"node": "Build Summary", "type": "main", "index": 0}]]},
        "Build Summary": {"main": [[
            {"node": "Send Summary Email", "type": "main", "index": 0},
            {"node": "Send Summary Telegram", "type": "main", "index": 0},
        ]]},
        "Error Trigger": {"main": [[{"node": "Error Handler", "type": "main", "index": 0}]]},
        "Error Handler": {"main": [[{"node": "Log Error", "type": "main", "index": 0}]]},
        "Log Error": {"main": [[{"node": "Telegram Error", "type": "main", "index": 0}]]},
    }


# ======================================================================
# LI-02: LEAD DISCOVERY & COLLECTION
# ======================================================================

def build_li02_nodes() -> list:
    nodes = []
    nodes.append(build_sticky_note(
        "Note LI-02",
        "LI-02: Lead Discovery & Collection\nLoads CSV-uploaded leads, normalises, deduplicates, stores in Airtable",
        [0, 100], 400, 120, 4,
    ))
    # Entry
    nodes.append(build_execute_workflow_trigger("Trigger", [220, 400]))
    nodes.append(build_manual_trigger("Manual Trigger", [220, 600]))
    # Load pending leads
    nodes.append(build_airtable_search(
        "Load Pending CSV", MARKETING_BASE_ID, TABLE_LEADS,
        "=AND({Source}='CSV_Upload',{Status}='New')", [460, 400], always_output=True,
    ))
    # Check has leads
    nodes.append(build_if_node("Has Leads?", "={{ $json.id !== undefined }}", [700, 400]))
    nodes.append(build_noop("No Leads", [700, 600]))
    # Normalise
    nodes.append(build_code_node("Normalize Lead Data", LI02_NORMALIZE_CODE, [940, 400]))
    # Rate limit
    nodes.append(build_code_node("Rate Limit Gate", LI02_RATE_LIMIT_CODE, [1180, 400]))
    # Loop
    nodes.append(build_split_in_batches("Loop Over Leads", [1420, 400], batch_size=1))
    # Check duplicate
    nodes.append(build_airtable_search(
        "Check Duplicate", MARKETING_BASE_ID, TABLE_LEADS,
        "={{ '{LinkedIn URL}=\"' + $json.linkedin_url + '\"' }}", [1660, 400], always_output=True,
    ))
    nodes.append(build_if_node("Is Duplicate?", "={{ $json.id !== undefined }}", [1900, 400]))
    nodes.append(build_noop("Skip Duplicate", [1900, 600]))
    # Create lead
    nodes.append(build_airtable_create("Create Lead", MARKETING_BASE_ID, TABLE_LEADS, [2140, 400]))
    # Log
    nodes.append(build_airtable_create("Log Discovery", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [2380, 400]))
    # Error handler
    nodes.append(build_error_trigger("Error Trigger", [220, 800]))
    nodes.append(build_code_node("Error Handler", ERROR_HANDLER_CODE, [460, 800]))
    nodes.append(build_airtable_create("Log Error", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [700, 800]))
    nodes.append(build_telegram_send("Telegram Error", OWNER_TELEGRAM_CHAT_ID, "={{ $json.telegram_message }}", [700, 1000]))
    return nodes


def build_li02_connections(nodes: list) -> dict:
    return {
        "Trigger": {"main": [[{"node": "Load Pending CSV", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Load Pending CSV", "type": "main", "index": 0}]]},
        "Load Pending CSV": {"main": [[{"node": "Has Leads?", "type": "main", "index": 0}]]},
        "Has Leads?": {"main": [
            [{"node": "Normalize Lead Data", "type": "main", "index": 0}],
            [{"node": "No Leads", "type": "main", "index": 0}],
        ]},
        "Normalize Lead Data": {"main": [[{"node": "Rate Limit Gate", "type": "main", "index": 0}]]},
        "Rate Limit Gate": {"main": [[{"node": "Loop Over Leads", "type": "main", "index": 0}]]},
        "Loop Over Leads": {"main": [
            [{"node": "Check Duplicate", "type": "main", "index": 0}],
        ]},
        "Check Duplicate": {"main": [[{"node": "Is Duplicate?", "type": "main", "index": 0}]]},
        "Is Duplicate?": {"main": [
            [{"node": "Skip Duplicate", "type": "main", "index": 0}],
            [{"node": "Create Lead", "type": "main", "index": 0}],
        ]},
        "Skip Duplicate": {"main": [[{"node": "Loop Over Leads", "type": "main", "index": 0}]]},
        "Create Lead": {"main": [[{"node": "Log Discovery", "type": "main", "index": 0}]]},
        "Log Discovery": {"main": [[{"node": "Loop Over Leads", "type": "main", "index": 0}]]},
        "Error Trigger": {"main": [[{"node": "Error Handler", "type": "main", "index": 0}]]},
        "Error Handler": {"main": [[{"node": "Log Error", "type": "main", "index": 0}]]},
        "Log Error": {"main": [[{"node": "Telegram Error", "type": "main", "index": 0}]]},
    }


# ======================================================================
# LI-03: DATA ENRICHMENT
# ======================================================================

def build_li03_nodes() -> list:
    nodes = []
    nodes.append(build_sticky_note(
        "Note LI-03",
        "LI-03: Data Enrichment\nScrapes company websites, AI extracts business intelligence",
        [0, 100], 400, 120, 5,
    ))
    # Entry
    nodes.append(build_execute_workflow_trigger("Trigger", [220, 400]))
    nodes.append(build_manual_trigger("Manual Trigger", [220, 600]))
    # Load new leads
    nodes.append(build_airtable_search(
        "Load New Leads", MARKETING_BASE_ID, TABLE_LEADS,
        "=AND({Status}='New')", [460, 400], always_output=True,
    ))
    nodes.append(build_if_node("Has Leads?", "={{ $json.id !== undefined }}", [700, 400]))
    nodes.append(build_noop("No Leads", [700, 600]))
    # Loop
    nodes.append(build_split_in_batches("Loop Over Leads", [940, 400], batch_size=1))
    # Build search URL (alias for lead reference)
    nodes.append(build_code_node("Load Lead + Enrichment Data", LI03_BUILD_SEARCH_URL_CODE, [1180, 400]))
    # Scrape website
    node_scrape = build_http_request(
        "Scrape Website", "GET",
        "={{ $json.company_website || $json.search_url }}", [1420, 400],
    )
    node_scrape["onError"] = "continueRegularOutput"
    nodes.append(node_scrape)
    # Wait for rate limit
    nodes.append(build_wait_node("Wait 3s", [1660, 400], seconds=3))
    # AI enrichment
    nodes.append(build_openrouter_ai(
        "AI Enrichment", LI03_ENRICHMENT_PROMPT,
        " JSON.stringify({company_name: $json.company_name, html_snippet: ($json.data || '').substring(0, 3000)})",
        [1900, 400], max_tokens=1500, temperature=0.2,
    ))
    # Parse AI response
    nodes.append(build_code_node("Parse AI Response", LI03_PARSE_AI_RESPONSE_CODE, [2140, 400]))
    # Store enrichment
    nodes.append(build_airtable_create("Create Enrichment", MARKETING_BASE_ID, TABLE_ENRICHMENT, [2380, 400]))
    # Update lead status
    nodes.append(build_airtable_update(
        "Update Lead Status", MARKETING_BASE_ID, TABLE_LEADS, [2620, 400],
        matching_columns=["Lead ID"],
    ))
    # Log
    nodes.append(build_airtable_create("Log Enrichment", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [2860, 400]))
    # Error handler
    nodes.append(build_error_trigger("Error Trigger", [220, 800]))
    nodes.append(build_code_node("Error Handler", ERROR_HANDLER_CODE, [460, 800]))
    nodes.append(build_airtable_create("Log Error", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [700, 800]))
    nodes.append(build_telegram_send("Telegram Error", OWNER_TELEGRAM_CHAT_ID, "={{ $json.telegram_message }}", [700, 1000]))
    return nodes


def build_li03_connections(nodes: list) -> dict:
    return {
        "Trigger": {"main": [[{"node": "Load New Leads", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Load New Leads", "type": "main", "index": 0}]]},
        "Load New Leads": {"main": [[{"node": "Has Leads?", "type": "main", "index": 0}]]},
        "Has Leads?": {"main": [
            [{"node": "Loop Over Leads", "type": "main", "index": 0}],
            [{"node": "No Leads", "type": "main", "index": 0}],
        ]},
        "Loop Over Leads": {"main": [
            [{"node": "Load Lead + Enrichment Data", "type": "main", "index": 0}],
        ]},
        "Load Lead + Enrichment Data": {"main": [[{"node": "Scrape Website", "type": "main", "index": 0}]]},
        "Scrape Website": {"main": [[{"node": "Wait 3s", "type": "main", "index": 0}]]},
        "Wait 3s": {"main": [[{"node": "AI Enrichment", "type": "main", "index": 0}]]},
        "AI Enrichment": {"main": [[{"node": "Parse AI Response", "type": "main", "index": 0}]]},
        "Parse AI Response": {"main": [[{"node": "Create Enrichment", "type": "main", "index": 0}]]},
        "Create Enrichment": {"main": [[{"node": "Update Lead Status", "type": "main", "index": 0}]]},
        "Update Lead Status": {"main": [[{"node": "Log Enrichment", "type": "main", "index": 0}]]},
        "Log Enrichment": {"main": [[{"node": "Loop Over Leads", "type": "main", "index": 0}]]},
        "Error Trigger": {"main": [[{"node": "Error Handler", "type": "main", "index": 0}]]},
        "Error Handler": {"main": [[{"node": "Log Error", "type": "main", "index": 0}]]},
        "Log Error": {"main": [[{"node": "Telegram Error", "type": "main", "index": 0}]]},
    }


# ======================================================================
# LI-04: ICP SCORING
# ======================================================================

def build_li04_nodes() -> list:
    nodes = []
    nodes.append(build_sticky_note(
        "Note LI-04",
        "LI-04: ICP Scoring\nAI scores leads against Ideal Customer Profile",
        [0, 100], 350, 120, 5,
    ))
    # Entry
    nodes.append(build_execute_workflow_trigger("Trigger", [220, 400]))
    nodes.append(build_manual_trigger("Manual Trigger", [220, 600]))
    # Load enriched leads
    nodes.append(build_airtable_search(
        "Load Enriched Leads", MARKETING_BASE_ID, TABLE_LEADS,
        "={Status}='Enriched'", [460, 400], always_output=True,
    ))
    nodes.append(build_if_node("Has Leads?", "={{ $json.id !== undefined }}", [700, 400]))
    nodes.append(build_noop("No Leads", [700, 600]))
    # Loop
    nodes.append(build_split_in_batches("Loop Over Leads", [940, 400], batch_size=1))
    # Load enrichment data
    nodes.append(build_airtable_search(
        "Load Enrichment Data", MARKETING_BASE_ID, TABLE_ENRICHMENT,
        "={{ '{Lead ID}=\"' + ($json.lead_id || $json['Lead ID'] || '') + '\"' }}",
        [1180, 400], always_output=True,
    ))
    # Build scoring context
    nodes.append(build_code_node("Build Scoring Context", LI04_BUILD_SCORING_CONTEXT_CODE, [1420, 400]))
    # AI ICP scoring
    nodes.append(build_openrouter_ai(
        "AI ICP Score", LI04_ICP_SCORING_PROMPT,
        " $json.scoring_context",
        [1660, 400], max_tokens=1500, temperature=0.2,
    ))
    # Parse score
    nodes.append(build_code_node("Parse Score", LI04_PARSE_SCORE_CODE, [1900, 400]))
    # Store score
    nodes.append(build_airtable_create("Create Score", MARKETING_BASE_ID, TABLE_SCORES, [2140, 400]))
    # Update lead
    nodes.append(build_airtable_update(
        "Update Lead", MARKETING_BASE_ID, TABLE_LEADS, [2380, 400],
        matching_columns=["Lead ID"],
    ))
    # Log
    nodes.append(build_airtable_create("Log Scoring", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [2620, 400]))
    # Error handler
    nodes.append(build_error_trigger("Error Trigger", [220, 800]))
    nodes.append(build_code_node("Error Handler", ERROR_HANDLER_CODE, [460, 800]))
    nodes.append(build_airtable_create("Log Error", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [700, 800]))
    nodes.append(build_telegram_send("Telegram Error", OWNER_TELEGRAM_CHAT_ID, "={{ $json.telegram_message }}", [700, 1000]))
    return nodes


def build_li04_connections(nodes: list) -> dict:
    return {
        "Trigger": {"main": [[{"node": "Load Enriched Leads", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Load Enriched Leads", "type": "main", "index": 0}]]},
        "Load Enriched Leads": {"main": [[{"node": "Has Leads?", "type": "main", "index": 0}]]},
        "Has Leads?": {"main": [
            [{"node": "Loop Over Leads", "type": "main", "index": 0}],
            [{"node": "No Leads", "type": "main", "index": 0}],
        ]},
        "Loop Over Leads": {"main": [
            [{"node": "Load Enrichment Data", "type": "main", "index": 0}],
        ]},
        "Load Enrichment Data": {"main": [[{"node": "Build Scoring Context", "type": "main", "index": 0}]]},
        "Build Scoring Context": {"main": [[{"node": "AI ICP Score", "type": "main", "index": 0}]]},
        "AI ICP Score": {"main": [[{"node": "Parse Score", "type": "main", "index": 0}]]},
        "Parse Score": {"main": [[{"node": "Create Score", "type": "main", "index": 0}]]},
        "Create Score": {"main": [[{"node": "Update Lead", "type": "main", "index": 0}]]},
        "Update Lead": {"main": [[{"node": "Log Scoring", "type": "main", "index": 0}]]},
        "Log Scoring": {"main": [[{"node": "Loop Over Leads", "type": "main", "index": 0}]]},
        "Error Trigger": {"main": [[{"node": "Error Handler", "type": "main", "index": 0}]]},
        "Error Handler": {"main": [[{"node": "Log Error", "type": "main", "index": 0}]]},
        "Log Error": {"main": [[{"node": "Telegram Error", "type": "main", "index": 0}]]},
    }


# ======================================================================
# LI-05: PAIN POINT DETECTION
# ======================================================================

def build_li05_nodes() -> list:
    nodes = []
    nodes.append(build_sticky_note(
        "Note LI-05",
        "LI-05: Pain Point Detection\nAI identifies 3-7 operational pain points per lead",
        [0, 100], 400, 120, 6,
    ))
    # Entry
    nodes.append(build_execute_workflow_trigger("Trigger", [220, 400]))
    nodes.append(build_manual_trigger("Manual Trigger", [220, 600]))
    # Load scored leads (ICP >= 40)
    nodes.append(build_airtable_search(
        "Load Scored Leads", MARKETING_BASE_ID, TABLE_LEADS,
        "=AND({Status}='Scored',{ICP Score}>=40)", [460, 400], always_output=True,
    ))
    nodes.append(build_if_node("Has Leads?", "={{ $json.id !== undefined }}", [700, 400]))
    nodes.append(build_noop("No Leads", [700, 600]))
    # Loop
    nodes.append(build_split_in_batches("Loop Over Leads", [940, 400], batch_size=1))
    # Load enrichment for lead
    nodes.append(build_airtable_search(
        "Load Lead Enrichment", MARKETING_BASE_ID, TABLE_ENRICHMENT,
        "={{ '{Lead ID}=\"' + ($json.lead_id || $json['Lead ID'] || '') + '\"' }}",
        [1180, 400], always_output=True,
    ))
    # AI pain detection
    nodes.append(build_openrouter_ai(
        "AI Pain Detection", LI05_PAIN_DETECTION_PROMPT,
        " JSON.stringify({lead: {full_name: $json.full_name || $json['Full Name'], title: $json.title || $json['Title'], company: $json.company_name || $json['Company Name'], industry: $json.industry || $json['Industry']}, enrichment: {description: $('Load Lead Enrichment').first().json.company_description || '', services: $('Load Lead Enrichment').first().json.key_services || '', model: $('Load Lead Enrichment').first().json.business_model || ''}})",
        [1420, 400], max_tokens=2000, temperature=0.3,
    ))
    # Parse
    nodes.append(build_code_node("Parse Pain Points", LI05_PARSE_PAIN_POINTS_CODE, [1660, 400]))
    # Store pain points
    nodes.append(build_airtable_create("Store Pain Points", MARKETING_BASE_ID, TABLE_PAIN_POINTS, [1900, 400]))
    # Log
    nodes.append(build_airtable_create("Log Pain Detection", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [2140, 400]))
    # Error handler
    nodes.append(build_error_trigger("Error Trigger", [220, 800]))
    nodes.append(build_code_node("Error Handler", ERROR_HANDLER_CODE, [460, 800]))
    nodes.append(build_airtable_create("Log Error", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [700, 800]))
    nodes.append(build_telegram_send("Telegram Error", OWNER_TELEGRAM_CHAT_ID, "={{ $json.telegram_message }}", [700, 1000]))
    return nodes


def build_li05_connections(nodes: list) -> dict:
    return {
        "Trigger": {"main": [[{"node": "Load Scored Leads", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Load Scored Leads", "type": "main", "index": 0}]]},
        "Load Scored Leads": {"main": [[{"node": "Has Leads?", "type": "main", "index": 0}]]},
        "Has Leads?": {"main": [
            [{"node": "Loop Over Leads", "type": "main", "index": 0}],
            [{"node": "No Leads", "type": "main", "index": 0}],
        ]},
        "Loop Over Leads": {"main": [
            [{"node": "Load Lead Enrichment", "type": "main", "index": 0}],
        ]},
        "Load Lead Enrichment": {"main": [[{"node": "AI Pain Detection", "type": "main", "index": 0}]]},
        "AI Pain Detection": {"main": [[{"node": "Parse Pain Points", "type": "main", "index": 0}]]},
        "Parse Pain Points": {"main": [[{"node": "Store Pain Points", "type": "main", "index": 0}]]},
        "Store Pain Points": {"main": [[{"node": "Log Pain Detection", "type": "main", "index": 0}]]},
        "Log Pain Detection": {"main": [[{"node": "Loop Over Leads", "type": "main", "index": 0}]]},
        "Error Trigger": {"main": [[{"node": "Error Handler", "type": "main", "index": 0}]]},
        "Error Handler": {"main": [[{"node": "Log Error", "type": "main", "index": 0}]]},
        "Log Error": {"main": [[{"node": "Telegram Error", "type": "main", "index": 0}]]},
    }


# ======================================================================
# LI-06: AUTOMATION OPPORTUNITY MAPPING
# ======================================================================

def build_li06_nodes() -> list:
    nodes = []
    nodes.append(build_sticky_note(
        "Note LI-06",
        "LI-06: Automation Opportunity Mapping\nAI maps pain points to AnyVision solutions and packages",
        [0, 100], 450, 120, 5,
    ))
    # Entry
    nodes.append(build_execute_workflow_trigger("Trigger", [220, 400]))
    nodes.append(build_manual_trigger("Manual Trigger", [220, 600]))
    # Load leads with pain points
    nodes.append(build_airtable_search(
        "Load Leads with Pain Points", MARKETING_BASE_ID, TABLE_LEADS,
        "=AND({Status}='Scored',{ICP Score}>=40)", [460, 400], always_output=True,
    ))
    nodes.append(build_if_node("Has Leads?", "={{ $json.id !== undefined }}", [700, 400]))
    nodes.append(build_noop("No Leads", [700, 600]))
    # Loop
    nodes.append(build_split_in_batches("Loop Over Leads", [940, 400], batch_size=1))
    # Load pain points for this lead
    nodes.append(build_airtable_search(
        "Load Pain Points", MARKETING_BASE_ID, TABLE_PAIN_POINTS,
        "={{ '{Lead ID}=\"' + ($json.lead_id || $json['Lead ID'] || '') + '\"' }}",
        [1180, 400], always_output=True,
    ))
    # AI opportunity mapping
    nodes.append(build_openrouter_ai(
        "AI Opportunity Mapping", LI06_OPPORTUNITY_MAPPING_PROMPT,
        " JSON.stringify({lead: {full_name: $('Loop Over Leads').first().json.full_name || $('Loop Over Leads').first().json['Full Name'], company: $('Loop Over Leads').first().json.company_name || $('Loop Over Leads').first().json['Company Name'], industry: $('Loop Over Leads').first().json.industry || $('Loop Over Leads').first().json['Industry']}, pain_points: $input.all().map(i => ({pain: i.json.pain_point || i.json['Pain Point'], category: i.json.category || i.json['Category'], severity: i.json.severity || i.json['Severity']}))})",
        [1420, 400], max_tokens=2000, temperature=0.3,
    ))
    # Parse
    nodes.append(build_code_node("Parse Opportunities", LI06_PARSE_OPPORTUNITIES_CODE, [1660, 400]))
    # Store
    nodes.append(build_airtable_create("Store Opportunities", MARKETING_BASE_ID, TABLE_OPPORTUNITIES, [1900, 400]))
    # Log
    nodes.append(build_airtable_create("Log Opportunity Mapping", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [2140, 400]))
    # Error handler
    nodes.append(build_error_trigger("Error Trigger", [220, 800]))
    nodes.append(build_code_node("Error Handler", ERROR_HANDLER_CODE, [460, 800]))
    nodes.append(build_airtable_create("Log Error", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [700, 800]))
    nodes.append(build_telegram_send("Telegram Error", OWNER_TELEGRAM_CHAT_ID, "={{ $json.telegram_message }}", [700, 1000]))
    return nodes


def build_li06_connections(nodes: list) -> dict:
    return {
        "Trigger": {"main": [[{"node": "Load Leads with Pain Points", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Load Leads with Pain Points", "type": "main", "index": 0}]]},
        "Load Leads with Pain Points": {"main": [[{"node": "Has Leads?", "type": "main", "index": 0}]]},
        "Has Leads?": {"main": [
            [{"node": "Loop Over Leads", "type": "main", "index": 0}],
            [{"node": "No Leads", "type": "main", "index": 0}],
        ]},
        "Loop Over Leads": {"main": [
            [{"node": "Load Pain Points", "type": "main", "index": 0}],
        ]},
        "Load Pain Points": {"main": [[{"node": "AI Opportunity Mapping", "type": "main", "index": 0}]]},
        "AI Opportunity Mapping": {"main": [[{"node": "Parse Opportunities", "type": "main", "index": 0}]]},
        "Parse Opportunities": {"main": [[{"node": "Store Opportunities", "type": "main", "index": 0}]]},
        "Store Opportunities": {"main": [[{"node": "Log Opportunity Mapping", "type": "main", "index": 0}]]},
        "Log Opportunity Mapping": {"main": [[{"node": "Loop Over Leads", "type": "main", "index": 0}]]},
        "Error Trigger": {"main": [[{"node": "Error Handler", "type": "main", "index": 0}]]},
        "Error Handler": {"main": [[{"node": "Log Error", "type": "main", "index": 0}]]},
        "Log Error": {"main": [[{"node": "Telegram Error", "type": "main", "index": 0}]]},
    }


# ======================================================================
# LI-07: OUTREACH PERSONALIZATION
# ======================================================================

def build_li07_nodes() -> list:
    nodes = []
    nodes.append(build_sticky_note(
        "Note LI-07",
        "LI-07: Outreach Personalization\nAI generates personalised connection messages, follow-ups, pitches",
        [0, 100], 450, 120, 2,
    ))
    # Entry
    nodes.append(build_execute_workflow_trigger("Trigger", [220, 400]))
    nodes.append(build_manual_trigger("Manual Trigger", [220, 600]))
    # Load qualified leads
    nodes.append(build_airtable_search(
        "Load Qualified Leads", MARKETING_BASE_ID, TABLE_LEADS,
        "=AND({Status}='Scored',{ICP Score}>=40)", [460, 400], always_output=True,
    ))
    nodes.append(build_if_node("Has Leads?", "={{ $json.id !== undefined }}", [700, 400]))
    nodes.append(build_noop("No Leads", [700, 600]))
    # Loop
    nodes.append(build_split_in_batches("Loop Over Leads", [940, 400], batch_size=1))
    # Load opportunities
    nodes.append(build_airtable_search(
        "Load Opportunities", MARKETING_BASE_ID, TABLE_OPPORTUNITIES,
        "={{ '{Lead ID}=\"' + ($json.lead_id || $json['Lead ID'] || '') + '\"' }}",
        [1180, 400], always_output=True,
    ))
    # Load pain points
    nodes.append(build_airtable_search(
        "Load Pain Points", MARKETING_BASE_ID, TABLE_PAIN_POINTS,
        "={{ '{Lead ID}=\"' + ($('Loop Over Leads').first().json.lead_id || $('Loop Over Leads').first().json['Lead ID'] || '') + '\"' }}",
        [1180, 600], always_output=True,
    ))
    # Build outreach context
    nodes.append(build_code_node("Build Outreach Context", LI07_BUILD_OUTREACH_CONTEXT_CODE, [1420, 400]))
    # AI outreach generation
    nodes.append(build_openrouter_ai(
        "AI Outreach", LI07_OUTREACH_PROMPT,
        " $json.outreach_context",
        [1660, 400], max_tokens=2000, temperature=0.4,
    ))
    # Validate outreach
    nodes.append(build_code_node("Validate Outreach", LI07_VALIDATE_OUTREACH_CODE, [1900, 400]))
    # Store outreach
    nodes.append(build_airtable_create("Store Outreach", MARKETING_BASE_ID, TABLE_OUTREACH, [2140, 400]))
    # Log
    nodes.append(build_airtable_create("Log Outreach", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [2380, 400]))
    # Error handler
    nodes.append(build_error_trigger("Error Trigger", [220, 800]))
    nodes.append(build_code_node("Error Handler", ERROR_HANDLER_CODE, [460, 800]))
    nodes.append(build_airtable_create("Log Error", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [700, 800]))
    nodes.append(build_telegram_send("Telegram Error", OWNER_TELEGRAM_CHAT_ID, "={{ $json.telegram_message }}", [700, 1000]))
    return nodes


def build_li07_connections(nodes: list) -> dict:
    return {
        "Trigger": {"main": [[{"node": "Load Qualified Leads", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Load Qualified Leads", "type": "main", "index": 0}]]},
        "Load Qualified Leads": {"main": [[{"node": "Has Leads?", "type": "main", "index": 0}]]},
        "Has Leads?": {"main": [
            [{"node": "Loop Over Leads", "type": "main", "index": 0}],
            [{"node": "No Leads", "type": "main", "index": 0}],
        ]},
        "Loop Over Leads": {"main": [
            [{"node": "Load Opportunities", "type": "main", "index": 0}],
        ]},
        "Load Opportunities": {"main": [[{"node": "Load Pain Points", "type": "main", "index": 0}]]},
        "Load Pain Points": {"main": [[{"node": "Build Outreach Context", "type": "main", "index": 0}]]},
        "Build Outreach Context": {"main": [[{"node": "AI Outreach", "type": "main", "index": 0}]]},
        "AI Outreach": {"main": [[{"node": "Validate Outreach", "type": "main", "index": 0}]]},
        "Validate Outreach": {"main": [[{"node": "Store Outreach", "type": "main", "index": 0}]]},
        "Store Outreach": {"main": [[{"node": "Log Outreach", "type": "main", "index": 0}]]},
        "Log Outreach": {"main": [[{"node": "Loop Over Leads", "type": "main", "index": 0}]]},
        "Error Trigger": {"main": [[{"node": "Error Handler", "type": "main", "index": 0}]]},
        "Error Handler": {"main": [[{"node": "Log Error", "type": "main", "index": 0}]]},
        "Log Error": {"main": [[{"node": "Telegram Error", "type": "main", "index": 0}]]},
    }


# ======================================================================
# LI-08: LEAD PRIORITIZATION & QA
# ======================================================================

def build_li08_nodes() -> list:
    nodes = []
    nodes.append(build_sticky_note(
        "Note LI-08",
        "LI-08: Lead Prioritization & QA\nAggregates scores, calculates priority, validates quality, routes leads",
        [0, 100], 450, 120, 4,
    ))
    # Entry
    nodes.append(build_execute_workflow_trigger("Trigger", [220, 400]))
    nodes.append(build_manual_trigger("Manual Trigger", [220, 600]))
    # Load leads to prioritise
    nodes.append(build_airtable_search(
        "Load Leads to Prioritize", MARKETING_BASE_ID, TABLE_LEADS,
        "=AND({Status}='Scored',{ICP Score}>=40)", [460, 400], always_output=True,
    ))
    nodes.append(build_if_node("Has Leads?", "={{ $json.id !== undefined }}", [700, 400]))
    nodes.append(build_noop("No Leads", [700, 600]))
    # Loop
    nodes.append(build_split_in_batches("Loop Over Leads", [940, 400], batch_size=1))
    # Aggregate scores from various tables
    nodes.append(build_code_node("Aggregate Scores", LI08_AGGREGATE_SCORES_CODE, [1180, 400]))
    # Calculate priority
    nodes.append(build_code_node("Calculate Priority", LI08_CALCULATE_PRIORITY_CODE, [1420, 400]))
    # QA validation
    nodes.append(build_code_node("QA Validation", LI08_QA_VALIDATION_CODE, [1660, 400]))
    # Route by lane
    nodes.append(build_switch_node(
        "Route by Lane", "={{ $json.routing_lane }}",
        ["Ignore", "Nurture", "Manual_Review", "High_Priority"],
        [1900, 400],
    ))
    # Ignore lane
    nodes.append(build_airtable_update(
        "Update Ignore", MARKETING_BASE_ID, TABLE_LEADS, [2140, 200],
        matching_columns=["Lead ID"],
    ))
    # Nurture lane
    nodes.append(build_airtable_update(
        "Update Nurture", MARKETING_BASE_ID, TABLE_LEADS, [2140, 400],
        matching_columns=["Lead ID"],
    ))
    # Manual review lane
    nodes.append(build_airtable_update(
        "Update Manual Review", MARKETING_BASE_ID, TABLE_LEADS, [2140, 600],
        matching_columns=["Lead ID"],
    ))
    # High priority lane
    nodes.append(build_airtable_update(
        "Update High Priority", MARKETING_BASE_ID, TABLE_LEADS, [2140, 800],
        matching_columns=["Lead ID"],
    ))
    # Telegram alert for high priority
    nodes.append(build_telegram_send(
        "Telegram High Priority",
        OWNER_TELEGRAM_CHAT_ID,
        "=<b>High Priority Lead</b>\n\nName: {{ $json.full_name || $json['Full Name'] }}\nCompany: {{ $json.company_name || $json['Company Name'] }}\nICP Score: {{ $json.icp_score || $json['ICP Score'] }}\nPriority: {{ $json.final_priority_score }}",
        [2380, 800],
    ))
    # All lanes return to loop
    nodes.append(build_noop("Converge", [2380, 400]))
    # Error handler
    nodes.append(build_error_trigger("Error Trigger", [220, 800]))
    nodes.append(build_code_node("Error Handler", ERROR_HANDLER_CODE, [460, 800]))
    nodes.append(build_airtable_create("Log Error", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [700, 800]))
    nodes.append(build_telegram_send("Telegram Error", OWNER_TELEGRAM_CHAT_ID, "={{ $json.telegram_message }}", [700, 1000]))
    return nodes


def build_li08_connections(nodes: list) -> dict:
    return {
        "Trigger": {"main": [[{"node": "Load Leads to Prioritize", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Load Leads to Prioritize", "type": "main", "index": 0}]]},
        "Load Leads to Prioritize": {"main": [[{"node": "Has Leads?", "type": "main", "index": 0}]]},
        "Has Leads?": {"main": [
            [{"node": "Loop Over Leads", "type": "main", "index": 0}],
            [{"node": "No Leads", "type": "main", "index": 0}],
        ]},
        "Loop Over Leads": {"main": [
            [{"node": "Aggregate Scores", "type": "main", "index": 0}],
        ]},
        "Aggregate Scores": {"main": [[{"node": "Calculate Priority", "type": "main", "index": 0}]]},
        "Calculate Priority": {"main": [[{"node": "QA Validation", "type": "main", "index": 0}]]},
        "QA Validation": {"main": [[{"node": "Route by Lane", "type": "main", "index": 0}]]},
        "Route by Lane": {"main": [
            [{"node": "Update Ignore", "type": "main", "index": 0}],
            [{"node": "Update Nurture", "type": "main", "index": 0}],
            [{"node": "Update Manual Review", "type": "main", "index": 0}],
            [{"node": "Update High Priority", "type": "main", "index": 0}],
        ]},
        "Update Ignore": {"main": [[{"node": "Converge", "type": "main", "index": 0}]]},
        "Update Nurture": {"main": [[{"node": "Converge", "type": "main", "index": 0}]]},
        "Update Manual Review": {"main": [[{"node": "Converge", "type": "main", "index": 0}]]},
        "Update High Priority": {"main": [[{"node": "Telegram High Priority", "type": "main", "index": 0}]]},
        "Telegram High Priority": {"main": [[{"node": "Converge", "type": "main", "index": 0}]]},
        "Converge": {"main": [[{"node": "Loop Over Leads", "type": "main", "index": 0}]]},
        "Error Trigger": {"main": [[{"node": "Error Handler", "type": "main", "index": 0}]]},
        "Error Handler": {"main": [[{"node": "Log Error", "type": "main", "index": 0}]]},
        "Log Error": {"main": [[{"node": "Telegram Error", "type": "main", "index": 0}]]},
    }


# ======================================================================
# LI-09: CRM SYNC & DASHBOARD
# ======================================================================

def build_li09_nodes() -> list:
    nodes = []
    nodes.append(build_sticky_note(
        "Note LI-09",
        "LI-09: CRM Sync & Dashboard\nCreates pipeline records for finalised leads",
        [0, 100], 400, 120, 4,
    ))
    # Entry
    nodes.append(build_execute_workflow_trigger("Trigger", [220, 400]))
    nodes.append(build_manual_trigger("Manual Trigger", [220, 600]))
    # Load finalised leads
    nodes.append(build_airtable_search(
        "Load Finalized Leads", MARKETING_BASE_ID, TABLE_LEADS,
        "=OR({Status}='Approved',{Status}='Awaiting_Review')", [460, 400], always_output=True,
    ))
    nodes.append(build_if_node("Has Leads?", "={{ $json.id !== undefined }}", [700, 400]))
    nodes.append(build_noop("No Leads", [700, 600]))
    # Loop
    nodes.append(build_split_in_batches("Loop Over Leads", [940, 400], batch_size=1))
    # Build pipeline entry
    nodes.append(build_code_node("Build Pipeline Entry", LI09_BUILD_PIPELINE_CODE, [1180, 400]))
    # Create pipeline record
    nodes.append(build_airtable_create("Create Pipeline Record", MARKETING_BASE_ID, TABLE_PIPELINE, [1420, 400]))
    # Update lead master
    nodes.append(build_airtable_update(
        "Update Lead Master", MARKETING_BASE_ID, TABLE_LEADS, [1660, 400],
        matching_columns=["Lead ID"],
    ))
    # Log
    nodes.append(build_airtable_create("Log CRM Sync", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [1900, 400]))
    # Error handler
    nodes.append(build_error_trigger("Error Trigger", [220, 800]))
    nodes.append(build_code_node("Error Handler", ERROR_HANDLER_CODE, [460, 800]))
    nodes.append(build_airtable_create("Log Error", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [700, 800]))
    nodes.append(build_telegram_send("Telegram Error", OWNER_TELEGRAM_CHAT_ID, "={{ $json.telegram_message }}", [700, 1000]))
    return nodes


def build_li09_connections(nodes: list) -> dict:
    return {
        "Trigger": {"main": [[{"node": "Load Finalized Leads", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Load Finalized Leads", "type": "main", "index": 0}]]},
        "Load Finalized Leads": {"main": [[{"node": "Has Leads?", "type": "main", "index": 0}]]},
        "Has Leads?": {"main": [
            [{"node": "Loop Over Leads", "type": "main", "index": 0}],
            [{"node": "No Leads", "type": "main", "index": 0}],
        ]},
        "Loop Over Leads": {"main": [
            [{"node": "Build Pipeline Entry", "type": "main", "index": 0}],
        ]},
        "Build Pipeline Entry": {"main": [[{"node": "Create Pipeline Record", "type": "main", "index": 0}]]},
        "Create Pipeline Record": {"main": [[{"node": "Update Lead Master", "type": "main", "index": 0}]]},
        "Update Lead Master": {"main": [[{"node": "Log CRM Sync", "type": "main", "index": 0}]]},
        "Log CRM Sync": {"main": [[{"node": "Loop Over Leads", "type": "main", "index": 0}]]},
        "Error Trigger": {"main": [[{"node": "Error Handler", "type": "main", "index": 0}]]},
        "Error Handler": {"main": [[{"node": "Log Error", "type": "main", "index": 0}]]},
        "Log Error": {"main": [[{"node": "Telegram Error", "type": "main", "index": 0}]]},
    }


# ======================================================================
# LI-10: FEEDBACK & LEARNING LOOP
# ======================================================================

def build_li10_nodes() -> list:
    nodes = []
    nodes.append(build_sticky_note(
        "Note LI-10",
        "LI-10: Feedback & Learning Loop\nWebhook for outcome feedback + monthly AI analysis of win/loss patterns",
        [0, 100], 500, 120, 6,
    ))
    # Three entry points
    nodes.append(build_webhook_trigger("Webhook Feedback", "linkedin/feedback", [220, 300]))
    nodes.append(build_schedule_trigger("Monthly Schedule", "0 4 1 * *", [220, 500]))
    nodes.append(build_manual_trigger("Manual Trigger", [220, 700]))
    # Route by entry point
    nodes.append(build_switch_node(
        "Route by Trigger", "={{ $executionId ? ($input.first().json.body ? 'webhook' : 'schedule') : 'schedule' }}",
        ["webhook", "schedule"],
        [460, 500],
    ))

    # ── Webhook path ──
    nodes.append(build_code_node("Validate Feedback", LI10_VALIDATE_FEEDBACK_CODE, [700, 300]))
    nodes.append(build_if_node("Is Valid?", "={{ $json.valid === true }}", [940, 300]))
    nodes.append(build_respond_to_webhook("Respond Invalid", [940, 500]))
    # Store feedback
    nodes.append(build_airtable_create("Store Feedback", MARKETING_BASE_ID, TABLE_FEEDBACK, [1180, 300]))
    # Update lead status
    nodes.append(build_airtable_update(
        "Update Lead Status", MARKETING_BASE_ID, TABLE_LEADS, [1420, 300],
        matching_columns=["Lead ID"],
    ))
    # Update pipeline
    nodes.append(build_airtable_update(
        "Update Pipeline", MARKETING_BASE_ID, TABLE_PIPELINE, [1660, 300],
        matching_columns=["Lead ID"],
    ))
    # Respond success
    nodes.append(build_respond_to_webhook("Respond Success", [1900, 300]))

    # ── Schedule path ──
    nodes.append(build_airtable_search(
        "Load All Feedback", MARKETING_BASE_ID, TABLE_FEEDBACK,
        "=NOT({Outcome}='')", [700, 700], always_output=True,
    ))
    nodes.append(build_if_node("Has Data?", "={{ $json.id !== undefined }}", [940, 700]))
    nodes.append(build_noop("No Data", [940, 900]))
    # AI analysis
    nodes.append(build_openrouter_ai(
        "AI Pattern Analysis", LI10_LEARNING_PROMPT,
        " JSON.stringify($input.all().map(i => ({outcome: i.json.outcome || i.json['Outcome'], industry: i.json.industry || '', icp_score: i.json.icp_score_at_contact || i.json['ICP Score At Contact'] || 0, package: i.json.package_sold || i.json['Package Sold'] || '', revenue: i.json.revenue_zar || i.json['Revenue ZAR'] || 0})))",
        [1180, 700], max_tokens=2000, temperature=0.3,
    ))
    # Parse learning
    nodes.append(build_code_node("Parse Learning", LI10_PARSE_LEARNING_CODE, [1420, 700]))
    # Store insights
    nodes.append(build_airtable_create("Store Insights", MARKETING_BASE_ID, TABLE_FEEDBACK, [1660, 700]))
    # Send insights email
    nodes.append(build_gmail_send(
        "Send Insights Email", ALERT_EMAIL,
        "={{ $json.email_subject }}", "={{ $json.email_body }}", [1900, 700],
    ))

    # Error handler
    nodes.append(build_error_trigger("Error Trigger", [220, 1100]))
    nodes.append(build_code_node("Error Handler", ERROR_HANDLER_CODE, [460, 1100]))
    nodes.append(build_airtable_create("Log Error", MARKETING_BASE_ID, TABLE_AGENT_LOGS, [700, 1100]))
    nodes.append(build_telegram_send("Telegram Error", OWNER_TELEGRAM_CHAT_ID, "={{ $json.telegram_message }}", [700, 1300]))
    return nodes


def build_li10_connections(nodes: list) -> dict:
    return {
        "Webhook Feedback": {"main": [[{"node": "Route by Trigger", "type": "main", "index": 0}]]},
        "Monthly Schedule": {"main": [[{"node": "Route by Trigger", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Route by Trigger", "type": "main", "index": 0}]]},
        "Route by Trigger": {"main": [
            [{"node": "Validate Feedback", "type": "main", "index": 0}],
            [{"node": "Load All Feedback", "type": "main", "index": 0}],
        ]},
        # Webhook path
        "Validate Feedback": {"main": [[{"node": "Is Valid?", "type": "main", "index": 0}]]},
        "Is Valid?": {"main": [
            [{"node": "Store Feedback", "type": "main", "index": 0}],
            [{"node": "Respond Invalid", "type": "main", "index": 0}],
        ]},
        "Store Feedback": {"main": [[{"node": "Update Lead Status", "type": "main", "index": 0}]]},
        "Update Lead Status": {"main": [[{"node": "Update Pipeline", "type": "main", "index": 0}]]},
        "Update Pipeline": {"main": [[{"node": "Respond Success", "type": "main", "index": 0}]]},
        # Schedule path
        "Load All Feedback": {"main": [[{"node": "Has Data?", "type": "main", "index": 0}]]},
        "Has Data?": {"main": [
            [{"node": "AI Pattern Analysis", "type": "main", "index": 0}],
            [{"node": "No Data", "type": "main", "index": 0}],
        ]},
        "AI Pattern Analysis": {"main": [[{"node": "Parse Learning", "type": "main", "index": 0}]]},
        "Parse Learning": {"main": [[{"node": "Store Insights", "type": "main", "index": 0}]]},
        "Store Insights": {"main": [[{"node": "Send Insights Email", "type": "main", "index": 0}]]},
        # Error handler
        "Error Trigger": {"main": [[{"node": "Error Handler", "type": "main", "index": 0}]]},
        "Error Handler": {"main": [[{"node": "Log Error", "type": "main", "index": 0}]]},
        "Log Error": {"main": [[{"node": "Telegram Error", "type": "main", "index": 0}]]},
    }


# ======================================================================
# WORKFLOW BUILDERS REGISTRY
# ======================================================================

WORKFLOW_BUILDERS = {
    "li01": {
        "name": "LI-01 Lead Orchestrator",
        "build_nodes": build_li01_nodes,
        "build_connections": build_li01_connections,
        "filename": "li01_orchestrator.json",
        "tags": ["linkedin-dept", "orchestrator"],
    },
    "li02": {
        "name": "LI-02 Lead Discovery",
        "build_nodes": build_li02_nodes,
        "build_connections": build_li02_connections,
        "filename": "li02_discovery.json",
        "tags": ["linkedin-dept", "discovery"],
    },
    "li03": {
        "name": "LI-03 Data Enrichment",
        "build_nodes": build_li03_nodes,
        "build_connections": build_li03_connections,
        "filename": "li03_enrichment.json",
        "tags": ["linkedin-dept", "enrichment", "ai"],
    },
    "li04": {
        "name": "LI-04 ICP Scoring",
        "build_nodes": build_li04_nodes,
        "build_connections": build_li04_connections,
        "filename": "li04_icp_scoring.json",
        "tags": ["linkedin-dept", "scoring", "ai"],
    },
    "li05": {
        "name": "LI-05 Pain Detection",
        "build_nodes": build_li05_nodes,
        "build_connections": build_li05_connections,
        "filename": "li05_pain_detection.json",
        "tags": ["linkedin-dept", "pain-analysis", "ai"],
    },
    "li06": {
        "name": "LI-06 Opportunity Mapping",
        "build_nodes": build_li06_nodes,
        "build_connections": build_li06_connections,
        "filename": "li06_opportunity_mapping.json",
        "tags": ["linkedin-dept", "opportunity", "ai"],
    },
    "li07": {
        "name": "LI-07 Outreach Personalization",
        "build_nodes": build_li07_nodes,
        "build_connections": build_li07_connections,
        "filename": "li07_outreach.json",
        "tags": ["linkedin-dept", "outreach", "ai"],
    },
    "li08": {
        "name": "LI-08 Prioritization QA",
        "build_nodes": build_li08_nodes,
        "build_connections": build_li08_connections,
        "filename": "li08_prioritization_qa.json",
        "tags": ["linkedin-dept", "qa"],
    },
    "li09": {
        "name": "LI-09 CRM Sync",
        "build_nodes": build_li09_nodes,
        "build_connections": build_li09_connections,
        "filename": "li09_crm_sync.json",
        "tags": ["linkedin-dept", "crm"],
    },
    "li10": {
        "name": "LI-10 Feedback Loop",
        "build_nodes": build_li10_nodes,
        "build_connections": build_li10_connections,
        "filename": "li10_feedback_loop.json",
        "tags": ["linkedin-dept", "feedback", "ai"],
    },
}


# ======================================================================
# BUILD / DEPLOY / ACTIVATE / MAIN
# ======================================================================

def get_n8n_client():
    from n8n_client import N8nClient
    api_key = os.getenv("N8N_API_KEY", "")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env")
        sys.exit(1)
    return N8nClient(base_url=N8N_BASE_URL, api_key=api_key)


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python tools/deploy_linkedin_dept.py <build|deploy|activate> [workflow_key]")
        print()
        for key, spec in WORKFLOW_BUILDERS.items():
            print(f"  {key:<8} {spec['name']}")
        sys.exit(1)

    action = args[0]
    target = args[1] if len(args) > 1 else None
    keys = (
        [target]
        if target and target in WORKFLOW_BUILDERS
        else list(WORKFLOW_BUILDERS.keys())
    )

    if target and target not in WORKFLOW_BUILDERS:
        print(f"ERROR: Unknown workflow '{target}'")
        sys.exit(1)

    print("=" * 60)
    print("AVM LINKEDIN LEAD INTELLIGENCE - WORKFLOW BUILDER")
    print("=" * 60)
    print(f"Action: {action}")
    print(f"Workflows: {', '.join(keys)}")
    print()

    output_dir = Path(__file__).parent.parent / "workflows" / "linkedin-dept"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build
    print("Building workflows...")
    built = {}
    for key in keys:
        spec = WORKFLOW_BUILDERS[key]
        nodes = spec["build_nodes"]()
        connections = spec["build_connections"](nodes)
        wf = build_workflow(spec["name"], nodes, connections, tags=spec.get("tags", []))

        path = output_dir / spec["filename"]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)

        node_count = len(nodes)
        print(f"  + {spec['name']:<40} -> {spec['filename']} ({node_count} nodes)")
        built[key] = wf
    print()

    if action == "build":
        print(f"Build complete. {len(built)} workflows saved to {output_dir}")
        return

    # Deploy
    if action in ("deploy", "activate"):
        print("Deploying to n8n (inactive)...")
        client = get_n8n_client()
        deployed_ids = {}
        for key, wf in built.items():
            try:
                resp = client.create_workflow(wf)
                wf_id = resp.get("id", "unknown")
                deployed_ids[key] = wf_id
                print(f"  + {WORKFLOW_BUILDERS[key]['name']:<40} -> {wf_id}")
            except Exception as e:
                print(f"  - {WORKFLOW_BUILDERS[key]['name']:<40} FAILED: {e}")
        print()

        # Activate
        if action == "activate" and deployed_ids:
            print("Activating workflows...")
            for key, wf_id in deployed_ids.items():
                try:
                    client.activate_workflow(wf_id)
                    print(f"  + {WORKFLOW_BUILDERS[key]['name']:<40} ACTIVE")
                except Exception as e:
                    print(f"  - {WORKFLOW_BUILDERS[key]['name']:<40} FAILED: {e}")
            print()

        # Save manifest
        if deployed_ids:
            manifest_dir = Path(__file__).parent.parent / ".tmp"
            manifest_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = manifest_dir / "linkedin_workflow_ids.json"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump({
                    "deployed": deployed_ids,
                    "deployed_at": datetime.now().isoformat(),
                    "department": "linkedin-dept",
                }, f, indent=2)
            print(f"Manifest saved: {manifest_path}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
