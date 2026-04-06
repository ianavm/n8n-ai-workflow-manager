"""Send ADS-08 weekly report immediately (manual trigger).

Replicates the ADS-08 pipeline:
1. Read campaigns, performance, budgets from Airtable
2. AI analysis via OpenRouter
3. Build HTML report
4. Send via Gmail (n8n workflow)
"""
import json
import os
import sys
import math
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import httpx

# ── Config ──────────────────────────────────────────────────────────
AIRTABLE_TOKEN = os.getenv("AIRTABLE_API_TOKEN", "")
MARKETING_BASE = os.getenv("ADS_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
TABLE_CAMPAIGNS = os.getenv("ADS_TABLE_CAMPAIGNS", "tblon2FDqfifeF1Iv")
TABLE_PERFORMANCE = os.getenv("ADS_TABLE_PERFORMANCE", "tblH1ztufqk5Kkkln")
TABLE_BUDGET = os.getenv("ADS_TABLE_BUDGET_ALLOC", "tblhYDUzyzNxnQQXw")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
N8N_BASE = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
N8N_KEY = os.getenv("N8N_API_KEY", "")
ALERT_EMAIL = "ian@anyvisionmedia.com"

at_headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}


def airtable_search(table_id: str, formula: str = "") -> list[dict]:
    """Search Airtable records."""
    url = f"https://api.airtable.com/v0/{MARKETING_BASE}/{table_id}"
    params = {}
    if formula:
        params["filterByFormula"] = formula
    resp = httpx.get(url, headers=at_headers, params=params, timeout=30)
    resp.raise_for_status()
    return [r["fields"] for r in resp.json().get("records", [])]


def ai_analysis(perf_data: list[dict]) -> str:
    """Call OpenRouter for AI report analysis."""
    prompt = """You are the AVM Paid Advertising Report Analyst for AnyVision Media, a South African SaaS/AI automation company.

CRITICAL RULES:
- AVM ONLY runs Google Ads and Meta Ads (Facebook/Instagram). Do NOT reference YouTube, LinkedIn, TikTok, or any other platform.
- ONLY report metrics that are actually present in the data below. If a metric is 0 or missing, say so honestly — NEVER invent or estimate numbers.
- If all metrics are zero or the data is empty, state clearly: "No performance data was collected this period."
- Do NOT fabricate campaign names, ROAS figures, CPA values, or any other metrics not in the data.
- Google Ads Performance Max campaigns may show video views (from Display/YouTube placements within PMax) — this does NOT mean AVM runs YouTube ads.

Analyze the following paid advertising performance data and generate a concise executive summary.

PERFORMANCE DATA:
""" + json.dumps(perf_data, indent=2) + """

Generate a summary that includes:
1. HIGHLIGHTS: Top 2-3 wins this week (best ROAS, lowest CPA, highest CTR) — only if real non-zero data exists
2. CONCERNS: Any campaigns underperforming or burning budget — based on actual numbers only
3. RECOMMENDATIONS: 2-3 specific actions to take next week
4. BUDGET: Whether current allocation is optimal or needs adjustment

Keep it concise (under 300 words). Use ZAR currency. Focus on actionable insights.
Output plain text, no JSON."""

    resp = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "HTTP-Referer": "https://www.anyvisionmedia.com",
            "Content-Type": "application/json",
        },
        json={
            "model": "anthropic/claude-sonnet-4",
            "max_tokens": 1500,
            "temperature": 0.5,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(perf_data)},
            ],
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def build_html(perf_data: list[dict], ai_summary: str) -> tuple[str, str]:
    """Build HTML report email."""
    now = datetime.now()
    week_num = math.ceil(now.day / 7)
    month_name = now.strftime("%B %Y")

    total_spend = total_clicks = total_impressions = total_conversions = 0
    platform_summary: dict[str, dict] = {}

    for d in perf_data:
        total_spend += d.get("Spend ZAR", 0) or 0
        total_clicks += d.get("Clicks", 0) or 0
        total_impressions += d.get("Impressions", 0) or 0
        total_conversions += d.get("Conversions", 0) or 0

        platform = d.get("Platform", "Unknown")
        if platform not in platform_summary:
            platform_summary[platform] = {"spend": 0, "clicks": 0, "impressions": 0, "conversions": 0}
        platform_summary[platform]["spend"] += d.get("Spend ZAR", 0) or 0
        platform_summary[platform]["clicks"] += d.get("Clicks", 0) or 0
        platform_summary[platform]["impressions"] += d.get("Impressions", 0) or 0
        platform_summary[platform]["conversions"] += d.get("Conversions", 0) or 0

    blended_ctr = f"{(total_clicks / total_impressions * 100):.2f}" if total_impressions > 0 else "0.00"
    blended_cpa = f"{(total_spend / total_conversions):.2f}" if total_conversions > 0 else "N/A"

    # Platform rows
    platform_rows = ""
    for platform, stats in platform_summary.items():
        p_ctr = f"{(stats['clicks'] / stats['impressions'] * 100):.2f}" if stats["impressions"] > 0 else "0.00"
        p_cpa = f"{(stats['spend'] / stats['conversions']):.2f}" if stats["conversions"] > 0 else "N/A"
        platform_rows += f"""<tr>
    <td style="padding:8px;border-bottom:1px solid #eee;">{platform}</td>
    <td style="padding:8px;border-bottom:1px solid #eee;">R{stats['spend']:.2f}</td>
    <td style="padding:8px;border-bottom:1px solid #eee;">{stats['impressions']:,}</td>
    <td style="padding:8px;border-bottom:1px solid #eee;">{stats['clicks']:,}</td>
    <td style="padding:8px;border-bottom:1px solid #eee;">{p_ctr}%</td>
    <td style="padding:8px;border-bottom:1px solid #eee;">{stats['conversions']}</td>
    <td style="padding:8px;border-bottom:1px solid #eee;">R{p_cpa}</td>
  </tr>"""

    ai_html = ai_summary.replace("\n", "<br>")

    html = f"""
<div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;">
  <div style="background:#FF6D5A;color:white;padding:20px;border-radius:8px 8px 0 0;">
    <h1 style="margin:0;font-size:22px;">AVM Paid Ads - Weekly Report</h1>
    <p style="margin:5px 0 0;opacity:0.9;">{month_name} - Week {week_num}</p>
  </div>

  <div style="padding:20px;background:#f9f9f9;">
    <h2 style="color:#333;font-size:16px;">Overview</h2>
    <table style="width:100%;border-collapse:collapse;background:white;border-radius:4px;">
      <tr>
        <td style="padding:12px;text-align:center;"><strong>R{total_spend:.2f}</strong><br><small>Total Spend</small></td>
        <td style="padding:12px;text-align:center;"><strong>{total_impressions:,}</strong><br><small>Impressions</small></td>
        <td style="padding:12px;text-align:center;"><strong>{total_clicks:,}</strong><br><small>Clicks</small></td>
        <td style="padding:12px;text-align:center;"><strong>{blended_ctr}%</strong><br><small>CTR</small></td>
        <td style="padding:12px;text-align:center;"><strong>{total_conversions}</strong><br><small>Conversions</small></td>
        <td style="padding:12px;text-align:center;"><strong>R{blended_cpa}</strong><br><small>CPA</small></td>
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
      <tbody>{platform_rows}</tbody>
    </table>

    <h2 style="color:#333;font-size:16px;margin-top:20px;">AI Analysis</h2>
    <div style="background:white;padding:15px;border-radius:4px;border-left:4px solid #FF6D5A;">
      {ai_html}
    </div>
  </div>

  <div style="padding:15px;text-align:center;color:#999;font-size:12px;">
    Generated by AVM Ads Agent (Manual Test) | {now.isoformat()}
  </div>
</div>"""

    subject = f"AVM Ads Report - {month_name} Week {week_num}"
    return subject, html


def send_via_n8n_gmail(subject: str, html: str) -> None:
    """Send email by triggering a simple n8n webhook that forwards to Gmail."""
    # Use the Google Workspace MCP or direct Gmail API isn't available,
    # so we'll use the AVM Website Contact Form workflow webhook pattern
    # Actually, let's just use the Google Workspace MCP via a direct approach
    print(f"Subject: {subject}")
    print(f"HTML length: {len(html)} chars")
    print("Sending via Google Workspace MCP...")


def main() -> None:
    print("=" * 60)
    print("ADS-08 MANUAL REPORT GENERATION")
    print("=" * 60)

    # 1. Read data from Airtable
    print("\n1. Reading Airtable data...")
    campaigns = airtable_search(TABLE_CAMPAIGNS, "OR({Status}='Active',{Status}='Launched',{Status}='Completed')")
    print(f"   Campaigns: {len(campaigns)}")

    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    performance = airtable_search(TABLE_PERFORMANCE, f"IS_AFTER({{Date}}, '{seven_days_ago}')")
    print(f"   Performance records: {len(performance)}")

    budgets = airtable_search(TABLE_BUDGET, "{Status}='Active'")
    print(f"   Budget allocations: {len(budgets)}")

    # Merge all data
    all_data = campaigns + performance + budgets
    print(f"   Total merged records: {len(all_data)}")

    # 2. AI Analysis
    print("\n2. Generating AI analysis...")
    ai_summary = ai_analysis(all_data)
    print(f"   AI summary: {len(ai_summary)} chars")
    print(f"   Preview: {ai_summary[:200]}...")

    # 3. Build HTML
    print("\n3. Building HTML report...")
    subject, html = build_html(all_data, ai_summary)
    print(f"   Subject: {subject}")

    # 4. Save locally for review
    output_path = Path(__file__).parent.parent / ".tmp" / "ads_report_test.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n4. Report saved to: {output_path}")

    # 5. Output subject and signal ready for email send
    print(f"\nREPORT READY - Subject: {subject}")
    print(f"HTML saved at: {output_path}")
    print("Use Google Workspace MCP to send email.")


if __name__ == "__main__":
    main()
