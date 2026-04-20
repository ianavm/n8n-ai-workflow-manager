"""Generate a CSV of the 7 Tier 2 priority candidates for Airtable bulk import.

Outputs `workflows/linkedin-dept/tier2-import.csv` — drag-drop into Airtable's
`LI_Leads` table via the UI (Add records → Import data → CSV).

Airtable CSV import does NOT count against the monthly API quota, so this
path works even when API billing limit is exceeded.

Usage:
    python tools/generate_tier2_csv.py
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("csv_gen")

OUTPUT = Path(__file__).parent.parent / "workflows" / "linkedin-dept" / "tier2-import.csv"

FIELDS = [
    "Lead ID",
    "Full Name",
    "First Name",
    "Last Name",
    "Title",
    "Company Name",
    "Industry",
    "Location",
    "LinkedIn URL",
    "Company Website",
    "Employee Count",
    "Source",
    "Status",
    "POPIA Consent",
    "Source Metadata",
]


def meta(**kwargs) -> str:
    return json.dumps(kwargs, separators=(",", ":"))


RECORDS = [
    {
        "Lead ID": "LI-PRIORITY-T2-011",
        "Full Name": "James Paterson",
        "First Name": "James",
        "Last Name": "Paterson",
        "Title": "Co-Founder & CEO",
        "Company Name": "Aerobotics",
        "Industry": "Agritech (AI + drones for fruit/nut crops)",
        "Location": "Cape Town, South Africa",
        "LinkedIn URL": "https://www.linkedin.com/in/james-paterson-5735a8123/",
        "Company Website": "https://www.aerobotics.com",
        "Employee Count": "85-150",
        "Source": "CSV_Upload",
        "Status": "New",
        "POPIA Consent": "Pending",
        "Source Metadata": meta(
            tier=2,
            priority=True,
            motion="cold_outreach",
            urgency="medium",
            co_founder="Benji Meltzer (CTO)",
            education="MIT - Aeronautical Engineering masters",
            funding="$17M Series B Dec 2024",
            scale="85+ team, global fruit growers",
            hook="scaling_team_needs_ops_tooling",
            pain_hypothesis="Data science team on core ML - ops tooling (farmer onboarding, report gen, competitor intel) underinvested",
            pitch_angle="MIT technical founder - engineering specifics not AI hype",
            verification_needed=["recent_post", "email"],
        ),
    },
    {
        "Lead ID": "LI-PRIORITY-T2-012",
        "Full Name": "Russel Luck",
        "First Name": "Russel",
        "Last Name": "Luck",
        "Title": "Founder & CEO",
        "Company Name": "SwiftVEE",
        "Industry": "Agritech (Livestock Trading Platform)",
        "Location": "South Africa",
        "LinkedIn URL": "https://www.linkedin.com/in/russel1tech1law1/",
        "Company Website": "https://www.swiftvee.com",
        "Employee Count": "20-50",
        "Source": "CSV_Upload",
        "Status": "New",
        "POPIA Consent": "Pending",
        "Source Metadata": meta(
            tier=2,
            priority=True,
            motion="cold_outreach",
            urgency="high",
            founder_background="Tech lawyer turned farming entrepreneur - UCT Law + UNISA ICT Law LLM",
            funding="R173M Series A Dec 2025 (HAVAIC, Exeo Capital, Iain Williamson)",
            scale="$100M+ annual livestock traded",
            backers_notable="Google-backed",
            hook="scaling_series_a_tooling_gap",
            pain_hypothesis="Just closed R173M - scaling = tooling gap. Valuation prediction models, farmer sentiment monitoring, competitor auction tracking.",
            pitch_angle="Lawyer founder - systems + contracts language. Data pipelines not AI.",
            verification_needed=["recent_post", "email"],
        ),
    },
    {
        "Lead ID": "LI-PRIORITY-T2-013",
        "Full Name": "Alex Thomson",
        "First Name": "Alex",
        "Last Name": "Thomson",
        "Title": "Co-Founder",
        "Company Name": "Naked Insurance",
        "Industry": "Insurtech (AI-based consumer insurance)",
        "Location": "South Africa",
        "LinkedIn URL": "https://za.linkedin.com/in/alex-thomson-09404710",
        "Company Website": "https://www.naked.insure",
        "Employee Count": "50-150",
        "Source": "CSV_Upload",
        "Status": "New",
        "POPIA Consent": "Pending",
        "Source Metadata": meta(
            tier=2,
            priority=True,
            motion="cold_outreach",
            urgency="medium",
            co_founders=["Sumarie Greybe", "Ernest North"],
            all_actuaries=True,
            funding="R290M total incl R160M Naspers Series A",
            hook="ai_native_needs_data_infrastructure",
            pain_hypothesis="AI-native - they have AI. They need DATA. Claims fraud pattern scraping, competitor pricing, social sentiment.",
            pitch_angle="Actuary - probabilities + data quality. Not AI, DATA SOURCES.",
            verification_needed=["recent_post", "email"],
        ),
    },
    {
        "Lead ID": "LI-PRIORITY-T2-014",
        "Full Name": "Louw Hopley",
        "First Name": "Louw",
        "Last Name": "Hopley",
        "Title": "Co-Founder & CEO",
        "Company Name": "Root Platform",
        "Industry": "Insurtech (API / Embedded Insurance)",
        "Location": "Cape Town + London",
        "LinkedIn URL": "https://za.linkedin.com/in/louwhopley",
        "Company Website": "https://rootplatform.com",
        "Employee Count": "30-80",
        "Source": "CSV_Upload",
        "Status": "New",
        "POPIA Consent": "Pending",
        "Source Metadata": meta(
            tier=2,
            priority=True,
            motion="cold_outreach",
            urgency="medium",
            co_founders=["Jonathan Stewart", "Malan Joubert", "Philip Joubert"],
            current_team_lead_note="Charlotte Koep per some sources - verify decision-maker",
            funding="$3M seed + $1.5M Europe round",
            market="API-first embedded insurance platform",
            hook="api_platform_ecosystem_intel",
            pain_hypothesis="Root sells to insurers/retailers. AVM: e-commerce scraping for retailers missing embedded insurance, integration competitor monitoring, FSCA/FCA regulatory intel feed.",
            pitch_angle="API-first - developer/infrastructure language. Europe expansion = TAM scoping need.",
            verification_needed=["recent_post", "email", "charlotte_vs_louw"],
        ),
    },
    {
        "Lead ID": "LI-PRIORITY-T2-015",
        "Full Name": "Sumarie Greybe",
        "First Name": "Sumarie",
        "Last Name": "Greybe",
        "Title": "Co-Founder",
        "Company Name": "Naked Insurance",
        "Industry": "Insurtech (AI-based consumer insurance)",
        "Location": "South Africa",
        "LinkedIn URL": "https://za.linkedin.com/in/sumarie-greybe-fia-152920a2",
        "Company Website": "https://www.naked.insure",
        "Employee Count": "50-150",
        "Source": "CSV_Upload",
        "Status": "New",
        "POPIA Consent": "Pending",
        "Source Metadata": meta(
            tier=2,
            priority=True,
            motion="cold_outreach",
            urgency="low",
            parallel_to="LI-PRIORITY-T2-013 (Alex Thomson)",
            multi_thread_gating="Conditional - only send if Alex silent 14+ days",
            background="FIA actuary. UP 1994. Swiss Re, Quindiem founder, EY Africa Actuarial, Naked 2016.",
            signal="Rare woman leader SA insurance",
            hook="operator_angle_at_naked",
            pain_hypothesis="Same company as Alex but Sumarie = operator angle (pricing team tooling) not strategic",
            verification_needed=["recent_post", "email"],
        ),
    },
    {
        "Lead ID": "LI-PRIORITY-T2-016",
        "Full Name": "Kobus Rust",
        "First Name": "Kobus",
        "Last Name": "Rust",
        "Title": "Founder",
        "Company Name": "Exakt Life",
        "Industry": "Insurtech (ML Insurance Pricing)",
        "Location": "South Africa",
        "LinkedIn URL": "",
        "Company Website": "https://exaktlife.com",
        "Employee Count": "5-20",
        "Source": "CSV_Upload",
        "Status": "New",
        "POPIA Consent": "Pending",
        "Source Metadata": meta(
            tier=2,
            priority=True,
            motion="cold_outreach",
            urgency="medium",
            linkedin_url_status="TBD - manual lookup needed before send",
            background="Ex-insurance carrier SA pricing team - launched Exakt as transparent ML pricing",
            product="Transparent ML algorithm - explainable, not black-box",
            stage="Early - first paying users per 2024 Insurtech Gateway article",
            hook="early_stage_founder_needs_scaling_tooling",
            pain_hypothesis="Small team, technical product, first paying customers. AI model exists - data pipeline + onboarding automation is what team can't build.",
            pitch_angle="Actuary-technical language. Explainable models = data quality = AVM fit.",
            verification_needed=["linkedin_url_manual", "email", "current_stage_2026", "website_url_confirm"],
        ),
    },
    {
        "Lead ID": "LI-PRIORITY-T2-017",
        "Full Name": "Steve Beagelman",
        "First Name": "Steve",
        "Last Name": "Beagelman",
        "Title": "Founder & CEO",
        "Company Name": "SMB Franchise Advisors",
        "Industry": "Franchise Development Consulting",
        "Location": "United States",
        "LinkedIn URL": "",
        "Company Website": "https://smbfranchising.com",
        "Employee Count": "10-30",
        "Source": "CSV_Upload",
        "Status": "New",
        "POPIA Consent": "Pending",
        "Source Metadata": meta(
            tier=2,
            priority=True,
            motion="cold_outreach",
            urgency="medium",
            linkedin_url_status="TBD - manual lookup",
            background="35+ years franchise industry",
            team_member_linkedin="Shannon Wilburn, CFE - https://www.linkedin.com/in/shannonwilburn/",
            scale="500+ founders launched/grown franchises since 2009",
            market_position="Consultant-lite for smaller/emerging brands",
            hook="franchise_consultancy_needs_scalable_internal_tooling",
            pain_hypothesis="Franchise consultancy at scale = process automation need. AVM: franchisee candidate scoring, market-fit analysis per territory, FTC FDD filing competitor intel scraping.",
            pitch_angle="35-year franchise veteran - conservative, process-focused. Frame as 'automate the playbook not the advice.'",
            verification_needed=["linkedin_url_manual", "email", "current_hiring_signals"],
        ),
    },
]


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for rec in RECORDS:
            writer.writerow(rec)

    log.info("Wrote %d records to %s", len(RECORDS), OUTPUT)
    log.info("File size: %d bytes", OUTPUT.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
