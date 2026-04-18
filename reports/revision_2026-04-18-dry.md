# Revision Report — 2026-04-18 (DRY-RUN)

**Scope:** all active departments  
**Autonomy tier:** 3 (Semi-autonomous)  
**Total findings:** 612  
**Applied:** 0  
**Verified:** 0  

## By band

| Band | Count |
|---|---|
| APPLY | 115 |
| STAGE | 0 |
| PROPOSE | 497 |
| ESCALATE | 0 |

## By phase

| Phase | Count |
|---|---|
| Health | 0 |
| Drift | 14 |
| Quality | 483 |
| SOP | 115 |

## Top 20 most-urgent findings

| Phase | Dept | Band | Risk | Confidence | Summary |
|---|---|---|---|---|---|
| drift | accounting-v2 | PROPOSE | HIGH | 0.59 | Workflow JSON has no deploy script: wf01_master_data.json |
| drift | accounting-v2 | PROPOSE | HIGH | 0.59 | Workflow JSON has no deploy script: wf02_invoice_creation.json |
| drift | accounting-v2 | PROPOSE | HIGH | 0.59 | Workflow JSON has no deploy script: wf03_invoice_sending.json |
| drift | accounting-v2 | PROPOSE | HIGH | 0.59 | Workflow JSON has no deploy script: wf04_collections.json |
| drift | accounting-v2 | PROPOSE | HIGH | 0.59 | Workflow JSON has no deploy script: wf05_payments.json |
| drift | accounting-v2 | PROPOSE | HIGH | 0.59 | Workflow JSON has no deploy script: wf06_bill_intake.json |
| drift | accounting-v2 | PROPOSE | HIGH | 0.59 | Workflow JSON has no deploy script: wf07_supplier_payments.json |
| drift | accounting-v2 | PROPOSE | HIGH | 0.59 | Workflow JSON has no deploy script: wf08_approvals.json |
| drift | accounting-v2 | PROPOSE | HIGH | 0.59 | Workflow JSON has no deploy script: wf09_reporting.json |
| drift | accounting-v2 | PROPOSE | HIGH | 0.59 | Workflow JSON has no deploy script: wf10_exceptions.json |
| drift | client-projects | PROPOSE | HIGH | 0.59 | Workflow JSON has no deploy script: order_to_invoice_approval.json |
| drift | client-projects | PROPOSE | HIGH | 0.59 | Workflow JSON has no deploy script: order_to_invoice_intake.json |
| drift | email-mgmt | PROPOSE | HIGH | 0.59 | Workflow JSON has no deploy script: business_email_mgmt_outlook.json |
| drift | marketing-bridge | PROPOSE | HIGH | 0.59 | Workflow JSON has no deploy script: mkt_bridge_portal_action.json |
| quality | re-operations | PROPOSE | HIGH | 0.56 | AP-03 (INFO) at deploy_re_operations.py:61 |
| quality | re-operations | PROPOSE | HIGH | 0.56 | AP-03 (INFO) at deploy_re_operations.py:90 |
| quality | re-operations | PROPOSE | HIGH | 0.56 | AP-03 (INFO) at deploy_re_operations.py:93 |
| quality | re-operations | PROPOSE | HIGH | 0.56 | AP-08 (MEDIUM) at deploy_re_operations.py:859 |
| quality | re-operations | PROPOSE | HIGH | 0.56 | AP-08 (MEDIUM) at deploy_re_operations.py:937 |
| quality | re-operations | PROPOSE | HIGH | 0.56 | AP-08 (MEDIUM) at deploy_re_operations.py:998 |

## Applied fixes

(none — dry-run or nothing applyable)

## Next actions

- Review STAGE findings in Airtable Escalation_Queue.
- PROPOSE / ESCALATE findings need human triage before any tier promotion.
- Re-run with `--apply` once dry-run looks clean.

---
Manifest: `C:\Users\ianim\OneDrive\Desktop\Agentic Workflows\Workflow Manager\.tmp\revision\2026-04-18\manifest.jsonl`
Baseline snapshot: `C:\Users\ianim\OneDrive\Desktop\Agentic Workflows\Workflow Manager\.tmp\revision\2026-04-18\baseline`