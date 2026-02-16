# ✅ Setup Complete - Lead Scraper Ready for Production

**Date:** 2026-02-12
**Status:** ACTIVE and Scheduled

---

## What Was Built

### 🎯 Workflow: Lead Generating Web Scraper & CRM Automation
- **30 functional nodes** across 7 stages
- **Target:** ALL businesses in Fourways, Johannesburg
- **Focus:** Automation value prop (3x speed, 15h saved, 40% more leads)
- **Schedule:** Every Monday 9:00 AM (automatic)

---

## Your Dedicated Airtable Base

### 📊 Base: Lead Scraper - Fourways CRM
- **Base ID:** `app2ALQUP7CKEkHOz`
- **Table ID:** `tblOsuh298hB9WWrA`
- **Access:** https://airtable.com/app2ALQUP7CKEkHOz

### Fields (18 total):
1. Business Name, Email, Phone, Website, Address
2. Industry, Location, Rating
3. Social Links (LinkedIn, Facebook, Instagram)
4. **Lead Score** (0-100 with automation fit bonus)
5. **Automation Fit** (high/medium/low) - NEW FIELD
6. Status (New/Email Sent/Followed Up/Responded/Converted/Unsubscribed)
7. Source, Date Scraped, Email Sent Date, Notes

---

## What Happens on Each Run

### 1. Google Maps Scraping
- Searches: "businesses in Fourways, Johannesburg, South Africa"
- Scrapes: Up to 100 businesses
- Extracts: Names, addresses, phones, ratings, websites

### 2. Website Enrichment
- Visits each business website
- Extracts: Emails, phone numbers, social media links
- Rate limited: 2 seconds between requests

### 3. Lead Scoring & Qualification
- Scores 0-100 based on data completeness
- **Automation fit bonus:**
  - **+20 points:** Real estate, law, medical, consulting, agencies, retail, restaurants
  - **+10 points:** Contractors, logistics, manufacturing
  - **+5 points:** Other industries

### 4. CRM Storage (Dual Write)
- **Primary:** Airtable (checks for duplicates by email, creates/updates)
- **Mirror:** Google Sheets (appends all leads for easy sharing)

### 5. AI Email Outreach
- **Claude Sonnet** (via OpenRouter) generates personalized emails
- **Messaging:** Consultative, automation-focused
- **ROI Claims:** 3x faster deals, 15-20h saved, 40% more leads
- **CTA:** Free 15-min automation audit
- **Sent via:** Gmail (ian@anyvisionmedia.com)
- **Rate limit:** 30 seconds between sends

### 6. Summary & Reporting
- Email sent to ian@anyvisionmedia.com after each run
- **Includes:**
  - Total leads found
  - Automation fit breakdown (high/medium/low)
  - Top industries found
  - Average lead score
  - Actionable next steps

---

## Configuration Summary

| Setting | Value |
|---|---|
| **Search Query** | `businesses` (all types) |
| **Location** | Fourways, Johannesburg, South Africa |
| **Max Results** | 100 per run |
| **Schedule** | Monday 9:00 AM (weekly) |
| **n8n Workflow** | https://ianimmelman89.app.n8n.cloud/workflow/uq4hnH0YHfhYOOzO |
| **Airtable Base** | https://airtable.com/app2ALQUP7CKEkHOz |
| **Google Sheet** | https://docs.google.com/spreadsheets/d/1E9_OSvO6F37iG9wh_gaetPT3IzuwdeSNbomIPXzKu94 |

---

## Testing Instructions

### Quick Test (5 Leads)
1. Open workflow: https://ianimmelman89.app.n8n.cloud/workflow/uq4hnH0YHfhYOOzO
2. Click on "Search Config" node
3. Change `maxResults` from `100` to `5`
4. Click "Test workflow" (top right)
5. Wait ~2-3 minutes
6. Check results:
   - **Airtable:** 5 new leads in your base
   - **Gmail Sent:** 3-5 outreach emails
   - **Your Inbox:** 1 summary email

### Review Checklist
- [ ] Airtable has data with correct fields
- [ ] "Automation Fit" field shows high/medium/low
- [ ] "Lead Score" is 0-100
- [ ] Gmail sent folder has outreach emails
- [ ] Emails are personalized and mention automation
- [ ] Summary email received with breakdown

---

## Email Examples You'll See

### High-Fit Business (Real Estate)
**Subject:** Struggling with follow-up timing?
**Focus:** Automated lead nurturing, instant responses, scheduled viewings

### High-Fit Business (Restaurant)
**Subject:** Automate reservations + reduce no-shows
**Focus:** Booking confirmations, SMS reminders, waitlist management

### Medium-Fit Business (Contractor)
**Subject:** Quote faster, book more jobs
**Focus:** Lead capture, instant quote scheduling

_(See [EMAIL_EXAMPLES.md](EMAIL_EXAMPLES.md) for 7 full examples)_

---

## Next Steps

### After First Test Run
1. **Check email quality** - are they compelling and industry-specific?
2. **Verify lead scoring** - do high-fit businesses score 70+?
3. **Review Airtable data** - is all data captured correctly?
4. **Adjust if needed:**
   - Edit AI prompt in "AI Generate Email" node
   - Change search parameters in "Search Config" node
   - Adjust lead scoring in "Score Leads" node

### After First Real Run (Monday)
1. **Monitor responses** (replies come to ian@anyvisionmedia.com)
2. **Track metrics:**
   - Total leads: Target 80-100 per run
   - High-fit %: Target >60% scoring 70+
   - Reply rate: Target 2-5% positive responses
3. **Prioritize high-fit leads** for follow-up (sort by Lead Score in Airtable)

---

## Files Created

| File | Purpose |
|---|---|
| `FOURWAYS_WORKFLOW_SUMMARY.md` | Complete overview, schedule, troubleshooting |
| `EMAIL_EXAMPLES.md` | 7 example emails across industries |
| `CREATE_AIRTABLE_BASE.md` | Instructions for base creation (completed) |
| `SETUP_COMPLETE.md` | This file - final configuration summary |
| `tools/deploy_lead_scraper.py` | Deployment script (updated with new base) |
| `tools/update_airtable_base.py` | Script to change base IDs (used) |

---

## Important Notes

### Automation Fit Priority
**Focus outreach on high-fit leads first:**
- Real estate agencies (follow-up automation)
- Law firms (client intake automation)
- Medical/dental (appointment reminders)
- Consulting (pipeline automation)
- Agencies (lead nurturing)
- Retail/restaurants (customer engagement)

### Email Deliverability
- Workflow sends max ~40-50 emails per run (not all leads have emails)
- 30-second delay between sends prevents spam flags
- All emails include unsubscribe option
- Monitor Gmail for any bounces or spam warnings

### CRM Management
- **Airtable** = primary (searchable, filterable, automation-ready)
- **Google Sheets** = mirror (easy sharing, reporting, exports)
- Both update on every run
- Duplicates prevented by email address

---

## Troubleshooting

### No Leads Found
- Check Google Maps has results for "businesses in Fourways"
- Try more specific search (e.g., "shops in Fourways")

### Few Emails Scraped
- Normal - only 40-60% of businesses show emails publicly
- Workflow prioritizes businesses with full contact info

### Low Reply Rate
- Review generated emails in Gmail sent folder
- Adjust AI prompt if too generic or salesy
- Consider A/B testing different subject lines

### Airtable Duplicates
- Workflow checks by email before creating
- If duplicates appear, check "Check Airtable Exists" node

---

## Support

**Workflow URL:** https://ianimmelman89.app.n8n.cloud/workflow/uq4hnH0YHfhYOOzO
**Airtable Base:** https://airtable.com/app2ALQUP7CKEkHOz

**Next Automatic Run:** Monday, February 17, 2026 at 9:00 AM

---

**🎉 Everything is configured and ready to go!**

**Test it now, or wait until Monday for the first automatic run.**
