"""
Lead Research Pipeline - Job Listing to Client Opportunity Analyzer

Automates weekly discovery of AI/automation prospects by:
  1. Searching job boards via SerpAPI for automation-related listings
  2. Parsing results into structured lead records
  3. Using Claude AI (via OpenRouter) to analyze pain points and opportunities
  4. Saving results to Airtable (with CSV fallback)

Usage:
    python tools/lead_research.py search               # Search only, save raw results
    python tools/lead_research.py analyze               # Search + AI analysis
    python tools/lead_research.py report                # Search + analyze + summary report
    python tools/lead_research.py search --csv          # Force CSV output (skip Airtable)
    python tools/lead_research.py analyze --limit 5     # Analyze only first 5 results
"""

import json
import sys
import os
import csv
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
import httpx

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# -- Configuration -----------------------------------------------------------

SEARCH_QUERIES = [
    "remote n8n automation specialist hiring",
    "remote workflow automation engineer startup",
    "remote WhatsApp automation developer",
    "remote AI operations lead startup",
    "remote marketing automation specialist",
    "remote CRM automation specialist startup",
    "n8n automation expert freelance",
]

OPENROUTER_MODEL = "anthropic/claude-sonnet-4-20250514"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

ANALYSIS_PROMPT = """You are an AI automation consultant analyzing job listings to find
client opportunities for an AI automation agency (AnyVision Media).

The agency specializes in:
- n8n workflow automation
- AI-powered business process automation
- WhatsApp/email/CRM automation
- Marketing and SEO automation pipelines
- QuickBooks/accounting automation

Analyze this job listing and return a JSON object (no markdown, no code fences):

{{
  "company_name": "extracted or inferred company name",
  "pain_points": ["list of 2-4 hidden pain points this role reveals"],
  "automation_score": <1-10 integer, how strong the automation opportunity is>,
  "suggested_solution": "1-2 sentence description of what AnyVision could offer",
  "outreach_angle": "1-2 sentence personalized outreach hook",
  "tech_stack_overlap": ["list of overlapping technologies"],
  "deal_size_estimate": "small|medium|large based on role seniority and company size"
}}

Job listing:
Title: {title}
Company: {company}
Link: {link}
Description: {description}
"""

# -- Paths -------------------------------------------------------------------

TMP_DIR = Path(__file__).parent.parent / ".tmp" / "lead_research"
OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "lead-research"


# -- API Clients -------------------------------------------------------------

class SerpAPIClient:
    """Client for SerpAPI Google search."""

    BASE_URL = "https://serpapi.com/search"

    def __init__(self, api_key: str, timeout: int = 30):
        if not api_key:
            raise ValueError("SERPAPI_KEY is required")
        self.api_key = api_key
        self.client = httpx.Client(timeout=timeout)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def search(self, query: str, num_results: int = 10) -> List[Dict[str, Any]]:
        """
        Run a Google search via SerpAPI.

        Args:
            query: Search query string
            num_results: Number of results to request

        Returns:
            List of organic search result dicts
        """
        params = {
            "q": query,
            "api_key": self.api_key,
            "engine": "google",
            "num": num_results,
            "gl": "us",
            "hl": "en",
        }

        try:
            response = self.client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("organic_results", [])
        except httpx.HTTPStatusError as e:
            print(f"  SerpAPI error ({e.response.status_code}): {e.response.text[:200]}")
            return []
        except httpx.RequestError as e:
            print(f"  SerpAPI connection error: {e}")
            return []


class OpenRouterClient:
    """Client for OpenRouter AI completions."""

    def __init__(self, api_key: str, model: str = OPENROUTER_MODEL, timeout: int = 60):
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required")
        self.api_key = api_key
        self.model = model
        self.client = httpx.Client(timeout=timeout)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def analyze(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Send a prompt to Claude via OpenRouter and parse JSON response.

        Args:
            prompt: Full prompt string

        Returns:
            Parsed JSON dict or None on failure
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://anyvisionmedia.com",
            "X-Title": "AVM Lead Research",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1024,
        }

        try:
            response = self.client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"].strip()
            # Strip markdown code fences if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
            content = content.strip()

            return json.loads(content)

        except httpx.HTTPStatusError as e:
            print(f"  OpenRouter error ({e.response.status_code}): {e.response.text[:200]}")
            return None
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"  Failed to parse AI response: {e}")
            return None
        except httpx.RequestError as e:
            print(f"  OpenRouter connection error: {e}")
            return None


class AirtableClient:
    """Minimal Airtable client for lead storage."""

    BASE_URL = "https://api.airtable.com/v0"

    def __init__(self, api_token: str, base_id: str, table_name: str, timeout: int = 30):
        if not api_token:
            raise ValueError("AIRTABLE_API_TOKEN is required")
        if not base_id:
            raise ValueError("Airtable base ID is required")
        self.api_token = api_token
        self.base_id = base_id
        self.table_name = table_name
        self.client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
        )

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def create_record(self, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a single record in Airtable.

        Args:
            fields: Record field values

        Returns:
            Created record dict or None on failure
        """
        url = f"{self.BASE_URL}/{self.base_id}/{self.table_name}"
        payload = {"fields": fields}

        try:
            response = self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"  Airtable error ({e.response.status_code}): {e.response.text[:200]}")
            return None
        except httpx.RequestError as e:
            print(f"  Airtable connection error: {e}")
            return None

    def batch_create(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create records in batches of 10 (Airtable limit).

        Args:
            records: List of field dicts

        Returns:
            List of created record dicts
        """
        created = []
        url = f"{self.BASE_URL}/{self.base_id}/{self.table_name}"

        for i in range(0, len(records), 10):
            batch = records[i:i + 10]
            payload = {"records": [{"fields": r} for r in batch]}

            try:
                response = self.client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                created.extend(data.get("records", []))
            except httpx.HTTPStatusError as e:
                print(f"  Airtable batch error ({e.response.status_code}): {e.response.text[:200]}")
            except httpx.RequestError as e:
                print(f"  Airtable connection error: {e}")

            # Rate limit courtesy
            if i + 10 < len(records):
                time.sleep(0.25)

        return created


# -- Core Pipeline -----------------------------------------------------------

def generate_lead_id(title: str, link: str) -> str:
    """Generate a deterministic ID for deduplication."""
    raw = f"{title}|{link}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def search_listings(serp_client: SerpAPIClient, queries: List[str],
                    results_per_query: int = 10) -> List[Dict[str, Any]]:
    """
    Search multiple queries and return deduplicated listings.

    Args:
        serp_client: SerpAPI client instance
        queries: List of search query strings
        results_per_query: Max results per query

    Returns:
        Deduplicated list of lead dicts
    """
    seen_ids = set()
    leads = []

    for i, query in enumerate(queries, 1):
        print(f"  [{i}/{len(queries)}] Searching: {query}")
        results = serp_client.search(query, num_results=results_per_query)
        print(f"    -> {len(results)} results")

        for result in results:
            title = result.get("title", "").strip()
            link = result.get("link", "").strip()
            snippet = result.get("snippet", "").strip()

            if not title or not link:
                continue

            lead_id = generate_lead_id(title, link)
            if lead_id in seen_ids:
                continue
            seen_ids.add(lead_id)

            leads.append({
                "lead_id": lead_id,
                "title": title,
                "link": link,
                "snippet": snippet,
                "source_query": query,
                "company": _extract_company(title, link, snippet),
                "found_at": datetime.now().isoformat(),
            })

        # Rate limit courtesy between queries
        if i < len(queries):
            time.sleep(1)

    print(f"\n  Total unique leads: {len(leads)}")
    return leads


def _extract_company(title: str, link: str, snippet: str) -> str:
    """Best-effort company name extraction from listing metadata."""
    # Common job board patterns: "Role at Company" or "Role - Company"
    for sep in [" at ", " - ", " | ", " @ "]:
        if sep in title:
            parts = title.split(sep)
            if len(parts) >= 2:
                return parts[-1].strip()

    # Try domain extraction as fallback
    try:
        from urllib.parse import urlparse
        domain = urlparse(link).netloc
        # Remove www. and .com/.org etc
        parts = domain.replace("www.", "").split(".")
        if len(parts) >= 2:
            return parts[0].capitalize()
    except Exception:
        pass

    return "Unknown"


def analyze_listings(ai_client: OpenRouterClient,
                     leads: List[Dict[str, Any]],
                     limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Run AI analysis on each lead to score automation opportunity.

    Args:
        ai_client: OpenRouter client instance
        leads: List of lead dicts from search phase
        limit: Max number of leads to analyze (None = all)

    Returns:
        List of leads enriched with AI analysis
    """
    to_analyze = leads[:limit] if limit else leads
    analyzed = []

    for i, lead in enumerate(to_analyze, 1):
        print(f"  [{i}/{len(to_analyze)}] Analyzing: {lead['title'][:60]}...")

        prompt = ANALYSIS_PROMPT.format(
            title=lead["title"],
            company=lead["company"],
            link=lead["link"],
            description=lead["snippet"],
        )

        analysis = ai_client.analyze(prompt)

        if analysis:
            enriched = {**lead, "analysis": analysis}
            analyzed.append(enriched)
            score = analysis.get("automation_score", "?")
            print(f"    -> Score: {score}/10 | {analysis.get('deal_size_estimate', '?')}")
        else:
            print(f"    -> Analysis failed, keeping raw lead")
            analyzed.append({**lead, "analysis": None})

        # Rate limit courtesy between AI calls
        if i < len(to_analyze):
            time.sleep(0.5)

    return analyzed


def generate_report(leads: List[Dict[str, Any]]) -> str:
    """
    Generate a text summary report of analyzed leads.

    Args:
        leads: List of analyzed lead dicts

    Returns:
        Formatted report string
    """
    analyzed = [l for l in leads if l.get("analysis")]
    unanalyzed = [l for l in leads if not l.get("analysis")]

    # Sort by automation score descending
    analyzed.sort(
        key=lambda x: x.get("analysis", {}).get("automation_score", 0),
        reverse=True,
    )

    lines = [
        "=" * 70,
        "LEAD RESEARCH REPORT",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 70,
        "",
        f"Total leads found: {len(leads)}",
        f"Successfully analyzed: {len(analyzed)}",
        f"Analysis failed: {len(unanalyzed)}",
        "",
    ]

    # Top opportunities
    top = [l for l in analyzed if l["analysis"].get("automation_score", 0) >= 7]
    if top:
        lines.append("-" * 70)
        lines.append(f"TOP OPPORTUNITIES (score >= 7): {len(top)}")
        lines.append("-" * 70)
        for lead in top:
            a = lead["analysis"]
            lines.append(f"\n  Company: {a.get('company_name', lead['company'])}")
            lines.append(f"  Title: {lead['title']}")
            lines.append(f"  Score: {a['automation_score']}/10 | Size: {a.get('deal_size_estimate', '?')}")
            lines.append(f"  Solution: {a.get('suggested_solution', 'N/A')}")
            lines.append(f"  Outreach: {a.get('outreach_angle', 'N/A')}")
            lines.append(f"  Link: {lead['link']}")
            pain = ", ".join(a.get("pain_points", []))
            if pain:
                lines.append(f"  Pain points: {pain}")

    # Medium opportunities
    medium = [l for l in analyzed if 4 <= l["analysis"].get("automation_score", 0) < 7]
    if medium:
        lines.append("")
        lines.append("-" * 70)
        lines.append(f"MEDIUM OPPORTUNITIES (score 4-6): {len(medium)}")
        lines.append("-" * 70)
        for lead in medium:
            a = lead["analysis"]
            lines.append(f"\n  {a.get('company_name', lead['company'])} "
                         f"| Score: {a['automation_score']}/10 "
                         f"| {a.get('suggested_solution', 'N/A')[:80]}")

    # Low opportunities
    low = [l for l in analyzed if l["analysis"].get("automation_score", 0) < 4]
    if low:
        lines.append("")
        lines.append(f"\nLow-priority leads (score < 4): {len(low)} (omitted from report)")

    lines.append("")
    lines.append("=" * 70)
    lines.append("END OF REPORT")
    lines.append("=" * 70)

    return "\n".join(lines)


# -- Storage -----------------------------------------------------------------

def save_to_csv(leads: List[Dict[str, Any]], filepath: Path) -> Path:
    """
    Save leads to CSV file.

    Args:
        leads: List of lead dicts (possibly with analysis)
        filepath: Output CSV path

    Returns:
        Path to saved file
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "lead_id", "title", "company", "link", "snippet", "source_query",
        "found_at", "automation_score", "deal_size_estimate",
        "suggested_solution", "outreach_angle", "pain_points",
        "tech_stack_overlap",
    ]

    rows = []
    for lead in leads:
        analysis = lead.get("analysis") or {}
        row = {
            "lead_id": lead.get("lead_id", ""),
            "title": lead.get("title", ""),
            "company": analysis.get("company_name", lead.get("company", "")),
            "link": lead.get("link", ""),
            "snippet": lead.get("snippet", ""),
            "source_query": lead.get("source_query", ""),
            "found_at": lead.get("found_at", ""),
            "automation_score": analysis.get("automation_score", ""),
            "deal_size_estimate": analysis.get("deal_size_estimate", ""),
            "suggested_solution": analysis.get("suggested_solution", ""),
            "outreach_angle": analysis.get("outreach_angle", ""),
            "pain_points": "; ".join(analysis.get("pain_points", [])),
            "tech_stack_overlap": "; ".join(analysis.get("tech_stack_overlap", [])),
        }
        rows.append(row)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Saved {len(rows)} leads to {filepath}")
    return filepath


def save_to_airtable(leads: List[Dict[str, Any]],
                     airtable_client: AirtableClient) -> int:
    """
    Save analyzed leads to Airtable.

    Args:
        leads: List of lead dicts with analysis
        airtable_client: Airtable client instance

    Returns:
        Number of records created
    """
    records = []
    for lead in leads:
        analysis = lead.get("analysis") or {}
        fields = {
            "Lead ID": lead.get("lead_id", ""),
            "Title": lead.get("title", "")[:255],
            "Company": analysis.get("company_name", lead.get("company", ""))[:255],
            "Link": lead.get("link", ""),
            "Snippet": lead.get("snippet", "")[:1000],
            "Source Query": lead.get("source_query", "")[:255],
            "Found At": lead.get("found_at", ""),
            "Automation Score": analysis.get("automation_score"),
            "Deal Size": analysis.get("deal_size_estimate", ""),
            "Suggested Solution": analysis.get("suggested_solution", "")[:1000],
            "Outreach Angle": analysis.get("outreach_angle", "")[:1000],
            "Pain Points": "; ".join(analysis.get("pain_points", []))[:1000],
            "Tech Overlap": "; ".join(analysis.get("tech_stack_overlap", []))[:255],
        }
        records.append(fields)

    created = airtable_client.batch_create(records)
    print(f"  Created {len(created)} records in Airtable")
    return len(created)


def save_json(data: Any, filepath: Path) -> Path:
    """Save data as JSON with metadata."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "generated_at": datetime.now().isoformat(),
        "count": len(data) if isinstance(data, list) else 1,
        "data": data,
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  Saved JSON to {filepath}")
    return filepath


# -- CLI Commands ------------------------------------------------------------

def cmd_search(args) -> int:
    """Search job boards and save raw results."""
    print("=" * 60)
    print("LEAD RESEARCH - SEARCH")
    print("=" * 60)

    serpapi_key = os.getenv("SERPAPI_KEY")
    if not serpapi_key:
        print("\n  ERROR: SERPAPI_KEY not found in .env")
        print("  Add SERPAPI_KEY=your_key to your .env file")
        return 1

    start_time = time.time()

    print(f"\n[1/2] Searching {len(SEARCH_QUERIES)} queries...")
    print("-" * 60)

    with SerpAPIClient(serpapi_key) as serp:
        leads = search_listings(serp, SEARCH_QUERIES, results_per_query=10)

    if not leads:
        print("\n  No leads found. Check SerpAPI key and network.")
        return 1

    print(f"\n[2/2] Saving results...")
    print("-" * 60)

    # Always save JSON
    json_path = TMP_DIR / f"search_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    save_json(leads, json_path)

    # Save CSV
    csv_path = TMP_DIR / f"search_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    save_to_csv(leads, csv_path)

    elapsed = time.time() - start_time
    print(f"\n  Search complete ({elapsed:.1f}s)")
    print(f"  Found {len(leads)} unique leads")
    return 0


def cmd_analyze(args) -> int:
    """Search + AI analysis of each listing."""
    print("=" * 60)
    print("LEAD RESEARCH - ANALYZE")
    print("=" * 60)

    serpapi_key = os.getenv("SERPAPI_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    if not serpapi_key:
        print("\n  ERROR: SERPAPI_KEY not found in .env")
        return 1
    if not openrouter_key:
        print("\n  ERROR: OPENROUTER_API_KEY not found in .env")
        return 1

    start_time = time.time()
    limit = getattr(args, "limit", None)

    # Step 1: Search
    print(f"\n[1/3] Searching {len(SEARCH_QUERIES)} queries...")
    print("-" * 60)

    with SerpAPIClient(serpapi_key) as serp:
        leads = search_listings(serp, SEARCH_QUERIES, results_per_query=10)

    if not leads:
        print("\n  No leads found. Check SerpAPI key and network.")
        return 1

    # Step 2: Analyze
    print(f"\n[2/3] Analyzing leads with AI...")
    print("-" * 60)

    with OpenRouterClient(openrouter_key) as ai:
        analyzed = analyze_listings(ai, leads, limit=limit)

    # Step 3: Save
    print(f"\n[3/3] Saving results...")
    print("-" * 60)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    json_path = TMP_DIR / f"analyzed_{timestamp}.json"
    save_json(analyzed, json_path)

    csv_path = TMP_DIR / f"analyzed_{timestamp}.csv"
    save_to_csv(analyzed, csv_path)

    # Try Airtable if not forced CSV
    use_csv = getattr(args, "csv", False)
    if not use_csv:
        airtable_token = os.getenv("AIRTABLE_API_TOKEN")
        airtable_base = os.getenv("LEAD_RESEARCH_AIRTABLE_BASE", os.getenv("AIRTABLE_LEAD_SCRAPER_BASE", ""))
        airtable_table = os.getenv("LEAD_RESEARCH_AIRTABLE_TABLE", "Lead Research")

        if airtable_token and airtable_base:
            try:
                with AirtableClient(airtable_token, airtable_base, airtable_table) as at:
                    save_to_airtable(analyzed, at)
            except Exception as e:
                print(f"  Airtable save failed: {e}")
                print(f"  Results still saved to CSV: {csv_path}")
        else:
            print("  Airtable not configured (set LEAD_RESEARCH_AIRTABLE_BASE in .env)")
            print(f"  Results saved to CSV: {csv_path}")

    elapsed = time.time() - start_time
    scored = [l for l in analyzed if l.get("analysis")]
    print(f"\n  Analysis complete ({elapsed:.1f}s)")
    print(f"  Analyzed: {len(scored)}/{len(leads)} leads")
    return 0


def cmd_report(args) -> int:
    """Search + analyze + generate summary report."""
    print("=" * 60)
    print("LEAD RESEARCH - FULL REPORT")
    print("=" * 60)

    serpapi_key = os.getenv("SERPAPI_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    if not serpapi_key:
        print("\n  ERROR: SERPAPI_KEY not found in .env")
        return 1
    if not openrouter_key:
        print("\n  ERROR: OPENROUTER_API_KEY not found in .env")
        return 1

    start_time = time.time()
    limit = getattr(args, "limit", None)

    # Step 1: Search
    print(f"\n[1/4] Searching {len(SEARCH_QUERIES)} queries...")
    print("-" * 60)

    with SerpAPIClient(serpapi_key) as serp:
        leads = search_listings(serp, SEARCH_QUERIES, results_per_query=10)

    if not leads:
        print("\n  No leads found.")
        return 1

    # Step 2: Analyze
    print(f"\n[2/4] Analyzing leads with AI...")
    print("-" * 60)

    with OpenRouterClient(openrouter_key) as ai:
        analyzed = analyze_listings(ai, leads, limit=limit)

    # Step 3: Save data
    print(f"\n[3/4] Saving data...")
    print("-" * 60)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    json_path = TMP_DIR / f"report_{timestamp}.json"
    save_json(analyzed, json_path)

    csv_path = TMP_DIR / f"report_{timestamp}.csv"
    save_to_csv(analyzed, csv_path)

    # Try Airtable
    use_csv = getattr(args, "csv", False)
    if not use_csv:
        airtable_token = os.getenv("AIRTABLE_API_TOKEN")
        airtable_base = os.getenv("LEAD_RESEARCH_AIRTABLE_BASE", os.getenv("AIRTABLE_LEAD_SCRAPER_BASE", ""))
        airtable_table = os.getenv("LEAD_RESEARCH_AIRTABLE_TABLE", "Lead Research")

        if airtable_token and airtable_base:
            try:
                with AirtableClient(airtable_token, airtable_base, airtable_table) as at:
                    save_to_airtable(analyzed, at)
            except Exception as e:
                print(f"  Airtable save failed: {e}")

    # Step 4: Generate report
    print(f"\n[4/4] Generating report...")
    print("-" * 60)

    report = generate_report(analyzed)

    report_path = TMP_DIR / f"report_{timestamp}.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n  Report saved to {report_path}")
    print("")
    print(report)

    elapsed = time.time() - start_time
    print(f"\n  Full pipeline complete ({elapsed:.1f}s)")
    return 0


# -- Main --------------------------------------------------------------------

def main():
    """Main entry point with CLI argument parsing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Lead Research Pipeline - Job listing to client opportunity analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/lead_research.py search              # Search only
  python tools/lead_research.py analyze              # Search + AI analysis
  python tools/lead_research.py report               # Full pipeline with report
  python tools/lead_research.py analyze --limit 5    # Analyze only 5 leads
  python tools/lead_research.py search --csv         # Force CSV (skip Airtable)
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Pipeline mode")

    # search
    sp_search = subparsers.add_parser("search", help="Search job boards for leads")
    sp_search.add_argument("--csv", action="store_true", help="Force CSV output")

    # analyze
    sp_analyze = subparsers.add_parser("analyze", help="Search + AI analysis")
    sp_analyze.add_argument("--limit", type=int, default=None,
                            help="Max leads to analyze")
    sp_analyze.add_argument("--csv", action="store_true", help="Force CSV output")

    # report
    sp_report = subparsers.add_parser("report", help="Full pipeline with report")
    sp_report.add_argument("--limit", type=int, default=None,
                           help="Max leads to analyze")
    sp_report.add_argument("--csv", action="store_true", help="Force CSV output")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "search": cmd_search,
        "analyze": cmd_analyze,
        "report": cmd_report,
    }

    try:
        exit_code = commands[args.command](args)
        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\n\n  Interrupted by user")
        sys.exit(1)

    except Exception as e:
        print(f"\n  Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
