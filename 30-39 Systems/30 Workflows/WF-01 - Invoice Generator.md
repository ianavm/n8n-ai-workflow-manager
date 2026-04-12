---
type: workflow
wf_id: WF-01
department: accounting
n8n_id: 
schedule: "Daily"
active: true
dependencies: ["QuickBooks OAuth", "Airtable", "Gmail"]
owner: ian
last_audit: 2026-04-12
tags: [workflow, accounting]
---

# WF-01 - Invoice Generator

## Purpose
Generates and sends invoices automatically via QuickBooks integration. Part of the full AP/AR accounting pipeline.

## Trigger
Scheduled (daily)

## Key Nodes
- QuickBooks invoice creation
- Gmail delivery with HTML template
- Airtable logging

## Dependencies
- QuickBooks OAuth credential
- Airtable accounting base
- Gmail OAuth credential
- HTML templates in `templates/`

## Related
- SOP: [[workflows/accounting-dept/airtable_schema|Accounting Airtable Schema]]
- Deploy script: `tools/deploy_acct_v2_dept.py`
- Department: [[20 Accounting/]]
- Next in pipeline: [[WF-02 - Collections Manager]]

## Notes
- South African context: ZAR currency, 15% VAT
- Auto-approve bills < R10,000; escalate > R50,000
