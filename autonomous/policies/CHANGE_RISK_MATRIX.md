# Change Risk Matrix — AVM Autonomous Workflow Engineer

> Cross-references: [AUTONOMY_POLICY.md](AUTONOMY_POLICY.md), [APPROVAL_MATRIX.md](APPROVAL_MATRIX.md), [OPERATING_MODEL.md](../docs/OPERATING_MODEL.md)

## Risk Levels

### LOW Risk — Fully Autonomous (Tier 3+)

Changes that are easily reversible, non-breaking, and don't touch business logic.

| Action | Confidence Required | Rollback Plan Required | Example |
|---|---|---|---|
| Add/update logging nodes | 70% | No | Add Set node to capture execution metadata in ADS-04 |
| Add/update documentation | 60% | No | Update SOP for SEO-WF05 Trend Discovery |
| Add error-handling (try/catch, continueOnFail) | 75% | No | Add `continueOnFail: true` to Google Ads API node |
| Tune retry counts or timeouts | 70% | No | Increase HTTP timeout from 30s to 60s on external API calls |
| Add test cases | 60% | No | Create regression test for WF-02 Collections |
| Non-breaking refactors (rename variables, reformat) | 75% | No | Rename `data` to `performanceData` in Code node |
| Add monitoring/alerting hooks | 70% | No | Add Telegram notification on WF-06 failure |
| Prompt refinements (non-client-facing AI nodes) | 80% | Yes | Tweak ADS-01 strategy prompt for better output format |
| Fix typos in email templates | 70% | No | Fix "Invoce" → "Invoice" in WF-01 template |
| Add new fields to Airtable (additive only) | 75% | No | Add `last_optimized` field to Campaigns table |

---

### MEDIUM Risk — Threshold Checks (Tier 4+ auto, Tier 3 with approval)

Changes that alter workflow behavior but are bounded and testable.

| Action | Confidence Required | Rollback Plan Required | Example |
|---|---|---|---|
| Modify branching logic (If/Switch nodes) | 85% | Yes | Change ADS-02 route conditions for platform targeting |
| Update email/message templates (non-financial) | 85% | Yes | Update marketing outreach email copy |
| Change fallback/error recovery paths | 85% | Yes | Modify what happens when SerpAPI returns empty in SEO-WF05 |
| Modify trigger schedules | 85% | Yes | Change ADS-01 from weekly to bi-weekly |
| Add/modify integration mappings | 85% | Yes | Map new Airtable field in SEO-WF08 engagement tracking |
| Update AI model references | 90% | Yes | Switch from `claude-sonnet-4` to newer model in OpenRouter |
| Change data transformation logic in Code nodes | 85% | Yes | Modify score calculation in SEO-SCORE workflow |
| Add new workflow step (non-financial) | 85% | Yes | Add dedup check before lead capture in BRIDGE-02 |
| Modify webhook response format | 85% | Yes | Change SEO-WF09 lead capture webhook output |
| Update Google Sheets column mappings | 85% | Yes | Remap LinkedIn pipeline columns |

---

### HIGH Risk — Requires Explicit Approval (All Tiers)

Changes with financial, compliance, or irreversible impact.

| Action | Confidence Required | Rollback Plan Required | Example |
|---|---|---|---|
| Modify payment/invoice generation logic | N/A (manual only) | Yes | Change WF-01 invoice amount calculation |
| Change auto-approve thresholds | N/A (manual only) | Yes | Raise accounting auto-approve from R10K to R15K |
| Modify collections/reminder logic | 95% + approval | Yes | Change WF-02 reminder cadence or escalation |
| Create or delete production workflows | 95% + approval | Yes | Deploy new accounting workflow |
| Modify ad budget or bid logic | N/A (manual only) | Yes | Change ADS safety caps |
| Update credential references | N/A (manual only) | Yes | Switch Gmail OAuth credential in WF-03 |
| Modify compliance-related outputs | N/A (manual only) | Yes | Change POPIA consent handling |
| Alter lead qualification/scoring formulas | 95% + approval | Yes | Modify ICP scoring weights in LI-03 |
| Change client-facing email content | 95% + approval | Yes | Update invoice email template in WF-01 |
| Modify Airtable schema (destructive — remove/rename fields) | N/A (manual only) | Yes | Rename Campaign Status field |
| Change Supabase schema or RLS policies | N/A (manual only) | Yes | Alter client portal permissions |

---

### PROHIBITED — Never Autonomous

| Action | Reason |
|---|---|
| Delete production workflows without git backup | Irreversible data loss |
| Modify `.env` file | Secrets exposure risk |
| Change n8n credential passwords/tokens | Authentication breakage across all workflows |
| Override safety caps in `agent_registry.py` | Financial guardrail bypass |
| Send financial communications to clients | Legal/compliance liability |
| Execute `DROP TABLE`, `TRUNCATE`, `DELETE FROM` without WHERE | Catastrophic data loss |
| Push to `main`/`master` with `--force` | Destroys git history |
| Disable monitoring/alerting system | Blind to failures |
| Modify POPIA consent or data retention logic | Legal compliance risk |
| Access or log secret values | Security violation |

---

## Risk Classification Flowchart

```
Does the change touch payment, invoice, or financial logic?
  ├── YES → HIGH RISK
  │
  └── NO → Does it modify client-facing communications?
              ├── YES → HIGH RISK
              │
              └── NO → Does it alter workflow control flow (If/Switch/branching)?
                          ├── YES → MEDIUM RISK
                          │
                          └── NO → Does it modify data transformation logic?
                                      ├── YES → MEDIUM RISK
                                      │
                                      └── NO → Is it additive only (new logging, docs, tests)?
                                                  ├── YES → LOW RISK
                                                  │
                                                  └── NO → MEDIUM RISK (default safe)
```

## Department Risk Modifiers

Some departments carry inherently higher risk due to their business impact:

| Department | Base Risk Modifier | Reason |
|---|---|---|
| Accounting (WF-01 to WF-07) | +1 level | Financial transactions, VAT, compliance |
| Ads (ADS-01 to ADS-08) | +1 level for budget changes | Direct ad spend impact |
| LinkedIn Lead Intelligence | Standard | Lead pipeline, no financial transactions |
| Marketing (WF-01 to WF-04) | Standard | Content production, no client data |
| SEO + Social (WF-05 to WF-11) | Standard | Analytics, publishing |
| Support (SUP-01 to SUP-04) | Standard | Tickets, knowledge base |
| Email Classifier | Standard | Internal routing only |

**Example:** A "low risk" change to an accounting workflow (e.g., adding logging) becomes "medium risk" because of the department modifier.
