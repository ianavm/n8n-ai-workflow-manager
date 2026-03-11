# Real Estate Document Intake & Organization System

Automated document capture, classification, and filing for real estate agencies.

## Architecture

```
Outlook Mailbox --> WF-DI-01 (Intake) --> Google Drive /Incoming_Documents/
                                     └--> WF-DI-02 (Processing Sub-workflow)
                                            ├── PDF text extraction
                                            ├── OCR fallback (Google Document AI)
                                            ├── AI classification (Claude Sonnet)
                                            ├── Property matching
                                            ├── Folder creation + file move
                                            └── Low confidence --> Review Queue

WF-DI-03 (Admin Review) <-- Polls Google Sheets Review_Queue tab
WF-DI-04 (Notifications) --> Daily summary + review alerts + error alerts
```

## Workflows

| ID | Name | Trigger | Purpose |
|----|------|---------|---------|
| WF-DI-01 | Email Intake & Raw Storage | Outlook poll (1 min) | Download attachments, deduplicate, upload to Drive |
| WF-DI-02 | Document Processing | Sub-workflow call | Extract text, classify, match property, file |
| WF-DI-03 | Admin Review | Schedule (5 min) | Process admin review decisions from Google Sheets |
| WF-DI-04 | Notifications | Daily 8AM SAST + Error | Summary emails, review alerts, error notifications |

## Document Types

| Type | Folder | Description |
|------|--------|-------------|
| FICA | 01_FICA | Identity docs, proof of address, tax clearance |
| Offer_to_Purchase | 02_OTP | Sale agreements, deeds of sale |
| Mandate | 03_Mandate | Listing agreements |
| Title_Deed | 04_Title_Deed | Title deeds, transfer deeds |
| Municipal_Document | 05_Municipal | Rates clearance, zoning, building plans |
| Bond_Finance | 06_Bond_Finance | Bond approvals, bank documents |
| Compliance_Certificate | 07_Compliance | Electrical, plumbing, gas, beetle certs |
| Sectional_Scheme | 08_Sectional_Scheme | Body corporate docs, levy statements |
| Entity_Document | 09_Entity_Docs | Company registration, trust deeds |
| Other | 10_Other | Unclassified documents |

## Setup Instructions

### 1. Prerequisites

- n8n Cloud account (ianimmelman89.app.n8n.cloud)
- Google Workspace with Drive and Sheets access
- Microsoft 365 account with Outlook access
- Google Cloud project with Document AI API enabled

### 2. Create Google Sheets Database

```bash
python tools/setup_di_sheets.py --seed
```

This prints the headers for 6 tabs. Create a new Google Sheet named "Real Estate Document Tracker" and paste the headers.

### 3. Create Google Drive Folders

In Google Drive, create:
- `Incoming_Documents/` - Raw file landing zone
- `Properties/` - Organized property folder tree

Note both folder IDs from the Drive URL.

### 4. Create n8n Credentials

#### Microsoft Outlook OAuth2

1. Go to [Azure Portal](https://portal.azure.com) -> App Registrations -> New Registration
2. Name: "n8n Document Intake"
3. Redirect URI: `https://ianimmelman89.app.n8n.cloud/rest/oauth2-credential/callback`
4. API Permissions (Microsoft Graph, Delegated):
   - `Mail.ReadWrite`
   - `Mail.Send`
   - `offline_access`
5. Certificates & Secrets -> New Client Secret -> copy value
6. In n8n Cloud: Credentials -> New -> Microsoft Outlook OAuth2
7. Paste Client ID, Client Secret, Tenant ID
8. Complete OAuth consent flow
9. Note the n8n credential ID

#### Google Drive OAuth2

You already have this credential configured. Note its ID from n8n Cloud.

#### Google Document AI (for OCR)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable the Document AI API
3. Create a processor: Document AI -> Processors -> Create -> General (OCR)
4. Note: Project ID, Location (us/eu), Processor ID
5. The Google Drive OAuth2 credential's service account needs Document AI access

### 5. Configure Environment

Add to `.env`:

```bash
DI_SHEETS_ID=your_google_sheets_id
N8N_CRED_OUTLOOK=your_outlook_credential_id
N8N_CRED_GDRIVE=your_google_drive_credential_id
DI_GDRIVE_INCOMING_FOLDER_ID=your_incoming_folder_id
DI_GDRIVE_PROPERTIES_FOLDER_ID=your_properties_folder_id
DI_DOCAI_PROJECT_ID=your_gcp_project_id
DI_DOCAI_LOCATION=us
DI_DOCAI_PROCESSOR_ID=your_processor_id
```

### 6. Deploy Workflows

```bash
# Build all workflow JSONs
python tools/deploy_document_intake.py build

# Deploy WF-DI-02 first (sub-workflow)
python tools/deploy_document_intake.py deploy di02

# Note the WF-DI-02 ID from the output, add to .env:
# WF_DI_02_ID=the_id_from_output

# Deploy remaining workflows
python tools/deploy_document_intake.py deploy

# Activate all
python tools/deploy_document_intake.py activate
```

### 7. Test

1. Send a test email with a PDF attachment to the monitored Outlook mailbox
2. Wait 1-2 minutes for the Outlook trigger to fire
3. Check:
   - Google Drive `Incoming_Documents/` for the uploaded file
   - Google Sheets `Document_Log` tab for a new row with status "pending"
   - Google Sheets `Audit_Log` tab for intake entries
   - n8n execution log for WF-DI-02 processing

## Admin Review Process

1. Documents with low AI confidence land in the `Review_Queue` tab
2. Admins open the Google Sheet and fill in:
   - `admin_action`: approve / reclassify / create_property / flag_error
   - `admin_email`: their email address
   - `correct_doc_type`: (optional) override the AI classification
   - `correct_property_id`: (optional) link to existing property
   - `admin_notes`: (optional) any notes
3. WF-DI-03 polls every 5 minutes and processes completed reviews
4. Admin receives a confirmation email when processing is done

## Google Drive Folder Structure

```
Properties/
  Johannesburg/
    Sandton/
      12 Main Road/
        01_FICA/
        02_OTP/
        03_Mandate/
        ...
    Fourways/
      45 Cedar Avenue Unit 3/
        01_FICA/
        ...
  Cape Town/
    Sea Point/
      ...
```

Files are renamed: `YYYY-MM-DD_DocType_RefNumber_OriginalName.ext`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Outlook trigger not firing | Check credential OAuth flow, verify Mail.ReadWrite permission |
| PDF text extraction empty | Document is likely scanned - OCR will attempt automatically |
| AI confidence always low | Check the OpenRouter API key, review prompt tuning |
| Duplicate false positives | Different files can have same content hash - check actual content |
| Google Drive folder creation fails | Verify Drive credential has write access to Properties folder |
| Review emails not sending | Check Gmail OAuth credential (CRED_GMAIL) |
