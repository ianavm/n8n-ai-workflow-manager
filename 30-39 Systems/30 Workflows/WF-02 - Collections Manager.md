---
type: workflow
wf_id: WF-02
department: accounting
n8n_id: 
schedule: "Daily"
active: true
dependencies: ["QuickBooks OAuth", "Airtable", "Gmail"]
owner: ian
last_audit: 2026-04-12
tags: [workflow, accounting]
---

# WF-02 - Collections Manager

## Purpose
Manages overdue invoice collections. Sends payment reminders, escalates past-due accounts.

## Trigger
Scheduled (daily)

## Key Nodes
- QuickBooks overdue invoice query
- Email reminder sequence (HTML templates)
- Escalation logic

## Dependencies
- QuickBooks OAuth credential
- Gmail OAuth credential
- HTML templates in `templates/`

## Related
- SOP: [[workflows/accounting-dept/airtable_schema|Accounting Airtable Schema]]
- Deploy script: `tools/deploy_acct_v2_dept.py`
- Department: [[20 Accounting/]]
- Previous: [[WF-01 - Invoice Generator]]
- Next: [[WF-03 - Payment Reconciliation]]

## Notes
- Part of the full AP/AR pipeline: invoicing -> collections -> reconciliation -> bills -> month-end -> audit -> exceptions
