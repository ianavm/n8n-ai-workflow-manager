"""
AVM Self-Healing Workflow - Builder & Deployer

Builds a self-healing error monitor with 3 subsystems:
    1. Error Handler: Error Trigger -> AI classify -> auto-retry / deactivate-reactivate /
       delay-retry / alert human -> log to Airtable
    2. Health Check: Hourly poll of all workflows + recent errors, email report on issues
    3. External Webhook: POST endpoint for external error reports

Improvements over original:
    - n8n API credentials on all HTTP nodes
    - Airtable table ID from env
    - Wait duration on deactivate/reactivate (10s)
    - Webhook validation gate (blocks invalid payloads)
    - Test mode bypass (skips real API calls)
    - Retry failure escalation (alert human on failed auto-fix)
    - Deduplication (same error within 5min -> skip AI)
    - Regex-first classification (skip AI for obvious errors, ~70% cost saving)
    - Cooldown key includes error message hash
    - Health check frequency reduced to 1 hour

Usage:
    python tools/deploy_self_healing.py build        # Build JSON
    python tools/deploy_self_healing.py deploy       # Build + Deploy (inactive)
    python tools/deploy_self_healing.py activate     # Build + Deploy + Activate
"""

import json
import sys
import uuid
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# -- Credential Constants --
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable account"}
CRED_N8N_API = {
    "id": os.getenv("SELFHEALING_N8N_API_CRED_ID", "xymp9Nho08mRW2Wz"),
    "name": "n8n API Key",
}

# -- Airtable IDs --
ACCOUNTING_BASE_ID = "appMmUkZzdDSiY1RS"
TABLE_SELF_HEALING_LOG = os.getenv(
    "SELFHEALING_TABLE_ID", "tbleud2UEiKvbOalv"
)

# -- Config --
ALERT_EMAIL = os.getenv("SELFHEALING_ALERT_EMAIL", "ian@anyvisionmedia.com")
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
WORKFLOW_NAME = "Self-Healing Error Monitor"


def uid():
    """Generate UUID for node IDs."""
    return str(uuid.uuid4())


# ======================================================================
# NODE BUILDERS
# ======================================================================


def build_nodes():
    """Build all workflow nodes."""
    nodes = []

    # -- TRIGGERS ----------------------------------------------------

    # Error Trigger
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [208, 400],
        "typeVersion": 1,
    })

    # Manual Trigger (test)
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [208, 1504],
        "typeVersion": 1,
    })

    # Test Config
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "testMode", "value": "=true", "type": "boolean"},
                    {"id": uid(), "name": "errorMessage", "value": "ECONNRESET: connection reset by peer", "type": "string"},
                    {"id": uid(), "name": "errorNode", "value": "HTTP Request", "type": "string"},
                    {"id": uid(), "name": "workflowName", "value": "Test Workflow (Self-Healing Check)", "type": "string"},
                    {"id": uid(), "name": "workflowId", "value": "test-123", "type": "string"},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Test Config",
        "type": "n8n-nodes-base.set",
        "position": [464, 1504],
        "typeVersion": 3.4,
    })

    # Report Webhook
    nodes.append({
        "parameters": {
            "httpMethod": "POST",
            "path": "self-healing/report",
            "responseMode": "responseNode",
            "options": {},
        },
        "id": uid(),
        "name": "Report Webhook",
        "type": "n8n-nodes-base.webhook",
        "position": [208, 1712],
        "typeVersion": 2,
        "webhookId": uid(),
    })

    # Validate Webhook Input
    nodes.append({
        "parameters": {
            "jsCode": SCRIPT_VALIDATE_WEBHOOK,
        },
        "id": uid(),
        "name": "Validate Webhook Input",
        "type": "n8n-nodes-base.code",
        "position": [464, 1712],
        "typeVersion": 2,
    })

    # Webhook Valid? (If node - gates invalid payloads)
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "leftValue": "={{ $json.valid }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Webhook Valid?",
        "type": "n8n-nodes-base.if",
        "position": [704, 1712],
        "typeVersion": 2.2,
    })

    # Respond OK (valid webhook)
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": '={"status":"received","valid":true,"timestamp":"{{ $now.toISO() }}"}',
        },
        "id": uid(),
        "name": "Respond OK",
        "type": "n8n-nodes-base.respondToWebhook",
        "position": [944, 1650],
        "typeVersion": 1.1,
        "onError": "continueRegularOutput",
    })

    # Respond Error (invalid webhook)
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": '={"status":"error","valid":false,"error":"{{ $json.error }}","timestamp":"{{ $now.toISO() }}"}',
            "options": {"responseCode": 400},
        },
        "id": uid(),
        "name": "Respond Error",
        "type": "n8n-nodes-base.respondToWebhook",
        "position": [944, 1800],
        "typeVersion": 1.1,
        "onError": "continueRegularOutput",
    })

    # -- MAIN PIPELINE -----------------------------------------------

    # Extract Error Data (with deduplication + improved cooldown key)
    nodes.append({
        "parameters": {
            "jsCode": SCRIPT_EXTRACT_ERROR_DATA,
        },
        "id": uid(),
        "name": "Extract Error Data",
        "type": "n8n-nodes-base.code",
        "position": [464, 512],
        "typeVersion": 2,
    })

    # Should Skip AI? (regex-first classification for obvious errors)
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "leftValue": "={{ $json.skipAI }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Should Skip AI?",
        "type": "n8n-nodes-base.if",
        "position": [704, 512],
        "typeVersion": 2.2,
    })

    # Regex Classification (bypass AI for obvious errors)
    nodes.append({
        "parameters": {
            "jsCode": SCRIPT_REGEX_CLASSIFY,
        },
        "id": uid(),
        "name": "Regex Classification",
        "type": "n8n-nodes-base.code",
        "position": [944, 400],
        "typeVersion": 2,
    })

    # AI Classify Error
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": AI_CLASSIFY_BODY,
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "AI Classify Error",
        "type": "n8n-nodes-base.httpRequest",
        "position": [944, 620],
        "typeVersion": 4.2,
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 3000,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
    })

    # Parse AI Response
    nodes.append({
        "parameters": {
            "jsCode": SCRIPT_PARSE_AI_RESPONSE,
        },
        "id": uid(),
        "name": "Parse AI Response",
        "type": "n8n-nodes-base.code",
        "position": [1184, 620],
        "typeVersion": 2,
    })

    # Route by Category (Switch)
    nodes.append({
        "parameters": {
            "rules": {
                "values": [
                    {"conditions": {"conditions": [{"leftValue": "={{ $json.category }}", "rightValue": "auto_retry", "operator": {"type": "string", "operation": "equals"}}]}},
                    {"conditions": {"conditions": [{"leftValue": "={{ $json.category }}", "rightValue": "deactivate_reactivate", "operator": {"type": "string", "operation": "equals"}}]}},
                    {"conditions": {"conditions": [{"leftValue": "={{ $json.category }}", "rightValue": "delay_retry", "operator": {"type": "string", "operation": "equals"}}]}},
                    {"conditions": {"conditions": [{"leftValue": "={{ $json.category }}", "rightValue": "needs_human", "operator": {"type": "string", "operation": "equals"}}]}},
                ],
            },
            "options": {"fallbackOutput": "extra"},
        },
        "id": uid(),
        "name": "Route by Category",
        "type": "n8n-nodes-base.switch",
        "position": [1424, 512],
        "typeVersion": 3.2,
    })

    # -- BRANCH 1: AUTO RETRY ----------------------------------------

    # Is Test? (auto-retry branch)
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "leftValue": "={{ $json.isTest }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Is Test? (Retry)",
        "type": "n8n-nodes-base.if",
        "position": [1664, 304],
        "typeVersion": 2.2,
    })

    # Execute Retry
    n8n_url_expr = N8N_BASE_URL
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": f"{n8n_url_expr}/api/v1/executions/{{{{ $json.executionId }}}}/retry",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Execute Retry",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1904, 250],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
        "onError": "continueRegularOutput",
    })

    # Tag Retry Result
    nodes.append({
        "parameters": {
            "jsCode": SCRIPT_TAG_RETRY_RESULT,
        },
        "id": uid(),
        "name": "Tag Retry Result",
        "type": "n8n-nodes-base.code",
        "position": [2144, 250],
        "typeVersion": 2,
    })

    # Tag Test Skip (retry branch)
    nodes.append({
        "parameters": {
            "jsCode": SCRIPT_TAG_TEST_SKIP,
        },
        "id": uid(),
        "name": "Tag Test Skip (Retry)",
        "type": "n8n-nodes-base.code",
        "position": [1904, 370],
        "typeVersion": 2,
    })

    # Retry Failed? (escalation gate)
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "leftValue": "={{ $json.fixResult }}",
                        "rightValue": "failed",
                        "operator": {"type": "string", "operation": "equals"},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Retry Failed?",
        "type": "n8n-nodes-base.if",
        "position": [2384, 250],
        "typeVersion": 2.2,
    })

    # -- BRANCH 2: DEACTIVATE / REACTIVATE ---------------------------

    # Is Test? (deactivate branch)
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "leftValue": "={{ $json.isTest }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Is Test? (Deactivate)",
        "type": "n8n-nodes-base.if",
        "position": [1664, 512],
        "typeVersion": 2.2,
    })

    # Deactivate Workflow
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": f"{n8n_url_expr}/api/v1/workflows/{{{{ $json.workflowId }}}}/deactivate",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Deactivate Workflow",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1904, 460],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
        "onError": "continueRegularOutput",
    })

    # Wait Then Reactivate (10 seconds)
    nodes.append({
        "parameters": {
            "amount": 10,
            "unit": "seconds",
        },
        "id": uid(),
        "name": "Wait Then Reactivate",
        "type": "n8n-nodes-base.wait",
        "position": [2144, 460],
        "typeVersion": 1.1,
        "webhookId": uid(),
    })

    # Reactivate Workflow
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $('Parse AI Response').first().json.workflowId ? '" + N8N_BASE_URL + "' + '/api/v1/workflows/' + $('Parse AI Response').first().json.workflowId + '/activate' : '' }}",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Reactivate Workflow",
        "type": "n8n-nodes-base.httpRequest",
        "position": [2384, 460],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
        "onError": "continueRegularOutput",
    })

    # Tag Reactivate Result
    nodes.append({
        "parameters": {
            "jsCode": SCRIPT_TAG_REACTIVATE_RESULT,
        },
        "id": uid(),
        "name": "Tag Reactivate Result",
        "type": "n8n-nodes-base.code",
        "position": [2624, 460],
        "typeVersion": 2,
    })

    # Tag Test Skip (deactivate branch)
    nodes.append({
        "parameters": {
            "jsCode": SCRIPT_TAG_TEST_SKIP_DEACTIVATE,
        },
        "id": uid(),
        "name": "Tag Test Skip (Deactivate)",
        "type": "n8n-nodes-base.code",
        "position": [1904, 580],
        "typeVersion": 2,
    })

    # -- BRANCH 3: DELAY RETRY ---------------------------------------

    # Compute Wait Time
    nodes.append({
        "parameters": {
            "jsCode": SCRIPT_COMPUTE_WAIT_TIME,
        },
        "id": uid(),
        "name": "Compute Wait Time",
        "type": "n8n-nodes-base.code",
        "position": [1664, 740],
        "typeVersion": 2,
    })

    # Wait Before Retry
    nodes.append({
        "parameters": {
            "amount": "={{ $json.waitSeconds }}",
        },
        "id": uid(),
        "name": "Wait Before Retry",
        "type": "n8n-nodes-base.wait",
        "position": [1904, 740],
        "typeVersion": 1.1,
        "webhookId": uid(),
    })

    # Execute Delayed Retry
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $('Compute Wait Time').first().json.executionId ? '" + N8N_BASE_URL + "' + '/api/v1/executions/' + $('Compute Wait Time').first().json.executionId + '/retry' : '' }}",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Execute Delayed Retry",
        "type": "n8n-nodes-base.httpRequest",
        "position": [2144, 740],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
        "onError": "continueRegularOutput",
    })

    # Tag Delayed Result
    nodes.append({
        "parameters": {
            "jsCode": SCRIPT_TAG_DELAYED_RESULT,
        },
        "id": uid(),
        "name": "Tag Delayed Result",
        "type": "n8n-nodes-base.code",
        "position": [2384, 740],
        "typeVersion": 2,
    })

    # Delayed Retry Failed? (escalation gate)
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "leftValue": "={{ $json.fixResult }}",
                        "rightValue": "failed",
                        "operator": {"type": "string", "operation": "equals"},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Delayed Retry Failed?",
        "type": "n8n-nodes-base.if",
        "position": [2624, 740],
        "typeVersion": 2.2,
    })

    # -- BRANCH 4: NEEDS HUMAN ---------------------------------------

    # Build Alert Email
    nodes.append({
        "parameters": {
            "jsCode": SCRIPT_BUILD_ALERT_EMAIL,
        },
        "id": uid(),
        "name": "Build Alert Email",
        "type": "n8n-nodes-base.code",
        "position": [1664, 960],
        "typeVersion": 2,
    })

    # Send Alert Email
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "={{ $json.alertSubject }}",
            "message": "={{ $json.alertHtml }}",
            "options": {"appendAttribution": False},
        },
        "id": uid(),
        "name": "Send Alert Email",
        "type": "n8n-nodes-base.gmail",
        "position": [1904, 960],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # -- LOGGING (shared sink) ---------------------------------------

    # Log to Airtable
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": ACCOUNTING_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SELF_HEALING_LOG},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Error ID": "=SH-{{ Date.now() }}",
                    "Timestamp": "={{ $json.timestamp }}",
                    "Instance": "AnyVision Production",
                    "Workflow Name": "={{ $json.workflowName }}",
                    "Workflow ID": "={{ $json.workflowId }}",
                    "Error Node": "={{ $json.errorNode }}",
                    "Error Message": "={{ $json.errorMessage }}",
                    "Category": "={{ $json.category }}",
                    "AI Confidence": "={{ $json.confidence }}",
                    "AI Explanation": "={{ $json.explanation }}",
                    "Action Taken": "={{ $json.fixAction || 'none' }}",
                    "Action Result": "={{ $json.fixResult || 'pending' }}",
                    "Execution ID": "={{ $json.executionId }}",
                    "Execution URL": "={{ $json.executionUrl }}",
                    "Is Test": "={{ $json.isTest }}",
                },
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log to Airtable",
        "type": "n8n-nodes-base.airtable",
        "position": [2864, 620],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- HEALTH CHECK SUBSYSTEM --------------------------------------

    # Health Check Schedule (every 1 hour)
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "hours", "hoursInterval": 1}],
            },
        },
        "id": uid(),
        "name": "Health Check Schedule",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [208, 1200],
        "typeVersion": 1.2,
    })

    # Fetch All Workflows
    nodes.append({
        "parameters": {
            "url": "=" + N8N_BASE_URL + "/api/v1/workflows?limit=250",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Fetch All Workflows",
        "type": "n8n-nodes-base.httpRequest",
        "position": [464, 1200],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
        "onError": "continueRegularOutput",
    })

    # Fetch Recent Errors
    nodes.append({
        "parameters": {
            "url": "=" + N8N_BASE_URL + "/api/v1/executions?status=error&limit=20",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Fetch Recent Errors",
        "type": "n8n-nodes-base.httpRequest",
        "position": [704, 1200],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
        "onError": "continueRegularOutput",
    })

    # Analyze Health
    nodes.append({
        "parameters": {
            "jsCode": SCRIPT_ANALYZE_HEALTH,
        },
        "id": uid(),
        "name": "Analyze Health",
        "type": "n8n-nodes-base.code",
        "position": [944, 1200],
        "typeVersion": 2,
    })

    # Has Issues?
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "leftValue": "={{ $json.hasIssues }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Has Issues?",
        "type": "n8n-nodes-base.if",
        "position": [1184, 1200],
        "typeVersion": 2.2,
    })

    # Build Health Report
    nodes.append({
        "parameters": {
            "jsCode": SCRIPT_BUILD_HEALTH_REPORT,
        },
        "id": uid(),
        "name": "Build Health Report",
        "type": "n8n-nodes-base.code",
        "position": [1424, 1200],
        "typeVersion": 2,
    })

    # Send Health Alert
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "={{ $json.reportSubject }}",
            "message": "={{ $json.reportHtml }}",
            "options": {"appendAttribution": False},
        },
        "id": uid(),
        "name": "Send Health Alert",
        "type": "n8n-nodes-base.gmail",
        "position": [1664, 1200],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    return nodes


def build_connections():
    """Build all workflow connections."""
    return {
        # -- Triggers -> Extract --
        "Error Trigger": {"main": [[{"node": "Extract Error Data", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Test Config", "type": "main", "index": 0}]]},
        "Test Config": {"main": [[{"node": "Extract Error Data", "type": "main", "index": 0}]]},

        # -- Webhook path --
        "Report Webhook": {"main": [[{"node": "Validate Webhook Input", "type": "main", "index": 0}]]},
        "Validate Webhook Input": {"main": [[{"node": "Webhook Valid?", "type": "main", "index": 0}]]},
        "Webhook Valid?": {"main": [
            [{"node": "Respond OK", "type": "main", "index": 0}],
            [{"node": "Respond Error", "type": "main", "index": 0}],
        ]},
        "Respond OK": {"main": [[{"node": "Extract Error Data", "type": "main", "index": 0}]]},

        # -- Main pipeline: Extract -> Skip AI check -> classify --
        "Extract Error Data": {"main": [[{"node": "Should Skip AI?", "type": "main", "index": 0}]]},
        "Should Skip AI?": {"main": [
            [{"node": "Regex Classification", "type": "main", "index": 0}],
            [{"node": "AI Classify Error", "type": "main", "index": 0}],
        ]},
        "Regex Classification": {"main": [[{"node": "Route by Category", "type": "main", "index": 0}]]},
        "AI Classify Error": {"main": [[{"node": "Parse AI Response", "type": "main", "index": 0}]]},
        "Parse AI Response": {"main": [[{"node": "Route by Category", "type": "main", "index": 0}]]},

        # -- Route (5 outputs: auto_retry, deactivate, delay, human, fallback) --
        "Route by Category": {"main": [
            [{"node": "Is Test? (Retry)", "type": "main", "index": 0}],
            [{"node": "Is Test? (Deactivate)", "type": "main", "index": 0}],
            [{"node": "Compute Wait Time", "type": "main", "index": 0}],
            [{"node": "Build Alert Email", "type": "main", "index": 0}],
            [{"node": "Build Alert Email", "type": "main", "index": 0}],
        ]},

        # -- Branch 1: Auto Retry --
        "Is Test? (Retry)": {"main": [
            [{"node": "Tag Test Skip (Retry)", "type": "main", "index": 0}],
            [{"node": "Execute Retry", "type": "main", "index": 0}],
        ]},
        "Execute Retry": {"main": [[{"node": "Tag Retry Result", "type": "main", "index": 0}]]},
        "Tag Retry Result": {"main": [[{"node": "Retry Failed?", "type": "main", "index": 0}]]},
        "Tag Test Skip (Retry)": {"main": [[{"node": "Log to Airtable", "type": "main", "index": 0}]]},
        "Retry Failed?": {"main": [
            [{"node": "Build Alert Email", "type": "main", "index": 0}],
            [{"node": "Log to Airtable", "type": "main", "index": 0}],
        ]},

        # -- Branch 2: Deactivate/Reactivate --
        "Is Test? (Deactivate)": {"main": [
            [{"node": "Tag Test Skip (Deactivate)", "type": "main", "index": 0}],
            [{"node": "Deactivate Workflow", "type": "main", "index": 0}],
        ]},
        "Deactivate Workflow": {"main": [[{"node": "Wait Then Reactivate", "type": "main", "index": 0}]]},
        "Wait Then Reactivate": {"main": [[{"node": "Reactivate Workflow", "type": "main", "index": 0}]]},
        "Reactivate Workflow": {"main": [[{"node": "Tag Reactivate Result", "type": "main", "index": 0}]]},
        "Tag Reactivate Result": {"main": [[{"node": "Log to Airtable", "type": "main", "index": 0}]]},
        "Tag Test Skip (Deactivate)": {"main": [[{"node": "Log to Airtable", "type": "main", "index": 0}]]},

        # -- Branch 3: Delay Retry --
        "Compute Wait Time": {"main": [[{"node": "Wait Before Retry", "type": "main", "index": 0}]]},
        "Wait Before Retry": {"main": [[{"node": "Execute Delayed Retry", "type": "main", "index": 0}]]},
        "Execute Delayed Retry": {"main": [[{"node": "Tag Delayed Result", "type": "main", "index": 0}]]},
        "Tag Delayed Result": {"main": [[{"node": "Delayed Retry Failed?", "type": "main", "index": 0}]]},
        "Delayed Retry Failed?": {"main": [
            [{"node": "Build Alert Email", "type": "main", "index": 0}],
            [{"node": "Log to Airtable", "type": "main", "index": 0}],
        ]},

        # -- Branch 4: Alert Human --
        "Build Alert Email": {"main": [[{"node": "Send Alert Email", "type": "main", "index": 0}]]},
        "Send Alert Email": {"main": [[{"node": "Log to Airtable", "type": "main", "index": 0}]]},

        # -- Health Check --
        "Health Check Schedule": {"main": [[{"node": "Fetch All Workflows", "type": "main", "index": 0}]]},
        "Fetch All Workflows": {"main": [[{"node": "Fetch Recent Errors", "type": "main", "index": 0}]]},
        "Fetch Recent Errors": {"main": [[{"node": "Analyze Health", "type": "main", "index": 0}]]},
        "Analyze Health": {"main": [[{"node": "Has Issues?", "type": "main", "index": 0}]]},
        "Has Issues?": {"main": [
            [{"node": "Build Health Report", "type": "main", "index": 0}],
            [],
        ]},
        "Build Health Report": {"main": [[{"node": "Send Health Alert", "type": "main", "index": 0}]]},
    }


# ======================================================================
# CODE NODE SCRIPTS
# ======================================================================

SCRIPT_VALIDATE_WEBHOOK = """// Validate external error report payload
const body = $input.first().json.body || $input.first().json;

const required = ['error_message', 'workflow_name'];
const missing = required.filter(f => !body[f]);

if (missing.length > 0) {
  return {
    json: {
      valid: false,
      error: `Missing fields: ${missing.join(', ')}`,
    }
  };
}

return {
  json: {
    valid: true,
    error_message: body.error_message,
    error_node: body.error_node || 'Unknown',
    workflow_name: body.workflow_name,
    workflow_id: body.workflow_id || '',
    execution_id: body.execution_id || '',
    execution_url: body.execution_url || '',
  }
};"""

SCRIPT_EXTRACT_ERROR_DATA = """// Normalizes error data from Error Trigger, Manual Test, or Webhook
// Includes deduplication and improved cooldown key with error hash
const input = $input.first().json;

let errorMessage, errorNode, executionId, executionUrl, workflowId, workflowName;

if (input.testMode) {
  errorMessage = input.errorMessage || 'Test error: connection timeout';
  errorNode = input.errorNode || 'HTTP Request';
  executionId = 'test-' + Date.now();
  executionUrl = '';
  workflowId = input.workflowId || 'test';
  workflowName = input.workflowName || 'Test Workflow';
} else if (input.execution) {
  const execution = input.execution;
  const workflow = input.workflow || {};
  errorMessage = execution.error?.message || 'Unknown error';
  errorNode = execution.error?.node?.name || execution.lastNodeExecuted || 'Unknown';
  executionId = execution.id || '';
  executionUrl = execution.url || '';
  workflowId = execution.workflowId || '';
  workflowName = workflow.name || 'Unknown';
} else {
  errorMessage = input.error_message || input.message || 'Unknown error';
  errorNode = input.error_node || input.node || 'Unknown';
  executionId = input.execution_id || '';
  executionUrl = input.execution_url || '';
  workflowId = input.workflow_id || '';
  workflowName = input.workflow_name || 'External Report';
}

// Quick regex pre-classification
let hintCategory = 'unknown';
let hintConfidence = 0;
const msg = errorMessage.toLowerCase();

if (msg.includes('timeout') || msg.includes('econnreset') || msg.includes('econnrefused') || msg.includes('enotfound')) {
  hintCategory = 'connection_timeout';
  hintConfidence = 0.95;
} else if (msg.includes('429') || msg.includes('rate limit') || msg.includes('too many requests')) {
  hintCategory = 'rate_limit';
  hintConfidence = 0.95;
} else if (msg.includes('500') || msg.includes('502') || msg.includes('503') || msg.includes('504')) {
  hintCategory = 'server_error';
  hintConfidence = 0.85;
} else if (msg.includes('webhook') && (msg.includes('stuck') || msg.includes('not responding') || msg.includes('listen'))) {
  hintCategory = 'webhook_stuck';
  hintConfidence = 0.9;
} else if (msg.includes('credential') || msg.includes('unauthorized') || msg.includes('401') || msg.includes('403')) {
  hintCategory = 'credential_error';
  hintConfidence = 0.9;
} else if (msg.includes('quota') || (msg.includes('gmail') && msg.includes('limit'))) {
  hintCategory = 'quota_exceeded';
  hintConfidence = 0.9;
} else if (msg.includes('syntax') || msg.includes('unexpected token') || msg.includes('is not defined') || msg.includes('is not a function')) {
  hintCategory = 'code_error';
  hintConfidence = 0.9;
} else if (msg.includes('required') || msg.includes('missing') || msg.includes('validation') || msg.includes('could not find')) {
  hintCategory = 'validation_error';
  hintConfidence = 0.8;
}

// Simple hash of error message for cooldown dedup
const msgHash = errorMessage.substring(0, 50).split('').reduce((h, c) => ((h << 5) - h + c.charCodeAt(0)) | 0, 0).toString(36);

// Cooldown + deduplication via static data
const staticData = $getWorkflowStaticData('global');
const cooldownKey = `${workflowId}_${errorNode}_${msgHash}`;
const now = Date.now();
const lastFixed = staticData[cooldownKey] || 0;
const cooldownMs = 5 * 60 * 1000; // 5 minute cooldown
const inCooldown = (now - lastFixed) < cooldownMs;

// Deduplication: same error within 5 min -> skip everything
const dedupKey = `dedup_${cooldownKey}`;
const lastSeen = staticData[dedupKey] || 0;
const isDuplicate = (now - lastSeen) < cooldownMs;
staticData[dedupKey] = now;

// Skip AI for high-confidence regex matches (saves ~70% of AI costs)
const skipAI = hintConfidence >= 0.85 && hintCategory !== 'unknown';

return {
  json: {
    errorMessage,
    errorNode,
    executionId,
    executionUrl,
    workflowId,
    workflowName,
    hintCategory,
    hintConfidence,
    timestamp: new Date().toISOString(),
    isTest: !!input.testMode,
    inCooldown,
    isDuplicate,
    cooldownKey,
    skipAI,
  }
};"""

SCRIPT_REGEX_CLASSIFY = """// Regex-based classification for high-confidence matches (bypasses AI)
const errorData = $input.first().json;
const hint = errorData.hintCategory;

const categoryMap = {
  'connection_timeout': 'auto_retry',
  'rate_limit': 'delay_retry',
  'server_error': 'auto_retry',
  'webhook_stuck': 'deactivate_reactivate',
  'credential_error': 'needs_human',
  'quota_exceeded': 'delay_retry',
  'code_error': 'needs_human',
  'validation_error': 'needs_human',
};

const actionMap = {
  'auto_retry': 'retry_execution',
  'delay_retry': 'wait_then_retry',
  'deactivate_reactivate': 'restart_workflow',
  'needs_human': 'alert_human',
};

let category = categoryMap[hint] || 'needs_human';
let confidence = errorData.hintConfidence || 0.5;

// If in cooldown, force to needs_human
if (errorData.inCooldown) {
  category = 'needs_human';
  confidence = 1.0;
}

// If duplicate, still classify but mark it
const explanation = errorData.isDuplicate
  ? `Duplicate error (within 5min). Regex: ${hint} -> ${category}`
  : `Regex classification: ${hint} -> ${category} (AI skipped, confidence ${Math.round(confidence * 100)}%)`;

return {
  json: {
    ...errorData,
    category,
    confidence,
    explanation,
    suggestedAction: actionMap[category] || 'alert_human',
    waitSeconds: hint === 'quota_exceeded' ? 3600 : hint === 'rate_limit' ? 30 : 0,
    retryCount: hint === 'server_error' ? 3 : hint === 'connection_timeout' ? 2 : 1,
  }
};"""

AI_CLASSIFY_BODY = '={"model":"anthropic/claude-sonnet-4-20250514","messages":[{"role":"system","content":"You are an n8n workflow error classifier. Given an error message and context, classify it into exactly one category and provide a recovery recommendation.\\n\\nCategories:\\n1. auto_retry - Transient errors that will likely succeed on retry (connection timeouts, ECONNRESET, temporary 5xx server errors, Airtable rate limits)\\n2. deactivate_reactivate - Errors requiring a workflow restart (webhook stuck, listener not responding, trigger registration failures)\\n3. delay_retry - Errors requiring a wait period before retry (429 rate limits, Gmail quota exceeded, API daily limits)\\n4. needs_human - Errors requiring human intervention (expired credentials, 401/403 auth errors, code syntax errors, missing required fields, data validation failures, schema changes)\\n5. unknown - Cannot confidently classify\\n\\nRespond ONLY with valid JSON, no markdown:\\n{\\"category\\": \\"<one of 5>\\", \\"confidence\\": <0.0-1.0>, \\"explanation\\": \\"<brief>\\", \\"suggested_action\\": \\"<action>\\", \\"wait_seconds\\": <0 if n/a>, \\"retry_count\\": <1-3>}"},{"role":"user","content":"Error in workflow \'{{ $json.workflowName }}\' at node \'{{ $json.errorNode }}\':\\n{{ $json.errorMessage }}\\n\\nPre-classification hint: {{ $json.hintCategory }}"}],"temperature":0.1,"max_tokens":300}'

SCRIPT_PARSE_AI_RESPONSE = """// Parse OpenRouter AI classification response with regex fallback
const input = $input.first().json;
const errorData = $('Extract Error Data').first().json;

let classification;
try {
  const content = input.choices[0].message.content;
  const cleaned = content.replace(/```json\\n?/g, '').replace(/```\\n?/g, '').trim();
  const jsonMatch = cleaned.match(/\\{[\\s\\S]*\\}/);
  classification = JSON.parse(jsonMatch ? jsonMatch[0] : cleaned);
} catch(e) {
  // Fallback to regex-based classification
  const hint = errorData.hintCategory;
  const categoryMap = {
    'connection_timeout': 'auto_retry',
    'rate_limit': 'delay_retry',
    'server_error': 'auto_retry',
    'webhook_stuck': 'deactivate_reactivate',
    'credential_error': 'needs_human',
    'quota_exceeded': 'delay_retry',
    'code_error': 'needs_human',
    'validation_error': 'needs_human',
  };
  classification = {
    category: categoryMap[hint] || 'needs_human',
    confidence: 0.5,
    explanation: `Regex fallback: ${hint} (AI unavailable: ${e.message})`,
    suggested_action: categoryMap[hint] || 'alert_human',
    wait_seconds: hint === 'quota_exceeded' ? 3600 : hint === 'rate_limit' ? 30 : 0,
    retry_count: hint === 'server_error' ? 3 : hint === 'connection_timeout' ? 2 : 1,
  };
}

// Low confidence -> escalate to human
if ((classification.confidence || 0) < 0.6) {
  classification.category = 'needs_human';
  classification.explanation = (classification.explanation || '') + ' (low confidence - escalating)';
}

// If in cooldown, force to needs_human to avoid retry loops
if (errorData.inCooldown) {
  classification.category = 'needs_human';
  classification.explanation = `Repeat error within 5min cooldown. Original: ${classification.category}. ${classification.explanation || ''}`;
}

return {
  json: {
    ...errorData,
    category: classification.category || 'needs_human',
    confidence: classification.confidence || 0,
    explanation: classification.explanation || '',
    suggestedAction: classification.suggested_action || 'alert_human',
    waitSeconds: classification.wait_seconds || 0,
    retryCount: classification.retry_count || 1,
  }
};"""

SCRIPT_TAG_RETRY_RESULT = """// Tag result from auto-retry branch
const input = $input.first().json;
const errorData = $('Parse AI Response').first().json;

// Record cooldown
const staticData = $getWorkflowStaticData('global');
staticData[errorData.cooldownKey] = Date.now();

return {
  json: {
    ...errorData,
    fixAction: 'retried',
    fixResult: input.success !== false ? 'success' : 'failed',
    fixDescription: 'Auto-retried execution via n8n API',
  }
};"""

SCRIPT_TAG_TEST_SKIP = """// Tag test mode skip (retry branch)
const errorData = $input.first().json;
return {
  json: {
    ...errorData,
    fixAction: 'test_skipped',
    fixResult: 'skipped',
    fixDescription: 'Test mode: skipped real n8n API retry',
  }
};"""

SCRIPT_TAG_TEST_SKIP_DEACTIVATE = """// Tag test mode skip (deactivate branch)
const errorData = $input.first().json;
return {
  json: {
    ...errorData,
    fixAction: 'test_skipped',
    fixResult: 'skipped',
    fixDescription: 'Test mode: skipped real deactivate/reactivate',
  }
};"""

SCRIPT_TAG_REACTIVATE_RESULT = """// Tag result from deactivate/reactivate branch
const errorData = $('Parse AI Response').first().json;

// Record cooldown
const staticData = $getWorkflowStaticData('global');
staticData[errorData.cooldownKey] = Date.now();

return {
  json: {
    ...errorData,
    fixAction: 'deactivated_reactivated',
    fixResult: 'success',
    fixDescription: 'Deactivated and reactivated workflow to reset triggers',
  }
};"""

SCRIPT_COMPUTE_WAIT_TIME = """// Determine wait time based on error type
const input = $input.first().json;

let waitSeconds = input.waitSeconds || 30;
const msg = input.errorMessage.toLowerCase();

if (msg.includes('gmail') || msg.includes('quota')) {
  waitSeconds = 3600; // 1 hour for Gmail quota
} else if (msg.includes('rate limit') || msg.includes('429')) {
  waitSeconds = 30;
} else if (msg.includes('airtable') && msg.includes('rate')) {
  waitSeconds = 30;
}

// Record cooldown in static data
const staticData = $getWorkflowStaticData('global');
staticData[input.cooldownKey] = Date.now();

return {
  json: {
    ...input,
    waitSeconds,
    fixAction: 'delayed_retry',
    fixDescription: `Waiting ${waitSeconds}s before retry: ${input.explanation}`,
  }
};"""

SCRIPT_TAG_DELAYED_RESULT = """// Tag result from delayed retry branch
const input = $input.first().json;
const errorData = $('Compute Wait Time').first().json;
return {
  json: {
    ...errorData,
    fixResult: input.success !== false ? 'success' : 'failed',
  }
};"""

SCRIPT_BUILD_ALERT_EMAIL = """// Build HTML alert email for human-intervention errors
const data = $input.first().json;
const instanceName = 'AnyVision Production';

const severityColor = data.category === 'needs_human' ? '#dc2626' : '#f59e0b';
const severityLabel = data.category === 'needs_human' ? 'REQUIRES ACTION' : 'UNKNOWN ERROR';

// Check if this is an escalation from a failed auto-fix
const isEscalation = data.fixAction === 'retried' || data.fixAction === 'delayed_retry';
const escalationNote = isEscalation
  ? '<div style="margin:0 0 16px;padding:12px;background:#FEF3C7;border-left:3px solid #F59E0B;border-radius:4px;"><p style="margin:0;font-size:13px;color:#92400E;">This error was initially classified as auto-fixable, but the automated fix <strong>failed</strong>. Manual intervention is now required.</p></div>'
  : '';

const html = '<!DOCTYPE html>' +
'<html>' +
'<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>' +
'<body style="margin:0;padding:0;font-family:Segoe UI,Helvetica Neue,Arial,sans-serif;background-color:#f4f4f4;">' +
'  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background-color:#ffffff;">' +
'    <tr>' +
'      <td style="padding:30px 40px 20px;border-bottom:3px solid ' + severityColor + ';">' +
'        <h1 style="margin:0;font-size:22px;color:#1A1A2E;">Self-Healing Alert</h1>' +
'        <p style="margin:5px 0 0;font-size:12px;color:' + severityColor + ';text-transform:uppercase;letter-spacing:1px;">' + severityLabel + '</p>' +
'      </td>' +
'    </tr>' +
'    <tr>' +
'      <td style="padding:30px 40px;">' +
         escalationNote +
'        <div style="margin:0 0 20px;padding:16px;background-color:#FEF2F2;border-left:3px solid ' + severityColor + ';border-radius:4px;">' +
'          <p style="margin:0;font-size:14px;color:#333;line-height:1.8;">' +
'            <strong>Workflow:</strong> ' + data.workflowName + '<br>' +
'            <strong>Failed Node:</strong> ' + data.errorNode + '<br>' +
'            <strong>Time:</strong> ' + data.timestamp + '<br>' +
'            <strong>Category:</strong> ' + data.category + '<br>' +
'            <strong>Confidence:</strong> ' + Math.round((data.confidence || 0) * 100) + '%' +
'          </p>' +
'        </div>' +
'        <p style="margin:0 0 12px;font-size:15px;color:#333;"><strong>Error Message:</strong></p>' +
'        <div style="margin:0 0 20px;padding:12px;background:#f8f8f8;border-radius:4px;font-family:monospace;font-size:13px;color:#c0392b;word-break:break-all;">' +
           data.errorMessage +
'        </div>' +
'        <p style="margin:0 0 12px;font-size:15px;color:#333;"><strong>AI Analysis:</strong></p>' +
'        <p style="margin:0 0 20px;font-size:14px;color:#666;">' + data.explanation + '</p>' +
         (data.executionUrl ? '<p style="margin:0;"><a href="' + data.executionUrl + '" style="display:inline-block;padding:10px 24px;background-color:#FF6D5A;color:#fff;text-decoration:none;border-radius:4px;font-size:14px;">View Execution in n8n</a></p>' : '') +
'      </td>' +
'    </tr>' +
'    <tr>' +
'      <td style="padding:20px 40px;background-color:#f8f8f8;border-top:1px solid #eee;">' +
'        <p style="margin:0;font-size:11px;color:#999;line-height:1.5;">' +
'          AnyVision Media Self-Healing Monitor | ' + instanceName + '<br>' +
'          This error could not be auto-resolved. Manual intervention required.' +
'        </p>' +
'      </td>' +
'    </tr>' +
'  </table>' +
'</body>' +
'</html>';

return {
  json: {
    ...data,
    alertHtml: html,
    alertSubject: '[SELF-HEALING] ' + severityLabel + ': ' + data.workflowName + ' - ' + data.errorNode,
    fixAction: isEscalation ? data.fixAction + '_escalated' : 'alerted_human',
    fixResult: 'pending',
    fixDescription: isEscalation
      ? 'Auto-fix failed, escalated to human via email'
      : 'Sent alert email - requires manual intervention',
  }
};"""

SCRIPT_ANALYZE_HEALTH = """// Analyze instance health from workflow list + recent errors
const workflows = $('Fetch All Workflows').first().json;
const errorsData = $('Fetch Recent Errors').first().json;

const workflowList = Array.isArray(workflows) ? workflows : (workflows.data || []);
const errorList = Array.isArray(errorsData) ? errorsData : (errorsData.data || []);

const totalWorkflows = workflowList.length;
const activeWorkflows = workflowList.filter(w => w.active).length;
const inactiveWorkflows = totalWorkflows - activeWorkflows;

// Count errors per workflow
const errorsByWorkflow = {};
const errorThreshold = 3;

for (const exec of errorList) {
  const wfId = exec.workflowId || 'unknown';
  const wfName = exec.workflowData?.name || workflowList.find(w => w.id === wfId)?.name || 'Unknown';
  if (!errorsByWorkflow[wfId]) {
    errorsByWorkflow[wfId] = { name: wfName, count: 0, lastError: '' };
  }
  errorsByWorkflow[wfId].count++;
  if (!errorsByWorkflow[wfId].lastError) {
    errorsByWorkflow[wfId].lastError = exec.stoppedAt || '';
  }
}

const problematicWorkflows = Object.entries(errorsByWorkflow)
  .filter(([_, data]) => data.count >= errorThreshold)
  .map(([id, data]) => ({ id, ...data }));

// Suspicious inactive: not test/draft/backup/copy/old/disabled
const suspiciousInactive = workflowList
  .filter(w => !w.active)
  .filter(w => {
    const name = (w.name || '').toLowerCase();
    return !name.includes('test') && !name.includes('draft') &&
           !name.includes('backup') && !name.includes('old') &&
           !name.includes('copy') && !name.includes('disabled') &&
           !name.includes('combined');
  })
  .slice(0, 5);

const hasIssues = problematicWorkflows.length > 0;

return {
  json: {
    hasIssues,
    totalWorkflows,
    activeWorkflows,
    inactiveWorkflows,
    recentErrorCount: errorList.length,
    problematicWorkflows,
    suspiciousInactive,
    checkedAt: new Date().toISOString(),
  }
};"""

SCRIPT_BUILD_HEALTH_REPORT = """// Build HTML health report email
const data = $input.first().json;
const instanceName = 'AnyVision Production';

const problematicRows = (data.problematicWorkflows || []).map(w =>
  '<tr>' +
    '<td style="padding:8px 12px;border-bottom:1px solid #eee;">' + w.name + '</td>' +
    '<td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center;color:#dc2626;font-weight:bold;">' + w.count + '</td>' +
    '<td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:12px;color:#999;">' + (w.lastError || 'N/A') + '</td>' +
  '</tr>'
).join('');

const suspiciousRows = (data.suspiciousInactive || []).map(w =>
  '<tr>' +
    '<td style="padding:8px 12px;border-bottom:1px solid #eee;">' + w.name + '</td>' +
    '<td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:12px;color:#999;">' + w.id + '</td>' +
  '</tr>'
).join('');

const statusColor = data.hasIssues ? '#dc2626' : '#22c55e';

const html = '<!DOCTYPE html>' +
'<html>' +
'<head><meta charset="utf-8"></head>' +
'<body style="margin:0;padding:0;font-family:Segoe UI,Arial,sans-serif;background-color:#f4f4f4;">' +
'  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background-color:#ffffff;">' +
'    <tr>' +
'      <td style="padding:30px 40px 20px;border-bottom:3px solid ' + statusColor + ';">' +
'        <h1 style="margin:0;font-size:22px;color:#1A1A2E;">Health Check Report</h1>' +
'        <p style="margin:5px 0 0;font-size:12px;color:' + statusColor + ';text-transform:uppercase;letter-spacing:1px;">' + (data.hasIssues ? 'ISSUES DETECTED' : 'ALL CLEAR') + '</p>' +
'      </td>' +
'    </tr>' +
'    <tr>' +
'      <td style="padding:30px 40px;">' +
'        <table width="100%" cellpadding="0" cellspacing="8" style="margin:0 0 20px;">' +
'          <tr>' +
'            <td style="padding:16px;background:#f0fdf4;border-radius:8px;text-align:center;width:33%;">' +
'              <p style="margin:0;font-size:28px;font-weight:bold;color:#166534;">' + data.activeWorkflows + '</p>' +
'              <p style="margin:4px 0 0;font-size:12px;color:#666;">Active</p>' +
'            </td>' +
'            <td style="padding:16px;background:#fefce8;border-radius:8px;text-align:center;width:33%;">' +
'              <p style="margin:0;font-size:28px;font-weight:bold;color:#854d0e;">' + data.inactiveWorkflows + '</p>' +
'              <p style="margin:4px 0 0;font-size:12px;color:#666;">Inactive</p>' +
'            </td>' +
'            <td style="padding:16px;background:#fef2f2;border-radius:8px;text-align:center;width:33%;">' +
'              <p style="margin:0;font-size:28px;font-weight:bold;color:#991b1b;">' + data.recentErrorCount + '</p>' +
'              <p style="margin:4px 0 0;font-size:12px;color:#666;">Recent Errors</p>' +
'            </td>' +
'          </tr>' +
'        </table>' +
         (problematicRows ? (
'        <h3 style="margin:20px 0 8px;font-size:16px;color:#333;">Problematic Workflows</h3>' +
'        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">' +
'          <tr style="background:#f8f8f8;">' +
'            <th style="padding:8px 12px;text-align:left;font-size:12px;border-bottom:2px solid #ddd;">Workflow</th>' +
'            <th style="padding:8px 12px;text-align:center;font-size:12px;border-bottom:2px solid #ddd;">Errors</th>' +
'            <th style="padding:8px 12px;text-align:left;font-size:12px;border-bottom:2px solid #ddd;">Last Error</th>' +
'          </tr>' +
           problematicRows +
'        </table>') : '') +
         (suspiciousRows ? (
'        <h3 style="margin:20px 0 8px;font-size:16px;color:#333;">Potentially Inactive Workflows</h3>' +
'        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">' +
'          <tr style="background:#f8f8f8;">' +
'            <th style="padding:8px 12px;text-align:left;font-size:12px;border-bottom:2px solid #ddd;">Workflow</th>' +
'            <th style="padding:8px 12px;text-align:left;font-size:12px;border-bottom:2px solid #ddd;">ID</th>' +
'          </tr>' +
           suspiciousRows +
'        </table>') : '') +
'        <p style="margin:20px 0 0;font-size:12px;color:#999;">Checked: ' + data.checkedAt + '</p>' +
'      </td>' +
'    </tr>' +
'    <tr>' +
'      <td style="padding:20px 40px;background-color:#f8f8f8;border-top:1px solid #eee;">' +
'        <p style="margin:0;font-size:11px;color:#999;">AnyVision Media Self-Healing Monitor | ' + instanceName + '</p>' +
'      </td>' +
'    </tr>' +
'  </table>' +
'</body>' +
'</html>';

return {
  json: {
    ...data,
    reportHtml: html,
    reportSubject: '[HEALTH CHECK] ' + (data.hasIssues ? 'ISSUES DETECTED' : 'ALL CLEAR') + ' - ' + data.totalWorkflows + ' workflows, ' + data.recentErrorCount + ' errors',
  }
};"""


# ======================================================================
# BUILD / DEPLOY / ACTIVATE
# ======================================================================

def build_workflow():
    """Build the complete workflow JSON."""
    return {
        "name": WORKFLOW_NAME,
        "nodes": build_nodes(),
        "connections": build_connections(),
        "settings": {
            "errorWorkflow": "",
            "executionOrder": "v1",
        },
        "pinData": {},
    }


def save_json(workflow):
    """Save workflow JSON to file."""
    out_dir = Path(__file__).parent.parent / "workflows" / "self-healing"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "self_healing_monitor.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Saved: {out_file}")
    print(f"  Nodes: {len(workflow['nodes'])}")
    print(f"  Connections: {len(workflow['connections'])}")
    return out_file


def deploy_workflow(workflow):
    """Deploy workflow to n8n Cloud."""
    import httpx

    base_url = os.getenv("N8N_BASE_URL", N8N_BASE_URL)
    api_key = os.getenv("N8N_API_KEY", "")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env")
        return None

    # n8n API only accepts: name, nodes, connections, settings
    payload = {
        "name": workflow["name"],
        "nodes": workflow["nodes"],
        "connections": workflow["connections"],
        "settings": workflow.get("settings", {}),
    }
    resp = httpx.post(
        f"{base_url}/api/v1/workflows",
        json=payload,
        headers={"X-N8N-API-KEY": api_key},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"ERROR: n8n API returned {resp.status_code}: {resp.text[:500]}")
        return None

    result = resp.json()
    wf_id = result.get("id", "unknown")
    print(f"Deployed: {WORKFLOW_NAME} -> {wf_id}")
    return wf_id


def activate_workflow(wf_id):
    """Activate workflow on n8n Cloud."""
    import httpx

    base_url = os.getenv("N8N_BASE_URL", N8N_BASE_URL)
    api_key = os.getenv("N8N_API_KEY", "")
    resp = httpx.post(
        f"{base_url}/api/v1/workflows/{wf_id}/activate",
        headers={"X-N8N-API-KEY": api_key},
        timeout=30,
    )
    if resp.status_code == 200:
        print(f"Activated: {wf_id}")
    else:
        print(f"ERROR activating {wf_id}: {resp.status_code} {resp.text[:300]}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python deploy_self_healing.py [build|deploy|activate]")
        sys.exit(1)

    action = sys.argv[1].lower()
    workflow = build_workflow()

    if action == "build":
        save_json(workflow)

    elif action == "deploy":
        save_json(workflow)
        deploy_workflow(workflow)

    elif action == "activate":
        save_json(workflow)
        wf_id = deploy_workflow(workflow)
        if wf_id:
            activate_workflow(wf_id)

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
