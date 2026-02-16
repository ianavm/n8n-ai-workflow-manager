# SOP: Lead Generating Web Scraper & CRM Automation (v2)

## Quick Start

1. Open n8n and navigate to "Lead Generating Web Scraper & CRM Automation"
2. Edit the **Search Config** node to set your target:
   - `searchQuery` - The type of business (e.g., "dentists", "restaurants", "plumbers")
   - `location` - Geographic target (e.g., "Johannesburg", "Cape Town CBD")
   - `maxResults` - How many results to process (max 20 per page via Places API)
   - `googlePlacesApiKey` - Your Google Cloud API key (already configured)
3. Click **Test Workflow** to run manually, or leave active for weekly Monday runs

## How the Google Places API Works

The workflow uses the **Google Places API (New)** Text Search endpoint:
- Searches for businesses matching your query + location
- Returns structured data (name, address, phone, website, rating)
- Much more reliable than the old HTML scraping approach
- Costs ~$0.032 per request (20 results per call)
- API key is stored in the Search Config node

## Changing Target Industries

Edit the **Search Config** node:
```
searchQuery: "accountants"    # Change this
location: "Sandton"           # Change this
maxResults: 20                # Max 20 per API page
```

## Monitoring Runs

- Check your Gmail for summary reports after each run
- Check Airtable "Leads" table for new entries
- Check Google Sheets "LEAD GEN EMAILSCRAPER" for the full log
- Error notifications are sent automatically to ian@anyvisionmedia.com

## Managing Leads in Airtable

Status progression:
- **New** - Just scraped, automated outreach email sent
- **Email Sent** - Outreach email confirmed sent
- **Followed Up** - Manual follow-up done (update manually)
- **Responded** - Lead replied (update manually)
- **Converted** - Lead converted to client (update manually)
- **Unsubscribed** - Opted out (update manually)

## Customizing Email Templates

The email content is AI-generated per lead. To adjust the tone/style:
1. Edit the **AI Generate Email** node's prompt
2. Modify the HTML template in the **Format Email** node
3. Brand color is set to `#FF6D5A` in the template

## Error Handling

The workflow has built-in error resilience:
- **Scrape Website** - continues to next business if one fails
- **Extract Contact Info** - falls back gracefully if loop reference breaks
- **Format Email** - tries multiple data sources (Filter New Leads -> Score Leads -> input)
- **Error Trigger** - sends email alert on any unhandled failure

## Troubleshooting

| Issue | Solution |
|---|---|
| No businesses found | Check the Places API key is valid and the query/location makes sense |
| Places API error 403 | Verify Places API is enabled in Google Cloud Console |
| Places API error 429 | Rate limit hit - reduce maxResults or increase schedule interval |
| No emails extracted | Target businesses may not list emails on their websites |
| Airtable errors | Check credential "Whatsapp Multi Agent" is still valid |
| Gmail errors | Re-authorize "Gmail account AVM Tutorial" OAuth |
| AI email generation fails | Check OpenRouter credit balance |
| Duplicate emails sent | Check Filter New Leads node - should only pass Status="New" |

## Google Places API Billing

- Text Search: ~$32 per 1,000 requests
- Each request returns up to 20 results
- At 50 leads/week, that's ~3 requests = ~$0.10/week
- Monitor usage at: console.cloud.google.com > APIs & Services > Dashboard
