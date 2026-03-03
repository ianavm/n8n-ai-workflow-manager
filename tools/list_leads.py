"""
List all leads from the Lead Scraper Airtable CRM.

Queries both possible Airtable bases and displays all emailed businesses
with their name, industry, email, lead score, and date scraped.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
import httpx

load_dotenv(Path(__file__).parent.parent / ".env")

AIRTABLE_TOKEN = os.getenv("AIRTABLE_API_TOKEN")
BASE_IDS = [
    os.getenv("AIRTABLE_BASE_ID", "appzcZpiIZ6QPtJXT"),
    "app2ALQUP7CKEkHOz",
]
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json",
}


def list_tables(base_id):
    """List all tables in a base."""
    r = httpx.get(
        f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
        headers=HEADERS,
        timeout=30,
    )
    if r.status_code != 200:
        return []
    return r.json().get("tables", [])


def fetch_all_records(base_id, table_id, filter_formula=None):
    """Fetch all records from a table with optional filter."""
    records = []
    offset = None
    params = {"pageSize": 100}
    if filter_formula:
        params["filterByFormula"] = filter_formula

    while True:
        if offset:
            params["offset"] = offset
        r = httpx.get(
            f"https://api.airtable.com/v0/{base_id}/{table_id}",
            headers=HEADERS,
            params=params,
            timeout=30,
        )
        if r.status_code != 200:
            print(f"  Error fetching records: {r.status_code} {r.text[:200]}")
            break
        data = r.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break

    return records


def find_leads_table(base_id):
    """Find the leads table in a base."""
    tables = list_tables(base_id)
    for t in tables:
        name = t["name"].lower()
        if "lead" in name or "scraper" in name or "crm" in name:
            return t["id"], t["name"]
    # Fallback: return first table
    if tables:
        return tables[0]["id"], tables[0]["name"]
    return None, None


def main():
    if not AIRTABLE_TOKEN:
        print("Error: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)

    all_leads = []

    for base_id in BASE_IDS:
        print(f"\nChecking base {base_id}...")
        table_id, table_name = find_leads_table(base_id)
        if not table_id:
            print(f"  No tables found in base {base_id}")
            continue

        print(f"  Found table: {table_name} ({table_id})")

        # Fetch all records (no filter first to see everything)
        records = fetch_all_records(base_id, table_id)
        print(f"  Total records: {len(records)}")

        for rec in records:
            fields = rec.get("fields", {})
            name = fields.get("Business Name", fields.get("businessName", ""))
            industry = fields.get("Industry", fields.get("industry", ""))
            email = fields.get("Email", fields.get("email", ""))
            status = fields.get("Status", fields.get("status", ""))
            score = fields.get("Lead Score", fields.get("leadScore", ""))
            date = fields.get("Date Scraped", fields.get("datescraped", ""))

            if name:
                all_leads.append({
                    "name": name,
                    "industry": industry,
                    "email": email,
                    "status": status,
                    "score": score,
                    "date": date,
                    "base": base_id,
                })

    if not all_leads:
        print("\nNo leads found in any base.")
        return

    # Separate emailed vs all
    emailed = [l for l in all_leads if l["status"] == "Email Sent"]
    print(f"\n{'='*90}")
    print(f"  LEAD SCRAPER - BUSINESS BREAKDOWN")
    print(f"  Total leads: {len(all_leads)} | Emailed: {len(emailed)}")
    print(f"{'='*90}")

    # Print all leads grouped by industry
    industries = {}
    for lead in all_leads:
        ind = lead["industry"] or "Unknown"
        industries.setdefault(ind, []).append(lead)

    for industry in sorted(industries.keys()):
        leads = industries[industry]
        print(f"\n  --- {industry} ({len(leads)} businesses) ---")
        for l in sorted(leads, key=lambda x: x.get("score", 0) or 0, reverse=True):
            status_icon = "[EMAILED]" if l["status"] == "Email Sent" else "[NEW]    "
            score_str = f"Score: {l['score']}" if l["score"] else ""
            print(f"    {status_icon} {l['name']:<40} {l['email']:<35} {score_str}")

    print(f"\n{'='*90}")


if __name__ == "__main__":
    main()
