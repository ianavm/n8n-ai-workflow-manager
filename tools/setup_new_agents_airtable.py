"""
AVM New Agents - Airtable Setup

Creates tables for 11 new agents in the Operations Control base (appTCh0EeXQp0XqzW).
Each agent gets its own table(s) for storing operational data.

Tables created:
    1. Market_Intel         - Competitive findings, regulatory alerts
    2. Knowledge_Graph      - Indexed documents, FAQs, contradictions
    3. QA_Results           - Smoke test, regression, performance results
    4. Financial_Intel      - Payroll summaries, VAT prep, cash flow scenarios
    5. CRM_Unified          - Unified contacts from Airtable + Xero + Supabase
    6. CRM_Sync_Log         - Sync operation logs
    7. Data_Analysis        - Query results, trend data, report metadata
    8. Brand_Audit          - Brand compliance scores, content gate results
    9. DevOps_Releases      - Deployment logs, release notes, credential alerts
    10. Compliance_Audit    - Compliance scan results, policy checks
    11. Booking_Log         - Meeting scheduling, follow-up tracking
    12. Data_Quality        - Dedup results, validation reports, schema audits

Prerequisites:
    1. AIRTABLE_API_TOKEN set in .env
    2. ORCH_AIRTABLE_BASE_ID set in .env (appTCh0EeXQp0XqzW)

Usage:
    python tools/setup_new_agents_airtable.py              # Create all tables
    python tools/setup_new_agents_airtable.py --dry-run     # Preview without creating
    python tools/setup_new_agents_airtable.py --table Market_Intel  # Create one table
"""

import os
import sys
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# -- Configuration --
BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "appTCh0EeXQp0XqzW")
AIRTABLE_TOKEN = os.getenv("AIRTABLE_API_TOKEN", "")
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

# -- Reusable options --
DT_OPTIONS = {
    "timeZone": "Africa/Johannesburg",
    "dateFormat": {"name": "iso"},
    "timeFormat": {"name": "24hour"},
}

SIGNIFICANCE_CHOICES = [
    {"name": "High", "color": "redBright"},
    {"name": "Medium", "color": "yellowBright"},
    {"name": "Low", "color": "greenBright"},
]

STATUS_CHOICES = [
    {"name": "New", "color": "blueBright"},
    {"name": "Reviewed", "color": "yellowBright"},
    {"name": "Actioned", "color": "greenBright"},
    {"name": "Dismissed", "color": "grayBright"},
]

PASS_FAIL_CHOICES = [
    {"name": "Pass", "color": "greenBright"},
    {"name": "Fail", "color": "redBright"},
    {"name": "Warning", "color": "yellowBright"},
]

SYNC_STATUS_CHOICES = [
    {"name": "Active", "color": "greenBright"},
    {"name": "Merged - Duplicate", "color": "yellowBright"},
    {"name": "Inactive", "color": "grayBright"},
    {"name": "Needs Review", "color": "orangeBright"},
]

SOURCE_CHOICES = [
    {"name": "Airtable", "color": "blueBright"},
    {"name": "Xero", "color": "purpleBright"},
    {"name": "Portal", "color": "greenBright"},
    {"name": "Scraper", "color": "orangeBright"},
    {"name": "Manual", "color": "grayBright"},
]

COMPLIANCE_STATUS = [
    {"name": "Compliant", "color": "greenBright"},
    {"name": "Non-Compliant", "color": "redBright"},
    {"name": "Needs Review", "color": "yellowBright"},
    {"name": "Exempted", "color": "grayBright"},
]

# ============================================================
# TABLE DEFINITIONS
# ============================================================

TABLE_DEFINITIONS = {
    "Market_Intel": {
        "description": "Competitive intelligence findings, market research, regulatory alerts",
        "primary_field": "finding_id",
        "fields": [
            {"name": "date", "type": "dateTime", "options": DT_OPTIONS},
            {"name": "source", "type": "singleLineText"},
            {"name": "competitor", "type": "singleLineText"},
            {"name": "finding", "type": "multilineText"},
            {
                "name": "category",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Pricing", "color": "redBright"},
                        {"name": "Service", "color": "blueBright"},
                        {"name": "Hiring", "color": "greenBright"},
                        {"name": "Market", "color": "purpleBright"},
                        {"name": "Regulatory", "color": "orangeBright"},
                        {"name": "Technology", "color": "tealBright"},
                    ]
                },
            },
            {
                "name": "significance",
                "type": "singleSelect",
                "options": {"choices": SIGNIFICANCE_CHOICES},
            },
            {"name": "raw_data", "type": "multilineText"},
            {"name": "ai_analysis", "type": "multilineText"},
            {
                "name": "status",
                "type": "singleSelect",
                "options": {"choices": STATUS_CHOICES},
            },
        ],
    },
    "Knowledge_Graph": {
        "description": "Indexed documents, FAQs, contradiction detection for Knowledge Manager",
        "primary_field": "doc_id",
        "fields": [
            {"name": "title", "type": "singleLineText"},
            {"name": "content_summary", "type": "multilineText"},
            {"name": "source_url", "type": "url"},
            {
                "name": "doc_type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Contract", "color": "redBright"},
                        {"name": "SOP", "color": "blueBright"},
                        {"name": "FAQ", "color": "greenBright"},
                        {"name": "Brand Guide", "color": "purpleBright"},
                        {"name": "Policy", "color": "orangeBright"},
                        {"name": "Template", "color": "tealBright"},
                    ]
                },
            },
            {"name": "indexed_at", "type": "dateTime", "options": DT_OPTIONS},
            {"name": "last_checked", "type": "dateTime", "options": DT_OPTIONS},
            {"name": "contradictions", "type": "multilineText"},
            {"name": "tags", "type": "singleLineText"},
            {"name": "version", "type": "number", "options": {"precision": 0}},
        ],
    },
    "QA_Results": {
        "description": "Smoke test, regression, and performance benchmark results",
        "primary_field": "test_id",
        "fields": [
            {"name": "date", "type": "dateTime", "options": DT_OPTIONS},
            {
                "name": "test_suite",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Daily Smoke", "color": "blueBright"},
                        {"name": "Weekly Regression", "color": "purpleBright"},
                        {"name": "Performance Benchmark", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "url", "type": "url"},
            {"name": "total_tests", "type": "number", "options": {"precision": 0}},
            {"name": "passed", "type": "number", "options": {"precision": 0}},
            {"name": "failed", "type": "number", "options": {"precision": 0}},
            {"name": "health_score", "type": "number", "options": {"precision": 1}},
            {"name": "performance_score", "type": "number", "options": {"precision": 0}},
            {"name": "lcp_ms", "type": "number", "options": {"precision": 0}},
            {"name": "cls", "type": "number", "options": {"precision": 3}},
            {"name": "accessibility_score", "type": "number", "options": {"precision": 0}},
            {"name": "seo_score", "type": "number", "options": {"precision": 0}},
            {
                "name": "result",
                "type": "singleSelect",
                "options": {"choices": PASS_FAIL_CHOICES},
            },
            {"name": "details", "type": "multilineText"},
            {"name": "ai_analysis", "type": "multilineText"},
            {"name": "duration_ms", "type": "number", "options": {"precision": 0}},
        ],
    },
    "Financial_Intel": {
        "description": "Payroll summaries, VAT prep, cash flow scenarios, payment schedules",
        "primary_field": "report_id",
        "fields": [
            {"name": "date", "type": "dateTime", "options": DT_OPTIONS},
            {
                "name": "report_type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Payroll", "color": "blueBright"},
                        {"name": "VAT Prep", "color": "purpleBright"},
                        {"name": "Cash Flow", "color": "greenBright"},
                        {"name": "Payment Schedule", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "period", "type": "singleLineText"},
            {"name": "total_amount_zar", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {"name": "variance_pct", "type": "percent", "options": {"precision": 1}},
            {"name": "scenario_best", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {"name": "scenario_expected", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {"name": "scenario_worst", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {"name": "ai_notes", "type": "multilineText"},
            {
                "name": "status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Pending Review", "color": "yellowBright"},
                        {"name": "Approved", "color": "greenBright"},
                        {"name": "Processed", "color": "blueBright"},
                        {"name": "Flagged", "color": "redBright"},
                    ]
                },
            },
            {"name": "filing_deadline", "type": "dateTime", "options": DT_OPTIONS},
        ],
    },
    "CRM_Unified": {
        "description": "Unified contact records from Airtable, Xero, and Supabase",
        "primary_field": "contact_id",
        "fields": [
            {"name": "email", "type": "email"},
            {"name": "name", "type": "singleLineText"},
            {"name": "phone", "type": "phoneNumber"},
            {"name": "company", "type": "singleLineText"},
            {"name": "industry", "type": "singleLineText"},
            {"name": "company_size", "type": "singleLineText"},
            {"name": "location", "type": "singleLineText"},
            {
                "name": "source",
                "type": "singleSelect",
                "options": {"choices": SOURCE_CHOICES},
            },
            {
                "name": "sync_status",
                "type": "singleSelect",
                "options": {"choices": SYNC_STATUS_CHOICES},
            },
            {"name": "first_seen", "type": "dateTime", "options": DT_OPTIONS},
            {"name": "last_synced", "type": "dateTime", "options": DT_OPTIONS},
            {"name": "xero_contact_id", "type": "singleLineText"},
            {"name": "supabase_client_id", "type": "singleLineText"},
            {"name": "airtable_lead_id", "type": "singleLineText"},
            {"name": "enrichment_data", "type": "multilineText"},
            {"name": "activity_summary", "type": "multilineText"},
        ],
    },
    "CRM_Sync_Log": {
        "description": "Sync operation logs for CRM unification",
        "primary_field": "log_id",
        "fields": [
            {"name": "sync_time", "type": "dateTime", "options": DT_OPTIONS},
            {
                "name": "operation",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Hourly Sync", "color": "blueBright"},
                        {"name": "Nightly Dedup", "color": "purpleBright"},
                        {"name": "Weekly Enrichment", "color": "greenBright"},
                    ]
                },
            },
            {"name": "records_processed", "type": "number", "options": {"precision": 0}},
            {"name": "new_records", "type": "number", "options": {"precision": 0}},
            {"name": "updated_records", "type": "number", "options": {"precision": 0}},
            {"name": "duplicates_found", "type": "number", "options": {"precision": 0}},
            {"name": "errors", "type": "number", "options": {"precision": 0}},
            {"name": "duration_ms", "type": "number", "options": {"precision": 0}},
            {"name": "details", "type": "multilineText"},
        ],
    },
    "Data_Analysis": {
        "description": "Query results, trend data, automated report metadata",
        "primary_field": "query_id",
        "fields": [
            {"name": "date", "type": "dateTime", "options": DT_OPTIONS},
            {
                "name": "report_type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "On-Demand Query", "color": "blueBright"},
                        {"name": "Daily Trend", "color": "greenBright"},
                        {"name": "Monthly Report", "color": "purpleBright"},
                    ]
                },
            },
            {"name": "query", "type": "multilineText"},
            {"name": "result_summary", "type": "multilineText"},
            {"name": "rows_returned", "type": "number", "options": {"precision": 0}},
            {"name": "duration_ms", "type": "number", "options": {"precision": 0}},
            {"name": "output_url", "type": "url"},
            {"name": "requested_by", "type": "singleLineText"},
        ],
    },
    "Brand_Audit": {
        "description": "Brand compliance scores, content gate results, visual audit findings",
        "primary_field": "audit_id",
        "fields": [
            {"name": "date", "type": "dateTime", "options": DT_OPTIONS},
            {
                "name": "audit_type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Pre-Publish Gate", "color": "blueBright"},
                        {"name": "Weekly Audit", "color": "purpleBright"},
                        {"name": "Competitor Diff", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "content_url", "type": "url"},
            {"name": "compliance_score", "type": "number", "options": {"precision": 0}},
            {
                "name": "result",
                "type": "singleSelect",
                "options": {"choices": PASS_FAIL_CHOICES},
            },
            {"name": "issues_found", "type": "multilineText"},
            {"name": "recommendations", "type": "multilineText"},
            {"name": "color_compliance", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "tone_compliance", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "terminology_compliance", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
        ],
    },
    "DevOps_Releases": {
        "description": "Deployment logs, release notes, credential rotation alerts",
        "primary_field": "release_id",
        "fields": [
            {"name": "date", "type": "dateTime", "options": DT_OPTIONS},
            {
                "name": "event_type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Deployment", "color": "blueBright"},
                        {"name": "Rollback", "color": "redBright"},
                        {"name": "Credential Alert", "color": "orangeBright"},
                        {"name": "Release Notes", "color": "greenBright"},
                    ]
                },
            },
            {"name": "workflow_id", "type": "singleLineText"},
            {"name": "workflow_name", "type": "singleLineText"},
            {"name": "version", "type": "singleLineText"},
            {
                "name": "status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Success", "color": "greenBright"},
                        {"name": "Failed", "color": "redBright"},
                        {"name": "Rolled Back", "color": "orangeBright"},
                        {"name": "Pending", "color": "yellowBright"},
                    ]
                },
            },
            {"name": "release_notes", "type": "multilineText"},
            {"name": "changes_summary", "type": "multilineText"},
            {"name": "deployed_by", "type": "singleLineText"},
            {"name": "health_check_passed", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
        ],
    },
    "Compliance_Audit": {
        "description": "Compliance scan results, POPIA checks, ad policy reviews",
        "primary_field": "audit_id",
        "fields": [
            {"name": "date", "type": "dateTime", "options": DT_OPTIONS},
            {
                "name": "audit_type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Monthly Scan", "color": "blueBright"},
                        {"name": "Ad Policy", "color": "purpleBright"},
                        {"name": "POPIA", "color": "orangeBright"},
                        {"name": "BBBEE", "color": "greenBright"},
                        {"name": "Tax", "color": "redBright"},
                    ]
                },
            },
            {"name": "department", "type": "singleLineText"},
            {
                "name": "compliance_status",
                "type": "singleSelect",
                "options": {"choices": COMPLIANCE_STATUS},
            },
            {"name": "score", "type": "number", "options": {"precision": 0}},
            {"name": "findings", "type": "multilineText"},
            {"name": "violations", "type": "number", "options": {"precision": 0}},
            {"name": "action_required", "type": "multilineText"},
            {"name": "deadline", "type": "dateTime", "options": DT_OPTIONS},
            {"name": "resolved_at", "type": "dateTime", "options": DT_OPTIONS},
        ],
    },
    "Booking_Log": {
        "description": "Meeting scheduling, follow-up tracking, calendar optimization",
        "primary_field": "booking_id",
        "fields": [
            {"name": "meeting_date", "type": "dateTime", "options": DT_OPTIONS},
            {"name": "contact_name", "type": "singleLineText"},
            {"name": "contact_email", "type": "email"},
            {
                "name": "meeting_type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Discovery Call", "color": "blueBright"},
                        {"name": "Client Review", "color": "greenBright"},
                        {"name": "Internal", "color": "purpleBright"},
                        {"name": "Follow-Up", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "duration_min", "type": "number", "options": {"precision": 0}},
            {
                "name": "status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Scheduled", "color": "blueBright"},
                        {"name": "Confirmed", "color": "greenBright"},
                        {"name": "Completed", "color": "grayBright"},
                        {"name": "No-Show", "color": "redBright"},
                        {"name": "Rescheduled", "color": "yellowBright"},
                        {"name": "Cancelled", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "calendar_event_id", "type": "singleLineText"},
            {"name": "follow_up_sent", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "notes", "type": "multilineText"},
        ],
    },
    "Data_Quality": {
        "description": "Dedup scan results, validation reports, schema audit findings",
        "primary_field": "scan_id",
        "fields": [
            {"name": "date", "type": "dateTime", "options": DT_OPTIONS},
            {
                "name": "scan_type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Nightly Dedup", "color": "blueBright"},
                        {"name": "Weekly Quality", "color": "purpleBright"},
                        {"name": "Monthly Schema", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "table_name", "type": "singleLineText"},
            {"name": "base_id", "type": "singleLineText"},
            {"name": "total_records", "type": "number", "options": {"precision": 0}},
            {"name": "duplicates_found", "type": "number", "options": {"precision": 0}},
            {"name": "validation_errors", "type": "number", "options": {"precision": 0}},
            {"name": "stale_records", "type": "number", "options": {"precision": 0}},
            {"name": "quality_score", "type": "number", "options": {"precision": 1}},
            {"name": "details", "type": "multilineText"},
            {"name": "actions_taken", "type": "multilineText"},
        ],
    },
}


# ============================================================
# AIRTABLE API FUNCTIONS
# ============================================================

def get_headers():
    """Return auth headers for Airtable API."""
    return {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }


def list_existing_tables(base_id):
    """List existing tables in the base."""
    url = f"{AIRTABLE_META_API}/{base_id}/tables"
    resp = httpx.get(url, headers=get_headers(), timeout=30)
    resp.raise_for_status()
    return {t["name"]: t["id"] for t in resp.json().get("tables", [])}


def create_table(base_id, table_name, definition):
    """Create a table in Airtable."""
    url = f"{AIRTABLE_META_API}/{base_id}/tables"

    fields = [{"name": definition["primary_field"], "type": "singleLineText"}]
    fields.extend(definition["fields"])

    payload = {
        "name": table_name,
        "description": definition.get("description", ""),
        "fields": fields,
    }

    resp = httpx.post(url, headers=get_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    return result["id"]


# ============================================================
# CLI
# ============================================================

def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    target_table = None

    for i, arg in enumerate(args):
        if arg == "--table" and i + 1 < len(args):
            target_table = args[i + 1]

    print("=" * 60)
    print("NEW AGENTS - AIRTABLE SETUP")
    print("=" * 60)
    print(f"Base ID: {BASE_ID}")
    print(f"Tables to create: {len(TABLE_DEFINITIONS)}")
    if dry_run:
        print("MODE: DRY RUN (no changes)")
    print()

    if not AIRTABLE_TOKEN:
        print("ERROR: AIRTABLE_API_TOKEN not set in .env")
        sys.exit(1)

    if not BASE_ID:
        print("ERROR: ORCH_AIRTABLE_BASE_ID not set in .env")
        sys.exit(1)

    # Check existing tables
    print("Checking existing tables...")
    try:
        existing = list_existing_tables(BASE_ID)
        print(f"  Found {len(existing)} existing tables")
    except Exception as e:
        print(f"  ERROR listing tables: {e}")
        sys.exit(1)

    # Determine which tables to create
    tables_to_create = {}
    for name, definition in TABLE_DEFINITIONS.items():
        if target_table and name != target_table:
            continue
        if name in existing:
            print(f"  SKIP: {name} (already exists, ID: {existing[name]})")
        else:
            tables_to_create[name] = definition

    if not tables_to_create:
        print("\nNo new tables to create.")
        if target_table and target_table not in TABLE_DEFINITIONS:
            print(f"  Unknown table: {target_table}")
            print(f"  Available: {', '.join(TABLE_DEFINITIONS.keys())}")
        return

    print(f"\nCreating {len(tables_to_create)} tables...")

    created = {}
    for name, definition in tables_to_create.items():
        field_count = len(definition["fields"]) + 1  # +1 for primary
        print(f"\n  Creating: {name} ({field_count} fields)")

        if dry_run:
            print(f"    [DRY RUN] Would create {name}")
            continue

        try:
            table_id = create_table(BASE_ID, name, definition)
            created[name] = table_id
            print(f"    Created: {table_id}")
        except httpx.HTTPStatusError as e:
            print(f"    ERROR: {e.response.status_code} - {e.response.text[:200]}")
        except Exception as e:
            print(f"    ERROR: {e}")

    # Output env vars
    if created:
        print("\n" + "=" * 60)
        print("ADD TO .env:")
        print("=" * 60)

        env_map = {
            "Market_Intel": "MARKET_INTEL_TABLE_ID",
            "Knowledge_Graph": "KNOWLEDGE_GRAPH_TABLE_ID",
            "QA_Results": "QA_RESULTS_TABLE_ID",
            "Financial_Intel": "FINTEL_TABLE_ID",
            "CRM_Unified": "CRM_UNIFIED_TABLE_ID",
            "CRM_Sync_Log": "CRM_SYNC_LOG_TABLE_ID",
            "Data_Analysis": "DATA_ANALYSIS_TABLE_ID",
            "Brand_Audit": "BRAND_AUDIT_TABLE_ID",
            "DevOps_Releases": "DEVOPS_RELEASES_TABLE_ID",
            "Compliance_Audit": "COMPLIANCE_AUDIT_TABLE_ID",
            "Booking_Log": "BOOKING_LOG_TABLE_ID",
            "Data_Quality": "DATA_QUALITY_TABLE_ID",
        }

        for name, table_id in created.items():
            env_key = env_map.get(name, f"{name.upper()}_TABLE_ID")
            print(f"{env_key}={table_id}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Existing tables: {len(existing)}")
    print(f"  Skipped (already exist): {len(tables_to_create) - len(created) if not dry_run else 0}")
    print(f"  Created: {len(created) if not dry_run else 0}")
    print(f"  Dry run: {len(tables_to_create) if dry_run else 0}")

    if created:
        print("\nNext steps:")
        print("  1. Copy the table IDs above into your .env file")
        print("  2. Run deploy scripts with real table IDs")
        print("  3. Verify tables in Airtable UI")


if __name__ == "__main__":
    main()
