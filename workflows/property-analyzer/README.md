# Property Analyzer - Plausibility Analysis Workflow

## Overview

n8n workflow that analyzes uploaded property documents (PDF/DOCX/images) and produces an investment viability score (0-100) with detailed subscores, pros/cons, and red flags.

**Trigger:** Webhook POST from the client portal upload page.

## Setup

### Prerequisites

1. n8n Cloud instance with API key
2. OpenRouter API key with Claude Sonnet access (credential ID: `9ZgHenDBrFuyboov`)
3. Supabase project with `002_property_analyzer.sql` migration applied
4. Storage bucket `property-docs` created in Supabase

### Environment Variables

```bash
# In .env
N8N_BASE_URL=https://ianimmelman89.app.n8n.cloud
N8N_API_KEY=your_key
N8N_PROPERTY_ANALYZER_WEBHOOK_URL=https://ianimmelman89.app.n8n.cloud/webhook/property-analyzer/analyze
PROPERTY_ANALYZER_WEBHOOK_SECRET=generate_random_64_char_token
```

### Deploy

```bash
cd tools
python deploy_property_analyzer.py build     # Save JSON only
python deploy_property_analyzer.py deploy    # Deploy to n8n
python deploy_property_analyzer.py activate  # Deploy + activate
```

## Pipeline Stages

1. **Ingest** - Receive webhook with file_url, run_id, config
2. **Parse** - Download file, extract text
3. **Extract** - LLM (Claude Sonnet via OpenRouter) extracts structured facts to JSON schema
4. **Geocode** - Nominatim forward geocoding (SA-specific)
5. **Enrich** - Overpass API for nearby POIs (schools, hospitals, shops, transport)
6. **Score** - 6 weighted subscores computed deterministically
7. **Report** - Results saved to Supabase via callback webhook

## Scoring Model

| Subscore | Weight | Source |
|----------|--------|--------|
| Document Completeness | 15% | Extracted document flags |
| Location & Amenities | 20% | Overpass API POI data |
| Crime & Safety | 20% | SAPS data (Phase 2) |
| Market & Growth | 20% | FNB HPI (Phase 2) |
| Deal Financial | 20% | Price vs valuation calculations |
| Risk & Red Flags | 5% | Automated risk checks |

## Nodes (19 total)

- 1 Webhook trigger
- 5 Status update HTTP requests (callback to web app)
- 2 HTTP requests (file download, Nominatim geocode)
- 1 HTTP request (Overpass API)
- 1 HTTP request (OpenRouter LLM)
- 5 Code nodes (text extraction, validation, geocode processing, POI processing, scoring engine)
- 1 Code node (final payload builder)
- 1 HTTP request (completed callback)
- 1 Respond to Webhook
- 1 Error Trigger + 1 Error Handler

## Troubleshooting

- **Nominatim rate limit:** 1 request/second. Do not run batch analyses.
- **Overpass timeout:** Increase timeout if getting 429s. Current: 30s.
- **LLM extraction empty:** Check if PDF has extractable text (not scanned images).
- **Callback fails:** Verify PROPERTY_ANALYZER_WEBHOOK_SECRET matches between .env files.
