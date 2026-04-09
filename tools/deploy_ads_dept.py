"""
AVM Paid Advertising Department - Workflow Builder & Deployer

Builds and deploys autonomous marketing agent workflows for paid advertising
across Google Ads, Meta Ads, and TikTok Ads.

Phase 1 Workflows (Sprint 1):
    ADS-04: Performance Monitor (every 6 hours) - Pull metrics from all ad platforms
    ADS-08: Reporting Dashboard (Mon 08:00 SAST + Monthly 1st) - Weekly email report

Phase 2 Workflows (Sprint 2):
    ADS-01: Campaign Strategy Generator (Mon 07:00 SAST)
    ADS-02: Ad Copy & Creative Generator (Webhook)
    ADS-07: Cross-Channel Attribution (Daily 06:00 SAST)

Phase 3 Workflows (Sprint 3):
    ADS-05: Optimization Engine (Daily 20:00 SAST)
    ADS-06: Creative Recycler (Wed 10:00 SAST)
    ADS-03: Campaign Builder & Publisher (Webhook)

Usage:
    python tools/deploy_ads_dept.py build              # Build all JSONs
    python tools/deploy_ads_dept.py build ads04         # Build ADS-04 only
    python tools/deploy_ads_dept.py deploy              # Build + Deploy (inactive)
    python tools/deploy_ads_dept.py deploy ads04        # Deploy ADS-04 only
    python tools/deploy_ads_dept.py activate            # Build + Deploy + Activate
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

# ── Credential Constants ────────────────────────────────────
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable account"}
CRED_GOOGLE_SHEETS = {"id": os.getenv("N8N_CRED_GOOGLE_SHEETS", "OkpDXxwI8WcUJp4P"), "name": "Google Sheets account"}

# Ad platform credentials (set after creating in n8n UI)
CRED_GOOGLE_ADS = {"id": os.getenv("N8N_CRED_GOOGLE_ADS", "REPLACE_AFTER_SETUP"), "name": "Google Ads OAuth2"}
CRED_META_ADS = {"id": os.getenv("N8N_CRED_META_ADS", "REPLACE_AFTER_SETUP"), "name": "Meta Ads Graph API"}
CRED_TIKTOK_ADS = {"id": os.getenv("N8N_CRED_TIKTOK_ADS", "REPLACE_AFTER_SETUP"), "name": "TikTok Ads HTTP Auth"}

# ── Airtable IDs ────────────────────────────────────────────
MARKETING_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")

# Ads tables (created by setup_ads_airtable.py)
TABLE_CAMPAIGNS = os.getenv("ADS_TABLE_CAMPAIGNS", "REPLACE_AFTER_SETUP")
TABLE_ADSETS = os.getenv("ADS_TABLE_ADSETS", "REPLACE_AFTER_SETUP")
TABLE_CREATIVES = os.getenv("ADS_TABLE_CREATIVES", "REPLACE_AFTER_SETUP")
TABLE_PERFORMANCE = os.getenv("ADS_TABLE_PERFORMANCE", "REPLACE_AFTER_SETUP")
TABLE_BUDGET_ALLOC = os.getenv("ADS_TABLE_BUDGET_ALLOCATIONS", "REPLACE_AFTER_SETUP")
TABLE_AUDIENCES = os.getenv("ADS_TABLE_AUDIENCES", "REPLACE_AFTER_SETUP")
TABLE_AB_TESTS = os.getenv("ADS_TABLE_AB_TESTS", "REPLACE_AFTER_SETUP")
TABLE_APPROVALS = os.getenv("ADS_TABLE_APPROVALS", "REPLACE_AFTER_SETUP")

# Existing marketing tables (for cross-referencing)
TABLE_DISTRIBUTION_LOG = os.getenv("MARKETING_TABLE_DISTRIBUTION", "tblLI70ZD0DkJKXvI")
TABLE_RESEARCH_INSIGHTS = os.getenv("MARKETING_TABLE_RESEARCH_INSIGHTS", "tblPHMyQMedBvcGQz")
TABLE_CONTENT_CALENDAR = os.getenv("MARKETING_TABLE_CONTENT", "tblf3QGxX9K1y2h2H")

# Orchestrator tables
ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "REPLACE_AFTER_SETUP")
TABLE_ORCH_EVENTS = os.getenv("ORCH_TABLE_EVENTS", "REPLACE_AFTER_SETUP")

# ── Config ──────────────────────────────────────────────────
ALERT_EMAIL = os.getenv("SELFHEALING_ALERT_EMAIL", "ian@anyvisionmedia.com")
OPENROUTER_MODEL = "anthropic/claude-sonnet-4"

# Google Ads
GOOGLE_ADS_CUSTOMER_ID = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "REPLACE")
GOOGLE_ADS_MANAGER_ID = os.getenv("GOOGLE_ADS_MANAGER_ID", "REPLACE")

# Meta Ads
META_ADS_ACCOUNT_ID = os.getenv("META_ADS_ACCOUNT_ID", "REPLACE")

# TikTok Ads
TIKTOK_ADS_ADVERTISER_ID = os.getenv("TIKTOK_ADS_ADVERTISER_ID", "REPLACE")

# Budget safety caps
DAILY_CAP = int(os.getenv("ADS_DAILY_HARD_CAP_ZAR", "666"))
WEEKLY_CAP = int(os.getenv("ADS_WEEKLY_HARD_CAP_ZAR", "5000"))
MONTHLY_CAP = int(os.getenv("ADS_MONTHLY_HARD_CAP_ZAR", "20000"))


def uid():
    """Generate UUID for node IDs."""
    return str(uuid.uuid4())


# ======================================================================
# CODE NODE SCRIPTS
# ======================================================================

ADS04_TRANSFORM_GOOGLE_CODE = r"""
// Transform Google Ads API response to common schema
const items = $input.all();

// Handle upstream error / empty data (continueOnFail produces error item)
if (!items.length || items[0].json?.error || items[0].json?.message?.includes?.('403')) {
  return [{json: {skip: true, reason: 'Google Ads API unavailable'}}];
}

const results = [];
const now = new Date().toISOString().split('T')[0];
const hour = new Date().toISOString().split('T')[1].substring(0, 5);

for (const item of items) {
  const d = item.json;
  const metrics = d.metrics || d;
  const campaign = d.campaign || {};

  const impressions = parseInt(metrics.impressions || 0);
  // Google Ads API returns 'interactions' (superset of clicks); fall back to clicks if present
  const clicks = parseInt(metrics.clicks || metrics.interactions || 0);
  const costMicros = parseInt(metrics.costMicros || metrics.cost_micros || 0);
  const conversions = parseFloat(metrics.conversions || 0);
  const videoViews = parseInt(metrics.videoViews || metrics.video_views || 0);

  const spendZAR = costMicros / 1000000;
  const ctr = impressions > 0 ? clicks / impressions : 0;
  const cpc = clicks > 0 ? spendZAR / clicks : 0;
  const cpm = impressions > 0 ? (spendZAR / impressions) * 1000 : 0;
  const cpa = conversions > 0 ? spendZAR / conversions : 0;
  const roas = spendZAR > 0 ? (conversions * 100) / spendZAR : 0;

  // n8n Google Ads node returns flat structure: d.name, d.id (not nested under campaign)
  const campaignName = campaign.name || d.name || d.campaignName || 'Unknown';
  const campaignId = campaign.id || d.id || 'unknown';

  results.push({
    json: {
      'Performance ID': `gads_${campaignId}_${now}_${hour}`,
      'Campaign Name': campaignName,
      'Platform': 'google_ads',
      'Date': now,
      'Impressions': impressions,
      'Clicks': clicks,
      'CTR': parseFloat(ctr.toFixed(4)),
      'Spend ZAR': parseFloat(spendZAR.toFixed(2)),
      'Conversions': Math.round(conversions),
      'CPA ZAR': parseFloat(cpa.toFixed(2)),
      'ROAS': parseFloat(roas.toFixed(2)),
      'CPM ZAR': parseFloat(cpm.toFixed(2)),
      'CPC ZAR': parseFloat(cpc.toFixed(2)),
      'Video Views': videoViews,
      'Engagement Rate': 0,
      'Snapshot Hour': hour,
    }
  });
}

return results.length > 0 ? results : [{json: {skip: true, reason: 'No Google Ads data'}}];
"""

ADS04_TRANSFORM_META_CODE = r"""
// Transform Meta Ads insights to common schema
const items = $input.all();

// Meta Graph API wraps insights in a data[] array
// Response: { data: [ {campaign_id, impressions, ...}, ... ], paging: {...} }
const firstItem = items[0]?.json;
if (!firstItem || firstItem.error || (!firstItem.data && !firstItem.impressions)) {
  return [{json: {skip: true, reason: 'Meta Ads API unavailable'}}];
}

// Unwrap: if data[] array exists, iterate campaigns inside it; otherwise treat items as flat
const campaigns = firstItem.data || [firstItem];

const results = [];
const now = new Date().toISOString().split('T')[0];
const hour = new Date().toISOString().split('T')[1].substring(0, 5);

for (const d of campaigns) {
  const impressions = parseInt(d.impressions || 0);
  const clicks = parseInt(d.clicks || 0);
  const spend = parseFloat(d.spend || 0);
  const reach = parseInt(d.reach || 0);

  // Extract conversions from actions array
  let conversions = 0;
  if (d.actions) {
    for (const action of d.actions) {
      if (action.action_type === 'lead' || action.action_type === 'complete_registration' || action.action_type === 'purchase') {
        conversions += parseInt(action.value || 0);
      }
    }
  }

  const ctr = impressions > 0 ? clicks / impressions : 0;
  const cpc = clicks > 0 ? spend / clicks : 0;
  const cpm = impressions > 0 ? (spend / impressions) * 1000 : 0;
  const cpa = conversions > 0 ? spend / conversions : 0;
  const roas = spend > 0 ? (conversions * 100) / spend : 0;
  const engRate = reach > 0 ? clicks / reach : 0;

  results.push({
    json: {
      'Performance ID': `meta_${d.campaign_id || 'unknown'}_${now}_${hour}`,
      'Campaign Name': d.campaign_name || 'Unknown',
      'Platform': 'meta_ads',
      'Date': now,
      'Impressions': impressions,
      'Clicks': clicks,
      'CTR': parseFloat(ctr.toFixed(4)),
      'Spend ZAR': parseFloat(spend.toFixed(2)),
      'Conversions': conversions,
      'CPA ZAR': parseFloat(cpa.toFixed(2)),
      'ROAS': parseFloat(roas.toFixed(2)),
      'CPM ZAR': parseFloat(cpm.toFixed(2)),
      'CPC ZAR': parseFloat(cpc.toFixed(2)),
      'Video Views': parseInt(d.video_views || 0),
      'Engagement Rate': parseFloat(engRate.toFixed(4)),
      'Snapshot Hour': hour,
    }
  });
}

return results.length > 0 ? results : [{json: {skip: true, reason: 'No Meta Ads data'}}];
"""

ADS04_ANOMALY_DETECTION_CODE = r"""
// Detect anomalies: spend > 2x daily budget, CTR drop > 50% vs 7-day avg
const items = $input.all();
const anomalies = [];
const DAILY_CAP = 666;

for (const item of items) {
  const d = item.json;
  if (d.skip) continue;

  const issues = [];

  // Check spend against daily cap
  if (d['Spend ZAR'] > DAILY_CAP) {
    issues.push(`Spend R${d['Spend ZAR']} exceeds daily cap R${DAILY_CAP}`);
  }

  // Flag very low CTR (potential issue)
  if (d.Impressions > 1000 && d.CTR < 0.001) {
    issues.push(`CTR ${(d.CTR * 100).toFixed(2)}% critically low with ${d.Impressions} impressions`);
  }

  // Flag high CPA
  if (d['CPA ZAR'] > 800 && d.Conversions > 0) {
    issues.push(`CPA R${d['CPA ZAR']} exceeds R800 threshold`);
  }

  if (issues.length > 0) {
    anomalies.push({
      json: {
        campaign: d['Campaign Name'],
        platform: d.Platform,
        date: d.Date,
        issues: issues,
        spendZAR: d['Spend ZAR'],
        ctr: d.CTR,
        cpa: d['CPA ZAR'],
        severity: d['Spend ZAR'] > DAILY_CAP ? 'CRITICAL' : 'WARNING',
      }
    });
  }
}

if (anomalies.length > 0) {
  return anomalies;
} else {
  return [{json: {noAnomalies: true}}];
}
"""

ADS04_FILTER_SKIP_CODE = r"""
// Filter out skip items (no data from platform)
const items = $input.all();
return items.filter(item => !item.json.skip);
"""

ADS08_BUILD_REPORT_CODE = r"""
// Build email-friendly HTML report from performance data + AI summary
const perfItems = $('Merge Report Data').all();
const aiSummary = $('AI Report Generator').first().json;

const now = new Date();
const weekNum = Math.ceil((now.getDate()) / 7);
const monthName = now.toLocaleString('en-ZA', {month: 'long', year: 'numeric'});

let totalSpend = 0;
let totalClicks = 0;
let totalImpressions = 0;
let totalConversions = 0;
const platformSummary = {};

for (const item of perfItems) {
  const d = item.json;
  if (d.skip) continue;
  totalSpend += d['Spend ZAR'] || d['Total Spend ZAR'] || 0;
  totalClicks += d.Clicks || 0;
  totalImpressions += d.Impressions || 0;
  totalConversions += d.Conversions || d['Total Conversions'] || 0;

  const platform = d.Platform || 'Unknown';
  if (!platformSummary[platform]) {
    platformSummary[platform] = {spend: 0, clicks: 0, impressions: 0, conversions: 0};
  }
  platformSummary[platform].spend += d['Spend ZAR'] || d['Total Spend ZAR'] || 0;
  platformSummary[platform].clicks += d.Clicks || 0;
  platformSummary[platform].impressions += d.Impressions || 0;
  platformSummary[platform].conversions += d.Conversions || d['Total Conversions'] || 0;
}

const blendedCTR = totalImpressions > 0 ? ((totalClicks / totalImpressions) * 100).toFixed(2) : '0.00';
const blendedCPA = totalConversions > 0 ? (totalSpend / totalConversions).toFixed(2) : 'N/A';
const blendedROAS = totalSpend > 0 ? ((totalConversions * 100) / totalSpend).toFixed(2) : 'N/A';

// Build platform rows
let platformRows = '';
for (const [platform, stats] of Object.entries(platformSummary)) {
  const pCTR = stats.impressions > 0 ? ((stats.clicks / stats.impressions) * 100).toFixed(2) : '0.00';
  const pCPA = stats.conversions > 0 ? (stats.spend / stats.conversions).toFixed(2) : 'N/A';
  platformRows += `<tr>
    <td style="padding:8px;border-bottom:1px solid #eee;">${platform}</td>
    <td style="padding:8px;border-bottom:1px solid #eee;">R${stats.spend.toFixed(2)}</td>
    <td style="padding:8px;border-bottom:1px solid #eee;">${stats.impressions.toLocaleString()}</td>
    <td style="padding:8px;border-bottom:1px solid #eee;">${stats.clicks.toLocaleString()}</td>
    <td style="padding:8px;border-bottom:1px solid #eee;">${pCTR}%</td>
    <td style="padding:8px;border-bottom:1px solid #eee;">${stats.conversions}</td>
    <td style="padding:8px;border-bottom:1px solid #eee;">R${pCPA}</td>
  </tr>`;
}

const summaryText = aiSummary.choices?.[0]?.message?.content || aiSummary.summary || 'No AI summary available.';

const html = `
<div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;">
  <div style="background:#FF6D5A;color:white;padding:20px;border-radius:8px 8px 0 0;">
    <h1 style="margin:0;font-size:22px;">AVM Paid Ads - Weekly Report</h1>
    <p style="margin:5px 0 0;opacity:0.9;">${monthName} - Week ${weekNum}</p>
  </div>

  <div style="padding:20px;background:#f9f9f9;">
    <h2 style="color:#333;font-size:16px;">Overview</h2>
    <table style="width:100%;border-collapse:collapse;background:white;border-radius:4px;">
      <tr>
        <td style="padding:12px;text-align:center;"><strong>R${totalSpend.toFixed(2)}</strong><br><small>Total Spend</small></td>
        <td style="padding:12px;text-align:center;"><strong>${totalImpressions.toLocaleString()}</strong><br><small>Impressions</small></td>
        <td style="padding:12px;text-align:center;"><strong>${totalClicks.toLocaleString()}</strong><br><small>Clicks</small></td>
        <td style="padding:12px;text-align:center;"><strong>${blendedCTR}%</strong><br><small>CTR</small></td>
        <td style="padding:12px;text-align:center;"><strong>${totalConversions}</strong><br><small>Conversions</small></td>
        <td style="padding:12px;text-align:center;"><strong>R${blendedCPA}</strong><br><small>CPA</small></td>
      </tr>
    </table>

    <h2 style="color:#333;font-size:16px;margin-top:20px;">By Platform</h2>
    <table style="width:100%;border-collapse:collapse;background:white;border-radius:4px;">
      <thead>
        <tr style="background:#f0f0f0;">
          <th style="padding:8px;text-align:left;">Platform</th>
          <th style="padding:8px;">Spend</th>
          <th style="padding:8px;">Impressions</th>
          <th style="padding:8px;">Clicks</th>
          <th style="padding:8px;">CTR</th>
          <th style="padding:8px;">Conversions</th>
          <th style="padding:8px;">CPA</th>
        </tr>
      </thead>
      <tbody>${platformRows}</tbody>
    </table>

    <h2 style="color:#333;font-size:16px;margin-top:20px;">AI Analysis</h2>
    <div style="background:white;padding:15px;border-radius:4px;border-left:4px solid #FF6D5A;">
      ${summaryText.replace(/\n/g, '<br>')}
    </div>
  </div>

  <div style="padding:15px;text-align:center;color:#999;font-size:12px;">
    Generated by AVM Ads Agent (ADS-08) | ${now.toISOString()}
  </div>
</div>`;

return [{json: {
  html: html,
  subject: 'AVM Ads Report - ' + monthName + ' Week ' + weekNum,
  totalSpend: totalSpend,
  totalConversions: totalConversions,
  blendedCPA: blendedCPA,
  blendedROAS: blendedROAS,
}}];
"""

ADS08_AI_REPORT_PROMPT = """You are the AVM Paid Advertising Report Analyst for AnyVision Media, a South African SaaS/AI automation company.

CRITICAL RULES:
- AVM ONLY runs Google Ads and Meta Ads (Facebook/Instagram). Do NOT reference YouTube, LinkedIn, TikTok, or any other platform.
- ONLY report metrics that are actually present in the data below. If a metric is 0 or missing, say so honestly — NEVER invent or estimate numbers.
- If all metrics are zero or the data is empty, state clearly: "No performance data was collected this period."
- Do NOT fabricate campaign names, ROAS figures, CPA values, or any other metrics not in the data.
- Google Ads Performance Max campaigns may show video views (from Display/YouTube placements within PMax) — this does NOT mean AVM runs YouTube ads.

Analyze the following paid advertising performance data and generate a concise executive summary.

PERFORMANCE DATA:
{performance_data}

Generate a summary that includes:
1. HIGHLIGHTS: Top 2-3 wins this week (best ROAS, lowest CPA, highest CTR) — only if real non-zero data exists
2. CONCERNS: Any campaigns underperforming or burning budget — based on actual numbers only
3. RECOMMENDATIONS: 2-3 specific actions to take next week
4. BUDGET: Whether current allocation is optimal or needs adjustment

Keep it concise (under 300 words). Use ZAR currency. Focus on actionable insights.
Output plain text, no JSON."""

# ======================================================================
# ADS-01: CAMPAIGN STRATEGY GENERATOR
# ======================================================================

ADS01_STRATEGY_PROMPT = """You are the AVM Campaign Strategist for AnyVision Media, a South African SaaS/AI automation company.

BUSINESS CONTEXT:
- Company: AnyVision Media (www.anyvisionmedia.com)
- Services: AI consulting, workflow automation, web development, social media management
- Target: SMBs in South Africa looking to automate and scale
- Brand color: #FF6D5A
- Currency: ZAR (South African Rand)
- Key CTA: "Book a Free AI Strategy Call"

ORGANIC CONTENT PERFORMANCE (last 7 days):
{research_data}

CURRENT PAID CAMPAIGNS:
{current_campaigns}

BUDGET ALLOCATION:
{budget_data}

BUDGET CONSTRAINTS (MANDATORY):
- Daily budget per campaign: max R{daily_cap} (HARD LIMIT — never suggest higher)
- Weekly total across ALL campaigns: max R{weekly_cap}
- Monthly total: max R{monthly_cap}
- AVM ONLY runs Google Ads and Meta Ads. Do NOT suggest TikTok, LinkedIn, or other platforms.

Generate 2-3 campaign recommendations as a JSON array. Each item must have:
- campaign_name: descriptive name
- platform: one of "google_ads", "meta_ads"
- objective: one of "Traffic", "Conversions", "Lead_Gen", "Awareness"
- target_audience: description of who to target
- suggested_daily_budget_zar: number (MUST NOT exceed R{daily_cap})
- ad_format: one of "RSA", "Image", "Video", "Carousel"
- key_messages: array of 2-3 messaging angles
- duration_days: 7, 14, or 30
- priority: "High", "Medium", or "Low"
- reasoning: why this campaign should run

Focus on SaaS lead generation and client acquisition. Prioritize campaigns with highest expected ROAS.

Output ONLY valid JSON array, no markdown or extra text."""

# ======================================================================
# ADS-02: AD COPY & CREATIVE GENERATOR
# ======================================================================

ADS02_GOOGLE_COPY_PROMPT = """You are the AVM Google Ads Copywriter for AnyVision Media.

CAMPAIGN: {campaign_name}
OBJECTIVE: {objective}
TARGET AUDIENCE: {target_audience}
KEY MESSAGES: {key_messages}

Generate a Google Responsive Search Ad (RSA) with:
- 15 headlines (EXACTLY 30 characters max each, no exceptions)
- 4 descriptions (EXACTLY 90 characters max each, no exceptions)
- display_url_path1 (15 chars max)
- display_url_path2 (15 chars max)

Rules:
- Include "AnyVision Media" or "AnyVision" in at least 2 headlines
- Include numbers/stats where possible ("3x ROI", "60% faster")
- Include CTA headlines ("Book Free Call", "Start Today")
- No exclamation marks in headlines (Google policy)
- South African English spelling

Output as JSON: {{"headlines": [...], "descriptions": [...], "display_url_path1": "...", "display_url_path2": "..."}}"""

ADS02_META_COPY_PROMPT = """You are the AVM Meta Ads Copywriter for AnyVision Media.

CAMPAIGN: {campaign_name}
OBJECTIVE: {objective}
TARGET AUDIENCE: {target_audience}
KEY MESSAGES: {key_messages}
AD FORMAT: {ad_format}

Generate a Meta (Facebook/Instagram) ad with:
- primary_text: compelling body copy (max 125 chars for feed, can be longer for other placements)
- headline: attention-grabbing headline (max 40 chars)
- description: supporting text (max 30 chars)
- cta: one of "LEARN_MORE", "SIGN_UP", "CONTACT_US", "GET_QUOTE", "BOOK_NOW"

Also generate 2 alternative versions for A/B testing.

Rules:
- Hook in first line (question, stat, or bold claim)
- Social proof where possible
- Clear value proposition for SaaS/AI automation
- South African English

Output as JSON: {{"variants": [{{"primary_text": "...", "headline": "...", "description": "...", "cta": "..."}}, ...]}}"""

ADS02_TIKTOK_COPY_PROMPT = """You are the AVM TikTok Ads Scriptwriter for AnyVision Media.

CAMPAIGN: {campaign_name}
OBJECTIVE: {objective}
TARGET AUDIENCE: {target_audience}
KEY MESSAGES: {key_messages}

Generate a TikTok ad script with:
- hook: first 3 seconds attention grabber (max 15 words)
- script: full video script (50-100 words, conversational tone)
- caption: post caption (max 100 chars)
- hashtags: 5 relevant hashtags
- cta_text: call to action overlay text (max 20 chars)

Rules:
- Native TikTok feel (not corporate)
- Problem-solution structure
- Fast-paced, direct language
- Speak to pain points of business owners

Output as JSON: {{"hook": "...", "script": "...", "caption": "...", "hashtags": [...], "cta_text": "..."}}"""

ADS02_QUALITY_SCORE_PROMPT = """Rate this ad creative on a scale of 1-10 for each criterion:

AD CREATIVE:
{creative_json}

CAMPAIGN CONTEXT:
Platform: {platform}
Objective: {objective}
Target: {target_audience}

Rate each (1-10):
1. relevance: How well does it match the target audience and objective?
2. clarity: Is the message clear and easy to understand?
3. cta_strength: How compelling is the call to action?
4. differentiation: Does it stand out from generic ads?
5. compliance: Does it follow platform ad policies?

Output JSON: {{"relevance": N, "clarity": N, "cta_strength": N, "differentiation": N, "compliance": N, "overall": N, "feedback": "brief improvement suggestion"}}"""

# ======================================================================
# ADS-05: OPTIMIZATION ENGINE
# ======================================================================

ADS05_OPTIMIZATION_PROMPT = """You are the AVM Ads Optimization Agent for AnyVision Media.

CRITICAL RULES:
- AVM ONLY runs Google Ads and Meta Ads (Facebook/Instagram). Do NOT reference YouTube, LinkedIn, TikTok, or any other platform.
- ONLY reference campaigns that actually exist in the performance data below. NEVER invent campaign names.
- If the data contains campaign names, use those EXACT names. Do NOT create fictional names like "Facebook Brand Awareness" or "Google Search - Premium Products".
- If there is insufficient data to make recommendations, say so honestly.

7-DAY PERFORMANCE DATA:
{performance_data}

CURRENT BUDGET ALLOCATION:
{budget_data}

SAFETY CONSTRAINTS:
- Daily budget per campaign: max R{daily_cap}
- Weekly total across all campaigns: max R{weekly_cap}
- Monthly total: max R{monthly_cap}
- Max single bid change: 30%
- Max auto-approve budget increase: R200/day

Analyze trends and recommend specific optimizations:

For each recommendation, output JSON:
{{
  "campaign_name": "...",
  "platform": "...",
  "action": "bid_adjust|budget_change|pause|reactivate|targeting_change",
  "current_value": N,
  "proposed_value": N,
  "change_percent": N,
  "reasoning": "...",
  "confidence": "high|medium|low",
  "auto_approvable": true/false
}}

Rules:
- Be conservative. Only recommend changes backed by data.
- Flag auto_approvable=true ONLY if bid change < 20% AND budget increase < R200/day
- Recommend pausing campaigns with CPA > R800 and < 5 conversions
- Recommend increasing budget for campaigns with ROAS > 3.0
- Never recommend exceeding safety caps

Output as JSON array."""

# ======================================================================
# NODE BUILDERS
# ======================================================================

def build_schedule_trigger(name, cron_expression, position):
    """Build a Schedule Trigger node."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": position,
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": cron_expression}]
            }
        },
    }


def build_webhook_trigger(name, path, position, response_mode="onReceived"):
    """Build a Webhook Trigger node.

    Args:
        response_mode: "onReceived" (respond immediately) or "lastNode" (wait for Respond node).
    """
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
            "responseMode": response_mode,
        },
    }


def build_airtable_search(name, base_id, table_id, formula, position, sort_field=None, sort_desc=False):
    """Build an Airtable search node."""
    params = {
        "operation": "search",
        "base": {"__rl": True, "mode": "id", "value": base_id},
        "table": {"__rl": True, "mode": "id", "value": table_id},
        "filterByFormula": formula,
        "options": {},
    }
    if sort_field:
        params["sort"] = {"property": [{"field": sort_field, "direction": "desc" if sort_desc else "asc"}]}

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": position,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": params,
    }


def build_airtable_create(name, base_id, table_id, position):
    """Build an Airtable create node (auto-maps incoming JSON fields to Airtable). Auto-retries 3x."""
    return make_resilient({
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": position,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": base_id},
            "table": {"__rl": True, "mode": "id", "value": table_id},
            "columns": {
                "mappingMode": "autoMapInputData",
                "value": None,
            },
            "options": {},
        },
    })


def build_code_node(name, js_code, position, num_outputs=1):
    """Build a Code node with JavaScript.

    Args:
        num_outputs: Number of output branches (>1 enables multi-output mode).
    """
    params = {"jsCode": js_code}
    if num_outputs > 1:
        params["numberOfOutputs"] = num_outputs
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "parameters": params,
    }


def make_resilient(node: dict, retries: int = 3, wait_ms: int = 60000) -> dict:
    """Add retry + continueOnFail to any node for resilience."""
    node["retryOnFail"] = True
    node["maxTries"] = retries
    node["waitBetweenTries"] = wait_ms
    node["continueOnFail"] = True
    node["alwaysOutputData"] = True
    return node


def build_openrouter_request(name, system_prompt, user_message_expr, position, max_tokens=1500):
    """Build an HTTP Request node to OpenRouter for AI generation. Auto-retries 3x."""
    return make_resilient({
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": position,
        "credentials": {"openRouterApi": CRED_OPENROUTER},
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "openRouterApi",
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
                "temperature": 0.7,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "={{" + user_message_expr + "}}"},
                ],
            }),
            "options": {"timeout": 60000},
        },
    })


def build_gmail_send(name, to, subject_expr, body_expr, position, is_html=True):
    """Build a Gmail send node."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": position,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "parameters": {
            "operation": "send",
            "sendTo": to,
            "subject": subject_expr,
            "emailType": "html" if is_html else "text",
            "message": body_expr,
            "options": {},
        },
    }


def build_if_node(name, condition_expr, position, negate=False):
    """Build an If node (n8n v2.2 compatible).

    Args:
        name: Node name
        condition_expr: Expression to evaluate (e.g. "={{$json.noAnomalies}}")
        position: [x, y] position
        negate: If True, checks for false (true branch = expression is false)
    """
    # n8n If v2.2 requires: version=2, typeValidation="strict", singleValue for unary ops
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
                "combinator": "and",
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


def build_switch_node(name, field_expr, rules, position, operation="equals"):
    """Build a Switch node for routing.

    Args:
        operation: "equals" for exact match, "contains" for substring match.
    """
    values = []
    for rule_value in rules:
        values.append({
            "conditions": {
                "conditions": [
                    {
                        "leftValue": field_expr,
                        "rightValue": rule_value,
                        "operator": {"type": "string", "operation": operation},
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


def build_merge_node(name, position, mode="append"):
    """Build a Merge node."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.merge",
        "typeVersion": 3,
        "position": position,
        "parameters": {
            "mode": mode,
        },
    }


def build_http_request(name, method, url, position, auth_cred=None, headers=None, body=None):
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
    if auth_cred:
        node["credentials"] = {"httpHeaderAuth": auth_cred}
    if headers:
        node["parameters"]["sendHeaders"] = True
        node["parameters"]["headerParameters"] = {"parameters": headers}
    if body:
        node["parameters"]["sendBody"] = True
        node["parameters"]["specifyBody"] = "json"
        node["parameters"]["jsonBody"] = json.dumps(body) if isinstance(body, dict) else body
    return node


def build_google_ads_node(name, position, operation="getAll"):
    """Build native Google Ads node (read-only)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.googleAds",
        "typeVersion": 1,
        "position": position,
        "credentials": {"googleAdsOAuth2Api": CRED_GOOGLE_ADS},
        "parameters": {
            "resource": "campaign",
            "operation": operation,
            "managerCustomerId": GOOGLE_ADS_MANAGER_ID,
            "clientCustomerId": GOOGLE_ADS_CUSTOMER_ID,
            "returnAll": True,
            "additionalFields": {},
        },
    }


def build_facebook_graph_api(name, method, endpoint, position, fields=None):
    """Build Facebook Graph API node for Meta Ads."""
    params = {
        "httpRequestMethod": method,
        "graphApiVersion": "v25.0",
        "node": endpoint,
        "options": {},
    }
    if fields:
        # Split fields into separate query parameters if they contain & (e.g. date_preset, level)
        if "&" in fields:
            parts = fields.split("&")
            query_params = [{"name": "fields", "value": parts[0]}]
            for part in parts[1:]:
                k, v = part.split("=", 1)
                query_params.append({"name": k, "value": v})
            params["options"]["queryParameters"] = {"parameter": query_params}
        else:
            params["options"]["queryParameters"] = {"parameter": [{"name": "fields", "value": fields}]}

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.facebookGraphApi",
        "typeVersion": 1,
        "position": position,
        "credentials": {"facebookGraphApi": CRED_META_ADS},
        "parameters": params,
    }


def build_respond_webhook(name, position, response_data_expr="={{$json}}"):
    """Build a Respond to Webhook node."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": position,
        "parameters": {
            "respondWith": "json",
            "responseBody": response_data_expr,
        },
    }


def build_no_op(name, position):
    """Build a No Op node (pass-through)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": position,
        "parameters": {},
    }


# ======================================================================
# ADS-04: PERFORMANCE MONITOR
# ======================================================================

def build_ads04_nodes():
    """Build ADS-04: Performance Monitor nodes."""
    nodes = []

    # 1. Schedule Trigger - every 6 hours
    nodes.append(build_schedule_trigger(
        "Schedule Trigger", "0 */6 * * *", [250, 300]
    ))

    # 2. Read Active Campaigns from Airtable
    nodes.append(build_airtable_search(
        "Read Active Campaigns",
        MARKETING_BASE_ID, TABLE_CAMPAIGNS,
        "=OR({Status}='Launched',{Status}='Active')",
        [500, 300],
    ))

    # 3. Google Ads - Get Campaign Metrics (continueOnFail: account may not be enabled yet)
    google_node = build_google_ads_node("Google Ads Get Campaigns", [750, 100])
    google_node["continueOnFail"] = True
    google_node["alwaysOutputData"] = True
    nodes.append(google_node)

    # 4. Transform Google Ads data (handle empty/error input gracefully)
    nodes.append(build_code_node(
        "Transform Google Data", ADS04_TRANSFORM_GOOGLE_CODE, [1000, 100]
    ))

    # 5. Meta Ads - Get Insights (continueOnFail: credentials may not be ready)
    meta_node = build_facebook_graph_api(
        "Meta Ads Get Insights", "GET",
        f"={META_ADS_ACCOUNT_ID}/insights",
        [750, 300],
        fields="campaign_id,campaign_name,impressions,clicks,spend,actions,cpc,cpm,ctr,reach&date_preset=today&level=campaign",
    )
    meta_node["continueOnFail"] = True
    meta_node["alwaysOutputData"] = True
    nodes.append(meta_node)

    # 6. Transform Meta Ads data (handle empty/error input gracefully)
    nodes.append(build_code_node(
        "Transform Meta Data", ADS04_TRANSFORM_META_CODE, [1000, 300]
    ))

    # 7. TikTok Ads - REMOVED (not configured yet)
    # To re-add TikTok: add TikTok HTTP node here and chain via a second Merge node

    # 8. Merge All Platform Data (Google + Meta only)
    nodes.append(build_merge_node("Merge All Metrics", [1250, 300]))

    # 9. Filter out skip items
    nodes.append(build_code_node(
        "Filter Valid Data", ADS04_FILTER_SKIP_CODE, [1500, 300]
    ))

    # 10. Write to Ad_Performance table
    node = build_airtable_create(
        "Write Ad Performance", MARKETING_BASE_ID, TABLE_PERFORMANCE, [1750, 300]
    )
    node["continueOnFail"] = True
    nodes.append(node)

    # 11. Anomaly Detection
    nodes.append(build_code_node(
        "Anomaly Detection", ADS04_ANOMALY_DETECTION_CODE, [2000, 300]
    ))

    # 12. Check if anomalies exist (true branch = has anomalies)
    nodes.append(build_if_node(
        "Has Anomalies", "={{$json.noAnomalies}}", [2250, 300], negate=True
    ))

    # 13. Send Anomaly Alert (true branch)
    alert_body = "={{\"<h2>ADS ANOMALY ALERT</h2><pre>\" + JSON.stringify($json, null, 2) + \"</pre>\"}}"
    nodes.append(build_gmail_send(
        "Send Anomaly Alert", ALERT_EMAIL,
        "AVM Ads ALERT - Anomaly Detected",
        alert_body, [2500, 200],
    ))

    # 14. No anomalies - pass through (false branch)
    nodes.append(build_no_op("No Anomalies", [2500, 400]))

    return nodes


def build_ads04_connections(nodes):
    """Build ADS-04 connections."""
    nm = {n["name"]: n for n in nodes}
    return {
        "Schedule Trigger": {"main": [[
            {"node": "Read Active Campaigns", "type": "main", "index": 0},
        ]]},
        "Read Active Campaigns": {"main": [[
            {"node": "Google Ads Get Campaigns", "type": "main", "index": 0},
            {"node": "Meta Ads Get Insights", "type": "main", "index": 0},
        ]]},
        "Google Ads Get Campaigns": {"main": [[
            {"node": "Transform Google Data", "type": "main", "index": 0},
        ]]},
        "Transform Google Data": {"main": [[
            {"node": "Merge All Metrics", "type": "main", "index": 0},
        ]]},
        "Meta Ads Get Insights": {"main": [[
            {"node": "Transform Meta Data", "type": "main", "index": 0},
        ]]},
        "Transform Meta Data": {"main": [[
            {"node": "Merge All Metrics", "type": "main", "index": 1},
        ]]},
        "Merge All Metrics": {"main": [[
            {"node": "Filter Valid Data", "type": "main", "index": 0},
        ]]},
        "Filter Valid Data": {"main": [[
            {"node": "Write Ad Performance", "type": "main", "index": 0},
        ]]},
        "Write Ad Performance": {"main": [[
            {"node": "Anomaly Detection", "type": "main", "index": 0},
        ]]},
        "Anomaly Detection": {"main": [[
            {"node": "Has Anomalies", "type": "main", "index": 0},
        ]]},
        "Has Anomalies": {"main": [
            [{"node": "Send Anomaly Alert", "type": "main", "index": 0}],
            [{"node": "No Anomalies", "type": "main", "index": 0}],
        ]},
    }


# ======================================================================
# ADS-08: REPORTING DASHBOARD
# ======================================================================

def build_ads08_nodes():
    """Build ADS-08: Reporting Dashboard nodes."""
    nodes = []

    # 1. Schedule Trigger - Mon 08:00 SAST (06:00 UTC)
    nodes.append(build_schedule_trigger(
        "Schedule Trigger", "0 6 * * 1", [250, 300]
    ))

    # 2. Read Campaign Summary (last 7 days)
    nodes.append(build_airtable_search(
        "Read Campaign Summary",
        MARKETING_BASE_ID, TABLE_CAMPAIGNS,
        "=OR({Status}='Active',{Status}='Launched',{Status}='Completed')",
        [500, 300],
    ))

    # 3. Read Performance Data (last 7 days)
    nodes.append(build_airtable_search(
        "Read Performance Data",
        MARKETING_BASE_ID, TABLE_PERFORMANCE,
        "=IS_AFTER({Date}, DATEADD(TODAY(), -7, 'days'))",
        [500, 500],
    ))

    # 4. Read Budget Allocations
    nodes.append(build_airtable_search(
        "Read Budget Allocations",
        MARKETING_BASE_ID, TABLE_BUDGET_ALLOC,
        "={Status}='Active'",
        [500, 100],
    ))

    # 5. Merge data
    nodes.append(build_merge_node("Merge Report Data", [750, 300]))

    # 6. AI Report Generator
    node = build_openrouter_request(
        "AI Report Generator",
        ADS08_AI_REPORT_PROMPT.replace("{performance_data}", "{{JSON.stringify($json)}}"),
        "JSON.stringify($json)",
        [1000, 300],
        max_tokens=1500,
    )
    node["continueOnFail"] = True
    nodes.append(node)

    # 7. Build HTML Report
    nodes.append(build_code_node(
        "Build HTML Report", ADS08_BUILD_REPORT_CODE, [1250, 300]
    ))

    # 8. Send Weekly Email
    nodes.append(build_gmail_send(
        "Send Weekly Report", ALERT_EMAIL,
        "={{$json.subject}}",
        "={{$json.html}}",
        [1500, 300],
    ))

    # 9a. Format Gmail response into Orchestrator Events fields
    nodes.append(build_code_node("Format Report Log", r"""
// Transform Gmail send response into Orchestrator Events fields
const gmailResp = $input.first().json;

return [{json: {
  'Event Type': 'kpi_update',
  'Source Agent': 'ADS-08',
  'Priority': 'P4',
  'Status': 'Completed',
  'Payload': JSON.stringify({
    messageId: gmailResp.id || '',
    threadId: gmailResp.threadId || '',
    sentAt: new Date().toISOString(),
  }),
  'Created At': new Date().toISOString(),
}}];
""", [1625, 300]))

    # 9b. Log to orchestrator (defineBelow to prevent field leaking into singleSelect)
    nodes.append({
        "id": uid(),
        "name": "Log Report Event",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1750, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "continueOnFail": True,
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": ORCH_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_ORCH_EVENTS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Event Type": "={{ $json['Event Type'] }}",
                    "Source Agent": "={{ $json['Source Agent'] }}",
                    "Priority": "={{ $json['Priority'] }}",
                    "Status": "={{ $json['Status'] }}",
                    "Payload": "={{ $json['Payload'] }}",
                    "Created At": "={{ $json['Created At'] }}",
                },
            },
            "options": {},
        },
    })

    return nodes


def build_ads08_connections(nodes):
    """Build ADS-08 connections."""
    return {
        "Schedule Trigger": {"main": [[
            {"node": "Read Campaign Summary", "type": "main", "index": 0},
            {"node": "Read Performance Data", "type": "main", "index": 0},
            {"node": "Read Budget Allocations", "type": "main", "index": 0},
        ]]},
        "Read Campaign Summary": {"main": [[
            {"node": "Merge Report Data", "type": "main", "index": 0},
        ]]},
        "Read Performance Data": {"main": [[
            {"node": "Merge Report Data", "type": "main", "index": 1},
        ]]},
        "Read Budget Allocations": {"main": [[
            {"node": "Merge Report Data", "type": "main", "index": 2},
        ]]},
        "Merge Report Data": {"main": [[
            {"node": "AI Report Generator", "type": "main", "index": 0},
        ]]},
        "AI Report Generator": {"main": [[
            {"node": "Build HTML Report", "type": "main", "index": 0},
        ]]},
        "Build HTML Report": {"main": [[
            {"node": "Send Weekly Report", "type": "main", "index": 0},
        ]]},
        "Send Weekly Report": {"main": [[
            {"node": "Format Report Log", "type": "main", "index": 0},
        ]]},
        "Format Report Log": {"main": [[
            {"node": "Log Report Event", "type": "main", "index": 0},
        ]]},
    }


# ======================================================================
# ADS-01: CAMPAIGN STRATEGY GENERATOR
# ======================================================================

ADS01_PARSE_STRATEGY_CODE = r"""
// Parse AI strategy response into individual campaign records
const aiResp = $('AI Strategy Generator').first().json;
const content = aiResp.choices?.[0]?.message?.content || '[]';

let campaigns;
try {
  // Strip markdown code fences if present
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  campaigns = JSON.parse(cleaned);
} catch (e) {
  return [{json: {error: 'Failed to parse AI response', raw: content}}];
}

if (!Array.isArray(campaigns)) campaigns = [campaigns];

const now = new Date().toISOString().split('T')[0];
const results = [];

for (const c of campaigns) {
  results.push({
    json: {
      'Campaign Name': c.campaign_name || 'Untitled Campaign',
      'Platform': c.platform || 'google_ads',
      'Objective': c.objective || 'Conversions',
      'Status': 'Planned',
      'Target Audience': c.target_audience || '',
      'Daily Budget ZAR': c.suggested_daily_budget_zar || 100,
      'Lifetime Budget ZAR': (c.suggested_daily_budget_zar || 100) * (c.duration_days || 14),
      'Key Messages': JSON.stringify(c.key_messages || []),
      'Priority': c.priority || 'Medium',
      'Created At': now,
      'Created By': 'ADS-01',
    }
  });
}

return results.length > 0 ? results : [{json: {skip: true, reason: 'No campaigns generated'}}];
"""


def build_ads01_nodes():
    """Build ADS-01: Campaign Strategy Generator nodes."""
    nodes = []

    # 1. Schedule: Monday 07:00 SAST (05:00 UTC)
    nodes.append(build_schedule_trigger("Schedule Trigger", "0 5 * * 1", [250, 300]))

    # 2. Read Research Insights (organic content performance)
    nodes.append(build_airtable_search(
        "Read Research Insights", MARKETING_BASE_ID, TABLE_RESEARCH_INSIGHTS,
        "=IS_AFTER({Created At}, DATEADD(TODAY(), -7, 'days'))", [500, 100],
    ))

    # 3. Read Existing Campaigns
    nodes.append(build_airtable_search(
        "Read Current Campaigns", MARKETING_BASE_ID, TABLE_CAMPAIGNS,
        "=OR({Status}='Active',{Status}='Launched',{Status}='Planned')", [500, 300],
    ))

    # 4. Read Budget Allocations
    nodes.append(build_airtable_search(
        "Read Budget Data", MARKETING_BASE_ID, TABLE_BUDGET_ALLOC,
        "={Status}='Active'", [500, 500],
    ))

    # 5. Merge context data
    nodes.append(build_merge_node("Merge Context", [750, 300]))

    # 5b. Aggregate all merged items into structured context for AI
    nodes.append(build_code_node("Aggregate Context", r"""
// Collect all merged items into structured context
const items = $input.all();
const research = [];
const campaigns = [];
const budgets = [];

for (const item of items) {
  const d = item.json;
  if (d['Campaign Name'] && (d.Status === 'Active' || d.Status === 'Launched' || d.Status === 'Planned')) {
    campaigns.push(d);
  } else if (d['Allocation Name'] || d['Daily Budget ZAR'] !== undefined) {
    budgets.push(d);
  } else {
    research.push(d);
  }
}

return [{json: {
  research_insights: research,
  current_campaigns: campaigns,
  budget_allocation: budgets,
  timestamp: new Date().toISOString(),
}}];
""", [875, 300]))

    # 6. AI Strategy Generator
    prompt = ADS01_STRATEGY_PROMPT.replace(
        "{research_data}", "{{JSON.stringify($json)}}"
    ).replace(
        "{current_campaigns}", "{{JSON.stringify($json)}}"
    ).replace(
        "{budget_data}", "{{JSON.stringify($json)}}"
    ).replace(
        "{daily_cap}", str(DAILY_CAP)
    ).replace(
        "{weekly_cap}", str(WEEKLY_CAP)
    ).replace(
        "{monthly_cap}", str(MONTHLY_CAP)
    )
    node = build_openrouter_request(
        "AI Strategy Generator", prompt, "JSON.stringify($json)", [1000, 300], max_tokens=2000,
    )
    node["continueOnFail"] = True
    nodes.append(node)

    # 7. Parse AI response into campaign records
    nodes.append(build_code_node("Parse Strategy", ADS01_PARSE_STRATEGY_CODE, [1250, 300]))

    # 8. Filter valid campaigns
    nodes.append(build_code_node("Filter Valid", ADS04_FILTER_SKIP_CODE, [1500, 300]))

    # 9. Write planned campaigns to Airtable
    node = build_airtable_create(
        "Write Planned Campaigns", MARKETING_BASE_ID, TABLE_CAMPAIGNS, [1750, 300],
    )
    node["continueOnFail"] = True
    nodes.append(node)

    # 10. Send summary email
    nodes.append(build_gmail_send(
        "Email Strategy Summary", ALERT_EMAIL,
        "AVM Ads Strategy - New Campaigns Planned",
        "={{\"<h2>New Campaign Strategies</h2><pre>\" + JSON.stringify($json, null, 2) + \"</pre>\"}}",
        [2000, 200],
    ))

    # 11. Trigger ADS-02 to generate creatives for planned campaigns
    n8n_base = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    nodes.append({
        "id": uid(),
        "name": "Trigger Creative Generation",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2000, 450],
        "parameters": {
            "method": "POST",
            "url": f"{n8n_base}/webhook/ads-generate-creatives",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={\"triggered_by\": \"ADS-01\", \"timestamp\": \"\" + $now.toISO() + \"\"}",
            "options": {"timeout": 10000},
        },
        "continueOnFail": True,
    })

    return nodes


def build_ads01_connections(nodes):
    """Build ADS-01 connections."""
    return {
        "Schedule Trigger": {"main": [[
            {"node": "Read Research Insights", "type": "main", "index": 0},
            {"node": "Read Current Campaigns", "type": "main", "index": 0},
            {"node": "Read Budget Data", "type": "main", "index": 0},
        ]]},
        "Read Research Insights": {"main": [[
            {"node": "Merge Context", "type": "main", "index": 0},
        ]]},
        "Read Current Campaigns": {"main": [[
            {"node": "Merge Context", "type": "main", "index": 1},
        ]]},
        "Read Budget Data": {"main": [[
            {"node": "Merge Context", "type": "main", "index": 2},
        ]]},
        "Merge Context": {"main": [[
            {"node": "Aggregate Context", "type": "main", "index": 0},
        ]]},
        "Aggregate Context": {"main": [[
            {"node": "AI Strategy Generator", "type": "main", "index": 0},
        ]]},
        "AI Strategy Generator": {"main": [[
            {"node": "Parse Strategy", "type": "main", "index": 0},
        ]]},
        "Parse Strategy": {"main": [[
            {"node": "Filter Valid", "type": "main", "index": 0},
        ]]},
        "Filter Valid": {"main": [[
            {"node": "Write Planned Campaigns", "type": "main", "index": 0},
        ]]},
        "Write Planned Campaigns": {"main": [[
            {"node": "Email Strategy Summary", "type": "main", "index": 0},
            {"node": "Trigger Creative Generation", "type": "main", "index": 0},
        ]]},
    }


# ======================================================================
# ADS-02: AD COPY & CREATIVE GENERATOR
# ======================================================================

ADS02_PARSE_CREATIVES_CODE = r"""
// Parse AI creative responses and prepare for Airtable
const items = $input.all();
const results = [];
const now = new Date().toISOString().split('T')[0];
let idx = 0;

for (const item of items) {
  if (item.json.skip) continue;

  const resp = item.json;
  const content = resp.choices?.[0]?.message?.content || JSON.stringify(resp);

  let creative;
  try {
    const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
    creative = JSON.parse(cleaned);
  } catch (e) {
    creative = {raw: content};
  }

  const campaignName = item.json._campaignName || 'Unknown';
  const platform = item.json._platform || 'google_ads';

  // Handle Google RSA format
  if (creative.headlines) {
    idx++;
    results.push({json: {
      'Creative Name': `${campaignName} - RSA ${now} #${idx}`,
      'Campaign Name': campaignName,
      'Platform': platform,
      'Ad Format': 'RSA',
      'Status': 'Draft',
      'Headlines': JSON.stringify(creative.headlines),
      'Descriptions': JSON.stringify(creative.descriptions || []),
      'CTA': 'Learn_More',
      'Created At': now,
    }});
  }

  // Handle Meta format with variants
  if (creative.variants) {
    for (const v of creative.variants) {
      idx++;
      results.push({json: {
        'Creative Name': `${campaignName} - Meta ${now} #${idx}`,
        'Campaign Name': campaignName,
        'Platform': platform,
        'Ad Format': 'Image',
        'Status': 'Draft',
        'Primary Text': v.primary_text || '',
        'Headlines': JSON.stringify([v.headline || '']),
        'Descriptions': JSON.stringify([v.description || '']),
        'CTA': (v.cta || 'Learn_More').replace('_', '_'),
        'Created At': now,
      }});
    }
  }

  // Handle TikTok format
  if (creative.hook && creative.script) {
    idx++;
    results.push({json: {
      'Creative Name': `${campaignName} - TikTok ${now} #${idx}`,
      'Campaign Name': campaignName,
      'Platform': platform,
      'Ad Format': 'Video',
      'Status': 'Draft',
      'Primary Text': creative.script,
      'Headlines': JSON.stringify([creative.hook]),
      'Descriptions': JSON.stringify([creative.caption || '']),
      'CTA': 'Learn_More',
      'Created At': now,
    }});
  }
}

return results.length > 0 ? results : [{json: {skip: true, reason: 'No creatives parsed'}}];
"""

ADS02_QUALITY_FILTER_CODE = r"""
// Filter creatives by quality score (>= 6/10)
const items = $input.all();
const results = [];

for (const item of items) {
  if (item.json.skip) continue;

  const resp = item.json;
  const content = resp.choices?.[0]?.message?.content || '';

  let score;
  try {
    const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
    score = JSON.parse(cleaned);
  } catch (e) {
    score = {overall: 7}; // Default pass if parsing fails
  }

  const overall = score.overall || 7;
  const creative = $('Parse Creatives').first().json;

  if (overall >= 6) {
    results.push({json: {
      ...creative,
      'Quality Score': overall,
    }});
  }
}

return results.length > 0 ? results : [{json: {skip: true, reason: 'All creatives below quality threshold'}}];
"""


def build_ads02_nodes():
    """Build ADS-02: Ad Copy & Creative Generator nodes."""
    nodes = []

    # 1. Webhook trigger (called by ADS-01 or manual)
    nodes.append(build_webhook_trigger("Webhook Trigger", "ads-generate-creatives", [250, 300]))

    # 2. Read campaign plans (Planned status)
    nodes.append(build_airtable_search(
        "Read Campaign Plans", MARKETING_BASE_ID, TABLE_CAMPAIGNS,
        "={Status}='Planned'", [500, 300],
    ))

    # 2b. Guard against empty results (Switch crashes on 0 items)
    nodes.append(build_if_node(
        "Has Campaigns?",
        "={{$input.all().length > 0}}",
        [625, 300],
    ))

    # 3. Route by platform (Switch node — 3 outputs: google, meta, tiktok)
    nodes.append(build_switch_node(
        "Route by Platform",
        "={{$json.Platform}}",
        ["google_ads", "meta_ads", "tiktok_ads"],
        [750, 300],
        operation="contains",
    ))

    # 4. Google Copy Agent (continueOnFail for skip items from Route by Platform)
    google_prompt = ADS02_GOOGLE_COPY_PROMPT.replace(
        "{campaign_name}", "{{$json['Campaign Name']}}"
    ).replace("{objective}", "{{$json.Objective}}"
    ).replace("{target_audience}", "{{$json['Target Audience']}}"
    ).replace("{key_messages}", "{{$json['Key Messages']}}")
    google_node = build_openrouter_request(
        "Google Copy Agent", google_prompt, "JSON.stringify($json)", [1000, 100], max_tokens=2000,
    )
    google_node["continueOnFail"] = True
    google_node["alwaysOutputData"] = True
    nodes.append(google_node)

    # 5. Meta Copy Agent
    meta_prompt = ADS02_META_COPY_PROMPT.replace(
        "{campaign_name}", "{{$json['Campaign Name']}}"
    ).replace("{objective}", "{{$json.Objective}}"
    ).replace("{target_audience}", "{{$json['Target Audience']}}"
    ).replace("{key_messages}", "{{$json['Key Messages']}}"
    ).replace("{ad_format}", "Image")
    meta_node = build_openrouter_request(
        "Meta Copy Agent", meta_prompt, "JSON.stringify($json)", [1000, 300], max_tokens=1500,
    )
    meta_node["continueOnFail"] = True
    meta_node["alwaysOutputData"] = True
    nodes.append(meta_node)

    # 6. TikTok Script Agent
    tiktok_prompt = ADS02_TIKTOK_COPY_PROMPT.replace(
        "{campaign_name}", "{{$json['Campaign Name']}}"
    ).replace("{objective}", "{{$json.Objective}}"
    ).replace("{target_audience}", "{{$json['Target Audience']}}"
    ).replace("{key_messages}", "{{$json['Key Messages']}}")
    tiktok_node = build_openrouter_request(
        "TikTok Script Agent", tiktok_prompt, "JSON.stringify($json)", [1000, 500], max_tokens=1500,
    )
    tiktok_node["continueOnFail"] = True
    tiktok_node["alwaysOutputData"] = True
    nodes.append(tiktok_node)

    # 7. Merge all creative outputs
    nodes.append(build_merge_node("Merge Creatives", [1250, 300]))

    # 8. Parse creatives into Airtable format
    nodes.append(build_code_node("Parse Creatives", ADS02_PARSE_CREATIVES_CODE, [1500, 300]))

    # 9. Filter valid creatives
    nodes.append(build_code_node("Filter Valid Creatives", ADS04_FILTER_SKIP_CODE, [1750, 300]))

    # 10. Write to Ad_Creatives table
    node = build_airtable_create(
        "Write Creatives", MARKETING_BASE_ID, TABLE_CREATIVES, [2000, 300],
    )
    node["continueOnFail"] = True
    nodes.append(node)

    # 11. Create approval request (defineBelow — singleSelect must match exactly)
    nodes.append({
        "id": uid(),
        "name": "Create Approval Request",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [2250, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": MARKETING_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_APPROVALS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Campaign Name": "={{ $json.fields ? $json.fields['Campaign Name'] : $json['Campaign Name'] }}",
                    "Request Type": "Creative_Update",
                    "Requested By": "ADS-02",
                    "Status": "Pending",
                    "Details": "={{ ($json.fields ? $json.fields['Creative Name'] : $json['Creative Name']) + ' (' + ($json.fields ? $json.fields['Platform'] : $json['Platform']) + ')' }}",
                    "Created At": "={{ new Date().toISOString().split('T')[0] }}",
                },
            },
            "options": {},
        },
    })

    # 12. Email approval notification
    nodes.append(build_gmail_send(
        "Email Approval Link", ALERT_EMAIL,
        "AVM Ads - New Creatives Pending Approval",
        "={{\"<h2>New Ad Creatives Ready for Review</h2><p>\" + $json['Creative Name'] + \" created for \" + $json['Campaign Name'] + \"</p><pre>\" + JSON.stringify($json, null, 2) + \"</pre>\"}}",
        [2500, 300],
    ))

    return nodes


def build_ads02_connections(nodes):
    """Build ADS-02 connections."""
    return {
        "Webhook Trigger": {"main": [[
            {"node": "Read Campaign Plans", "type": "main", "index": 0},
        ]]},
        "Read Campaign Plans": {"main": [[
            {"node": "Has Campaigns?", "type": "main", "index": 0},
        ]]},
        "Has Campaigns?": {"main": [
            [{"node": "Route by Platform", "type": "main", "index": 0}],
            [],
        ]},
        "Route by Platform": {"main": [
            [{"node": "Google Copy Agent", "type": "main", "index": 0}],
            [{"node": "Meta Copy Agent", "type": "main", "index": 0}],
            [{"node": "TikTok Script Agent", "type": "main", "index": 0}],
        ]},
        "Google Copy Agent": {"main": [[
            {"node": "Merge Creatives", "type": "main", "index": 0},
        ]]},
        "Meta Copy Agent": {"main": [[
            {"node": "Merge Creatives", "type": "main", "index": 1},
        ]]},
        "TikTok Script Agent": {"main": [[
            {"node": "Merge Creatives", "type": "main", "index": 2},
        ]]},
        "Merge Creatives": {"main": [[
            {"node": "Parse Creatives", "type": "main", "index": 0},
        ]]},
        "Parse Creatives": {"main": [[
            {"node": "Filter Valid Creatives", "type": "main", "index": 0},
        ]]},
        "Filter Valid Creatives": {"main": [[
            {"node": "Write Creatives", "type": "main", "index": 0},
        ]]},
        "Write Creatives": {"main": [[
            {"node": "Create Approval Request", "type": "main", "index": 0},
        ]]},
        "Create Approval Request": {"main": [[
            {"node": "Email Approval Link", "type": "main", "index": 0},
        ]]},
    }


# ======================================================================
# ADS-03: CAMPAIGN BUILDER & PUBLISHER
# ======================================================================

ADS03_BUDGET_SAFETY_CODE = r"""
// Budget safety check - enforce all caps before campaign creation
const items = $input.all();
const DAILY_CAP = 666;
const WEEKLY_CAP = 5000;
const MONTHLY_CAP = 20000;

const results = [];

for (const item of items) {
  const d = item.json;
  const dailyBudget = d['Daily Budget ZAR'] || 0;
  const errors = [];

  if (dailyBudget > DAILY_CAP) {
    errors.push(`Daily R${dailyBudget} exceeds cap R${DAILY_CAP}`);
  }
  if (dailyBudget * 7 > WEEKLY_CAP) {
    errors.push(`Weekly projection R${dailyBudget * 7} exceeds cap R${WEEKLY_CAP}`);
  }
  if (dailyBudget * 30 > MONTHLY_CAP) {
    errors.push(`Monthly projection R${dailyBudget * 30} exceeds cap R${MONTHLY_CAP}`);
  }

  if (errors.length > 0) {
    results.push({json: {
      ...d,
      _budgetSafe: false,
      _budgetErrors: errors,
    }});
  } else {
    results.push({json: {
      ...d,
      _budgetSafe: true,
      _budgetErrors: [],
    }});
  }
}

return results;
"""

ADS03_BUILD_GOOGLE_CAMPAIGN_CODE = r"""
// Build Google Ads campaign creation payload
const items = $input.all();
const results = [];

for (const item of items) {
  const d = item.json;
  if (!d._budgetSafe) continue;

  const dailyBudgetMicros = Math.round((d['Daily Budget ZAR'] || 100) * 1000000);

  results.push({json: {
    _platform: 'google_ads',
    _campaignName: d['Campaign Name'],
    operations: [
      {
        create: {
          name: d['Campaign Name'],
          advertisingChannelType: d.Objective === 'Video_Views' ? 'VIDEO' : 'SEARCH',
          status: 'PAUSED',
          containsEuPoliticalAdvertising: false,
          campaignBudget: {
            amountMicros: dailyBudgetMicros,
            deliveryMethod: 'STANDARD',
          },
          startDate: new Date().toISOString().split('T')[0].replace(/-/g, ''),
          endDate: new Date(Date.now() + (d.duration_days || 14) * 86400000).toISOString().split('T')[0].replace(/-/g, ''),
        }
      }
    ],
  }});
}

return results.length > 0 ? results : [{json: {skip: true}}];
"""

ADS03_BUILD_META_CAMPAIGN_CODE = r"""
// Build Meta Ads campaign creation payload
const items = $input.all();
const results = [];

const objectiveMap = {
  'Traffic': 'OUTCOME_TRAFFIC',
  'Conversions': 'OUTCOME_SALES',
  'Lead_Gen': 'OUTCOME_LEADS',
  'Awareness': 'OUTCOME_AWARENESS',
  'Video_Views': 'OUTCOME_ENGAGEMENT',
};

for (const item of items) {
  const d = item.json;
  if (!d._budgetSafe) continue;

  results.push({json: {
    _platform: 'meta_ads',
    _campaignName: d['Campaign Name'],
    name: d['Campaign Name'],
    objective: objectiveMap[d.Objective] || 'OUTCOME_LEADS',
    status: 'PAUSED',
    daily_budget: Math.round((d['Daily Budget ZAR'] || 100) * 100),
    special_ad_categories: [],
  }});
}

return results.length > 0 ? results : [{json: {skip: true}}];
"""

ADS03_UPDATE_STATUS_CODE = r"""
// Update campaign status to Launched after creation
const items = $input.all();
const results = [];
const now = new Date().toISOString().split('T')[0];

for (const item of items) {
  const d = item.json;
  if (d.skip) continue;

  results.push({json: {
    'Campaign Name': d._campaignName || d['Campaign Name'] || 'Unknown',
    'Status': 'Launched',
    'Start Date': now,
    'External Campaign ID': d.id || d.campaign_id || '',
  }});
}

return results.length > 0 ? results : [{json: {skip: true}}];
"""


def build_ads03_nodes():
    """Build ADS-03: Campaign Builder & Publisher nodes."""
    nodes = []

    # 1. Webhook trigger (approval callback)
    nodes.append(build_webhook_trigger("Webhook Trigger", "ads-build-campaign", [250, 300]))

    # 2. Read approved campaigns
    nodes.append(build_airtable_search(
        "Read Approved Campaigns", MARKETING_BASE_ID, TABLE_CAMPAIGNS,
        "={Status}='Approved'", [500, 300],
    ))

    # 3. Read creatives for campaigns
    nodes.append(build_airtable_search(
        "Read Creatives", MARKETING_BASE_ID, TABLE_CREATIVES,
        "={Status}='Approved'", [500, 500],
    ))

    # 4. Budget safety check
    nodes.append(build_code_node("Budget Safety Check", ADS03_BUDGET_SAFETY_CODE, [750, 300]))

    # 5. Check budget safe
    nodes.append(build_if_node("Budget Safe?", "={{$json._budgetSafe}}", [1000, 300]))

    # 6. Build Google campaign payload
    nodes.append(build_code_node("Build Google Campaign", ADS03_BUILD_GOOGLE_CAMPAIGN_CODE, [1250, 100]))

    # 7. Build Meta campaign payload
    nodes.append(build_code_node("Build Meta Campaign", ADS03_BUILD_META_CAMPAIGN_CODE, [1250, 300]))

    # 8. Google Ads HTTP (create campaign)
    node = build_http_request(
        "Create Google Campaign", "POST",
        f"https://googleads.googleapis.com/v20/customers/{GOOGLE_ADS_CUSTOMER_ID}/campaigns:mutate",
        [1500, 100],
        auth_cred=CRED_GOOGLE_ADS,
    )
    node["continueOnFail"] = True
    nodes.append(node)

    # 9. Meta Ads (create campaign via Graph API)
    meta_campaign_node = build_facebook_graph_api(
        "Create Meta Campaign", "POST",
        f"={META_ADS_ACCOUNT_ID}/campaigns",
        [1500, 300],
    )
    # Add campaign data as query parameters (Facebook Marketing API accepts these)
    meta_campaign_node["parameters"]["options"] = {
        "queryParameters": {
            "parameter": [
                {"name": "name", "value": "={{$json.name}}"},
                {"name": "objective", "value": "={{$json.objective}}"},
                {"name": "status", "value": "={{$json.status}}"},
                {"name": "daily_budget", "value": "={{$json.daily_budget}}"},
                {"name": "special_ad_categories", "value": "={{JSON.stringify($json.special_ad_categories || [])}}"},
            ]
        }
    }
    meta_campaign_node["continueOnFail"] = True
    nodes.append(meta_campaign_node)

    # 10. Merge results
    nodes.append(build_merge_node("Merge Results", [1750, 200]))

    # 11. Update status to Launched
    nodes.append(build_code_node("Update Status", ADS03_UPDATE_STATUS_CODE, [2000, 200]))

    # 12. Budget rejected alert
    nodes.append(build_gmail_send(
        "Budget Rejected Alert", ALERT_EMAIL,
        "AVM Ads ALERT - Budget Safety Block",
        "={{\"<h2>BUDGET SAFETY BLOCK</h2><pre>\" + JSON.stringify($json._budgetErrors, null, 2) + \"</pre>\"}}",
        [1250, 500],
    ))

    return nodes


def build_ads03_connections(nodes):
    """Build ADS-03 connections."""
    return {
        "Webhook Trigger": {"main": [[
            {"node": "Read Approved Campaigns", "type": "main", "index": 0},
        ]]},
        "Read Approved Campaigns": {"main": [[
            {"node": "Read Creatives", "type": "main", "index": 0},
        ]]},
        "Read Creatives": {"main": [[
            {"node": "Budget Safety Check", "type": "main", "index": 0},
        ]]},
        "Budget Safety Check": {"main": [[
            {"node": "Budget Safe?", "type": "main", "index": 0},
        ]]},
        "Budget Safe?": {"main": [
            [  # true branch - budget OK
                {"node": "Build Google Campaign", "type": "main", "index": 0},
                {"node": "Build Meta Campaign", "type": "main", "index": 0},
            ],
            [  # false branch - budget exceeded
                {"node": "Budget Rejected Alert", "type": "main", "index": 0},
            ],
        ]},
        "Build Google Campaign": {"main": [[
            {"node": "Create Google Campaign", "type": "main", "index": 0},
        ]]},
        "Build Meta Campaign": {"main": [[
            {"node": "Create Meta Campaign", "type": "main", "index": 0},
        ]]},
        "Create Google Campaign": {"main": [[
            {"node": "Merge Results", "type": "main", "index": 0},
        ]]},
        "Create Meta Campaign": {"main": [[
            {"node": "Merge Results", "type": "main", "index": 1},
        ]]},
        "Merge Results": {"main": [[
            {"node": "Update Status", "type": "main", "index": 0},
        ]]},
    }


# ======================================================================
# ADS-05: OPTIMIZATION ENGINE
# ======================================================================

ADS05_COMPUTE_SIGNALS_CODE = r"""
// Compute optimization signals from 7-day performance data
const items = $input.all();
const campaignStats = {};

for (const item of items) {
  const d = item.json;
  if (d.skip) continue;

  const key = d['Campaign Name'] + '|' + d.Platform;
  if (!campaignStats[key]) {
    campaignStats[key] = {
      campaign: d['Campaign Name'],
      platform: d.Platform,
      days: 0,
      totalSpend: 0,
      totalClicks: 0,
      totalImpressions: 0,
      totalConversions: 0,
      dailySpends: [],
      dailyCTRs: [],
      dailyCPAs: [],
    };
  }

  const s = campaignStats[key];
  s.days++;
  s.totalSpend += d['Spend ZAR'] || 0;
  s.totalClicks += d.Clicks || 0;
  s.totalImpressions += d.Impressions || 0;
  s.totalConversions += d.Conversions || 0;
  s.dailySpends.push(d['Spend ZAR'] || 0);
  s.dailyCTRs.push(d.CTR || 0);
  if (d.Conversions > 0) s.dailyCPAs.push(d['CPA ZAR'] || 0);
}

const results = [];
for (const [key, s] of Object.entries(campaignStats)) {
  const avgDailySpend = s.totalSpend / Math.max(s.days, 1);
  const avgCTR = s.dailyCTRs.reduce((a, b) => a + b, 0) / Math.max(s.dailyCTRs.length, 1);
  const avgCPA = s.dailyCPAs.length > 0
    ? s.dailyCPAs.reduce((a, b) => a + b, 0) / s.dailyCPAs.length
    : 0;
  const roas = s.totalSpend > 0 ? (s.totalConversions * 100) / s.totalSpend : 0;

  // Trend: compare last 3 days vs first 3 days
  const recentSpend = s.dailySpends.slice(-3).reduce((a, b) => a + b, 0) / 3;
  const earlySpend = s.dailySpends.slice(0, 3).reduce((a, b) => a + b, 0) / 3;
  const spendTrend = earlySpend > 0 ? (recentSpend - earlySpend) / earlySpend : 0;

  results.push({json: {
    campaign: s.campaign,
    platform: s.platform,
    days: s.days,
    totalSpend: parseFloat(s.totalSpend.toFixed(2)),
    avgDailySpend: parseFloat(avgDailySpend.toFixed(2)),
    totalClicks: s.totalClicks,
    totalImpressions: s.totalImpressions,
    totalConversions: s.totalConversions,
    avgCTR: parseFloat(avgCTR.toFixed(4)),
    avgCPA: parseFloat(avgCPA.toFixed(2)),
    roas: parseFloat(roas.toFixed(2)),
    spendTrend: parseFloat(spendTrend.toFixed(2)),
  }});
}

return results.length > 0 ? results : [{json: {skip: true, reason: 'No performance data'}}];
"""

ADS05_PARSE_OPTIMIZATIONS_CODE = r"""
// Parse AI optimization recommendations into flat list with _autoApprove flag
const aiResp = $('AI Optimizer').first().json;
const content = aiResp.choices?.[0]?.message?.content || '[]';

let recommendations;
try {
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  recommendations = JSON.parse(cleaned);
} catch (e) {
  return [{json: {skip: true, _noData: true}}];
}

if (!Array.isArray(recommendations)) recommendations = [recommendations];
if (recommendations.length === 0) {
  return [{json: {skip: true, _noData: true}}];
}

const results = [];
const now = new Date().toISOString().split('T')[0];

for (const rec of recommendations) {
  const isAuto = !!rec.auto_approvable;
  results.push({json: {
    'Campaign Name': rec.campaign_name || rec.campaign || 'Unknown',
    'Request Type': 'Optimization',
    'Requested By': 'ADS-05',
    'Details': JSON.stringify(rec),
    'Created At': now,
    'Status': isAuto ? 'Approved' : 'Pending',
  }});
}

return results.length > 0 ? results : [{json: {skip: true, _noData: true}}];
"""


def build_ads05_nodes():
    """Build ADS-05: Optimization Engine nodes."""
    nodes = []

    # 1. Schedule: Daily 20:00 SAST (18:00 UTC)
    nodes.append(build_schedule_trigger("Schedule Trigger", "0 18 * * *", [250, 300]))

    # 2. Read 7-day performance
    nodes.append(build_airtable_search(
        "Read 7-Day Performance", MARKETING_BASE_ID, TABLE_PERFORMANCE,
        "=IS_AFTER({Date}, DATEADD(TODAY(), -7, 'days'))", [500, 300],
    ))

    # 3. Read budget allocations
    nodes.append(build_airtable_search(
        "Read Budgets", MARKETING_BASE_ID, TABLE_BUDGET_ALLOC,
        "={Status}='Active'", [500, 500],
    ))

    # 4. Compute optimization signals
    nodes.append(build_code_node("Compute Signals", ADS05_COMPUTE_SIGNALS_CODE, [750, 300]))

    # 5. Merge with budget data
    nodes.append(build_merge_node("Merge Data", [1000, 400]))

    # 5b. Aggregate merged performance + budget data for AI
    nodes.append(build_code_node("Aggregate Data", r"""
// Collect all merged items into structured context
const items = $input.all();
const performance = [];
const budgets = [];

for (const item of items) {
  const d = item.json;
  if (d['Allocation Name'] || d['Daily Budget ZAR'] !== undefined) {
    budgets.push(d);
  } else {
    performance.push(d);
  }
}

return [{json: {
  performance_data: performance,
  budget_data: budgets,
  timestamp: new Date().toISOString(),
}}];
""", [1125, 350]))

    # 6. AI Optimizer
    prompt = ADS05_OPTIMIZATION_PROMPT.replace(
        "{performance_data}", "{{JSON.stringify($json)}}"
    ).replace("{budget_data}", "{{JSON.stringify($json)}}"
    ).replace("{daily_cap}", str(DAILY_CAP)
    ).replace("{weekly_cap}", str(WEEKLY_CAP)
    ).replace("{monthly_cap}", str(MONTHLY_CAP))
    node = build_openrouter_request(
        "AI Optimizer", prompt, "JSON.stringify($json)", [1250, 300], max_tokens=2000,
    )
    node["continueOnFail"] = True
    nodes.append(node)

    # 7. Parse recommendations (single output with _autoApprove flag)
    nodes.append(build_code_node("Parse Optimizations", ADS05_PARSE_OPTIMIZATIONS_CODE, [1500, 300]))

    # 7b. Filter skip items
    nodes.append(build_code_node("Filter Valid Opts", ADS04_FILTER_SKIP_CODE, [1625, 300]))

    # 7c. Split by auto-approve flag
    nodes.append(build_if_node("Auto Approve?", "={{$json.Status === 'Approved'}}", [1750, 300]))

    # 8. Log auto-applied changes (true branch — defineBelow to prevent field leaking)
    nodes.append({
        "id": uid(),
        "name": "Log Auto Changes",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [2000, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "continueOnFail": True,
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": MARKETING_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_APPROVALS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Campaign Name": "={{ $json['Campaign Name'] }}",
                    "Request Type": "={{ $json['Request Type'] }}",
                    "Requested By": "={{ $json['Requested By'] }}",
                    "Status": "={{ $json['Status'] }}",
                    "Details": "={{ $json['Details'] }}",
                    "Created At": "={{ $json['Created At'] }}",
                },
            },
            "options": {},
        },
    })

    # 9. Create approval requests for manual changes (false branch — defineBelow)
    nodes.append({
        "id": uid(),
        "name": "Create Approval Requests",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [2000, 500],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "continueOnFail": True,
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": MARKETING_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_APPROVALS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Campaign Name": "={{ $json['Campaign Name'] }}",
                    "Request Type": "={{ $json['Request Type'] }}",
                    "Requested By": "={{ $json['Requested By'] }}",
                    "Status": "={{ $json['Status'] }}",
                    "Details": "={{ $json['Details'] }}",
                    "Created At": "={{ $json['Created At'] }}",
                },
            },
            "options": {},
        },
    })

    # 10. Email optimization summary
    nodes.append(build_gmail_send(
        "Email Optimization Summary", ALERT_EMAIL,
        "AVM Ads - Daily Optimization Report",
        "={{\"<h2>Optimization Recommendations</h2><pre>\" + JSON.stringify($json, null, 2) + \"</pre>\"}}",
        [2000, 350],
    ))

    return nodes


def build_ads05_connections(nodes):
    """Build ADS-05 connections."""
    return {
        "Schedule Trigger": {"main": [[
            {"node": "Read 7-Day Performance", "type": "main", "index": 0},
            {"node": "Read Budgets", "type": "main", "index": 0},
        ]]},
        "Read 7-Day Performance": {"main": [[
            {"node": "Compute Signals", "type": "main", "index": 0},
        ]]},
        "Compute Signals": {"main": [[
            {"node": "Merge Data", "type": "main", "index": 0},
        ]]},
        "Read Budgets": {"main": [[
            {"node": "Merge Data", "type": "main", "index": 1},
        ]]},
        "Merge Data": {"main": [[
            {"node": "Aggregate Data", "type": "main", "index": 0},
        ]]},
        "Aggregate Data": {"main": [[
            {"node": "AI Optimizer", "type": "main", "index": 0},
        ]]},
        "AI Optimizer": {"main": [[
            {"node": "Parse Optimizations", "type": "main", "index": 0},
        ]]},
        "Parse Optimizations": {"main": [[
            {"node": "Filter Valid Opts", "type": "main", "index": 0},
        ]]},
        "Filter Valid Opts": {"main": [[
            {"node": "Auto Approve?", "type": "main", "index": 0},
        ]]},
        "Auto Approve?": {"main": [
            [{"node": "Log Auto Changes", "type": "main", "index": 0}],
            [{"node": "Create Approval Requests", "type": "main", "index": 0}],
        ]},
        "Log Auto Changes": {"main": [[
            {"node": "Email Optimization Summary", "type": "main", "index": 0},
        ]]},
        "Create Approval Requests": {"main": [[
            {"node": "Email Optimization Summary", "type": "main", "index": 0},
        ]]},
    }


# ======================================================================
# ADS-06: CREATIVE RECYCLER
# ======================================================================

ADS06_FIND_TOP_PERFORMERS_CODE = r"""
// Find top-performing campaigns (ROAS > 2.0 or CTR top 20%)
const items = $input.all();
const campaignMetrics = {};

for (const item of items) {
  const d = item.json;
  if (d.skip) continue;

  const key = d['Campaign Name'];
  if (!campaignMetrics[key]) {
    campaignMetrics[key] = {
      campaign: key,
      platform: d.Platform,
      totalSpend: 0,
      totalConversions: 0,
      totalClicks: 0,
      totalImpressions: 0,
    };
  }
  const m = campaignMetrics[key];
  m.totalSpend += d['Spend ZAR'] || 0;
  m.totalConversions += d.Conversions || 0;
  m.totalClicks += d.Clicks || 0;
  m.totalImpressions += d.Impressions || 0;
}

const ranked = Object.values(campaignMetrics)
  .map(m => ({
    ...m,
    roas: m.totalSpend > 0 ? (m.totalConversions * 100) / m.totalSpend : 0,
    ctr: m.totalImpressions > 0 ? m.totalClicks / m.totalImpressions : 0,
  }))
  .filter(m => m.roas > 2.0 || m.ctr > 0.02)
  .sort((a, b) => b.roas - a.roas)
  .slice(0, 5);

return ranked.length > 0
  ? ranked.map(m => ({json: m}))
  : [{json: {skip: true, reason: 'No top performers found'}}];
"""

ADS06_PREPARE_AI_INPUT_CODE = r"""
// Aggregate top performers + creatives into a single item for AI
const topPerformers = $('Filter Valid').all().map(i => i.json);
const creatives = $('Read Original Creatives').all().map(i => i.json);

return [{json: {
  topPerformers: topPerformers.slice(0, 5),
  creatives: creatives.slice(0, 10),
}}];
"""

ADS06_GENERATE_VARIANTS_CODE = r"""
// Parse AI variant suggestions and create new creative records
const aiResp = $('AI Variant Generator').first().json;
const content = aiResp.choices?.[0]?.message?.content || '[]';
const creatives = $('Prepare AI Input').first().json.creatives || [];

let variants;
try {
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  variants = JSON.parse(cleaned);
} catch (e) {
  return [{json: {skip: true, reason: 'Failed to parse AI response'}}];
}

if (!Array.isArray(variants)) variants = [variants];

const now = new Date().toISOString().split('T')[0];
const results = [];

for (let i = 0; i < variants.length; i++) {
  const v = variants[i];
  const orig = creatives[0] || {};

  results.push({json: {
    'Creative Name': `${orig['Creative Name'] || 'Recycled'} - Variant ${now} #${i + 1}`,
    'Campaign Name': v.campaign_name || orig['Campaign Name'] || '',
    'Platform': v.platform || orig.Platform || 'google_ads',
    'Ad Format': v.ad_format || orig['Ad Format'] || 'RSA',
    'Status': 'Draft',
    'Headlines': JSON.stringify(v.headlines || []),
    'Descriptions': JSON.stringify(v.descriptions || []),
    'Primary Text': v.primary_text || '',
    'CTA': v.cta || 'Learn_More',
    'Parent Creative ID': orig['Creative Name'] || '',
    'Created At': now,
  }});
}

return results.length > 0 ? results : [{json: {skip: true, reason: 'No variants generated'}}];
"""

ADS06_VARIANT_PROMPT = """You are the AVM Creative Recycler for AnyVision Media.

TOP PERFORMING CAMPAIGNS:
{top_performers}

ORIGINAL CREATIVES:
{original_creatives}

Generate 2-3 new ad creative variants based on the winning patterns. For each variant:
- Keep the winning messaging angle but change the specific wording
- Try different hooks, CTAs, or emotional triggers
- Maintain platform-specific format requirements
- Reference the original creative it's based on

Output ONLY a JSON array (no markdown, no explanation) with fields: campaign_name, platform, ad_format, headlines[], descriptions[], primary_text, cta"""


def build_ads06_nodes():
    """Build ADS-06: Creative Recycler nodes."""
    nodes = []

    # 1. Schedule: Wednesday 10:00 SAST (08:00 UTC)
    nodes.append(build_schedule_trigger("Schedule Trigger", "0 8 * * 3", [250, 300]))

    # 2. Read performance data (last 14 days)
    nodes.append(build_airtable_search(
        "Read Performance", MARKETING_BASE_ID, TABLE_PERFORMANCE,
        "=IS_AFTER({Date}, DATEADD(TODAY(), -14, 'days'))", [500, 300],
    ))

    # 3. Find top performers
    nodes.append(build_code_node("Find Top Performers", ADS06_FIND_TOP_PERFORMERS_CODE, [750, 300]))

    # 4. Filter valid (skip check)
    nodes.append(build_code_node("Filter Valid", ADS04_FILTER_SKIP_CODE, [1000, 300]))

    # 5. Read original creatives for top campaigns
    nodes.append(build_airtable_search(
        "Read Original Creatives", MARKETING_BASE_ID, TABLE_CREATIVES,
        "=OR({Status}='Active',{Status}='Approved')", [1250, 300],
    ))

    # 6. Prepare AI Input — aggregate top performers + creatives into single item
    nodes.append(build_code_node("Prepare AI Input", ADS06_PREPARE_AI_INPUT_CODE, [1500, 300]))

    # 7. AI Variant Generator — runs once with aggregated data
    prompt = ADS06_VARIANT_PROMPT.replace(
        "{top_performers}", "={{JSON.stringify($json.topPerformers)}}"
    ).replace("{original_creatives}", "={{JSON.stringify($json.creatives)}}")
    node = build_openrouter_request(
        "AI Variant Generator", prompt, "JSON.stringify($json)", [1750, 300], max_tokens=2000,
    )
    node["continueOnFail"] = True
    nodes.append(node)

    # 8. Parse variants
    nodes.append(build_code_node("Parse Variants", ADS06_GENERATE_VARIANTS_CODE, [2000, 300]))

    # 9. Filter out skip items before Airtable write
    nodes.append(build_code_node("Filter Variants", ADS04_FILTER_SKIP_CODE, [2250, 300]))

    # 10. Write new creatives
    node = build_airtable_create(
        "Write New Creatives", MARKETING_BASE_ID, TABLE_CREATIVES, [2500, 300],
    )
    node["continueOnFail"] = True
    nodes.append(node)

    # 11. Email summary
    nodes.append(build_gmail_send(
        "Email Recycler Summary", ALERT_EMAIL,
        "AVM Ads - Creative Recycler: New Variants Created",
        "={{\"<h2>Creative Recycler Results</h2><pre>\" + JSON.stringify($json, null, 2) + \"</pre>\"}}",
        [2750, 300],
    ))

    return nodes


def build_ads06_connections(nodes):
    """Build ADS-06 connections."""
    return {
        "Schedule Trigger": {"main": [[
            {"node": "Read Performance", "type": "main", "index": 0},
        ]]},
        "Read Performance": {"main": [[
            {"node": "Find Top Performers", "type": "main", "index": 0},
        ]]},
        "Find Top Performers": {"main": [[
            {"node": "Filter Valid", "type": "main", "index": 0},
        ]]},
        "Filter Valid": {"main": [[
            {"node": "Read Original Creatives", "type": "main", "index": 0},
        ]]},
        "Read Original Creatives": {"main": [[
            {"node": "Prepare AI Input", "type": "main", "index": 0},
        ]]},
        "Prepare AI Input": {"main": [[
            {"node": "AI Variant Generator", "type": "main", "index": 0},
        ]]},
        "AI Variant Generator": {"main": [[
            {"node": "Parse Variants", "type": "main", "index": 0},
        ]]},
        "Parse Variants": {"main": [[
            {"node": "Filter Variants", "type": "main", "index": 0},
        ]]},
        "Filter Variants": {"main": [[
            {"node": "Write New Creatives", "type": "main", "index": 0},
        ]]},
        "Write New Creatives": {"main": [[
            {"node": "Email Recycler Summary", "type": "main", "index": 0},
        ]]},
    }


# ======================================================================
# ADS-07: CROSS-CHANNEL ATTRIBUTION
# ======================================================================

ADS07_COMPUTE_ATTRIBUTION_CODE = r"""
// Compute cross-channel attribution: paid + organic data
const adPerf = $('Read Ad Performance').all();
const orgPerf = $('Read Organic Performance').all();

const channels = {};

// Aggregate paid performance
for (const item of adPerf) {
  const d = item.json;
  if (d.skip) continue;
  const key = d.Platform || 'unknown';
  if (!channels[key]) {
    channels[key] = {channel: key, type: 'paid', spend: 0, conversions: 0, clicks: 0, impressions: 0};
  }
  channels[key].spend += d['Spend ZAR'] || 0;
  channels[key].conversions += d.Conversions || 0;
  channels[key].clicks += d.Clicks || 0;
  channels[key].impressions += d.Impressions || 0;
}

// Aggregate organic performance
for (const item of orgPerf) {
  const d = item.json;
  const key = 'organic_' + (d.Platform || d.platform || 'content');
  if (!channels[key]) {
    channels[key] = {channel: key, type: 'organic', spend: 0, conversions: 0, clicks: 0, impressions: 0};
  }
  channels[key].clicks += d.Clicks || d.clicks || d.Engagement || 0;
  channels[key].impressions += d.Impressions || d.impressions || d.Reach || 0;
}

// Compute metrics
const totalSpend = Object.values(channels).reduce((sum, c) => sum + c.spend, 0);
const totalConversions = Object.values(channels).reduce((sum, c) => sum + c.conversions, 0);
const blendedCAC = totalConversions > 0 ? totalSpend / totalConversions : 0;

const results = Object.values(channels).map(c => ({
  channel: c.channel,
  type: c.type,
  spend: parseFloat(c.spend.toFixed(2)),
  conversions: c.conversions,
  clicks: c.clicks,
  impressions: c.impressions,
  cpa: c.conversions > 0 ? parseFloat((c.spend / c.conversions).toFixed(2)) : 0,
  roas: c.spend > 0 ? parseFloat(((c.conversions * 100) / c.spend).toFixed(2)) : 0,
  spendShare: totalSpend > 0 ? parseFloat((c.spend / totalSpend * 100).toFixed(1)) : 0,
}));

return [{json: {
  channels: results,
  totalSpend: parseFloat(totalSpend.toFixed(2)),
  totalConversions: totalConversions,
  blendedCAC: parseFloat(blendedCAC.toFixed(2)),
  reportDate: new Date().toISOString().split('T')[0],
}}];
"""

ADS07_ATTRIBUTION_PROMPT = """You are the AVM Attribution Analyst for AnyVision Media.

CROSS-CHANNEL DATA (last 7 days):
{attribution_data}

Analyze the data and provide:
1. CHANNEL EFFICIENCY: Rank channels by ROI (both paid and organic)
2. BUDGET REALLOCATION: Should budget shift between channels? Be specific.
3. ORGANIC-PAID SYNERGY: Are organic and paid reinforcing each other?
4. CAC ANALYSIS: Is the blended customer acquisition cost sustainable?
5. RECOMMENDED ACTIONS: 2-3 specific budget or strategy changes

Output as JSON:
{
  "channel_rankings": [{"channel": "", "efficiency_score": 0, "recommendation": ""}],
  "budget_reallocation": {"from": "", "to": "", "amount_zar": 0, "reasoning": ""},
  "synergy_insights": "",
  "cac_assessment": "",
  "actions": [""]
}"""


def build_ads07_nodes():
    """Build ADS-07: Cross-Channel Attribution nodes."""
    nodes = []

    # 1. Schedule: Daily 06:00 SAST (04:00 UTC)
    nodes.append(build_schedule_trigger("Schedule Trigger", "0 4 * * *", [250, 300]))

    # 2. Read Ad Performance (last 7 days)
    ad_perf_node = build_airtable_search(
        "Read Ad Performance", MARKETING_BASE_ID, TABLE_PERFORMANCE,
        "=IS_AFTER({Date}, DATEADD(TODAY(), -7, 'days'))", [500, 200],
    )
    ad_perf_node["alwaysOutputData"] = True
    nodes.append(ad_perf_node)

    # 3. Read Organic Performance (Distribution Log)
    org_perf_node = build_airtable_search(
        "Read Organic Performance", MARKETING_BASE_ID, TABLE_DISTRIBUTION_LOG,
        "=IS_AFTER({Published At}, DATEADD(TODAY(), -7, 'days'))", [500, 400],
    )
    org_perf_node["alwaysOutputData"] = True
    nodes.append(org_perf_node)

    # 4. Merge paid + organic data before attribution computation
    nodes.append(build_merge_node("Merge Paid Organic", [750, 300]))

    # 5. Compute Attribution
    nodes.append(build_code_node("Compute Attribution", ADS07_COMPUTE_ATTRIBUTION_CODE, [1000, 300]))

    # 6. AI Attribution Analyst
    prompt = ADS07_ATTRIBUTION_PROMPT.replace(
        "{attribution_data}", "{{JSON.stringify($json)}}"
    )
    node = build_openrouter_request(
        "AI Attribution Analyst", prompt, "JSON.stringify($json)", [1250, 300], max_tokens=1500,
    )
    node["continueOnFail"] = True
    nodes.append(node)

    # 6a. Format AI response into Orchestrator Events fields
    # Event Type options: health_check, alert, escalation, cross_dept, kpi_update, decision, lead_qualified, invoice_created, content_published, support_ticket
    # Priority options (Airtable select): P1, P2, P3, P4
    # Status options (Airtable select): Pending, Processing, Completed, Failed
    nodes.append(build_code_node("Format Attribution Data", r"""
// Transform AI Attribution Analyst response into Orchestrator Events fields
const aiResp = $input.first().json;
const content = aiResp.choices?.[0]?.message?.content || JSON.stringify(aiResp);

return [{json: {
  'Event Type': 'kpi_update',
  'Source Agent': 'ADS-07',
  'Priority': 'P4',
  'Status': 'Completed',
  'Payload': typeof content === 'string' ? content : JSON.stringify(content),
  'Created At': new Date().toISOString(),
}}];
""", [1500, 300]))

    # 7b. Write attribution data to Operations Events table (defineBelow + continueOnFail so email still sends)
    nodes.append({
        "id": uid(),
        "name": "Write Attribution",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1750, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "continueOnFail": True,
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": ORCH_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_ORCH_EVENTS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Event Type": "={{ $json['Event Type'] }}",
                    "Source Agent": "={{ $json['Source Agent'] }}",
                    "Priority": "={{ $json['Priority'] }}",
                    "Status": "={{ $json['Status'] }}",
                    "Payload": "={{ $json['Payload'] }}",
                    "Created At": "={{ $json['Created At'] }}",
                },
            },
            "options": {},
        },
    })

    # 8. Email attribution report
    nodes.append(build_gmail_send(
        "Email Attribution Report", ALERT_EMAIL,
        "AVM Ads - Daily Attribution Report",
        "={{\"<h2>Cross-Channel Attribution</h2><pre>\" + JSON.stringify($json, null, 2) + \"</pre>\"}}",
        [2000, 300],
    ))

    return nodes


def build_ads07_connections(nodes):
    """Build ADS-07 connections."""
    return {
        "Schedule Trigger": {"main": [[
            {"node": "Read Ad Performance", "type": "main", "index": 0},
            {"node": "Read Organic Performance", "type": "main", "index": 0},
        ]]},
        "Read Ad Performance": {"main": [[
            {"node": "Merge Paid Organic", "type": "main", "index": 0},
        ]]},
        "Read Organic Performance": {"main": [[
            {"node": "Merge Paid Organic", "type": "main", "index": 1},
        ]]},
        "Merge Paid Organic": {"main": [[
            {"node": "Compute Attribution", "type": "main", "index": 0},
        ]]},
        "Compute Attribution": {"main": [[
            {"node": "AI Attribution Analyst", "type": "main", "index": 0},
        ]]},
        "AI Attribution Analyst": {"main": [[
            {"node": "Format Attribution Data", "type": "main", "index": 0},
        ]]},
        "Format Attribution Data": {"main": [[
            {"node": "Write Attribution", "type": "main", "index": 0},
        ]]},
        "Write Attribution": {"main": [[
            {"node": "Email Attribution Report", "type": "main", "index": 0},
        ]]},
    }


# ======================================================================
# WORKFLOW ASSEMBLY
# ======================================================================

WORKFLOW_BUILDERS = {
    "ads01": {
        "name": "AVM Ads: Strategy Generator",
        "build_nodes": build_ads01_nodes,
        "build_connections": build_ads01_connections,
        "filename": "ads01_strategy_generator.json",
        "tags": ["ads-dept", "strategy", "phase-2"],
    },
    "ads02": {
        "name": "AVM Ads: Copy & Creative Generator",
        "build_nodes": build_ads02_nodes,
        "build_connections": build_ads02_connections,
        "filename": "ads02_copy_creative_generator.json",
        "tags": ["ads-dept", "creative", "phase-2"],
    },
    "ads03": {
        "name": "AVM Ads: Campaign Builder",
        "build_nodes": build_ads03_nodes,
        "build_connections": build_ads03_connections,
        "filename": "ads03_campaign_builder.json",
        "tags": ["ads-dept", "publishing", "phase-3"],
    },
    "ads04": {
        "name": "AVM Ads: Performance Monitor",
        "build_nodes": build_ads04_nodes,
        "build_connections": build_ads04_connections,
        "filename": "ads04_performance_monitor.json",
        "tags": ["ads-dept", "monitoring", "phase-1"],
    },
    "ads05": {
        "name": "AVM Ads: Optimization Engine",
        "build_nodes": build_ads05_nodes,
        "build_connections": build_ads05_connections,
        "filename": "ads05_optimization_engine.json",
        "tags": ["ads-dept", "optimization", "phase-2"],
    },
    "ads06": {
        "name": "AVM Ads: Creative Recycler",
        "build_nodes": build_ads06_nodes,
        "build_connections": build_ads06_connections,
        "filename": "ads06_creative_recycler.json",
        "tags": ["ads-dept", "creative", "phase-3"],
    },
    "ads07": {
        "name": "AVM Ads: Attribution Engine",
        "build_nodes": build_ads07_nodes,
        "build_connections": build_ads07_connections,
        "filename": "ads07_attribution.json",
        "tags": ["ads-dept", "attribution", "phase-2"],
    },
    "ads08": {
        "name": "AVM Ads: Reporting Dashboard",
        "build_nodes": build_ads08_nodes,
        "build_connections": build_ads08_connections,
        "filename": "ads08_reporting_dashboard.json",
        "tags": ["ads-dept", "reporting", "phase-1"],
    },
}


def build_workflow(key):
    """Build a complete workflow JSON."""
    spec = WORKFLOW_BUILDERS[key]
    nodes = spec["build_nodes"]()
    connections = spec["build_connections"](nodes)

    return {
        "name": spec["name"],
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
            "errorWorkflow": os.getenv("ADS_ERROR_WORKFLOW_ID", "L915QaaJuo6au7Oe"),
        },
    }


def save_workflow(key, workflow_data):
    """Save workflow JSON to file."""
    spec = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "ads-dept"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / spec["filename"]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow_data, f, indent=2, ensure_ascii=False)

    node_count = len(workflow_data["nodes"])
    print(f"  + {spec['name']:<40} -> {output_path.name} ({node_count} nodes)")
    return output_path


def get_n8n_client():
    """Create N8nClient with credentials from env."""
    try:
        from tools.n8n_client import N8nClient
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent))
        from n8n_client import N8nClient

    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    api_key = os.getenv("N8N_API_KEY", "")
    if not api_key:
        raise ValueError("N8N_API_KEY not set in .env")
    return N8nClient(base_url=base_url, api_key=api_key)


def deploy_workflow(workflow_data):
    """Deploy workflow to n8n via API."""
    client = get_n8n_client()
    resp = client.create_workflow(workflow_data)
    return resp


def activate_workflow(workflow_id):
    """Activate a workflow by ID."""
    client = get_n8n_client()
    resp = client.activate_workflow(workflow_id)
    return resp


# ======================================================================
# CLI
# ======================================================================

def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python tools/deploy_ads_dept.py <build|deploy|activate> [workflow_key]")
        print()
        print("Available workflows:")
        for key, spec in WORKFLOW_BUILDERS.items():
            print(f"  {key:<10} {spec['name']}")
        sys.exit(1)

    action = args[0]
    target = args[1] if len(args) > 1 else None

    keys = [target] if target and target in WORKFLOW_BUILDERS else list(WORKFLOW_BUILDERS.keys())

    if target and target not in WORKFLOW_BUILDERS:
        print(f"ERROR: Unknown workflow '{target}'. Available: {', '.join(WORKFLOW_BUILDERS.keys())}")
        sys.exit(1)

    print("=" * 60)
    print("AVM PAID ADVERTISING - WORKFLOW BUILDER")
    print("=" * 60)
    print()
    print(f"Action: {action}")
    print(f"Workflows: {', '.join(keys)}")
    print(f"Marketing Base: {MARKETING_BASE_ID}")
    print()

    # Build
    print("Building workflows...")
    print("-" * 40)
    built = {}
    for key in keys:
        workflow = build_workflow(key)
        path = save_workflow(key, workflow)
        built[key] = workflow
    print()

    if action == "build":
        print("Build complete. Run 'deploy' to push to n8n.")
        return

    # Deploy
    if action in ("deploy", "activate"):
        print("Deploying to n8n (inactive)...")
        print("-" * 40)
        deployed_ids = {}
        for key, workflow in built.items():
            try:
                resp = deploy_workflow(workflow)
                wf_id = resp.get("id", "unknown")
                deployed_ids[key] = wf_id
                print(f"  + {WORKFLOW_BUILDERS[key]['name']:<40} -> {wf_id}")
            except Exception as e:
                print(f"  - {WORKFLOW_BUILDERS[key]['name']:<40} FAILED: {e}")
        print()

        if action == "activate" and deployed_ids:
            print("Activating workflows...")
            print("-" * 40)
            for key, wf_id in deployed_ids.items():
                try:
                    activate_workflow(wf_id)
                    print(f"  + {WORKFLOW_BUILDERS[key]['name']:<40} ACTIVE")
                except Exception as e:
                    print(f"  - {WORKFLOW_BUILDERS[key]['name']:<40} FAILED: {e}")
            print()

        # Save deployed IDs
        if deployed_ids:
            output_dir = Path(__file__).parent.parent / ".tmp"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "ads_workflow_ids.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({
                    "deployed": deployed_ids,
                    "deployed_at": datetime.now().isoformat(),
                }, f, indent=2)
            print(f"Workflow IDs saved to: {output_path}")

    print()
    print("Next steps:")
    print("  1. Verify workflows in n8n UI")
    print("  2. Set up Google Ads + Meta Ads credentials in n8n")
    print("  3. Manual trigger ADS-04 to test metric collection")
    print("  4. Check Ad_Performance Airtable table for data")


if __name__ == "__main__":
    main()
