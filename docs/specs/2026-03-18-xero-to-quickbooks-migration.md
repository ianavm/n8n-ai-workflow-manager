# Xero to QuickBooks Online Migration

**Date:** 2026-03-18
**Status:** Approved
**Author:** Claude Code + Ian Immelman

## Context

AnyVision Media is swapping Xero for QuickBooks Online (South Africa edition) as accounting platform. Xero had minimal data (recently added), so no data migration needed — clean swap of API integration layer only.

**QBO Plan:** Essentials (AR invoicing, AP bills, multi-currency, no payroll)
**Region:** QBO South Africa (native ZAR, 15% VAT codes)
**n8n Integration:** Native `n8n-nodes-base.quickbooks` node + HTTP Request for reports

## Scope

### Remove (2 workflows)
| Workflow | ID | Reason |
|----------|----|--------|
| FINTEL-01 Payroll | `mywOowwRhK3ovV8R` | 1-person team, no payroll needed |
| FINTEL-04 Payment Scheduler | `1XYu0y0DMH1c8JX9` | Essentials plan, no programmatic payments |

### Swap Xero -> QBO (6 workflows)
| Workflow | ID | Changes |
|----------|----|---------|
| WF-01 Sales & Invoicing | `twSg4SfNdlmdITHj` | Invoice create: Xero HTTP -> QBO node `invoice.create` |
| WF-03 Payments & Reconciliation | `ygwBtSysINRWHJxB` | Payment fetch: Xero HTTP -> QBO node `payment.getAll` |
| WF-04 Supplier Bills | `ZEcxIC9M5ehQvsbg` | Bill create: Xero HTTP -> QBO node `bill.create` |
| WF-06 Master Data Audit | `gwMuSElYqDTRGFKa` | Contact compare: Xero HTTP -> QBO node `customer.getAll` + `vendor.getAll` |
| FINTEL-02 VAT Prep | `OgLBLCZyQuV1wgEG` | VAT data: Xero HTTP -> QBO HTTP `reports/GstReport` |
| FINTEL-03 Cash Flow | `wEXsboGxGfRlEDEH` | Aging: Xero HTTP -> QBO HTTP `reports/AgedReceivables` + `AgedPayables` |

### Update references (no logic change)
| File | Change |
|------|--------|
| CRM-01 (`EiuQcBeQG7AVcbYE`) | Remove Xero contact sync step |
| DEVOPS-02 (`VuBUg4r0BLL81KIF`) | Monitor QBO OAuth2 instead of Xero |
| `config.json` | Replace `xero_focus`, `xero_tenant_id` with `quickbooks` equivalents |
| `.env.template` | Replace `XERO_*` vars with `QBO_*` |
| `tools/credentials.py` | `CRED_XERO` -> `CRED_QUICKBOOKS` (`quickBooksOAuth2Api`) |
| `tools/deploy_accounting_wf01.py` | Swap Xero nodes for QBO nodes |
| `tools/deploy_financial_intel.py` | Remove FINTEL-01/04, update FINTEL-02/03 |
| `tools/deploy_accounting_dept.py` | Update descriptions and credential refs |
| `CLAUDE.md` | Update tech stack, MCP servers, integration list |
| `.mcp.json` | Remove Xero MCP server |

## Credential Setup

- **n8n credential type:** `quickBooksOAuth2Api`
- **Required from Intuit Developer Portal:** Client ID, Client Secret
- **Obtained after OAuth:** Company ID (replaces Xero tenant ID)
- **Env vars:** `QBO_CLIENT_ID`, `QBO_CLIENT_SECRET`, `QBO_COMPANY_ID`, `ACCOUNTING_QBO_CRED_ID`

## API Mapping

| Operation | Xero | QBO |
|-----------|------|-----|
| Create Invoice (AR) | `POST /api.xro/2.0/Invoices` (type: ACCREC) | n8n node: `quickbooks.invoice.create` |
| Create Bill (AP) | `POST /api.xro/2.0/Invoices` (type: ACCPAY) | n8n node: `quickbooks.bill.create` |
| Get Payments | `GET /api.xro/2.0/Payments` | n8n node: `quickbooks.payment.getAll` |
| Get Customers | `GET /api.xro/2.0/Contacts` (isCustomer) | n8n node: `quickbooks.customer.getAll` |
| Get Vendors | `GET /api.xro/2.0/Contacts` (isSupplier) | n8n node: `quickbooks.vendor.getAll` |
| AR Aging | `GET /Reports/AgedReceivablesByContact` | HTTP: `GET /v3/company/{id}/reports/AgedReceivables` |
| AP Aging | `GET /Reports/AgedPayablesByContact` | HTTP: `GET /v3/company/{id}/reports/AgedPayables` |
| VAT/GST Report | `GET /Reports/BASReport` | HTTP: `GET /v3/company/{id}/reports/GstReport` |
| Get Estimate | n/a | n8n node: `quickbooks.estimate.get` (available if needed) |

## Tax Code Mapping (Xero -> QBO ZA)

| Xero Tax Type | QBO ZA Code | Description |
|---------------|-------------|-------------|
| OUTPUT2 | `TAX` | Standard Rate 15% VAT |
| OUTPUTZERO | `NON` | Zero Rated |
| EXEMPTOUTPUT | `EXEMPT` | VAT Exempt |

## Invoice Field Mapping

| Xero Field | QBO Field |
|------------|-----------|
| `Contact.ContactID` | `CustomerRef.value` (Customer ID) |
| `LineItems[].Description` | `Line[].Description` |
| `LineItems[].Quantity` | `Line[].SalesItemLineDetail.Qty` |
| `LineItems[].UnitAmount` | `Line[].SalesItemLineDetail.UnitPrice` |
| `LineItems[].AccountCode` | `Line[].SalesItemLineDetail.ItemRef` |
| `LineItems[].TaxType` | `Line[].SalesItemLineDetail.TaxCodeRef` |
| `CurrencyCode` (ZAR) | `CurrencyRef.value` (ZAR) |
| `Status` (AUTHORISED) | `EmailStatus` (NeedToSend) |
| `InvoiceNumber` | `DocNumber` |
| `DueDate` | `DueDate` |

## Bill Field Mapping

| Xero Field | QBO Field |
|------------|-----------|
| `Contact.ContactID` (supplier) | `VendorRef.value` |
| `LineItems[].Description` | `Line[].Description` |
| `LineItems[].Quantity` | `Line[].ItemBasedExpenseLineDetail.Qty` |
| `LineItems[].UnitAmount` | `Line[].ItemBasedExpenseLineDetail.UnitPrice` |
| `LineItems[].AccountCode` | `Line[].AccountBasedExpenseLineDetail.AccountRef` |
| `Total` | `TotalAmt` |

## What Does NOT Change

- Airtable schema and field names (Invoice ID, Status, etc.)
- Email templates (AVM-branded, not accounting-platform-branded)
- Workflow trigger schedules
- Approval routing logic (auto-approve < R10,000, escalate > R50,000)
- Currency (ZAR throughout)
- Email suppression system

## Execution Plan

1. **Create QBO OAuth2 credential** in n8n UI (after QBO account ready)
2. **Run migration script** `tools/migrate_xero_to_quickbooks.py`:
   - Deactivate affected workflows
   - Patch each workflow (swap nodes, update credentials)
   - Reactivate
3. **Deactivate FINTEL-01 and FINTEL-04** permanently
4. **Update deploy scripts** (source of truth for rebuilds)
5. **Update config.json, .env.template, credentials.py, CLAUDE.md, .mcp.json**
6. **Test** with manual invoice creation in WF-01
7. **Update memory** with migration results

## Verification

- [ ] WF-01: Create test invoice -> appears in QBO as Draft/NeedToSend
- [ ] WF-03: Payment recorded in QBO -> syncs to Airtable
- [ ] WF-04: Email with bill attachment -> bill created in QBO
- [ ] WF-06: Customer/vendor data matches between QBO and Airtable
- [ ] FINTEL-02: VAT report pulls correct ZA tax data
- [ ] FINTEL-03: Aging reports return valid AR/AP data
- [ ] CRM-01: No Xero references remain
- [ ] DEVOPS-02: Monitors QBO credential expiry
