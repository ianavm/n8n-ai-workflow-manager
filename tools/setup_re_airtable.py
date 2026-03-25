"""
RE Operations - Airtable Base Setup Tool

Creates all 14 required tables in a NEW Airtable base for the
Real Estate Operations system (RE-01 through RE-18 workflows).

Prerequisites:
    1. AIRTABLE_API_TOKEN set in .env
    2. RE_AIRTABLE_BASE_ID set in .env (create a new base in Airtable first)

Usage:
    python tools/setup_re_airtable.py              # Create all tables
    python tools/setup_re_airtable.py --seed        # Create tables + seed sample data
"""

import os
import sys
import json
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# -- Configuration --------------------------------------------------------
RE_BASE_ID = os.getenv("RE_AIRTABLE_BASE_ID", "")

AIRTABLE_API = "https://api.airtable.com/v0"
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

# -- Reusable Choice Sets -------------------------------------------------

STATUS_COLORS = {
    "New": "blueBright",
    "Exploring": "cyanBright",
    "Qualified": "yellowBright",
    "Hot": "redBright",
    "Converted": "greenBright",
    "Cold": "grayBright",
    "Closed": "grayDark1",
}

DEAL_STATUS_CHOICES = [
    {"name": "Enquiry", "color": "blueBright"},
    {"name": "Viewing_Scheduled", "color": "cyanBright"},
    {"name": "Viewed", "color": "cyanDark1"},
    {"name": "Offer_Made", "color": "yellowBright"},
    {"name": "Offer_Accepted", "color": "yellowDark1"},
    {"name": "Bond_Applied", "color": "orangeBright"},
    {"name": "Bond_Approved", "color": "orangeDark1"},
    {"name": "Transfer_In_Progress", "color": "purpleBright"},
    {"name": "Registered", "color": "greenBright"},
    {"name": "Cancelled", "color": "redBright"},
]

PROVINCE_CHOICES = [
    {"name": "Gauteng", "color": "blueBright"},
    {"name": "Western_Cape", "color": "greenBright"},
    {"name": "KZN", "color": "yellowBright"},
    {"name": "Eastern_Cape", "color": "cyanBright"},
    {"name": "Free_State", "color": "orangeBright"},
    {"name": "Limpopo", "color": "purpleBright"},
    {"name": "Mpumalanga", "color": "pinkBright"},
    {"name": "North_West", "color": "grayBright"},
    {"name": "Northern_Cape", "color": "redBright"},
]

AREA_CHOICES = [
    {"name": "Sandton", "color": "blueBright"},
    {"name": "Fourways", "color": "greenBright"},
    {"name": "Randburg", "color": "cyanBright"},
    {"name": "Midrand", "color": "yellowBright"},
    {"name": "Bryanston", "color": "purpleBright"},
    {"name": "Roodepoort", "color": "orangeBright"},
    {"name": "Centurion", "color": "pinkBright"},
    {"name": "Pretoria", "color": "redBright"},
    {"name": "Johannesburg_CBD", "color": "grayBright"},
    {"name": "Bedfordview", "color": "grayDark1"},
    {"name": "Other", "color": "blueDark1"},
]

DOC_TYPE_CHOICES = [
    {"name": "FICA", "color": "blueBright"},
    {"name": "OTP", "color": "greenBright"},
    {"name": "MANDATE", "color": "cyanBright"},
    {"name": "TITLE", "color": "yellowBright"},
    {"name": "MUNICIPAL", "color": "orangeBright"},
    {"name": "BOND", "color": "purpleBright"},
    {"name": "COMPLIANCE", "color": "pinkBright"},
    {"name": "SECTIONAL", "color": "redBright"},
    {"name": "ENTITY", "color": "grayBright"},
    {"name": "VALUATION", "color": "blueDark1"},
    {"name": "INSPECTION", "color": "greenDark1"},
    {"name": "INSURANCE", "color": "cyanDark1"},
    {"name": "COMMISSION", "color": "yellowDark1"},
    {"name": "CORRESPONDENCE", "color": "orangeDark1"},
    {"name": "OTHER", "color": "grayDark1"},
]

SEVERITY_CHOICES = [
    {"name": "Critical", "color": "redBright"},
    {"name": "High", "color": "orangeBright"},
    {"name": "Medium", "color": "yellowBright"},
    {"name": "Low", "color": "blueBright"},
]

# -- Table Definitions -----------------------------------------------------

TABLE_DEFINITIONS = {
    "Clients": {
        "description": "Client master records - buyers, sellers, landlords, tenants",
        "primary_field": "Full Name",
        "fields": [
            {"name": "First Name", "type": "singleLineText"},
            {"name": "Surname", "type": "singleLineText"},
            {"name": "Email", "type": "email"},
            {"name": "Phone", "type": "phoneNumber"},
            {"name": "Phone Normalized", "type": "singleLineText"},
            {"name": "ID Number", "type": "singleLineText"},
            {
                "name": "Client Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Buyer", "color": "blueBright"},
                        {"name": "Seller", "color": "greenBright"},
                        {"name": "Landlord", "color": "purpleBright"},
                        {"name": "Tenant", "color": "yellowBright"},
                        {"name": "Both", "color": "cyanBright"},
                    ]
                },
            },
            {
                "name": "Source",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "WhatsApp", "color": "greenBright"},
                        {"name": "Email", "color": "blueBright"},
                        {"name": "Referral", "color": "purpleBright"},
                        {"name": "Walk-in", "color": "yellowBright"},
                        {"name": "Website", "color": "cyanBright"},
                        {"name": "Social", "color": "pinkBright"},
                    ]
                },
            },
            {"name": "Notes", "type": "multilineText"},
            {"name": "POPIA Consent", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "POPIA Consent Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Updated At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },

    "Leads": {
        "description": "Lead tracking - enquiries from WhatsApp, email, referral, walk-in",
        "primary_field": "Lead ID",
        "fields": [
            {"name": "Client Name", "type": "singleLineText"},
            {"name": "Channel ID", "type": "singleLineText"},
            {
                "name": "Source",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "WhatsApp", "color": "greenBright"},
                        {"name": "Email", "color": "blueBright"},
                        {"name": "Referral", "color": "purpleBright"},
                        {"name": "Walk-in", "color": "yellowBright"},
                        {"name": "Website", "color": "cyanBright"},
                    ]
                },
            },
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "New", "color": "blueBright"},
                        {"name": "Exploring", "color": "cyanBright"},
                        {"name": "Qualified", "color": "yellowBright"},
                        {"name": "Hot", "color": "redBright"},
                        {"name": "Converted", "color": "greenBright"},
                        {"name": "Cold", "color": "grayBright"},
                        {"name": "Closed", "color": "grayDark1"},
                    ]
                },
            },
            {"name": "Score", "type": "number", "options": {"precision": 0}},
            {"name": "Budget Min", "type": "number", "options": {"precision": 0}},
            {"name": "Budget Max", "type": "number", "options": {"precision": 0}},
            {"name": "Bedrooms", "type": "number", "options": {"precision": 0}},
            {"name": "Area Preference", "type": "singleLineText"},
            {
                "name": "Property Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Freehold", "color": "blueBright"},
                        {"name": "Sectional_Title", "color": "greenBright"},
                        {"name": "Rental", "color": "yellowBright"},
                        {"name": "Commercial", "color": "purpleBright"},
                        {"name": "Agricultural", "color": "orangeBright"},
                    ]
                },
            },
            {
                "name": "Timeline",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Immediate", "color": "redBright"},
                        {"name": "1_month", "color": "orangeBright"},
                        {"name": "3_months", "color": "yellowBright"},
                        {"name": "6_months", "color": "cyanBright"},
                        {"name": "Exploring", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Pre Approved", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "Assigned Agent", "type": "singleLineText"},
            {"name": "Assigned At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Last Contact", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Next Follow Up", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Follow Up Count", "type": "number", "options": {"precision": 0}},
            {"name": "Qualification Notes", "type": "multilineText"},
            {"name": "Deal Ref", "type": "singleLineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Updated At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },

    "Properties": {
        "description": "Property listings - sales and rentals with full details",
        "primary_field": "Property ID",
        "fields": [
            {"name": "Address", "type": "singleLineText"},
            {"name": "Suburb", "type": "singleLineText"},
            {"name": "City", "type": "singleLineText"},
            {
                "name": "Province",
                "type": "singleSelect",
                "options": {"choices": PROVINCE_CHOICES},
            },
            {
                "name": "Property Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Freehold", "color": "blueBright"},
                        {"name": "Sectional_Title", "color": "greenBright"},
                        {"name": "Commercial", "color": "purpleBright"},
                        {"name": "Agricultural", "color": "orangeBright"},
                    ]
                },
            },
            {
                "name": "Listing Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Sale", "color": "greenBright"},
                        {"name": "Rental", "color": "blueBright"},
                    ]
                },
            },
            {"name": "Price", "type": "number", "options": {"precision": 0}},
            {"name": "Bedrooms", "type": "number", "options": {"precision": 0}},
            {"name": "Bathrooms", "type": "number", "options": {"precision": 0}},
            {"name": "Garages", "type": "number", "options": {"precision": 0}},
            {"name": "Floor Size SqM", "type": "number", "options": {"precision": 0}},
            {"name": "Erf Size SqM", "type": "number", "options": {"precision": 0}},
            {"name": "Description", "type": "multilineText"},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Available", "color": "greenBright"},
                        {"name": "Under_Offer", "color": "yellowBright"},
                        {"name": "Sold", "color": "redBright"},
                        {"name": "Withdrawn", "color": "grayBright"},
                        {"name": "Coming_Soon", "color": "blueBright"},
                    ]
                },
            },
            {"name": "Listing Agent", "type": "singleLineText"},
            {"name": "Listing Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {
                "name": "Mandate Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Sole", "color": "greenBright"},
                        {"name": "Open", "color": "blueBright"},
                    ]
                },
            },
            {"name": "Drive Folder ID", "type": "singleLineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Updated At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },

    "Agents": {
        "description": "Real estate agent profiles with per-agent credentials and config",
        "primary_field": "Agent Name",
        "fields": [
            {"name": "Agent ID", "type": "singleLineText"},
            {"name": "Email", "type": "email"},
            {"name": "Phone", "type": "phoneNumber"},
            {"name": "WhatsApp Phone Number ID", "type": "singleLineText"},
            {"name": "WhatsApp WABA ID", "type": "singleLineText"},
            {"name": "WhatsApp Credential ID", "type": "singleLineText"},
            {
                "name": "Email Provider",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Gmail", "color": "redBright"},
                        {"name": "Outlook", "color": "blueBright"},
                    ]
                },
            },
            {"name": "Email Credential ID", "type": "singleLineText"},
            {
                "name": "Calendar Provider",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Google", "color": "blueBright"},
                        {"name": "Outlook", "color": "purpleBright"},
                    ]
                },
            },
            {"name": "Calendar ID", "type": "singleLineText"},
            {"name": "Calendar Credential ID", "type": "singleLineText"},
            {
                "name": "Specialization",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Residential", "color": "greenBright"},
                        {"name": "Commercial", "color": "purpleBright"},
                        {"name": "Luxury", "color": "yellowBright"},
                        {"name": "Rental", "color": "blueBright"},
                        {"name": "Industrial", "color": "orangeBright"},
                    ]
                },
            },
            {
                "name": "Areas",
                "type": "multipleSelects",
                "options": {"choices": AREA_CHOICES},
            },
            {"name": "Is Active", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "Is Available", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "Working Hours", "type": "singleLineText"},
            {"name": "Working Days", "type": "singleLineText"},
            {"name": "Max Active Leads", "type": "number", "options": {"precision": 0}},
            {"name": "Current Lead Count", "type": "number", "options": {"precision": 0}},
            {"name": "Avg Response Time Min", "type": "number", "options": {"precision": 1}},
            {"name": "Last Assigned At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Telegram Chat ID", "type": "singleLineText"},
            {
                "name": "Role",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Agent", "color": "blueBright"},
                        {"name": "Manager", "color": "purpleBright"},
                        {"name": "Owner", "color": "redBright"},
                    ]
                },
            },
            {"name": "System Prompt", "type": "multilineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },

    "Admin Staff": {
        "description": "Admin and management staff with Telegram IDs and specializations",
        "primary_field": "Name",
        "fields": [
            {"name": "Admin ID", "type": "singleLineText"},
            {"name": "Email", "type": "email"},
            {"name": "Phone", "type": "phoneNumber"},
            {
                "name": "Role",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Owner", "color": "redBright"},
                        {"name": "Manager", "color": "purpleBright"},
                        {"name": "Compliance_Admin", "color": "blueBright"},
                        {"name": "Finance_Admin", "color": "greenBright"},
                        {"name": "Listing_Admin", "color": "yellowBright"},
                        {"name": "Transaction_Admin", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "Telegram User ID", "type": "singleLineText"},
            {"name": "Telegram Chat ID", "type": "singleLineText"},
            {"name": "Is Active", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {
                "name": "Specialization",
                "type": "multipleSelects",
                "options": {
                    "choices": [
                        {"name": "FICA", "color": "blueBright"},
                        {"name": "OTP", "color": "greenBright"},
                        {"name": "Bond", "color": "purpleBright"},
                        {"name": "Commission", "color": "yellowBright"},
                        {"name": "Listings", "color": "orangeBright"},
                        {"name": "General", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Max Daily Tasks", "type": "number", "options": {"precision": 0}},
            {"name": "Current Task Count", "type": "number", "options": {"precision": 0}},
        ],
    },

    "Deals": {
        "description": "Property transactions - sale or rental pipeline from enquiry to registration",
        "primary_field": "Deal ID",
        "fields": [
            {"name": "Deal Ref", "type": "singleLineText"},
            {"name": "Property ID", "type": "singleLineText"},
            {"name": "Client Name", "type": "singleLineText"},
            {"name": "Seller Client", "type": "singleLineText"},
            {"name": "Agent Name", "type": "singleLineText"},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {"choices": DEAL_STATUS_CHOICES},
            },
            {
                "name": "Deal Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Sale", "color": "greenBright"},
                        {"name": "Rental", "color": "blueBright"},
                    ]
                },
            },
            {"name": "Offer Amount", "type": "number", "options": {"precision": 0}},
            {"name": "Accepted Amount", "type": "number", "options": {"precision": 0}},
            {"name": "Commission Pct", "type": "number", "options": {"precision": 2}},
            {"name": "Commission Amount", "type": "number", "options": {"precision": 0}},
            {"name": "Offer Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Bond Approval Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Transfer Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Registration Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Drive Folder ID", "type": "singleLineText"},
            {"name": "Notes", "type": "multilineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Updated At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },

    "Documents": {
        "description": "Document registry - classification, filing, review status",
        "primary_field": "Doc ID",
        "fields": [
            {"name": "Deal Ref", "type": "singleLineText"},
            {"name": "Client Name", "type": "singleLineText"},
            {
                "name": "Doc Type",
                "type": "singleSelect",
                "options": {"choices": DOC_TYPE_CHOICES},
            },
            {"name": "Original Filename", "type": "singleLineText"},
            {"name": "Renamed Filename", "type": "singleLineText"},
            {"name": "Drive File ID", "type": "singleLineText"},
            {"name": "Drive Folder ID", "type": "singleLineText"},
            {"name": "Content Hash", "type": "singleLineText"},
            {"name": "Classification Confidence", "type": "number", "options": {"precision": 2}},
            {"name": "Extracted Metadata", "type": "multilineText"},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Pending", "color": "blueBright"},
                        {"name": "Classified", "color": "cyanBright"},
                        {"name": "Filed", "color": "greenBright"},
                        {"name": "Review_Required", "color": "yellowBright"},
                        {"name": "Rejected", "color": "redBright"},
                    ]
                },
            },
            {"name": "Reviewed By", "type": "singleLineText"},
            {"name": "Review Notes", "type": "multilineText"},
            {
                "name": "Source",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Email", "color": "blueBright"},
                        {"name": "WhatsApp", "color": "greenBright"},
                        {"name": "Upload", "color": "purpleBright"},
                        {"name": "Scan", "color": "yellowBright"},
                    ]
                },
            },
            {"name": "Source Message ID", "type": "singleLineText"},
            {"name": "Page Count", "type": "number", "options": {"precision": 0}},
            {"name": "File Size Bytes", "type": "number", "options": {"precision": 0}},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Updated At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },

    "Appointments": {
        "description": "Property viewings, meetings, signings - with calendar integration",
        "primary_field": "Appointment ID",
        "fields": [
            {"name": "Deal Ref", "type": "singleLineText"},
            {"name": "Property ID", "type": "singleLineText"},
            {"name": "Client Name", "type": "singleLineText"},
            {"name": "Agent Name", "type": "singleLineText"},
            {
                "name": "Appointment Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "First_Viewing", "color": "blueBright"},
                        {"name": "Second_Viewing", "color": "cyanBright"},
                        {"name": "Valuation", "color": "purpleBright"},
                        {"name": "Signing", "color": "greenBright"},
                        {"name": "Handover", "color": "yellowBright"},
                        {"name": "Meeting", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "Start Time", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "End Time", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Location", "type": "singleLineText"},
            {"name": "Calendar Event ID", "type": "singleLineText"},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Scheduled", "color": "blueBright"},
                        {"name": "Confirmed", "color": "cyanBright"},
                        {"name": "Completed", "color": "greenBright"},
                        {"name": "Cancelled", "color": "redBright"},
                        {"name": "No_Show", "color": "grayDark1"},
                    ]
                },
            },
            {"name": "Reminder 24h Sent", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "Reminder 2h Sent", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "Outcome Notes", "type": "multilineText"},
            {
                "name": "Client Feedback",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Interested", "color": "greenBright"},
                        {"name": "Not_Interested", "color": "redBright"},
                        {"name": "Wants_Second_Viewing", "color": "yellowBright"},
                        {"name": "Made_Offer", "color": "purpleBright"},
                    ]
                },
            },
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Updated At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },

    "Messages": {
        "description": "Unified message log - WhatsApp, email, Telegram, system messages",
        "primary_field": "Message ID",
        "fields": [
            {"name": "External Message ID", "type": "singleLineText"},
            {
                "name": "Channel",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "WhatsApp", "color": "greenBright"},
                        {"name": "Email", "color": "blueBright"},
                        {"name": "Telegram", "color": "cyanBright"},
                        {"name": "System", "color": "grayBright"},
                    ]
                },
            },
            {
                "name": "Direction",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Inbound", "color": "blueBright"},
                        {"name": "Outbound", "color": "greenBright"},
                        {"name": "System", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Sender ID", "type": "singleLineText"},
            {"name": "Recipient ID", "type": "singleLineText"},
            {"name": "Agent Name", "type": "singleLineText"},
            {"name": "Client Name", "type": "singleLineText"},
            {"name": "Lead ID", "type": "singleLineText"},
            {"name": "Body", "type": "multilineText"},
            {"name": "Intent", "type": "singleLineText"},
            {"name": "Confidence", "type": "number", "options": {"precision": 2}},
            {
                "name": "Response Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "AI_Auto", "color": "greenBright"},
                        {"name": "AI_Draft", "color": "yellowBright"},
                        {"name": "Human", "color": "blueBright"},
                        {"name": "System", "color": "grayBright"},
                        {"name": "Handoff", "color": "redBright"},
                    ]
                },
            },
            {"name": "Processing Time Ms", "type": "number", "options": {"precision": 0}},
            {"name": "Conversation ID", "type": "singleLineText"},
            {"name": "Timestamp", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },

    "Email Threads": {
        "description": "Email thread tracking - Gmail/Outlook threads with classification",
        "primary_field": "Thread ID",
        "fields": [
            {"name": "Conversation ID", "type": "singleLineText"},
            {"name": "Subject", "type": "singleLineText"},
            {"name": "Participants", "type": "multilineText"},
            {"name": "Last Activity", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Message Count", "type": "number", "options": {"precision": 0}},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Open", "color": "blueBright"},
                        {"name": "Awaiting_Reply", "color": "yellowBright"},
                        {"name": "Resolved", "color": "greenBright"},
                        {"name": "Archived", "color": "grayBright"},
                    ]
                },
            },
            {
                "name": "Classification",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "New_Enquiry", "color": "blueBright"},
                        {"name": "Agent_Compliance", "color": "purpleBright"},
                        {"name": "Listing_Admin", "color": "cyanBright"},
                        {"name": "Commission", "color": "greenBright"},
                        {"name": "Document_Submission", "color": "yellowBright"},
                        {"name": "Appointment", "color": "orangeBright"},
                        {"name": "Client_Update", "color": "pinkBright"},
                        {"name": "Internal", "color": "grayBright"},
                        {"name": "Spam_Irrelevant", "color": "grayDark1"},
                    ]
                },
            },
            {"name": "Assigned To", "type": "singleLineText"},
            {"name": "Deal Ref", "type": "singleLineText"},
            {"name": "Has Attachments", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Updated At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },

    "Activity Log": {
        "description": "Event log for all system activity - leads, deals, docs, messages",
        "primary_field": "Log ID",
        "fields": [
            {"name": "Timestamp", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {
                "name": "Event Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Lead_Created", "color": "blueBright"},
                        {"name": "Lead_Assigned", "color": "cyanBright"},
                        {"name": "Appointment_Booked", "color": "greenBright"},
                        {"name": "Document_Filed", "color": "yellowBright"},
                        {"name": "Email_Sent", "color": "purpleBright"},
                        {"name": "WhatsApp_Sent", "color": "pinkBright"},
                        {"name": "Deal_Updated", "color": "orangeBright"},
                        {"name": "Agent_Status", "color": "grayBright"},
                        {"name": "Escalation", "color": "redBright"},
                        {"name": "System_Event", "color": "grayDark1"},
                    ]
                },
            },
            {"name": "Entity Type", "type": "singleLineText"},
            {"name": "Entity ID", "type": "singleLineText"},
            {"name": "Actor", "type": "singleLineText"},
            {"name": "Description", "type": "multilineText"},
            {"name": "Metadata", "type": "multilineText"},
        ],
    },

    "Assignments": {
        "description": "Lead assignment history - who got what and why",
        "primary_field": "Assignment ID",
        "fields": [
            {"name": "Lead ID", "type": "singleLineText"},
            {"name": "Agent Name", "type": "singleLineText"},
            {"name": "Assigned By", "type": "singleLineText"},
            {
                "name": "Assignment Reason",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Round_Robin", "color": "blueBright"},
                        {"name": "Specialization", "color": "greenBright"},
                        {"name": "Manual", "color": "purpleBright"},
                        {"name": "Reassignment", "color": "yellowBright"},
                        {"name": "Area_Match", "color": "cyanBright"},
                    ]
                },
            },
            {"name": "Score Breakdown", "type": "multilineText"},
            {"name": "Previous Agent", "type": "singleLineText"},
            {"name": "Assigned At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Active", "color": "greenBright"},
                        {"name": "Completed", "color": "blueBright"},
                        {"name": "Reassigned", "color": "yellowBright"},
                    ]
                },
            },
        ],
    },

    "Exceptions": {
        "description": "Escalation and exception tracking - SLA breaches, errors, anomalies",
        "primary_field": "Exception ID",
        "fields": [
            {
                "name": "Exception Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "SLA_Breach", "color": "redBright"},
                        {"name": "Stale_Lead", "color": "orangeBright"},
                        {"name": "Missed_Appointment", "color": "yellowBright"},
                        {"name": "System_Error", "color": "purpleBright"},
                        {"name": "Low_Confidence", "color": "cyanBright"},
                        {"name": "Duplicate_Lead", "color": "blueBright"},
                        {"name": "Missing_Document", "color": "pinkBright"},
                    ]
                },
            },
            {
                "name": "Severity",
                "type": "singleSelect",
                "options": {"choices": SEVERITY_CHOICES},
            },
            {"name": "Entity Type", "type": "singleLineText"},
            {"name": "Entity ID", "type": "singleLineText"},
            {"name": "Description", "type": "multilineText"},
            {"name": "Recommended Action", "type": "multilineText"},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Open", "color": "redBright"},
                        {"name": "Acknowledged", "color": "yellowBright"},
                        {"name": "Resolved", "color": "greenBright"},
                        {"name": "Dismissed", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Resolved By", "type": "singleLineText"},
            {"name": "Resolved At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Resolution Notes", "type": "multilineText"},
            {"name": "Escalated To", "type": "singleLineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Last Notified", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },

    "Audit Log": {
        "description": "Immutable audit trail - all create/update/delete/approve/override actions",
        "primary_field": "Audit ID",
        "fields": [
            {"name": "Timestamp", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {
                "name": "Action",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Create", "color": "greenBright"},
                        {"name": "Read", "color": "blueBright"},
                        {"name": "Update", "color": "yellowBright"},
                        {"name": "Delete", "color": "redBright"},
                        {"name": "Approve", "color": "cyanBright"},
                        {"name": "Reject", "color": "orangeBright"},
                        {"name": "Override", "color": "purpleBright"},
                        {"name": "Login", "color": "grayBright"},
                        {"name": "Command", "color": "pinkBright"},
                    ]
                },
            },
            {"name": "Entity Type", "type": "singleLineText"},
            {"name": "Entity ID", "type": "singleLineText"},
            {"name": "Actor", "type": "singleLineText"},
            {
                "name": "Actor Role",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Owner", "color": "redBright"},
                        {"name": "Manager", "color": "purpleBright"},
                        {"name": "Agent", "color": "blueBright"},
                        {"name": "Admin", "color": "greenBright"},
                        {"name": "System", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Old Value", "type": "multilineText"},
            {"name": "New Value", "type": "multilineText"},
            {
                "name": "Channel",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Telegram", "color": "cyanBright"},
                        {"name": "Portal", "color": "blueBright"},
                        {"name": "API", "color": "purpleBright"},
                        {"name": "n8n", "color": "orangeBright"},
                    ]
                },
            },
        ],
    },
}


# -- Sample Seed Data -------------------------------------------------------

SEED_AGENTS = [
    {
        "Agent Name": "Ian Immelman",
        "Agent ID": "AGT-001",
        "Email": "ian@anyvisionmedia.com",
        "Email Provider": "Gmail",
        "Calendar Provider": "Google",
        "Specialization": "Residential",
        "Areas": ["Sandton", "Fourways", "Bryanston"],
        "Is Active": True,
        "Is Available": True,
        "Working Hours": "08:00-17:00",
        "Working Days": "1,2,3,4,5",
        "Max Active Leads": 30,
        "Current Lead Count": 0,
        "Role": "Owner",
        "Created At": datetime.now().strftime("%Y-%m-%d"),
    },
]

SEED_ADMIN_STAFF = [
    {
        "Name": "Ian Immelman",
        "Admin ID": "ADM-001",
        "Email": "ian@anyvisionmedia.com",
        "Role": "Owner",
        "Is Active": True,
        "Specialization": ["FICA", "OTP", "Bond", "Commission", "Listings", "General"],
        "Max Daily Tasks": 50,
        "Current Task Count": 0,
    },
]

SEED_PROPERTIES = [
    {
        "Property ID": "JHB-SDT-001",
        "Address": "123 Example Street",
        "Suburb": "Sandton",
        "City": "Johannesburg",
        "Province": "Gauteng",
        "Property Type": "Sectional_Title",
        "Listing Type": "Sale",
        "Price": 2500000,
        "Bedrooms": 3,
        "Bathrooms": 2,
        "Garages": 1,
        "Floor Size SqM": 120,
        "Description": "Modern 3-bedroom apartment in Sandton with secure parking.",
        "Status": "Available",
        "Listing Agent": "Ian Immelman",
        "Mandate Type": "Sole",
        "Created At": datetime.now().strftime("%Y-%m-%d"),
    },
    {
        "Property ID": "JHB-FWY-001",
        "Address": "45 Cedar Avenue",
        "Suburb": "Fourways",
        "City": "Johannesburg",
        "Province": "Gauteng",
        "Property Type": "Freehold",
        "Listing Type": "Sale",
        "Price": 3800000,
        "Bedrooms": 4,
        "Bathrooms": 3,
        "Garages": 2,
        "Floor Size SqM": 250,
        "Erf Size SqM": 800,
        "Description": "Spacious family home in Fourways with pool and large garden.",
        "Status": "Available",
        "Listing Agent": "Ian Immelman",
        "Mandate Type": "Open",
        "Created At": datetime.now().strftime("%Y-%m-%d"),
    },
]


# -- Setup Functions --------------------------------------------------------

def create_table(client, token, base_id, table_name, table_def):
    """Create a table with fields via Airtable API."""
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


def seed_table(client, token, base_id, table_id, records_data):
    """Seed a table with initial records."""
    records = [{"fields": rec} for rec in records_data]

    # Airtable batch limit is 10 records per request
    created = 0
    for i in range(0, len(records), 10):
        batch = records[i:i + 10]
        resp = client.post(
            f"{AIRTABLE_API}/{base_id}/{table_id}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"records": batch},
        )
        if resp.status_code == 200:
            created += len(resp.json().get("records", []))
        else:
            print(f"    Seed error: {resp.status_code} - {resp.text[:200]}")

    return created


def main():
    seed_mode = "--seed" in sys.argv

    print("=" * 60)
    print("RE OPERATIONS - AIRTABLE BASE SETUP")
    print("=" * 60)
    print()

    token = os.getenv("AIRTABLE_API_TOKEN")
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)

    base_id = RE_BASE_ID
    if not base_id:
        print("ERROR: RE_AIRTABLE_BASE_ID not set in .env")
        print()
        print("Steps to fix:")
        print("  1. Create a new Airtable base called 'RE Operations'")
        print("  2. Copy the base ID from the URL (starts with 'app')")
        print("  3. Add RE_AIRTABLE_BASE_ID=appXXXXXXXXXXXXX to .env")
        sys.exit(1)

    print(f"Base ID: {base_id}")
    print(f"Tables to create: {len(TABLE_DEFINITIONS)}")
    print(f"Seed mode: {'ON' if seed_mode else 'OFF'}")
    print()

    client = httpx.Client(timeout=30)
    created_tables = {}

    # Create all tables
    print("Creating tables...")
    print("-" * 40)

    for table_name, table_def in TABLE_DEFINITIONS.items():
        table_id, result = create_table(client, token, base_id, table_name, table_def)
        if table_id:
            created_tables[table_name] = table_id
            print(f"  + {table_name:<25} -> {table_id} ({result} fields)")
        else:
            print(f"  - {table_name:<25} FAILED: {result}")

    print()

    # Seed data if requested
    if seed_mode and created_tables:
        print("Seeding data...")
        print("-" * 40)

        if "Agents" in created_tables:
            count = seed_table(client, token, base_id, created_tables["Agents"], SEED_AGENTS)
            print(f"  + Agents: {count} records seeded")

        if "Admin Staff" in created_tables:
            count = seed_table(client, token, base_id, created_tables["Admin Staff"], SEED_ADMIN_STAFF)
            print(f"  + Admin Staff: {count} records seeded")

        if "Properties" in created_tables:
            count = seed_table(client, token, base_id, created_tables["Properties"], SEED_PROPERTIES)
            print(f"  + Properties: {count} records seeded")

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
            "Clients": "RE_TABLE_CLIENTS",
            "Leads": "RE_TABLE_LEADS",
            "Properties": "RE_TABLE_PROPERTIES",
            "Agents": "RE_TABLE_AGENTS",
            "Admin Staff": "RE_TABLE_ADMIN_STAFF",
            "Deals": "RE_TABLE_DEALS",
            "Documents": "RE_TABLE_DOCUMENTS",
            "Appointments": "RE_TABLE_APPOINTMENTS",
            "Messages": "RE_TABLE_MESSAGES",
            "Email Threads": "RE_TABLE_EMAIL_THREADS",
            "Activity Log": "RE_TABLE_ACTIVITY_LOG",
            "Assignments": "RE_TABLE_ASSIGNMENTS",
            "Exceptions": "RE_TABLE_EXCEPTIONS",
            "Audit Log": "RE_TABLE_AUDIT_LOG",
        }

        for table_name, table_id in created_tables.items():
            env_key = env_key_map.get(table_name, f"RE_TABLE_{table_name.upper().replace(' ', '_')}")
            print(f"  {env_key}={table_id}")

        print()
        print("Copy the above lines into your .env file.")
        print()


if __name__ == "__main__":
    main()
