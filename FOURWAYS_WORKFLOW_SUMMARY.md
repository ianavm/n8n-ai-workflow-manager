# Fourways All-Business Lead Scraper - Revision Summary

## Overview
Workflow revised to target ALL businesses in Fourways with a compelling automation-focused value proposition.

---

## What Changed

### 1. **Search Scope - WIDENED**
| Before | After |
|---|---|
| "dentists" in Johannesburg | **ALL businesses** in Fourways, Johannesburg |
| 50 max results | **100 max results** |
| Single industry focus | Multi-industry (real estate, legal, medical, consulting, retail, restaurants, contractors, etc.) |

### 2. **Messaging - AUTOMATION VALUE PROP**

**Core Promise:**
- ⚡ **Close deals 3x faster** through automated follow-ups and nurture sequences
- ⏰ **Save 15-20 hours/week** by eliminating manual data entry and scheduling
- 📈 **Generate 40% more leads** with automated marketing and CRM workflows

**Email Approach:**
- ❌ **NOT:** Generic "I came across your business..."
- ✅ **YES:** Consultative, industry-specific pain point identification
- ✅ **YES:** Concrete ROI (time saved OR revenue gained OR cost reduced)
- ✅ **YES:** FREE 15-min automation audit (no pitch, just value)

**Example Subject Lines:**
- Real estate: `Struggling with follow-up timing?`
- Law firms: `Automate legal workflows - save 15h/week`
- Dental clinics: `Close 3x more appointments with automation`
- Restaurants: `Save 12h/week automating reservations & orders`

### 3. **Lead Qualification - AUTOMATION FIT SCORING**

Leads are now scored with an **automation fit bonus** (+0 to +20 points):

| Fit Level | Industries | Bonus | Focus |
|---|---|---|---|
| **High** (+20) | Real estate, law, medical, dental, consulting, agencies, marketing, insurance, accounting, retail, restaurants, salons, fitness, hotels | +20 pts | CRM automation, follow-up sequences, lead nurturing |
| **Medium** (+10) | Manufacturing, logistics, construction, contractors, plumbing, HVAC, landscaping, cleaning, automotive | +10 pts | Workflow automation, scheduling, invoicing |
| **Low** (+5) | Other industries | +5 pts | Basic lead capture |

### 4. **Email Template - BRANDED & CONSULTATIVE**

**Header:**
```
AnyVision Media
Business Automation & Lead Generation
```

**Body Structure:**
1. Personalized opening showing industry knowledge
2. ONE specific automation opportunity for their business type
3. Quick win example: "We helped [similar business] save 12 hours/week..."
4. ROI in concrete terms
5. CTA: Free 15-min automation audit

**Footer:**
- Professional signature (Ian Immelman, Director)
- Unsubscribe option
- "Listed on Google Maps in Fourways" transparency note

### 5. **Summary Reporting - AUTOMATION INSIGHTS**

After each run, you'll receive an email with:
- **Total leads found**
- **Automation fit breakdown:**
  - 🟢 High Fit: X businesses (prioritize these)
  - 🟡 Medium Fit: Y businesses
  - ⚪ Low Fit: Z businesses
- **Top industries found** (e.g., "real estate (15), law firms (8), restaurants (12)")
- **Actionable next steps** (which leads to prioritize)

---

## Business Types Targeted

### High-Priority (High Automation Fit)
Real estate agencies, law firms, medical clinics, dental practices, consulting firms, marketing agencies, insurance brokers, accounting firms, finance advisors, restaurants, retail stores, salons, spas, fitness centers, gyms, hotels

### Medium-Priority (Medium Automation Fit)
Manufacturing, logistics companies, construction firms, contractors (plumbing, electrical, HVAC), landscaping services, cleaning services, automotive repair

### Also Included
Any other business type in Fourways

---

## Data Captured Per Lead

| Field | Source | Usage |
|---|---|---|
| Business Name | Google Maps | Personalization |
| Email | Website scrape | Outreach |
| Phone | Maps + Website | Multi-channel |
| Website | Google Maps | Validation |
| Address | Google Maps | Location targeting |
| Industry | Search context | Personalization |
| Rating | Google Maps | Quality signal |
| Social Links | Website scrape | Multi-channel, credibility |
| **Lead Score** | Algorithm | Prioritization (0-100) |
| **Automation Fit** | Industry analysis | Strategic segmentation |

---

## CRM Structure (Airtable + Google Sheets)

**Airtable "Leads" Table** (Dedicated Base: `app2ALQUP7CKEkHOz`)
- Business Name, Email, Phone, Website, Address
- Industry, Location, Rating
- Social - LinkedIn, Facebook, Instagram
- **Lead Score** (0-100 with automation bonus)
- **Automation Fit** (high/medium/low)
- Status (New → Email Sent → Followed Up → Responded → Converted)
- Source, Date Scraped, Email Sent Date
- **Notes** (Auto-populated with automation opportunity)

**Google Sheets Mirror:**
- Same columns for easy sharing/reporting
- Headers auto-create on first run

---

## Schedule

**Automatic Run:** Every Monday at 9:00 AM
**Manual Run:** Available via n8n UI ("Test workflow" button)

---

## Recommended First Test

1. Open workflow in [n8n UI](https://ianimmelman89.app.n8n.cloud/workflow/uq4hnH0YHfhYOOzO)
2. Edit "Search Config" node
3. Change `maxResults` from `100` to `10` (small test)
4. Click "Test workflow"
5. Check:
   - Airtable "Leads" table for data
   - Your email for summary
   - Gmail sent folder for outreach emails

**Expected results (test with 10):**
- ~8-10 leads found
- ~3-5 high-automation-fit businesses
- ~3-5 emails sent (only to new leads with emails)
- 1 summary email to ian@anyvisionmedia.com

---

## Next Steps After First Run

1. **Review high-fit leads** in Airtable (sort by Lead Score descending)
2. **Check email deliverability** (sent folder + any bounces)
3. **Monitor responses** (replies will come to ian@anyvisionmedia.com)
4. **Adjust messaging** if needed (edit AI prompt in "AI Generate Email" node)
5. **Scale up** (increase maxResults back to 100 for full coverage)

---

## Key Metrics to Track

- **Lead Score Distribution:** Aim for >60% high-fit (score 70+)
- **Email Open Rate:** Target 15-25% (check Gmail tracking if enabled)
- **Reply Rate:** Target 2-5% positive responses
- **Meeting Booking Rate:** Target 1-3% of total leads

---

## Troubleshooting

| Issue | Solution |
|---|---|
| No leads found | Check Google Maps has results for "businesses in Fourways" |
| No emails scraped | Normal - not all sites show emails publicly. Expect ~40-60% hit rate |
| Gmail rate limit | Workflow has 30s delay between sends. Consider splitting large runs |
| Airtable duplicates | Workflow checks existing records by email before creating |
| Low reply rate | Review AI-generated emails, adjust prompt for more personalization |

---

## Files Modified

- **Workflow:** `uq4hnH0YHfhYOOzO` (Lead Generating Web Scraper & CRM Automation)
- **Deployment script:** `tools/deploy_lead_scraper.py` (includes OpenRouter credential fix)
- **Backup:** `.tmp/backups/lead_scraper_original.json`

---

## Support Resources

- **n8n Workflow URL:** https://ianimmelman89.app.n8n.cloud/workflow/uq4hnH0YHfhYOOzO
- **Airtable Base (Dedicated):** https://airtable.com/app2ALQUP7CKEkHOz
- **Google Sheet:** https://docs.google.com/spreadsheets/d/1E9_OSvO6F37iG9wh_gaetPT3IzuwdeSNbomIPXzKu94

---

**Status:** ✅ ACTIVE and scheduled
**Last Updated:** 2026-02-12
**Deployed By:** Claude Code Agent
