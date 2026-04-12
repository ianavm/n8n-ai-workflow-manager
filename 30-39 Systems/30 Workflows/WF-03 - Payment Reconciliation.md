---
type: workflow
wf_id: WF-03
department: accounting
n8n_id: 
schedule: "Daily"
active: true
dependencies: ["QuickBooks OAuth", "Airtable"]
owner: ian
last_audit: 2026-04-12
tags: [workflow, accounting]
---

# WF-03 - Payment Reconciliation

## Purpose
Reconciles incoming payments against outstanding invoices in QuickBooks. Flags mismatches for manual review.

## Trigger
Scheduled (daily)

## Key Nodes
- QuickBooks payment query
- Matching logic
- Airtable reconciliation log

## Dependencies
- QuickBooks OAuth credential
- Airtable accounting base

## Related
- SOP: [[workflows/accounting-dept/airtable_schema|Accounting Airtable Schema]]
- Deploy script: `tools/deploy_acct_v2_dept.py`
- Department: [[20 Accounting/]]
- Previous: [[WF-02 - Collections Manager]]

## Notes
- Email suppression system active (sub-workflow `foWQmkUEt79vGZXO`)
