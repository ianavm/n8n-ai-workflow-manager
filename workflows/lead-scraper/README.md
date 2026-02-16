# Lead Generating Web Scraper & CRM Automation

**Workflow ID:** `uq4hnH0YHfhYOOzO`
**Status:** Active
**Schedule:** Weekly, Mondays at 9:00 AM
**Last Updated:** 2026-02-11 (v2 - Google Places API)

## Overview

Automated lead generation pipeline that uses the Google Places API to find businesses, enriches data by scraping their websites for emails/social links, scores leads, stores them in Airtable CRM + Google Sheets, and sends AI-generated personalized outreach emails.

## Pipeline Stages

### Stage 1: Triggers & Configuration
- **Schedule Trigger** - Runs weekly on Monday 9AM
- **Manual Trigger** - Click "Test workflow" for ad-hoc runs
- **Search Config** - Set node with search parameters:
  - `searchQuery`: "dentists" (change to target industry)
  - `location`: "Johannesburg" (change to target area)
  - `maxResults`: 50
  - `googlePlacesApiKey`: Your Google Places API key
  - `senderName`: Ian Immelman
  - `senderCompany`: AnyVision Media
  - `senderTitle`: Director
  - `senderEmail`: ian@anyvisionmedia.com

### Stage 2: Google Places API (v2 - replaced HTML scraping)
- **Places Text Search** - POST to `places.googleapis.com/v1/places:searchText`
- Returns structured data: business name, address, phone, website, rating, review count
- Up to 20 results per page (pagination node available but disabled)

### Stage 3: Website Scraping & Enrichment
- Loops through businesses one at a time with error handling (`continueOnFail`)
- 2-second rate limiting between requests
- Extracts emails, phone numbers, LinkedIn/Facebook/Instagram links
- Follows redirects (up to 3 hops)

### Stage 4: Scoring & Dedup
- Deduplicates by email
- Scores leads 0-100 based on data completeness:
  - Email: +20 | Phone: +15 | Business Name: +15
  - Address: +10 | Rating: +10 | Social Media: +10
  - Website: +10 | Multiple contact methods: +10

### Stage 5: CRM Storage
- **Airtable** (primary CRM): Creates new records or updates existing ones
  - Base: `appzcZpiIZ6QPtJXT` (n8n Workflows)
  - Table: `tbludJQgwxtvcyo2Q` (Leads)
  - Matching key: Email
- **Google Sheets** (mirror): Appends all leads for easy sharing
  - Sheet: "LEAD GEN EMAILSCRAPER"

### Stage 6: AI Email Outreach
- **Filter New Leads** - Only emails leads with Status="New" (skips existing/updated)
- 30-second rate limit between emails
- AI generates personalized cold email via OpenRouter (Claude Sonnet)
- Formats into branded HTML template with AnyVision branding (#FF6D5A)
- Sends via Gmail
- Updates Airtable status to "Email Sent" with date

### Stage 7: Notifications
- Summary email with stats after each run
- Error alert emails on any failures

## Required Credentials

| Credential | Name | Used By |
|---|---|---|
| Airtable Token API | Whatsapp Multi Agent (ZyBrcAO6fps7YB3u) | Check/Create/Update/Status Airtable nodes |
| Google Sheets OAuth2 | Google Sheets AVM Tutorial (OkpDXxwI8WcUJp4P) | Append to Sheets |
| Gmail OAuth2 | Gmail account AVM Tutorial (2IuycrTIgWJZEjBE) | Send Outreach Email, Send Summary, Error Notification |
| OpenRouter API | OpenRouter 2WC (9ZgHenDBrFuyboov) | AI Generate Email |
| Google Places API | API key in Search Config node | Places Text Search |

## Airtable "Leads" Table Schema

| Field | Type | Notes |
|---|---|---|
| Business Name | Single Line Text | Primary identifier |
| Email | Email | Used as matching key for dedup |
| Phone | Phone Number | |
| Website | URL | |
| Address | Single Line Text | |
| Industry | Single Line Text | From search config |
| Location | Single Line Text | From search config |
| Rating | Number | Google Places rating |
| Social - LinkedIn | URL | |
| Social - Facebook | URL | |
| Social - Instagram | URL | |
| Lead Score | Number | 0-100 |
| Status | Single Select | New, Email Sent, Followed Up, Responded, Converted, Unsubscribed |
| Source | Single Line Text | "Google Maps Scraper" |
| Date Scraped | Date | |
| Email Sent Date | Date | |
| Notes | Long Text | Email subject stored here |

## Version History

### v2 (2026-02-11) - Google Places API + 14 Bug Fixes

**Major: Replaced broken Google Maps HTML scraping with Google Places API**
1. `Build Maps URL` -> `Places Text Search` - proper Google Places API Text Search
2. `Scrape Google Maps` -> `Places Page 2` (disabled, available for pagination)
3. `Extract Business Data` -> `Parse Places Results` - structured API response parser

**Bug Fixes:**
4. `Check Airtable Exists` - removed extra `=` prefix in Airtable filter formula
5. `Update in Airtable` - added missing Email field for record matching (would fail to find records)
6. `Update Lead Status` - fixed broken expression `={{ .item.json.leadEmail }}` -> `={{ $('Format Email').item.json.leadEmail }}`
7. `AI Generate Email` - fixed `['Business Name']` being parsed as JS array literal instead of property access
8. `Format Email` - complete rewrite with multi-source fallback chain (Score Leads -> Filter New Leads -> input)
9. `Filter New Leads` - changed from broken `$json.id exists` to `Status == "New" AND Email exists`
10. `Scrape Website` - added `continueOnFail` error handling + redirect following (3 hops)
11. `Extract Contact Info` - added try/catch fallback for Loop Over Businesses reference
12. `Aggregate Results` - fixed broken template literal in Airtable URL (from v1 fixes)
13. All connections updated for renamed nodes
14. Sticky notes updated to reflect new architecture

### v1 (2026-02-11) - Initial Fixes
- Fixed 6 issues in the original workflow (see workflow_fixed.json)

## Files

- `workflow_backup_original.json` - Original workflow before any fixes
- `workflow_fixed.json` - v1 fixes (6 patches)
- `workflow_v2_places_api.json` - v2 with Google Places API + 14 fixes (currently deployed)
