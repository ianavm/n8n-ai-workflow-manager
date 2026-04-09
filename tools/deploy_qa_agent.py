"""
AVM QA Agent - Workflow Builder & Deployer

Builds 3 QA workflows for automated testing using n8n HTTP nodes.

Workflows:
    QA-01: Daily Smoke Test       (Daily 06:00 SAST = 04:00 UTC) - Health check all URLs, alert on failures
    QA-02: Weekly Regression Suite (Sun 02:00 SAST = 00:00 UTC) - Comprehensive tests + AI regression analysis
    QA-03: Performance Benchmark   (Daily 12:00 SAST = 10:00 UTC) - PageSpeed API, threshold alerts

Usage:
    python tools/deploy_qa_agent.py build              # Build all JSONs
    python tools/deploy_qa_agent.py build qa01          # Build QA-01 only
    python tools/deploy_qa_agent.py deploy              # Build + Deploy (inactive)
    python tools/deploy_qa_agent.py activate             # Build + Deploy + Activate
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

# -- Credential Constants --
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail AVM"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable PAT"}

# -- Airtable IDs --
ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "appTCh0EeXQp0XqzW")
TABLE_QA_RESULTS = os.getenv("QA_RESULTS_TABLE_ID", "REPLACE_AFTER_SETUP")

# -- Config --
AI_MODEL = "anthropic/claude-sonnet-4-20250514"
ALERT_EMAIL = "ian@anyvisionmedia.com"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# URLs to test
PORTAL_URL = "https://portal.anyvisionmedia.com"
LANDING_URL = "https://www.anyvisionmedia.com"

# Performance thresholds
THRESHOLDS = {
    "page_load_ms": 3000,
    "lcp_ms": 2500,
    "cls": 0.1,
    "status_code": 200,
}


def uid():
    """Generate UUID for node IDs."""
    return str(uuid.uuid4())


def airtable_ref(base, table):
    return {"base": {"__rl": True, "value": base, "mode": "id"},
            "table": {"__rl": True, "value": table, "mode": "id"}}


# ======================================================================
# QA-01: Daily Smoke Test
# ======================================================================

def build_qa01_nodes():
    nodes = []

    # 1. Schedule Trigger (Daily 04:00 UTC = 06:00 SAST)
    nodes.append({
        "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 4 * * *"}]}},
        "id": uid(), "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
        "position": [220, 300],
    })

    # 2. Set Test URLs
    nodes.append({
        "parameters": {"mode": "raw", "jsonOutput": json.dumps([
            {"url": PORTAL_URL + "/login", "name": "Portal Login", "expect": "portal"},
            {"url": PORTAL_URL + "/dashboard", "name": "Portal Dashboard", "expect": "portal"},
            {"url": LANDING_URL, "name": "Landing Page Home", "expect": "AnyVision"},
            {"url": LANDING_URL + "/about", "name": "Landing Page About", "expect": "AnyVision"},
            {"url": LANDING_URL + "/services", "name": "Landing Page Services", "expect": "AnyVision"},
        ]), "options": {}},
        "id": uid(), "name": "Set Test URLs",
        "type": "n8n-nodes-base.set", "typeVersion": 3.4,
        "position": [440, 300],
    })

    # 3. Split URLs (Code)
    nodes.append({
        "parameters": {"jsCode": """const urls = $input.first().json;
const items = Array.isArray(urls) ? urls : (urls.json ? [urls] : Object.values(urls));
return items.map(u => ({json: u}));"""},
        "id": uid(), "name": "Split URLs",
        "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [660, 300],
    })

    # 4. HTTP Health Check
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "={{ $json.url }}",
            "options": {"timeout": 10000, "redirect": {"followRedirects": True}},
        },
        "id": uid(), "name": "HTTP Health Check",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": [880, 300],
        "continueOnFail": True,
        "alwaysOutputData": True,
    })

    # 5. Analyze Response (Code)
    nodes.append({
        "parameters": {"jsCode": """const items = $input.all();
const results = [];
for (const item of items) {
  const d = item.json;
  const urlInfo = $('Split URLs').all()[items.indexOf(item)]?.json || {};
  const statusCode = d.statusCode || d.status || 0;
  const responseTime = d.responseTime || d.timings?.total || 0;
  const body = typeof d.data === 'string' ? d.data : (typeof d.body === 'string' ? d.body : JSON.stringify(d));
  const expectStr = urlInfo.expect || 'AnyVision';
  const hasExpected = body.toLowerCase().includes(expectStr.toLowerCase());
  const isErrorPage = body.toLowerCase().includes('error') && body.toLowerCase().includes('500');
  const passed = statusCode === """ + str(THRESHOLDS["status_code"]) + """ && responseTime < """ + str(THRESHOLDS["page_load_ms"]) + """ && hasExpected && !isErrorPage;
  results.push({json: {
    url: urlInfo.url || d.url || 'unknown',
    name: urlInfo.name || 'unknown',
    status_code: statusCode,
    response_time_ms: responseTime,
    has_expected_content: hasExpected,
    is_error_page: isErrorPage,
    passed: passed,
    reason: !passed ? (statusCode !== 200 ? 'Bad status: ' + statusCode : responseTime >= """ + str(THRESHOLDS["page_load_ms"]) + """ ? 'Slow: ' + responseTime + 'ms' : !hasExpected ? 'Missing expected content' : 'Error page detected') : 'OK',
  }});
}
return results;"""},
        "id": uid(), "name": "Analyze Response",
        "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [1100, 300],
    })

    # 6. Aggregate Results (Code)
    nodes.append({
        "parameters": {"jsCode": """const results = $input.all().map(i => i.json);
const total = results.length;
const passed = results.filter(r => r.passed).length;
const failed = total - passed;
const healthScore = total > 0 ? Math.round((passed / total) * 100) : 0;
const startTime = $('Schedule Trigger').first().json.timestamp || new Date().toISOString();
const duration = Date.now() - new Date(startTime).getTime();
return [{json: {
  date: new Date().toISOString().split('T')[0],
  test_suite: 'Daily Smoke',
  total_tests: total,
  passed: passed,
  failed: failed,
  health_score: healthScore,
  details: JSON.stringify(results),
  duration_ms: duration > 0 && duration < 600000 ? duration : 0,
  failed_tests: results.filter(r => !r.passed),
}}];"""},
        "id": uid(), "name": "Aggregate Results",
        "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [1320, 300],
    })

    # 7. Write Results (Airtable create)
    nodes.append({
        "parameters": {
            "operation": "create",
            **airtable_ref(ORCH_BASE_ID, TABLE_QA_RESULTS),
            "columns": {"value": {
                "Date": "={{ $json.date }}",
                "Test Suite": "={{ $json.test_suite }}",
                "Total Tests": "={{ $json.total_tests }}",
                "Passed": "={{ $json.passed }}",
                "Failed": "={{ $json.failed }}",
                "Health Score %": "={{ $json.health_score }}",
                "Details": "={{ $json.details }}",
                "Duration ms": "={{ $json.duration_ms }}",
            }},
            "options": {},
        },
        "id": uid(), "name": "Write Results",
        "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1540, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 8. Check Failures (If)
    nodes.append({
        "parameters": {
            "conditions": {"conditions": [
                {"leftValue": "={{ $('Aggregate Results').first().json.failed }}",
                 "rightValue": 0,
                 "operator": {"type": "number", "operation": "gt"}},
            ]},
            "options": {},
        },
        "id": uid(), "name": "Check Failures",
        "type": "n8n-nodes-base.if", "typeVersion": 2.2,
        "position": [1760, 300],
    })

    # 9. Alert Email (Gmail)
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=QA ALERT: Smoke Test Failures ({{ $('Aggregate Results').first().json.failed }}/{{ $('Aggregate Results').first().json.total_tests }} failed)",
            "emailType": "html",
            "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FF6D5A;padding:15px;text-align:center"><h2 style="color:white;margin:0">QA Alert - Smoke Test Failures</h2></div>
<div style="padding:20px">
<p><strong>Date:</strong> {{ $('Aggregate Results').first().json.date }}</p>
<p><strong>Health Score:</strong> {{ $('Aggregate Results').first().json.health_score }}%</p>
<p><strong>Passed:</strong> {{ $('Aggregate Results').first().json.passed }} | <strong>Failed:</strong> {{ $('Aggregate Results').first().json.failed }}</p>
<h3>Failed Tests:</h3>
<ul>
{{ $('Aggregate Results').first().json.failed_tests.map(t => '<li><strong>' + t.name + '</strong> (' + t.url + ') - ' + t.reason + '</li>').join('') }}
</ul>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AnyVision Media QA Agent</div>
</div>""",
            "options": {},
        },
        "id": uid(), "name": "Alert Email",
        "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1980, 200],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # 10. Sticky Note
    nodes.append({
        "parameters": {"content": "## QA-01: Daily Smoke Test\n\n**Schedule:** Daily 06:00 SAST (04:00 UTC)\n\nTests all portal and landing page URLs for:\n- HTTP 200 status\n- Response time < 3s\n- Expected content present\n- No error pages\n\nAlerts on any failure via email."},
        "id": uid(), "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
        "position": [180, 80],
    })

    return nodes


def build_qa01_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Set Test URLs", "type": "main", "index": 0}]]},
        "Set Test URLs": {"main": [[{"node": "Split URLs", "type": "main", "index": 0}]]},
        "Split URLs": {"main": [[{"node": "HTTP Health Check", "type": "main", "index": 0}]]},
        "HTTP Health Check": {"main": [[{"node": "Analyze Response", "type": "main", "index": 0}]]},
        "Analyze Response": {"main": [[{"node": "Aggregate Results", "type": "main", "index": 0}]]},
        "Aggregate Results": {"main": [[{"node": "Write Results", "type": "main", "index": 0}]]},
        "Write Results": {"main": [[{"node": "Check Failures", "type": "main", "index": 0}]]},
        "Check Failures": {"main": [
            [{"node": "Alert Email", "type": "main", "index": 0}],
            [],
        ]},
    }


# ======================================================================
# QA-02: Weekly Regression Suite
# ======================================================================

def build_qa02_nodes():
    nodes = []

    # 1. Schedule Trigger (Sun 00:00 UTC = 02:00 SAST)
    nodes.append({
        "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 0 * * 0"}]}},
        "id": uid(), "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
        "position": [220, 300],
    })

    # 2. Set Test Suite (Code)
    nodes.append({
        "parameters": {"jsCode": """const tests = [
  // Landing pages
  {url: '""" + LANDING_URL + """', name: 'Landing Home', method: 'GET', expect: 'AnyVision'},
  {url: '""" + LANDING_URL + """/about', name: 'Landing About', method: 'GET', expect: 'AnyVision'},
  {url: '""" + LANDING_URL + """/services', name: 'Landing Services', method: 'GET', expect: 'AnyVision'},
  {url: '""" + LANDING_URL + """/contact', name: 'Landing Contact', method: 'GET', expect: 'AnyVision'},
  // Portal pages
  {url: '""" + PORTAL_URL + """/login', name: 'Portal Login', method: 'GET', expect: 'portal'},
  {url: '""" + PORTAL_URL + """/signup', name: 'Portal Signup', method: 'GET', expect: 'portal'},
  {url: '""" + PORTAL_URL + """/dashboard', name: 'Portal Dashboard', method: 'GET', expect: 'portal'},
  {url: '""" + PORTAL_URL + """/billing', name: 'Portal Billing', method: 'GET', expect: 'portal'},
  // Robots & Sitemap
  {url: '""" + LANDING_URL + """/robots.txt', name: 'Robots.txt', method: 'GET', expect: 'User-agent', type: 'robots'},
  {url: '""" + LANDING_URL + """/sitemap.xml', name: 'Sitemap.xml', method: 'GET', expect: 'urlset', type: 'sitemap'},
];
return tests.map(t => ({json: t}));"""},
        "id": uid(), "name": "Set Test Suite",
        "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [440, 300],
    })

    # 3. Execute Tests (httpRequest)
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "={{ $json.url }}",
            "options": {"timeout": 15000, "redirect": {"followRedirects": True}},
        },
        "id": uid(), "name": "Execute Tests",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": [660, 300],
        "continueOnFail": True,
        "alwaysOutputData": True,
    })

    # 4. SSL Check (httpRequest HEAD)
    nodes.append({
        "parameters": {
            "method": "HEAD",
            "url": LANDING_URL,
            "options": {"timeout": 10000, "redirect": {"followRedirects": True}},
        },
        "id": uid(), "name": "SSL Check",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": [660, 500],
        "continueOnFail": True,
        "alwaysOutputData": True,
    })

    # 5. Sitemap Check (httpRequest)
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": LANDING_URL + "/sitemap.xml",
            "options": {"timeout": 10000},
        },
        "id": uid(), "name": "Sitemap Check",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": [660, 650],
        "continueOnFail": True,
        "alwaysOutputData": True,
    })

    # 6. Robots Check (httpRequest)
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": LANDING_URL + "/robots.txt",
            "options": {"timeout": 10000},
        },
        "id": uid(), "name": "Robots Check",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": [660, 800],
        "continueOnFail": True,
        "alwaysOutputData": True,
    })

    # 7. Analyze All Results (Code)
    nodes.append({
        "parameters": {"jsCode": """const testResults = $('Execute Tests').all();
const testSuite = $('Set Test Suite').all();
const sslResult = $('SSL Check').first().json;
const sitemapResult = $('Sitemap Check').first().json;
const robotsResult = $('Robots Check').first().json;

const results = [];
for (let i = 0; i < testResults.length; i++) {
  const d = testResults[i].json;
  const info = testSuite[i]?.json || {};
  const statusCode = d.statusCode || d.status || 0;
  const responseTime = d.responseTime || d.timings?.total || 0;
  const body = typeof d.data === 'string' ? d.data : (typeof d.body === 'string' ? d.body : JSON.stringify(d));
  const expectStr = info.expect || '';
  const hasExpected = expectStr ? body.toLowerCase().includes(expectStr.toLowerCase()) : true;
  const passed = statusCode === 200 && hasExpected;
  results.push({
    url: info.url || 'unknown', name: info.name || 'unknown', type: info.type || 'page',
    status_code: statusCode, response_time_ms: responseTime,
    has_expected_content: hasExpected, passed: passed,
    reason: passed ? 'OK' : (statusCode !== 200 ? 'Status ' + statusCode : 'Missing expected content'),
  });
}

// SSL check
const sslPassed = (sslResult.statusCode || sslResult.status || 0) === 200;
results.push({url: '""" + LANDING_URL + """', name: 'SSL Certificate', type: 'ssl',
  status_code: sslResult.statusCode || 0, response_time_ms: 0,
  passed: sslPassed, reason: sslPassed ? 'OK' : 'SSL check failed'});

// Sitemap check
const sitemapBody = typeof sitemapResult.data === 'string' ? sitemapResult.data : JSON.stringify(sitemapResult);
const sitemapPassed = (sitemapResult.statusCode || 0) === 200 && sitemapBody.includes('urlset');
results.push({url: '""" + LANDING_URL + """/sitemap.xml', name: 'Sitemap XML', type: 'sitemap',
  status_code: sitemapResult.statusCode || 0, response_time_ms: 0,
  passed: sitemapPassed, reason: sitemapPassed ? 'OK' : 'Sitemap invalid or missing'});

// Robots check
const robotsBody = typeof robotsResult.data === 'string' ? robotsResult.data : JSON.stringify(robotsResult);
const robotsPassed = (robotsResult.statusCode || 0) === 200 && robotsBody.includes('User-agent');
results.push({url: '""" + LANDING_URL + """/robots.txt', name: 'Robots.txt', type: 'robots',
  status_code: robotsResult.statusCode || 0, response_time_ms: 0,
  passed: robotsPassed, reason: robotsPassed ? 'OK' : 'Robots.txt invalid or missing'});

const total = results.length;
const passed = results.filter(r => r.passed).length;
const failed = total - passed;
const regressions = results.filter(r => !r.passed && r.type === 'page');
const perfScore = total > 0 ? Math.round((passed / total) * 100) : 0;

return [{json: {
  week: new Date().toISOString().split('T')[0],
  test_suite: 'Weekly Regression',
  total_tests: total, passed: passed, failed: failed,
  regressions: regressions.length,
  performance_score: perfScore,
  all_results: results,
  results_json: JSON.stringify(results),
}}];"""},
        "id": uid(), "name": "Analyze All Results",
        "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [880, 300],
    })

    # 8. AI Regression Analysis (httpRequest -> OpenRouter)
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": OPENROUTER_URL,
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '={"model":"' + AI_MODEL + '","max_tokens":1500,"messages":[{"role":"system","content":"You are a QA engineer analyzing weekly regression test results for AnyVision Media web properties. Identify regressions, patterns, and recommend fixes. Be concise. Output JSON: {summary: string, regressions: [{url, issue, severity}], recommendations: [string], overall_status: PASS/WARN/FAIL}"},{"role":"user","content":"Weekly regression results:\\n{{ JSON.stringify($json.all_results, null, 2) }}"}]}',
            "options": {},
        },
        "id": uid(), "name": "AI Regression Analysis",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": [1100, 300],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "continueOnFail": True,
    })

    # 9. Write Report (Airtable create)
    nodes.append({
        "parameters": {
            "operation": "create",
            **airtable_ref(ORCH_BASE_ID, TABLE_QA_RESULTS),
            "columns": {"value": {
                "Date": "={{ $('Analyze All Results').first().json.week }}",
                "Test Suite": "=Weekly Regression",
                "Total Tests": "={{ $('Analyze All Results').first().json.total_tests }}",
                "Passed": "={{ $('Analyze All Results').first().json.passed }}",
                "Failed": "={{ $('Analyze All Results').first().json.failed }}",
                "Health Score %": "={{ $('Analyze All Results').first().json.performance_score }}",
                "Details": "={{ $('Analyze All Results').first().json.results_json }}",
                "Duration ms": "=0",
            }},
            "options": {},
        },
        "id": uid(), "name": "Write Report",
        "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
        "position": [1320, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 10. Send Weekly Report (Gmail)
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=QA Weekly Regression Report - {{ $('Analyze All Results').first().json.week }} ({{ $('Analyze All Results').first().json.performance_score }}% health)",
            "emailType": "html",
            "message": """=<div style="font-family:Arial,sans-serif;max-width:700px">
<div style="background:#FF6D5A;padding:15px;text-align:center"><h2 style="color:white;margin:0">Weekly Regression Report</h2></div>
<div style="padding:20px">
<p><strong>Week:</strong> {{ $('Analyze All Results').first().json.week }}</p>
<p><strong>Health Score:</strong> {{ $('Analyze All Results').first().json.performance_score }}%</p>
<p><strong>Total:</strong> {{ $('Analyze All Results').first().json.total_tests }} | <strong>Passed:</strong> {{ $('Analyze All Results').first().json.passed }} | <strong>Failed:</strong> {{ $('Analyze All Results').first().json.failed }} | <strong>Regressions:</strong> {{ $('Analyze All Results').first().json.regressions }}</p>
<h3>AI Analysis:</h3>
<pre style="background:#f5f5f5;padding:10px;border-radius:4px;white-space:pre-wrap">{{ $json.choices ? $json.choices[0].message.content : 'AI analysis unavailable' }}</pre>
<h3>All Results:</h3>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<tr style="background:#eee"><th style="padding:5px;border:1px solid #ddd">Test</th><th style="padding:5px;border:1px solid #ddd">Status</th><th style="padding:5px;border:1px solid #ddd">Code</th><th style="padding:5px;border:1px solid #ddd">Reason</th></tr>
{{ $('Analyze All Results').first().json.all_results.map(r => '<tr><td style="padding:5px;border:1px solid #ddd">' + r.name + '</td><td style="padding:5px;border:1px solid #ddd;color:' + (r.passed ? 'green' : 'red') + '">' + (r.passed ? 'PASS' : 'FAIL') + '</td><td style="padding:5px;border:1px solid #ddd">' + r.status_code + '</td><td style="padding:5px;border:1px solid #ddd">' + r.reason + '</td></tr>').join('') }}
</table>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AnyVision Media QA Agent</div>
</div>""",
            "options": {},
        },
        "id": uid(), "name": "Send Weekly Report",
        "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1540, 300],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # 11. Sticky Note
    nodes.append({
        "parameters": {"content": "## QA-02: Weekly Regression Suite\n\n**Schedule:** Sunday 02:00 SAST (00:00 UTC)\n\nComprehensive tests:\n- All landing pages + portal pages\n- SSL certificate validation\n- robots.txt & sitemap.xml\n- AI-powered regression analysis\n\nFull report emailed weekly."},
        "id": uid(), "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
        "position": [180, 80],
    })

    return nodes


def build_qa02_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[
            {"node": "Set Test Suite", "type": "main", "index": 0},
            {"node": "SSL Check", "type": "main", "index": 0},
            {"node": "Sitemap Check", "type": "main", "index": 0},
            {"node": "Robots Check", "type": "main", "index": 0},
        ]]},
        "Set Test Suite": {"main": [[{"node": "Execute Tests", "type": "main", "index": 0}]]},
        "Execute Tests": {"main": [[{"node": "Analyze All Results", "type": "main", "index": 0}]]},
        "SSL Check": {"main": [[{"node": "Analyze All Results", "type": "main", "index": 0}]]},
        "Sitemap Check": {"main": [[{"node": "Analyze All Results", "type": "main", "index": 0}]]},
        "Robots Check": {"main": [[{"node": "Analyze All Results", "type": "main", "index": 0}]]},
        "Analyze All Results": {"main": [[{"node": "AI Regression Analysis", "type": "main", "index": 0}]]},
        "AI Regression Analysis": {"main": [[{"node": "Write Report", "type": "main", "index": 0}]]},
        "Write Report": {"main": [[{"node": "Send Weekly Report", "type": "main", "index": 0}]]},
    }


# ======================================================================
# QA-03: Performance Benchmark
# ======================================================================

def build_qa03_nodes():
    nodes = []

    # 1. Schedule Trigger (Daily 10:00 UTC = 12:00 SAST)
    nodes.append({
        "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 10 * * *"}]}},
        "id": uid(), "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
        "position": [220, 300],
    })

    # 2. Set Target URLs
    nodes.append({
        "parameters": {"mode": "raw", "jsonOutput": json.dumps([
            {"url": LANDING_URL, "name": "Landing Page"},
            {"url": PORTAL_URL, "name": "Client Portal"},
        ]), "options": {}},
        "id": uid(), "name": "Set Target URLs",
        "type": "n8n-nodes-base.set", "typeVersion": 3.4,
        "position": [440, 300],
    })

    # 3. Split Targets (Code)
    nodes.append({
        "parameters": {"jsCode": """const urls = $input.first().json;
const items = Array.isArray(urls) ? urls : Object.values(urls);
return items.map(u => ({json: u}));"""},
        "id": uid(), "name": "Split Targets",
        "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [660, 300],
    })

    # 4. PageSpeed API Call (httpRequest)
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "=https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={{ encodeURIComponent($json.url) }}&strategy=mobile&category=performance&category=accessibility&category=best-practices&category=seo",
            "options": {"timeout": 60000},
        },
        "id": uid(), "name": "PageSpeed API Call",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": [880, 300],
        "continueOnFail": True,
        "alwaysOutputData": True,
    })

    # 5. Parse PageSpeed Results (Code)
    nodes.append({
        "parameters": {"jsCode": """const items = $input.all();
const targets = $('Split Targets').all();
const results = [];

for (let i = 0; i < items.length; i++) {
  const d = items[i].json;
  const target = targets[i]?.json || {};
  const lhr = d.lighthouseResult || {};
  const cats = lhr.categories || {};
  const audits = lhr.audits || {};

  const perfScore = Math.round((cats.performance?.score || 0) * 100);
  const a11yScore = Math.round((cats.accessibility?.score || 0) * 100);
  const seoScore = Math.round((cats.seo?.score || 0) * 100);
  const bpScore = Math.round((cats['best-practices']?.score || 0) * 100);

  const lcpMs = Math.round((audits['largest-contentful-paint']?.numericValue || 0));
  const fidMs = Math.round((audits['max-potential-fid']?.numericValue || 0));
  const clsVal = audits['cumulative-layout-shift']?.numericValue || 0;

  const passed = perfScore >= 70 && lcpMs < """ + str(THRESHOLDS["lcp_ms"]) + """ && clsVal < """ + str(THRESHOLDS["cls"]) + """;

  results.push({json: {
    date: new Date().toISOString().split('T')[0],
    url: target.url || 'unknown',
    name: target.name || 'unknown',
    performance_score: perfScore,
    accessibility_score: a11yScore,
    seo_score: seoScore,
    best_practices_score: bpScore,
    lcp_ms: lcpMs,
    fid_ms: fidMs,
    cls: Math.round(clsVal * 1000) / 1000,
    passed: passed,
    reason: !passed ? (perfScore < 70 ? 'Performance below 70: ' + perfScore : lcpMs >= """ + str(THRESHOLDS["lcp_ms"]) + """ ? 'LCP too high: ' + lcpMs + 'ms' : 'CLS too high: ' + clsVal) : 'OK',
  }});
}
return results;"""},
        "id": uid(), "name": "Parse PageSpeed Results",
        "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [1100, 300],
    })

    # 6. Check Against Thresholds (Code)
    nodes.append({
        "parameters": {"jsCode": """const results = $input.all().map(i => i.json);
const degraded = results.filter(r => !r.passed);
const allPassed = degraded.length === 0;
return [{json: {
  results: results,
  degraded: degraded,
  all_passed: allPassed,
  degraded_count: degraded.length,
  total: results.length,
}}];"""},
        "id": uid(), "name": "Check Against Thresholds",
        "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [1320, 300],
    })

    # 7. Expand Results (Code) - one record per URL for Airtable
    nodes.append({
        "parameters": {"jsCode": """const data = $input.first().json;
return data.results.map(r => ({json: r}));"""},
        "id": uid(), "name": "Expand Results",
        "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [1540, 300],
    })

    # 8. Write Benchmark (Airtable create)
    nodes.append({
        "parameters": {
            "operation": "create",
            **airtable_ref(ORCH_BASE_ID, TABLE_QA_RESULTS),
            "columns": {"value": {
                "Date": "={{ $json.date }}",
                "Test Suite": "=Performance Benchmark",
                "Total Tests": "=1",
                "Passed": "={{ $json.passed ? 1 : 0 }}",
                "Failed": "={{ $json.passed ? 0 : 1 }}",
                "Health Score %": "={{ $json.performance_score }}",
                "Details": "={{ JSON.stringify({url: $json.url, lcp_ms: $json.lcp_ms, cls: $json.cls, fid_ms: $json.fid_ms, accessibility: $json.accessibility_score, seo: $json.seo_score, best_practices: $json.best_practices_score}) }}",
                "Duration ms": "={{ $json.lcp_ms }}",
            }},
            "options": {},
        },
        "id": uid(), "name": "Write Benchmark",
        "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1760, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 9. Check Degradation (If)
    nodes.append({
        "parameters": {
            "conditions": {"conditions": [
                {"leftValue": "={{ $('Check Against Thresholds').first().json.degraded_count }}",
                 "rightValue": 0,
                 "operator": {"type": "number", "operation": "gt"}},
            ]},
            "options": {},
        },
        "id": uid(), "name": "Check Degradation",
        "type": "n8n-nodes-base.if", "typeVersion": 2.2,
        "position": [1980, 300],
    })

    # 10. Alert on Degradation (Gmail)
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=QA ALERT: Performance Degradation Detected ({{ $('Check Against Thresholds').first().json.degraded_count }} URLs)",
            "emailType": "html",
            "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FF6D5A;padding:15px;text-align:center"><h2 style="color:white;margin:0">Performance Degradation Alert</h2></div>
<div style="padding:20px">
<p><strong>Date:</strong> {{ $('Check Against Thresholds').first().json.results[0].date }}</p>
<h3>Degraded URLs:</h3>
<ul>
{{ $('Check Against Thresholds').first().json.degraded.map(d => '<li><strong>' + d.name + '</strong> (' + d.url + ')<br>Performance: ' + d.performance_score + '% | LCP: ' + d.lcp_ms + 'ms | CLS: ' + d.cls + '<br>Issue: ' + d.reason + '</li>').join('') }}
</ul>
<h3>Thresholds:</h3>
<ul><li>Performance Score >= 70</li><li>LCP < """ + str(THRESHOLDS["lcp_ms"]) + """ms</li><li>CLS < """ + str(THRESHOLDS["cls"]) + """</li></ul>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AnyVision Media QA Agent</div>
</div>""",
            "options": {},
        },
        "id": uid(), "name": "Alert on Degradation",
        "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [2200, 200],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # 11. Sticky Note
    nodes.append({
        "parameters": {"content": "## QA-03: Performance Benchmark\n\n**Schedule:** Daily 12:00 SAST (10:00 UTC)\n\nUses Google PageSpeed Insights API (mobile):\n- Performance score >= 70\n- LCP < 2500ms\n- CLS < 0.1\n\nAlerts on performance degradation."},
        "id": uid(), "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
        "position": [180, 80],
    })

    return nodes


def build_qa03_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Set Target URLs", "type": "main", "index": 0}]]},
        "Set Target URLs": {"main": [[{"node": "Split Targets", "type": "main", "index": 0}]]},
        "Split Targets": {"main": [[{"node": "PageSpeed API Call", "type": "main", "index": 0}]]},
        "PageSpeed API Call": {"main": [[{"node": "Parse PageSpeed Results", "type": "main", "index": 0}]]},
        "Parse PageSpeed Results": {"main": [[{"node": "Check Against Thresholds", "type": "main", "index": 0}]]},
        "Check Against Thresholds": {"main": [[{"node": "Expand Results", "type": "main", "index": 0}]]},
        "Expand Results": {"main": [[{"node": "Write Benchmark", "type": "main", "index": 0}]]},
        "Write Benchmark": {"main": [[{"node": "Check Degradation", "type": "main", "index": 0}]]},
        "Check Degradation": {"main": [
            [{"node": "Alert on Degradation", "type": "main", "index": 0}],
            [],
        ]},
    }


# ======================================================================
# WORKFLOW ASSEMBLY & DEPLOYMENT
# ======================================================================

WORKFLOW_BUILDERS = {
    "qa01": {
        "name": "QA-01 Daily Smoke Test",
        "build_nodes": build_qa01_nodes,
        "build_connections": build_qa01_connections,
        "filename": "qa01_daily_smoke_test.json",
        "tags": ["qa", "smoke-test", "daily"],
    },
    "qa02": {
        "name": "QA-02 Weekly Regression Suite",
        "build_nodes": build_qa02_nodes,
        "build_connections": build_qa02_connections,
        "filename": "qa02_weekly_regression_suite.json",
        "tags": ["qa", "regression", "weekly"],
    },
    "qa03": {
        "name": "QA-03 Performance Benchmark",
        "build_nodes": build_qa03_nodes,
        "build_connections": build_qa03_connections,
        "filename": "qa03_performance_benchmark.json",
        "tags": ["qa", "performance", "pagespeed"],
    },
}


def build_workflow_json(key):
    builder = WORKFLOW_BUILDERS[key]
    nodes = builder["build_nodes"]()
    connections = builder["build_connections"](nodes)
    return {
        "name": builder["name"],
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "tags": builder["tags"],
        "meta": {
            "templateCredsSetupCompleted": True,
            "builder": "deploy_qa_agent.py",
            "built_at": datetime.now().isoformat(),
        },
    }


def save_workflow(key, workflow_json):
    builder = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "qa-agent"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / builder["filename"]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow_json, f, indent=2, ensure_ascii=False)
    node_count = len(workflow_json["nodes"])
    print(f"  + {builder['name']:<40} ({node_count} nodes) -> {output_path}")
    return output_path


def print_workflow_stats():
    print()
    print("Workflow Summary:")
    print("-" * 40)
    total_nodes = 0
    for key, builder in WORKFLOW_BUILDERS.items():
        nodes = builder["build_nodes"]()
        count = len(nodes)
        total_nodes += count
        print(f"  {key:<12} {builder['name']:<40} {count} nodes")
    print(f"  {'TOTAL':<12} {'':40} {total_nodes} nodes")


def deploy_workflow(key, workflow_json, activate=False):
    from n8n_client import N8nClient
    api_key = os.getenv("N8N_API_KEY")
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env")
        sys.exit(1)
    client = N8nClient(base_url, api_key, timeout=30)
    builder = WORKFLOW_BUILDERS[key]
    # Strip fields n8n API rejects (tags as strings, meta)
    deploy_payload = {k: v for k, v in workflow_json.items() if k not in ("tags", "meta", "active")}
    resp = client.create_workflow(deploy_payload)
    if resp and "id" in resp:
        wf_id = resp["id"]
        print(f"  + {builder['name']:<40} Deployed -> {wf_id}")
        if activate:
            import time
            time.sleep(2)
            client.activate_workflow(wf_id)
            print(f"    Activated: {wf_id}")
        return wf_id
    else:
        print(f"  - {builder['name']:<40} FAILED to deploy")
        return None


def main():
    if len(sys.argv) < 2:
        print("AVM QA Agent - Workflow Builder")
        print()
        print("Usage:")
        print("  python tools/deploy_qa_agent.py build              # Build all")
        print("  python tools/deploy_qa_agent.py build qa01         # Build one")
        print("  python tools/deploy_qa_agent.py deploy             # Build + Deploy (inactive)")
        print("  python tools/deploy_qa_agent.py activate           # Build + Deploy + Activate")
        print()
        print("Workflows:")
        for key, builder in WORKFLOW_BUILDERS.items():
            print(f"  {key:<12} {builder['name']}")
        print_workflow_stats()
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
    print("AVM QA AGENT - WORKFLOW BUILDER")
    print("=" * 60)
    print()
    print(f"Action: {action}")
    print(f"Workflows: {', '.join(keys)}")
    print()

    if action == "build":
        print("Building workflow JSONs...")
        print("-" * 40)
        for key in keys:
            wf_json = build_workflow_json(key)
            save_workflow(key, wf_json)
        print_workflow_stats()
        print()
        print("Build complete. Inspect workflows in: workflows/qa-agent/")

    elif action in ("deploy", "activate"):
        do_activate = action == "activate"
        print(f"Building and deploying ({'+ activating' if do_activate else 'inactive'})...")
        print("-" * 40)
        deployed_ids = {}
        for key in keys:
            wf_json = build_workflow_json(key)
            save_workflow(key, wf_json)
            wf_id = deploy_workflow(key, wf_json, activate=do_activate)
            if wf_id:
                deployed_ids[key] = wf_id
        print_workflow_stats()
        print()
        if deployed_ids:
            print("Deployed Workflow IDs:")
            for key, wf_id in deployed_ids.items():
                print(f"  {key}: {wf_id}")

    else:
        print(f"Unknown action: {action}")
        print("Valid: build, deploy, activate")
        sys.exit(1)


if __name__ == "__main__":
    main()
