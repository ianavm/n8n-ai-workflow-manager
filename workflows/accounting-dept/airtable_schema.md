# Accounting Department - Airtable Schema

Base: **Accounting Department**
Base ID: Set in `.env` as `ACCOUNTING_AIRTABLE_BASE_ID`

## Tables Overview

| Table | Primary Field | Purpose | Env Key |
|-------|--------------|---------|---------|
| Customers | Customer ID | Customer master data for AR | `ACCOUNTING_TABLE_CUSTOMERS` |
| Suppliers | Supplier ID | Supplier master data for AP | `ACCOUNTING_TABLE_SUPPLIERS` |
| Products Services | Item Code | Product/service catalog | `ACCOUNTING_TABLE_PRODUCTS_SERVICES` |
| Invoices | Invoice ID | Invoice tracking for AR | `ACCOUNTING_TABLE_INVOICES` |
| Payments | Payment ID | Payment reconciliation | `ACCOUNTING_TABLE_PAYMENTS` |
| Supplier Bills | Bill ID | AP bill tracking | `ACCOUNTING_TABLE_SUPPLIER_BILLS` |
| Tasks | Task ID | Human task queue | `ACCOUNTING_TABLE_TASKS` |
| Audit Log | Timestamp | Immutable audit trail | `ACCOUNTING_TABLE_AUDIT_LOG` |
| System Config | Key | Key-value config store | `ACCOUNTING_TABLE_SYSTEM_CONFIG` |

## Status Lifecycles

### Invoice Status
```
Draft → Pending Approval → Sent → Partial → Paid
                                 → Overdue → Disputed → (resolved)
                                 → Cancelled
```

### Supplier Bill Approval
```
Pending → Auto Approved (< R10k known supplier)
       → Awaiting Approval → Approved → (create in Xero)
                            → Rejected
```

### Supplier Bill Payment
```
Unpaid → Scheduled → Paid
```

### Task Status
```
Open → In Progress → Completed
                   → Escalated (overdue)
```

### Payment Reconciliation
```
Unmatched → Matched (exact/fuzzy)
          → Partial Match
          → Manual Review (low confidence)
```

## Table Details

### Customers
| Field | Type | Notes |
|-------|------|-------|
| Customer ID | Primary (text) | Auto or manual |
| Legal Name | Single line text | |
| Trading Name | Single line text | |
| Email | Email | Primary contact |
| Phone | Phone number | |
| Billing Address | Long text | |
| VAT Number | Single line text | SA VAT format |
| Default Payment Terms | Select | COD/7/14/30/60 days |
| Credit Limit | Currency (R) | |
| Risk Flag | Select | Low/Medium/High |
| Preferred Channel | Select | Email/WhatsApp/Both |
| Xero Contact ID | Single line text | Linked to Xero |
| Active | Checkbox | |
| Created At | Date (ISO) | |
| Updated At | Date (ISO) | |

### Suppliers
| Field | Type | Notes |
|-------|------|-------|
| Supplier ID | Primary (text) | |
| VAT Number | Single line text | |
| Email | Email | |
| Phone | Phone number | |
| Bank Details Hash | Single line text | For change detection |
| Xero Contact ID | Single line text | |
| Default Category | Select | Software/Hosting/Marketing/Office/Professional Services/Travel/Equipment/Other |
| Payment Terms | Select | COD/7/14/30 days |
| Active | Checkbox | |
| Created At | Date (ISO) | |

### Products Services
| Field | Type | Notes |
|-------|------|-------|
| Item Code | Primary (text) | e.g., WEB-DEV, AI-AUTO |
| Description | Long text | |
| Unit Price | Currency (R) | |
| VAT Rate Code | Select | STANDARD_15/ZERO_RATED/EXEMPT |
| Revenue Account Code | Single line text | Xero account |
| Cost Account Code | Single line text | |
| Active | Checkbox | |

### Invoices
| Field | Type | Notes |
|-------|------|-------|
| Invoice ID | Primary (text) | Internal reference |
| Invoice Number | Single line text | AVM-XXXX format |
| Customer ID | Single line text | Links to Customers |
| Customer Name | Single line text | Denormalized |
| Issue Date | Date (ISO) | |
| Due Date | Date (ISO) | |
| Status | Select | Draft/Pending Approval/Sent/Partial/Paid/Overdue/Disputed/Cancelled |
| Subtotal | Currency (R) | |
| VAT Amount | Currency (R) | |
| Total | Currency (R) | |
| Amount Paid | Currency (R) | |
| Balance Due | Currency (R) | |
| Currency | Single line text | Default: ZAR |
| Line Items JSON | Long text | JSON array of line items |
| PDF URL | URL | Google Drive link |
| Xero Invoice ID | Single line text | |
| Source | Select | CRM/Web Form/WhatsApp/Manual |
| Reminder Count | Number (int) | |
| Last Reminder Date | Date (ISO) | |
| Next Reminder Date | Date (ISO) | Used by WF-02 |
| Dispute Reason | Long text | |
| Dispute Owner | Single line text | |
| Created By | Single line text | system/human |
| Created At | Date (ISO) | |
| Sent At | Date (ISO) | |

### Payments
| Field | Type | Notes |
|-------|------|-------|
| Payment ID | Primary (text) | |
| Invoice Refs | Single line text | Comma-separated invoice IDs |
| Amount | Currency (R) | |
| Date Received | Date (ISO) | |
| Method | Select | EFT/Stripe/PayFast/Cash/Credit Card |
| Reference Text | Single line text | Bank reference / gateway ID |
| Reconciliation Status | Select | Unmatched/Matched/Partial Match/Manual Review |
| Xero Payment ID | Single line text | |
| Gateway Transaction ID | Single line text | Stripe/PayFast ID |
| Created At | Date (ISO) | |

### Supplier Bills
| Field | Type | Notes |
|-------|------|-------|
| Bill ID | Primary (text) | |
| Supplier Name | Single line text | |
| Supplier Ref | Single line text | Links to Suppliers |
| Bill Number | Single line text | Supplier's invoice # |
| Bill Date | Date (ISO) | |
| Due Date | Date (ISO) | |
| Subtotal | Currency (R) | |
| VAT Amount | Currency (R) | |
| Total Amount | Currency (R) | |
| Category | Select | Software/Hosting/Marketing/Office/Professional Services/Travel/Equipment/Other |
| Cost Center | Single line text | |
| Attachment URL | URL | Google Drive link |
| OCR Raw JSON | Long text | AI extraction output |
| Approval Status | Select | Pending/Auto Approved/Awaiting Approval/Approved/Rejected |
| Approver | Single line text | |
| Approved At | Date (ISO) | |
| Payment Status | Select | Unpaid/Scheduled/Paid |
| Xero Bill ID | Single line text | |
| Created At | Date (ISO) | |

### Tasks
| Field | Type | Notes |
|-------|------|-------|
| Task ID | Primary (text) | UUID |
| Type | Select | Invoice Approval/Bill Approval/Payment Reconciliation/Dispute Resolution/Exception Review/Month End Task |
| Priority | Select | Low/Medium/High/Urgent |
| Owner | Single line text | |
| Status | Select | Open/In Progress/Completed/Escalated |
| Related Record ID | Single line text | |
| Related Table | Single line text | Invoices/Supplier Bills/Payments |
| Description | Long text | |
| Resolution Notes | Long text | |
| Approval Token | Single line text | UUID for webhook approval |
| Due At | Date (ISO) | |
| Created At | Date (ISO) | |
| Completed At | Date (ISO) | |

### Audit Log
| Field | Type | Notes |
|-------|------|-------|
| Timestamp | Primary (text) | ISO timestamp |
| Workflow Name | Single line text | WF-01 through WF-07 |
| Event Type | Select | 15 event types (see below) |
| Record Type | Single line text | Invoice/Payment/Bill/Customer/Supplier |
| Record ID | Single line text | |
| Action Taken | Long text | |
| Actor | Single line text | system / human name |
| Result | Select | Success/Failed/Partial |
| Error Details | Long text | |
| Metadata JSON | Long text | |
| Created At | Date (ISO) | |

**Event Types**: INVOICE_CREATED, INVOICE_SENT, INVOICE_UPDATED, PAYMENT_RECEIVED, PAYMENT_RECONCILED, BILL_CREATED, BILL_APPROVED, BILL_PAID, REMINDER_SENT, DISPUTE_OPENED, DISPUTE_RESOLVED, XERO_SYNC, MONTH_END_CLOSE, EXCEPTION, MASTER_DATA_CHANGE

### System Config
| Field | Type | Notes |
|-------|------|-------|
| Key | Primary (text) | Config key name |
| Value | Long text | JSON string |
| Updated At | Date (ISO) | |
| Updated By | Single line text | setup/WF-XX |

**Seed Keys**: vat_standard_rate, vat_zero_rate, vat_exempt, approval_threshold, high_value_invoice_threshold, reminder_cadence, default_currency, company_details, invoice_prefix, payfast_config

## Cross-Workflow Data Flow

```
WF-01 (Sales)     → writes Invoices, Customers, Audit Log
WF-02 (Collections) → reads Invoices, writes Invoices (reminders), Tasks, Audit Log
WF-03 (Payments)  → writes Payments, updates Invoices, Audit Log
WF-04 (Bills)     → writes Supplier Bills, Suppliers, Tasks, Audit Log
WF-05 (Month-End) → reads ALL tables, writes Tasks, Audit Log
WF-06 (Master Data) → reads/writes Customers, Suppliers, System Config, Audit Log
WF-07 (Exceptions) → reads/writes Tasks, updates Invoices/Bills, Audit Log
```
