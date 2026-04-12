---
type: workflow
wf_id: ADS-01
department: paid-ads
n8n_id: 
schedule: "Daily"
active: true
dependencies: ["Google Ads API", "Meta Ads API", "Airtable"]
owner: ian
last_audit: 2026-04-12
tags: [workflow, ads]
---

# ADS-01 - Orchestrator

## Purpose
Main orchestrator for the paid advertising department. Coordinates all 9 ADS workflows, monitors budget caps, and triggers downstream workflows.

## Trigger
Scheduled (daily)

## Key Nodes
- Budget cap check (R666/day, R5,000/week, R20,000/month)
- Downstream workflow triggers (ADS-02 through ADS-08)
- Error handler + SHM integration

## Dependencies
- Google Ads API (account ID 6925797193 - currently CUSTOMER_NOT_ENABLED)
- Meta Ads API
- Airtable ads base

## Related
- SOP: [[workflows/ads-dept/airtable_schema|Ads Airtable Schema]]
- Deploy script: `tools/deploy_ads_dept.py`
- Department: [[23 Paid Ads/]]
- Budget monitor: [[ADS-02 - Budget Monitor]]
- Budget enforcer: workflow ID `YR6LFkWO9rnNceOp`

## Notes
- 9/10 workflows active. ADS-03 inactive (Google Ads CUSTOMER_NOT_ENABLED)
- Safety caps updated 2026-04-08 for launch: R666/day, R5,000/week, R20,000/month
- Full revision 2026-04-09: Fixed autoMap->defineBelow (ADS-05/07/08), empty guard (ADS-02), SHM credential+expressions
