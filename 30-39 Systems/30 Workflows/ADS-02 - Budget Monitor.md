---
type: workflow
wf_id: ADS-02
department: paid-ads
n8n_id: 
schedule: "Every 4 hours"
active: true
dependencies: ["Google Ads API", "Airtable"]
owner: ian
last_audit: 2026-04-12
tags: [workflow, ads, budget]
---

# ADS-02 - Budget Monitor

## Purpose
Monitors daily/weekly/monthly ad spend against safety caps. Alerts via Telegram when thresholds are approached or exceeded.

## Trigger
Scheduled: every 4 hours

## Key Nodes
- Google Ads spend query
- Budget threshold comparison
- Telegram alert (@AVMCRMBot, chat 6311361442)

## Dependencies
- Google Ads API
- Airtable ads base

## Related
- Deploy script: `tools/deploy_ads_dept.py`
- Department: [[23 Paid Ads/]]
- Orchestrator: [[ADS-01 - Orchestrator]]
- Budget enforcer: workflow ID `YR6LFkWO9rnNceOp` (ADS-09)

## Notes
- Fixed 2026-04-10: empty guard for propagation, `? (?): FAILED` false alert resolved
- Real R672/day overspend detected but Google Ads 404 on mutate (manual pause needed)
- Safety caps: R666/day, R5,000/week, R20,000/month
