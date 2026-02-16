# Create Dedicated Airtable Base for Lead Scraper

Your API token doesn't have the `schema.bases:write` scope needed to create bases programmatically. Follow these steps to create the base manually, then I'll update the workflow.

---

## Step 1: Create New Base

1. Go to https://airtable.com
2. Click **"Create a base"** (or **"Add a base"**)
3. Choose **"Start from scratch"**
4. Name it: **`Lead Scraper - Fourways CRM`**
5. Click **"Create base"**

---

## Step 2: Get Base ID

Once the base is created:

1. Look at the URL in your browser. It will be: `https://airtable.com/appXXXXXXXXXXXX/...`
2. Copy the part that starts with `app` (e.g., `appAbc123Def456`)
3. **Save this Base ID** - you'll give it to me in the next step

---

## Step 3: Create "Leads" Table

Airtable creates a default table when you create a base. Rename it:

1. Click on the table name (probably "Table 1")
2. Rename to: **`Leads`**
3. Delete all the default fields

---

## Step 4: Add These Fields

Click **"+"** to add fields with these **exact names and types**:

| Field Name | Type | Options |
|---|---|---|
| **Business Name** | Single line text | (primary field) |
| **Email** | Email | |
| **Phone** | Phone number | |
| **Website** | URL | |
| **Address** | Single line text | |
| **Industry** | Single line text | |
| **Location** | Single line text | |
| **Rating** | Number | Format: Decimal (1.0) |
| **Social - LinkedIn** | URL | |
| **Social - Facebook** | URL | |
| **Social - Instagram** | URL | |
| **Lead Score** | Number | Format: Integer (100) |
| **Automation Fit** | Single select | Options: `high`, `medium`, `low` |
| **Status** | Single select | Options: `New`, `Email Sent`, `Followed Up`, `Responded`, `Converted`, `Unsubscribed` |
| **Source** | Single line text | |
| **Date Scraped** | Date | Format: ISO (2024-01-15) |
| **Email Sent Date** | Date | Format: ISO |
| **Notes** | Long text | |

### For Single Select Fields:

**Automation Fit:**
- Add option: `high` (green color)
- Add option: `medium` (yellow color)
- Add option: `low` (gray color)

**Status:**
- Add option: `New` (blue color)
- Add option: `Email Sent` (yellow color)
- Add option: `Followed Up` (orange color)
- Add option: `Responded` (green color)
- Add option: `Converted` (dark green color)
- Add option: `Unsubscribed` (red color)

---

## Step 5: Get Table ID

After creating all fields:

1. Click on the table name dropdown (top left)
2. Right-click the "Leads" table → **"Copy table URL"** (or just look at the URL)
3. The URL will be: `https://airtable.com/appXXXXXXXXXXXX/tblYYYYYYYYYYYYY/...`
4. Copy the part that starts with `tbl` (e.g., `tblAbc123Def456`)
5. **Save this Table ID**

---

## Step 6: Give Me the IDs

Once you have both IDs, paste them here in this format:

```
Base ID: appXXXXXXXXXXXX
Table ID: tblYYYYYYYYYYYY
```

I will then:
1. Update the workflow to use your new dedicated base
2. Redeploy it
3. Verify everything is connected

---

## Quick Copy-Paste for Fields

If you want to speed up field creation, create them in this order and these types:

```
1. Business Name - Single line text
2. Email - Email
3. Phone - Phone number
4. Website - URL
5. Address - Single line text
6. Industry - Single line text
7. Location - Single line text
8. Rating - Number (decimal, 1 place)
9. Social - LinkedIn - URL
10. Social - Facebook - URL
11. Social - Instagram - URL
12. Lead Score - Number (integer)
13. Automation Fit - Single select (high, medium, low)
14. Status - Single select (New, Email Sent, Followed Up, Responded, Converted, Unsubscribed)
15. Source - Single line text
16. Date Scraped - Date (ISO format)
17. Email Sent Date - Date (ISO format)
18. Notes - Long text
```

---

## Alternative: Keep Using Current Base

If you prefer to keep using the existing base (`appzcZpiIZ6QPtJXT - Whatsapp Multi Agent`), that's fine too. The "Leads" table is already set up there. Just let me know and I'll make sure it has all the right fields.

---

**Once you provide the Base ID and Table ID, I'll update the workflow in under 30 seconds.**
