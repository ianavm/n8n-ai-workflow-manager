"""
LinkedIn Lead Intelligence - Airtable Base Setup Tool

Creates all 10 required tables in the Marketing Department Airtable base
for the LinkedIn Lead Intelligence System (LI-01 through LI-10).

Extends the existing Marketing base (apptjjBx34z9340tK) rather than creating a new one.

Prerequisites:
    1. AIRTABLE_API_TOKEN set in .env
    2. MARKETING_AIRTABLE_BASE_ID set in .env (existing marketing base)

Usage:
    python tools/setup_linkedin_airtable.py              # Create all tables
    python tools/setup_linkedin_airtable.py --seed        # Create tables + seed sample data
"""

import os
import sys
import json
import httpx
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# ── Configuration ──────────────────────────────────────────────
# Uses the SAME marketing base (extending it with LinkedIn tables)
MARKETING_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "")

AIRTABLE_API = "https://api.airtable.com/v0"
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

# ── Table Definitions ──────────────────────────────────────────

TABLE_DEFINITIONS = {
    "LI_Campaigns": {
        "description": "Campaign configs with ICP filters, schedules, and status flags",
        "primary_field": "Campaign Name",
        "fields": [
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Active", "color": "greenBright"},
                        {"name": "Paused", "color": "yellowBright"},
                        {"name": "Draft", "color": "blueBright"},
                        {"name": "Completed", "color": "grayBright"},
                        {"name": "Emergency_Stop", "color": "redBright"},
                    ]
                },
            },
            {"name": "ICP Titles", "type": "multilineText"},
            {"name": "ICP Industries", "type": "multilineText"},
            {"name": "ICP Company Size", "type": "singleLineText"},
            {"name": "ICP Locations", "type": "multilineText"},
            {"name": "ICP Keywords", "type": "multilineText"},
            {"name": "Red Flag Keywords", "type": "multilineText"},
            {
                "name": "Schedule",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Daily", "color": "blueBright"},
                        {"name": "Weekly_Monday", "color": "greenBright"},
                        {"name": "Weekly_Wednesday", "color": "greenBright"},
                        {"name": "Manual_Only", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Batch Size", "type": "number", "options": {"precision": 0}},
            {"name": "Daily Action Limit", "type": "number", "options": {"precision": 0}},
            {"name": "Hourly Rate Limit", "type": "number", "options": {"precision": 0}},
            {"name": "Emergency Pause", "type": "checkbox", "options": {"icon": "check", "color": "redBright"}},
            {"name": "Token Budget Daily", "type": "number", "options": {"precision": 0}},
            {"name": "Last Run", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Total Leads Processed", "type": "number", "options": {"precision": 0}},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "LI_Leads": {
        "description": "Master lead record with all profile and company data",
        "primary_field": "Lead ID",
        "fields": [
            {"name": "Campaign ID", "type": "singleLineText"},
            {"name": "Full Name", "type": "singleLineText"},
            {"name": "First Name", "type": "singleLineText"},
            {"name": "Last Name", "type": "singleLineText"},
            {"name": "Title", "type": "singleLineText"},
            {"name": "Company Name", "type": "singleLineText"},
            {"name": "Industry", "type": "singleLineText"},
            {"name": "Location", "type": "singleLineText"},
            {"name": "LinkedIn URL", "type": "url"},
            {"name": "Email", "type": "email"},
            {"name": "Phone", "type": "phoneNumber"},
            {"name": "Company Website", "type": "url"},
            {"name": "Company LinkedIn", "type": "url"},
            {"name": "Employee Count", "type": "singleLineText"},
            {
                "name": "Source",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "PhantomBuster", "color": "blueBright"},
                        {"name": "CSV_Upload", "color": "greenBright"},
                        {"name": "LinkedIn_API", "color": "purpleBright"},
                        {"name": "Apify", "color": "orangeBright"},
                        {"name": "Manual", "color": "grayBright"},
                    ]
                },
            },
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "New", "color": "blueBright"},
                        {"name": "Enriched", "color": "yellowBright"},
                        {"name": "Scored", "color": "orangeBright"},
                        {"name": "Qualified", "color": "greenBright"},
                        {"name": "Awaiting_Review", "color": "purpleBright"},
                        {"name": "Approved", "color": "greenDark1"},
                        {"name": "Contacted", "color": "cyanBright"},
                        {"name": "Replied", "color": "tealBright"},
                        {"name": "Discovery", "color": "blueDark1"},
                        {"name": "Proposal", "color": "pinkBright"},
                        {"name": "Won", "color": "greenBright"},
                        {"name": "Lost", "color": "redBright"},
                        {"name": "Nurture", "color": "yellowBright"},
                        {"name": "Ignore", "color": "grayBright"},
                    ]
                },
            },
            {
                "name": "Priority Band",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Very_High", "color": "redBright"},
                        {"name": "High", "color": "orangeBright"},
                        {"name": "Medium", "color": "yellowBright"},
                        {"name": "Low", "color": "grayBright"},
                    ]
                },
            },
            {"name": "ICP Score", "type": "number", "options": {"precision": 0}},
            {"name": "Final Priority Score", "type": "number", "options": {"precision": 0}},
            {"name": "Red Flags", "type": "multilineText"},
            {"name": "Opt Out", "type": "checkbox", "options": {"icon": "check", "color": "redBright"}},
            {
                "name": "POPIA Consent",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Pending", "color": "yellowBright"},
                        {"name": "Granted", "color": "greenBright"},
                        {"name": "Withdrawn", "color": "redBright"},
                    ]
                },
            },
            {"name": "Source Metadata", "type": "multilineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Updated At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "LI_Enrichment": {
        "description": "Company enrichment data per lead",
        "primary_field": "Enrichment ID",
        "fields": [
            {"name": "Lead ID", "type": "singleLineText"},
            {"name": "Company Website", "type": "url"},
            {
                "name": "Website Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Active", "color": "greenBright"},
                        {"name": "Down", "color": "redBright"},
                        {"name": "Not_Found", "color": "grayBright"},
                        {"name": "Redirect", "color": "yellowBright"},
                    ]
                },
            },
            {"name": "Website Quality Score", "type": "number", "options": {"precision": 0}},
            {"name": "Has Blog", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "Social Presence", "type": "multilineText"},
            {"name": "Digital Presence Score", "type": "number", "options": {"precision": 0}},
            {"name": "Tech Stack Hints", "type": "multilineText"},
            {"name": "Business Model", "type": "singleLineText"},
            {"name": "Employee Estimate", "type": "singleLineText"},
            {"name": "Company Description", "type": "multilineText"},
            {"name": "Key Services", "type": "multilineText"},
            {"name": "Raw HTML Snippet", "type": "multilineText"},
            {"name": "Enriched At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "LI_Scores": {
        "description": "ICP, pain, opportunity, and final priority scores per lead",
        "primary_field": "Score ID",
        "fields": [
            {"name": "Lead ID", "type": "singleLineText"},
            {
                "name": "Score Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "ICP", "color": "blueBright"},
                        {"name": "Pain", "color": "orangeBright"},
                        {"name": "Opportunity", "color": "purpleBright"},
                        {"name": "Priority", "color": "redBright"},
                    ]
                },
            },
            {"name": "Total Score", "type": "number", "options": {"precision": 0}},
            {"name": "Decision Maker Score", "type": "number", "options": {"precision": 0}},
            {"name": "Company Size Score", "type": "number", "options": {"precision": 0}},
            {"name": "Industry Score", "type": "number", "options": {"precision": 0}},
            {"name": "Pain Indicator Score", "type": "number", "options": {"precision": 0}},
            {"name": "Automation Potential Score", "type": "number", "options": {"precision": 0}},
            {"name": "Engagement Likelihood Score", "type": "number", "options": {"precision": 0}},
            {"name": "Confidence", "type": "number", "options": {"precision": 2}},
            {"name": "AI Reasoning", "type": "multilineText"},
            {"name": "Red Flags Detected", "type": "multilineText"},
            {"name": "Scored At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "LI_Pain_Points": {
        "description": "Individual pain points detected per lead",
        "primary_field": "Pain Point ID",
        "fields": [
            {"name": "Lead ID", "type": "singleLineText"},
            {"name": "Pain Point", "type": "singleLineText"},
            {
                "name": "Category",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Manual_Processes", "color": "orangeBright"},
                        {"name": "Data_Silos", "color": "blueBright"},
                        {"name": "Customer_Experience", "color": "purpleBright"},
                        {"name": "Reporting_Visibility", "color": "greenBright"},
                        {"name": "Communication_Gaps", "color": "yellowBright"},
                        {"name": "Scaling_Bottleneck", "color": "redBright"},
                        {"name": "Cost_Inefficiency", "color": "pinkBright"},
                    ]
                },
            },
            {"name": "Severity", "type": "number", "options": {"precision": 0}},
            {"name": "Confidence", "type": "number", "options": {"precision": 2}},
            {"name": "Evidence", "type": "multilineText"},
            {"name": "Automation Category", "type": "singleLineText"},
            {"name": "Detected At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "LI_Automation_Opportunities": {
        "description": "Recommended AVM solutions mapped per lead",
        "primary_field": "Opportunity ID",
        "fields": [
            {"name": "Lead ID", "type": "singleLineText"},
            {"name": "Solution Name", "type": "singleLineText"},
            {"name": "Pain Points Addressed", "type": "multilineText"},
            {"name": "ROI Hypothesis", "type": "multilineText"},
            {
                "name": "Suggested Package",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Lite_R1999", "color": "greenBright"},
                        {"name": "Growth_R4999", "color": "blueBright"},
                        {"name": "Pro_R14999", "color": "purpleBright"},
                        {"name": "Enterprise_R29999", "color": "orangeBright"},
                    ]
                },
            },
            {
                "name": "Implementation Complexity",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Simple", "color": "greenBright"},
                        {"name": "Moderate", "color": "yellowBright"},
                        {"name": "Complex", "color": "orangeBright"},
                        {"name": "Enterprise", "color": "redBright"},
                    ]
                },
            },
            {"name": "Rank", "type": "number", "options": {"precision": 0}},
            {"name": "Confidence", "type": "number", "options": {"precision": 2}},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "LI_Outreach": {
        "description": "Generated outreach copy per lead",
        "primary_field": "Outreach ID",
        "fields": [
            {"name": "Lead ID", "type": "singleLineText"},
            {"name": "Connection Message", "type": "multilineText"},
            {"name": "Follow Up 1", "type": "multilineText"},
            {"name": "Follow Up 2", "type": "multilineText"},
            {"name": "Short Pitch", "type": "multilineText"},
            {"name": "Email Draft", "type": "multilineText"},
            {"name": "Email Subject", "type": "singleLineText"},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Draft", "color": "yellowBright"},
                        {"name": "Ready", "color": "greenBright"},
                        {"name": "Approved", "color": "greenDark1"},
                        {"name": "Sent", "color": "blueBright"},
                    ]
                },
            },
            {"name": "Personalization Score", "type": "number", "options": {"precision": 0}},
            {"name": "Approved By", "type": "singleLineText"},
            {"name": "Approved At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Generated At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "LI_Pipeline": {
        "description": "CRM pipeline status tracking per lead",
        "primary_field": "Pipeline ID",
        "fields": [
            {"name": "Lead ID", "type": "singleLineText"},
            {
                "name": "Stage",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "New", "color": "blueBright"},
                        {"name": "Enriched", "color": "cyanBright"},
                        {"name": "Qualified", "color": "yellowBright"},
                        {"name": "Awaiting_Review", "color": "purpleBright"},
                        {"name": "Approved", "color": "greenBright"},
                        {"name": "Contacted", "color": "orangeBright"},
                        {"name": "Replied", "color": "tealBright"},
                        {"name": "Discovery", "color": "blueDark1"},
                        {"name": "Proposal", "color": "pinkBright"},
                        {"name": "Won", "color": "greenDark1"},
                        {"name": "Lost", "color": "redBright"},
                        {"name": "Nurture", "color": "yellowBright"},
                    ]
                },
            },
            {"name": "Previous Stage", "type": "singleLineText"},
            {"name": "Stage Changed At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Days In Stage", "type": "number", "options": {"precision": 0}},
            {"name": "Owner", "type": "singleLineText"},
            {"name": "Notes", "type": "multilineText"},
            {"name": "Next Action", "type": "singleLineText"},
            {"name": "Next Action Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "LI_Feedback": {
        "description": "Outcome data and learning records",
        "primary_field": "Feedback ID",
        "fields": [
            {"name": "Lead ID", "type": "singleLineText"},
            {
                "name": "Outcome",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "No_Reply", "color": "grayBright"},
                        {"name": "Replied_Positive", "color": "greenBright"},
                        {"name": "Replied_Negative", "color": "redBright"},
                        {"name": "Meeting_Booked", "color": "blueBright"},
                        {"name": "Proposal_Sent", "color": "purpleBright"},
                        {"name": "Deal_Won", "color": "greenDark1"},
                        {"name": "Deal_Lost", "color": "redBright"},
                        {"name": "Nurture", "color": "yellowBright"},
                    ]
                },
            },
            {"name": "Revenue ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "Package Sold", "type": "singleLineText"},
            {"name": "Feedback Notes", "type": "multilineText"},
            {"name": "ICP Score At Contact", "type": "number", "options": {"precision": 0}},
            {"name": "Priority Band At Contact", "type": "singleLineText"},
            {"name": "Learning Insights", "type": "multilineText"},
            {"name": "Recorded At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "LI_Agent_Logs": {
        "description": "Agent execution logs for audit trail",
        "primary_field": "Log ID",
        "fields": [
            {"name": "Workflow", "type": "singleLineText"},
            {"name": "Lead ID", "type": "singleLineText"},
            {"name": "Action", "type": "singleLineText"},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Success", "color": "greenBright"},
                        {"name": "Failed", "color": "redBright"},
                        {"name": "Skipped", "color": "grayBright"},
                        {"name": "Rate_Limited", "color": "yellowBright"},
                    ]
                },
            },
            {"name": "Input Summary", "type": "multilineText"},
            {"name": "Output Summary", "type": "multilineText"},
            {"name": "Tokens Used", "type": "number", "options": {"precision": 0}},
            {"name": "Duration MS", "type": "number", "options": {"precision": 0}},
            {"name": "Error Message", "type": "multilineText"},
            {"name": "Execution ID", "type": "singleLineText"},
            {"name": "Timestamp", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
}

# ── Sample Data for Seeding ───────────────────────────────────

SEED_CAMPAIGNS = [
    {
        "Campaign Name": "SA SMB Decision Makers Q2 2026",
        "Status": "Draft",
        "ICP Titles": '["CEO", "COO", "CTO", "Managing Director", "Operations Director", "Marketing Director", "Head of Operations", "Founder"]',
        "ICP Industries": '["Professional Services", "Real Estate", "E-commerce", "Healthcare Admin", "Logistics", "Finance", "Hospitality", "Education", "Manufacturing", "Retail"]',
        "ICP Company Size": "10-500",
        "ICP Locations": '["Johannesburg", "Cape Town", "Durban", "Pretoria", "Gauteng", "Western Cape", "KwaZulu-Natal", "South Africa"]',
        "ICP Keywords": '["automation", "efficiency", "operations", "scaling", "digital transformation", "AI", "workflow", "CRM", "manual processes"]',
        "Red Flag Keywords": '["automation agency", "developer", "freelancer", "looking for work", "job seeking", "student", "intern"]',
        "Schedule": "Weekly_Monday",
        "Batch Size": 50,
        "Daily Action Limit": 200,
        "Hourly Rate Limit": 100,
        "Token Budget Daily": 30000,
    },
]


def create_table(
    client: httpx.Client,
    token: str,
    base_id: str,
    table_name: str,
    table_def: dict,
) -> tuple[str | None, int | str]:
    """Create a table with fields via Airtable API.

    Creates with a "Name" primary field then renames to the table-specific
    primary field name.

    Returns:
        (table_id, field_count) on success, or (None, error_msg) on failure.
    """
    payload = {
        "name": table_name,
        "description": table_def["description"],
        "fields": [
            {"name": "Name", "type": "singleLineText"},  # Primary field (required)
            *table_def["fields"],
        ],
    }

    resp = client.post(
        f"{AIRTABLE_META_API}/{base_id}/tables",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
    )

    if resp.status_code == 200:
        table_data = resp.json()
        table_id = table_data["id"]
        field_count = len(table_data.get("fields", []))

        # Rename primary field to table-specific name
        primary_name = table_def.get("primary_field", "Name")
        if primary_name != "Name":
            primary_field_id = table_data["fields"][0]["id"]
            rename_resp = client.patch(
                f"{AIRTABLE_META_API}/{base_id}/tables/{table_id}/fields/{primary_field_id}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"name": primary_name},
            )
            if rename_resp.status_code != 200:
                print(f"    Warning: Could not rename primary field: {rename_resp.status_code}")

        return table_id, field_count
    else:
        error_msg = resp.text[:200]
        return None, error_msg


def seed_campaigns(
    client: httpx.Client,
    token: str,
    base_id: str,
    table_id: str,
) -> int:
    """Seed campaigns table with initial campaign data.

    Returns:
        Number of records successfully created.
    """
    records = []
    for campaign in SEED_CAMPAIGNS:
        records.append({
            "fields": {
                "Campaign Name": campaign["Campaign Name"],
                "Status": campaign["Status"],
                "ICP Titles": campaign["ICP Titles"],
                "ICP Industries": campaign["ICP Industries"],
                "ICP Company Size": campaign["ICP Company Size"],
                "ICP Locations": campaign["ICP Locations"],
                "ICP Keywords": campaign["ICP Keywords"],
                "Red Flag Keywords": campaign["Red Flag Keywords"],
                "Schedule": campaign["Schedule"],
                "Batch Size": campaign["Batch Size"],
                "Daily Action Limit": campaign["Daily Action Limit"],
                "Hourly Rate Limit": campaign["Hourly Rate Limit"],
                "Token Budget Daily": campaign["Token Budget Daily"],
                "Created At": datetime.now().strftime("%Y-%m-%d"),
            }
        })

    resp = client.post(
        f"{AIRTABLE_API}/{base_id}/{table_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"records": records},
    )

    if resp.status_code == 200:
        return len(resp.json().get("records", []))
    else:
        print(f"    Seed error: {resp.status_code} - {resp.text[:200]}")
        return 0


def main() -> None:
    seed_mode = "--seed" in sys.argv

    print("=" * 60)
    print("LINKEDIN LEAD INTELLIGENCE - AIRTABLE SETUP")
    print("=" * 60)
    print()

    token = os.getenv("AIRTABLE_API_TOKEN")
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)

    base_id = MARKETING_BASE_ID
    if not base_id:
        print("ERROR: MARKETING_AIRTABLE_BASE_ID not set.")
        print()
        print("Steps to fix:")
        print("  1. Set MARKETING_AIRTABLE_BASE_ID in .env")
        print("  2. This should be the existing Marketing Department base ID")
        print("  3. The LinkedIn tables will be added to this base")
        sys.exit(1)

    print(f"Base ID: {base_id}")
    print(f"Tables to create: {len(TABLE_DEFINITIONS)}")
    print(f"Seed mode: {'ON' if seed_mode else 'OFF'}")
    print()

    client = httpx.Client(timeout=30)
    created_tables: dict[str, str] = {}

    # Create all tables
    print("Creating tables...")
    print("-" * 40)

    for table_name, table_def in TABLE_DEFINITIONS.items():
        table_id, result = create_table(client, token, base_id, table_name, table_def)
        if table_id:
            created_tables[table_name] = table_id
            print(f"  + {table_name:<35} -> {table_id} ({result} fields)")
        else:
            print(f"  - {table_name:<35} FAILED: {result}")

    print()

    # Seed data if requested
    if seed_mode and created_tables:
        print("Seeding data...")
        print("-" * 40)

        if "LI_Campaigns" in created_tables:
            count = seed_campaigns(client, token, base_id, created_tables["LI_Campaigns"])
            print(f"  + LI_Campaigns: {count} records seeded")

        print()

    client.close()

    # Summary
    print("=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print()
    print(f"Created: {len(created_tables)}/{len(TABLE_DEFINITIONS)} tables")
    print()

    if created_tables:
        print("Table IDs (add these to .env):")
        print("-" * 40)
        env_key_map = {
            "LI_Campaigns": "LI_TABLE_CAMPAIGNS",
            "LI_Leads": "LI_TABLE_LEADS",
            "LI_Enrichment": "LI_TABLE_ENRICHMENT",
            "LI_Scores": "LI_TABLE_SCORES",
            "LI_Pain_Points": "LI_TABLE_PAIN_POINTS",
            "LI_Automation_Opportunities": "LI_TABLE_OPPORTUNITIES",
            "LI_Outreach": "LI_TABLE_OUTREACH",
            "LI_Pipeline": "LI_TABLE_PIPELINE",
            "LI_Feedback": "LI_TABLE_FEEDBACK",
            "LI_Agent_Logs": "LI_TABLE_AGENT_LOGS",
        }
        for name, tid in created_tables.items():
            env_key = env_key_map.get(name, name.upper().replace(" ", "_"))
            print(f'  {env_key}={tid}')
        print()

        # Save to .tmp for reference
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "linkedin_airtable_ids.json"

        ids_data = {
            "base_id": base_id,
            "tables": {env_key_map.get(name, name): tid for name, tid in created_tables.items()},
            "created_at": datetime.now().isoformat(),
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ids_data, f, indent=2)
        print(f"Table IDs saved to: {output_path}")

    print()
    print("Next steps:")
    print("  1. Add the table IDs above to your .env file")
    print("  2. Update config.json with the linkedin_dept section")
    print("  3. Deploy LinkedIn Lead Intelligence workflows (LI-01 through LI-10)")


if __name__ == "__main__":
    main()
