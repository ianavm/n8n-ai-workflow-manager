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
    "LINKEDIN": "iCZCgD4UDdlRVmiN",   # LinkedIn lead gen, scoring & comms
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
