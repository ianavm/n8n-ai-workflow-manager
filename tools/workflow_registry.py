"""
Registry of deployed n8n workflow IDs.

Single source of truth for workflow references across all tools and scripts.
Update this file whenever a workflow is deployed or redeployed with a new ID.

Usage:
    from workflow_registry import WORKFLOWS, get_id

    wf_id = get_id("ACC_WF01")  # -> "twSg4SfNdlmdITHj"
    wf_id = WORKFLOWS["SEO_WF05"]  # -> "5XZFaoQxfyJOlqje"
"""

WORKFLOWS = {
    # ============================================================
    # Accounting Department (7 workflows)
    # ============================================================
    "ACC_WF01": "twSg4SfNdlmdITHj",   # Invoice Processing
    "ACC_WF02": "CWQ9zjCTaf56RBe6",   # Collections & Follow-up
    "ACC_WF03": "ygwBtSysINRWHJxB",   # Payments & Reconciliation
    "ACC_WF04": "ZEcxIC9M5ehQvsbg",   # Supplier Bills
    "ACC_WF05": "f0Wh4SOxbODbs4TE",   # Month-End Close
    "ACC_WF06": "gwMuSElYqDTRGFKa",   # Audit Trail & Compliance
    "ACC_WF07": "EmpOzaaDGqsLvg5j",   # Exception Handling

    # ============================================================
    # SEO + Social Growth Engine (8 workflows + scoring)
    # ============================================================
    "SEO_SCORE": "0US5H9smGsrCUsv7",  # Scoring Engine (sub-workflow)
    "SEO_WF05": "5XZFaoQxfyJOlqje",   # Trend Discovery
    "SEO_WF06": "ipsnBC5Xox4DWgBg",   # SEO Content Production
    "SEO_WF07": "u7LSuq6zmAY8P7fU",   # Publishing
    "SEO_WF08": "M67NBeAEHfDIJ9wz",   # Engagement Monitoring
    "SEO_WF09": "BpZ4LkxKjHoGfjUq",   # Lead Capture (webhook)
    "SEO_WF10": "Xlu3tGHgM5DDXnkl",   # SEO Maintenance
    "SEO_WF11": "Y80dDSmWQfUlfvib",   # Analytics & Reporting

    # ============================================================
    # Bridge Integration (4 workflows)
    # ============================================================
    "BRIDGE_01": "IqODyj5suLusrkIx",  # Lead Sync (Scraper -> SEO)
    "BRIDGE_02": "tOT9DtpE8DspXSjm",  # Email Reply Matcher
    "BRIDGE_03": "0ynfcpEwHrPaghTl",  # Unified Scoring
    "BRIDGE_04": "OlHyOU8mHxJ1uZuc",  # Warm Lead Nurture

    # ============================================================
    # Document Intake System (4 workflows + combined)
    # ============================================================
    "DI_WF01": "vmgo05EB23oxrzdJ",    # Email Intake + Raw Storage
    "DI_WF02": "DGOHBQdheEqkIazg",    # Document Processing (sub-workflow)
    "DI_WF03": "ke6GEKchjJdTtyY7",    # Review Queue & Approval
    "DI_WF04": "fBGm2ZpHpmixBVNi",    # Daily Summary & Notifications
    "DI_COMBINED": "iHELQBAfDKBxNYgV", # Combined Intake Pipeline

    # ============================================================
    # LinkedIn Lead Generation
    # ============================================================
    # ============================================================
    # AVM Orchestrator (4 workflows)
    # ============================================================
    "ORCH_01": "5XR7j7hQ8cdWpi1e",    # Health Monitor (every 15 min)
    "ORCH_02": "47CJmRKTh9kPZ7u5",    # Cross-Dept Event Router
    "ORCH_03": "JDrgcv5iNIXLyQfs",    # Daily KPI Aggregation
    "ORCH_04": "2gXlFqBtOoReQfaT",    # Weekly Executive Report

    # ============================================================
    # Intelligence & Optimization (5 workflows)
    # ============================================================
    "INTEL_01": "P9NgW8csqbCh817f",    # Cross-Dept Correlator
    "INTEL_02": "Fmut5pJ4fVXIfxke",    # Executive Intelligence Report
    "INTEL_03": "hSiIZJu5bgDIOCDO",    # Prompt Performance Tracker
    "OPT_01": "Rsyz1BHai3q94wPI",      # A/B Test Manager
    "OPT_02": "I37U9l1kOcsr8fpP",      # A/B Test Analyzer

    # ============================================================
    # Ads Department (8 workflows + 2 support workflows)
    # ============================================================
    "ADS_01": "mrzwNb9Eul9Lq2uM",     # Strategy Generator
    "ADS_02": "7BBjmuvwF1l8DMQX",     # Copy & Creative Generator
    "ADS_03": "oEZIqJ81NXOb3jix",     # Campaign Builder (INACTIVE - Google Ads CUSTOMER_NOT_ENABLED)
    "ADS_04": "rIYu0FHFx741ml8d",     # Performance Monitor
    "ADS_05": "cfDyiFLx0X89s3VL",     # Optimization Engine
    "ADS_06": "bXxRU6rBC4kKw8bZ",     # Creative Recycler
    "ADS_07": "HkhBl7f69GckvEpY",     # Attribution Engine
    "ADS_08": "m8Kjjiy9jwliykOo",     # Reporting Dashboard
    "ADS_ERR": "L915QaaJuo6au7Oe",    # Error Handler
    "ADS_SHM": "5k1OKJuaAWVPf7Lb",    # Self-Healing Monitor

    # ============================================================
    # Support (4 workflows)
    # ============================================================
    "SUP_01": "Pk0B97gW8xtcgHBf",     # Ticket Creator
    "SUP_02": "EnnsJg43EazmEHJl",     # SLA Monitor
    "SUP_03": "HnmuFSsdx7hasPcI",     # Auto-Resolver
    "SUP_04": "3CQqDNDtgLJi2ZUu",     # KB Builder

    # ============================================================
    # Client Relations (4 workflows)
    # ============================================================
    "CR_01": "5Qzbyar2VTIbAuEo",      # Client Health Scorer
    "CR_02": "3ZzWEUmgVNIxNmx3",      # Renewal Manager
    "CR_03": "e1ufCH2KvuvrBQPm",      # Onboarding Automation
    "CR_04": "fOygygjEdwAyf5of",      # Satisfaction Pulse

    # ============================================================
    # Finance Agent (2 workflows)
    # ============================================================
    "FIN_08": "3Gb4pWJhsf2aHhsW",     # Cash Flow Forecast
    "FIN_09": "6bo7BSssN6SQeodg",     # Anomaly Detector

    # ============================================================
    # WhatsApp Agent (3 workflows)
    # ============================================================
    "WA_01": "YBxMfFdFb7BCUxzi",      # Conversation Analyzer
    "WA_02": "phF5vteIF4y6Tevt",      # CRM Sync
    "WA_03": "6C9PPWe4IWoUhjq2",      # Issue Detector

    # ============================================================
    # Self-Healing (1 workflow)
    # ============================================================
    "SELF_HEALING": "EyLZIilcnAidOv7R",  # Self-Healing Error Monitor

    # ============================================================
    # RE Operations (19 workflows)
    # ============================================================
    "RE_01": "GEVrxiSWmmlxAaH0",      # WhatsApp Intake
    "RE_02": "cPJnLkWpPrgJkSS6",      # Lead Router
    "RE_03": "E5KOoMCK5E9EGoK5",      # WhatsApp AI Comms
    "RE_04": "qLGbpfJf8DA1NXg3",      # Email AI Comms
    "RE_05": "tsJsDqaXKajM4Ji4",      # Booking Coordinator
    "RE_06": "1yyPXJbYXJc9R3W6",      # Document Classifier
    "RE_07": "qpZlTfgUuRsnBQFw",      # Email Intake
    "RE_08": "deajJpSeUQqKhvEb",      # Document Filing
    "RE_09": "KGc5cpmCHYbPaOgO",      # Telegram Command Hub
    "RE_10": "HC1VNZrZqARCXnZJ",      # Team Notifications
    "RE_11": "4HnNBzw00rkdc2rR",      # Daily Summary
    "RE_12": "DU4UaP6HSVxdydAk",      # Agent Performance
    "RE_13": "HFclWELoCQDC4qEO",      # Stale Lead Follow-up
    "RE_14": "gYfJuJh6WPbKJHwx",      # Escalation Engine
    "RE_15": "T0UJYKCsfeaa5lE8",      # Scoring Engine
    "RE_16": "HnFI6dKPXDJFMsVP",      # Assignment Engine
    "RE_17": "APCxVRECbsa1xbH0",      # Orchestrator Monitor
    "RE_18": "MfGMU3RLTepoiQEV",      # Telegram Alert Router
    "RE_19": "IxC9jNsGeU7Fonoh",      # Document Pack Sender

    # ============================================================
    # NEW AGENTS - Market Intelligence (3 workflows)
    # ============================================================
    "INTEL_04": "gijDxxcJjHMHnaUn",   # Daily Competitive Scan
    "INTEL_05": "S7sUARwMIijtPeRf",   # Weekly Market Digest
    "INTEL_06": "sbEwotSVpnyqrQtG",   # Regulatory Alert

    # ============================================================
    # NEW AGENTS - Knowledge Manager (3 workflows)
    # ============================================================
    "KM_01": "yl6JUOIkQstPhGQp",      # Document Indexer
    "KM_02": "Nw5LtlkQZGc3tDJF",      # Contradiction Detector
    "KM_03": "85BvMeuhsc7jCMlw",      # FAQ Generator

    # ============================================================
    # NEW AGENTS - QA Agent (3 workflows)
    # ============================================================
    "QA_01": "oWZ6VTwbYOflPAMS",      # Daily Smoke Test
    "QA_02": "0LdRipyCFSBe4k0k",      # Weekly Regression Suite
    "QA_03": "N0VEU3RHsq3OIoqR",      # Performance Benchmark

    # ============================================================
    # NEW AGENTS - Financial Intelligence (4 workflows)
    # ============================================================
    "FINTEL_01": "mywOowwRhK3ovV8R",  # Monthly Payroll Run
    "FINTEL_02": "OgLBLCZyQuV1wgEG",  # Quarterly VAT Prep
    "FINTEL_03": "wEXsboGxGfRlEDEH",  # Cash Flow Scenarios
    "FINTEL_04": "1XYu0y0DMH1c8JX9",  # Smart Payment Scheduler

    # ============================================================
    # NEW AGENTS - CRM Sync (3 workflows)
    # ============================================================
    "CRM_01": "EiuQcBeQG7AVcbYE",     # Hourly Sync
    "CRM_02": "Up3ROwbRMHVjZhvc",     # Nightly Dedup
    "CRM_03": "BtOSWQwrhGweBDK9",     # Weekly Enrichment

    # ============================================================
    # NEW AGENTS - Data Analyst (3 workflows)
    # ============================================================
    "DATA_01": "6gzRYYhAIv08cvIK",    # On-Demand Query Agent
    "DATA_02": "oMFz2y6ntoqcYxkZ",    # Daily Trend Dashboard
    "DATA_03": "U1PM6yCbbEE8I6YH",    # Monthly Report Automation

    # ============================================================
    # NEW AGENTS - Brand Guardian (3 workflows)
    # ============================================================
    "BRAND_01": "50nJrGBGaqgmT7pr",   # Pre-Publish Gate
    "BRAND_02": "aLyEUA8r08NvSRUk",   # Weekly Brand Audit
    "BRAND_03": "f3TES6QXLW5VQNHA",   # Competitor Differentiation

    # ============================================================
    # NEW AGENTS - DevOps Coordinator (3 workflows)
    # ============================================================
    "DEVOPS_01": "4Aqa5MYibl3sJufj",  # Auto-Deploy Monitor
    "DEVOPS_02": "VuBUg4r0BLL81KIF",  # Credential Rotation Alert
    "DEVOPS_03": "sCx9folUZZHBjT9K",  # Release Notes Generator

    # ============================================================
    # NEW AGENTS - Compliance Auditor (3 workflows)
    # ============================================================
    "COMPLY_01": "LUu04DSW25dOmWIY",  # Monthly Compliance Scan
    "COMPLY_02": "EXnkfN49D36P9LFE",  # Ad Policy Check
    "COMPLY_03": "wNUidyYs4cslPT0W",  # POPIA Audit

    # ============================================================
    # NEW AGENTS - Booking Assistant (3 workflows)
    # ============================================================
    "BOOK_01": "OnO0pefXoNWWtp7L",    # Meeting Scheduler
    "BOOK_02": "yIQe9s8RVdMs91oo",    # Follow-Up Nudge
    "BOOK_03": "TKhl6Oyn7Nx4L9kr",    # Calendar Optimizer

    # ============================================================
    # NEW AGENTS - Data Curator (3 workflows)
    # ============================================================
    "CURE_01": "mYMT5IxJUl9TPMcV",    # Nightly Dedup Scan
    "CURE_02": "pbEVUg4fMNmFtaUZ",    # Weekly Quality Report
    "CURE_03": "qortQbQC3sEz7YeN",    # Monthly Schema Audit

    # ============================================================
    # Churn Predictor
    # ============================================================
    "OPT_03": "TPp402GuDxnruRd2",      # Churn Predictor

    # ============================================================
    # Email Suppression
    # ============================================================
    "EMAIL_SUPPRESSION": "foWQmkUEt79vGZXO",  # Email Suppression Check (sub-workflow)
}


def get_id(key):
    """Get workflow ID by registry key.

    Args:
        key: Registry key (e.g., "ACC_WF01", "SEO_WF05")

    Returns:
        Workflow ID string or None if not found.
    """
    return WORKFLOWS.get(key)


def get_ids_by_prefix(prefix):
    """Get all workflow IDs matching a prefix.

    Args:
        prefix: Key prefix (e.g., "ACC", "SEO", "BRIDGE", "DI")

    Returns:
        Dict of matching key -> workflow ID pairs.
    """
    return {k: v for k, v in WORKFLOWS.items() if k.startswith(prefix)}


def list_all():
    """Print all registered workflows."""
    for key, wf_id in WORKFLOWS.items():
        print(f"  {key:20s} -> {wf_id}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        prefix = sys.argv[1].upper()
        matches = get_ids_by_prefix(prefix)
        if matches:
            for key, wf_id in matches.items():
                print(f"  {key:20s} -> {wf_id}")
        else:
            print(f"No workflows matching prefix '{prefix}'")
    else:
        print("All registered workflows:")
        list_all()
