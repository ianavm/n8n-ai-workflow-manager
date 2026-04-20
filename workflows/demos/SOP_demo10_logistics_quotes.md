# DEMO-10 — Logistics Quote Request Handler

> **Headline result:** *"Quote request handled automatically."*

## Business problem

Every freight/warehousing SMB has the same bottleneck: a website form fires a quote request, it sits in someone's inbox until they find time to calculate, draft a response, send it — and by then the lead has requested 3 other quotes. Industry response-time benchmark is 4-24 hours. This workflow makes it **90 seconds**, with a plausible estimate, transit days, and a 72-hour follow-up scheduled automatically.

**Niche-specific by design.** When you're pitching a warehousing or 3PL prospect, showing a workflow tailored to THEIR form fields (origin, destination, weight, pallets) beats any generic lead-reply demo by a mile.

## Target client

3PLs, warehousing companies, freight brokers, last-mile delivery ops in SA. This demo opens the whole logistics vertical — and the R500B+ SA freight market has exactly zero "AI-first" competitors right now.

## Demo scenario (90s)

1. Open the quote form (real HTML page or Postman screen). Show the 10 fields.
2. Fill: PE -> Midrand, 4200kg, 6 pallets, ambient beverages, pickup 2026-04-25.
3. Hit submit.
4. ~30s: Quote email lands in the "customer" inbox (you) — proper R-amount, transit days, rationale paragraph.
5. Switch to `Quotes_Log` — new row with Quote_ID, company, lane, estimate.
6. Switch to `Follow_Ups` — 72h follow-up row auto-scheduled for this quote.
7. "If they don't reply in 3 days, DEMO-08 auto-chases them. You never lose another quote to silence."

## Architecture

```
Webhook Trigger (origin, destination, weight_kg, pallet_count, ...)
  -> Demo Config (fixture quote payload)
     -> DEMO_MODE Switch
        -> demo: Load Fixture Quote
        -> live: Normalise Quote Fields
     -> Merge Quote Sources
     -> Build Quote Prompt (pricing heuristics baked into prompt)
     -> AI Draft Quote (Sonnet, generates estimateZAR + transitDays + HTML body)
     -> Parse Quote (fallback rough calc if AI fails)
     -> Send Quote Email (Gmail)
     -> Log Quote (Quotes_Log)
     -> Create 72h Follow-Up (Follow_Ups append, dated +72h, status=due)
     -> Audit Log
     -> Respond
```

## Demo narration (beats)

1. **0:00** "Warehousing clients bleed leads. They take 4 hours to quote. I do it in 90 seconds."
2. **0:10** Fill form. Hit submit.
3. **0:25** Cut to Gmail — quote email, R82,000 estimate, 2-day transit, rationale.
4. **0:50** Sheet — row added. `Quotes_Log` table grows live.
5. **1:05** Follow-Ups tab — auto-scheduled for 72h from now.
6. **1:25** "Next quote request. Same 90 seconds. Night or day. No forgotten quotes."

### Best opening shot
The quote form pre-filled on screen, with your finger hovering on submit.

### Before-vs-After angle
- **Before:** 4-24 hour reply time. 30% of quotes lost to faster competitors.
- **After:** 90 seconds. Every quote is professional, logged, and auto-followed-up.

## Credentials checklist

| Layer | Demo | Production |
|---|---|---|
| Gmail OAuth | shared | client OAuth with freight-branded signature |
| Google Sheets | demo sheet | client workbook |
| OpenRouter | shared | per-client (pricing logic becomes proprietary) |

**Production note:** The pricing heuristics in the prompt (`R18/km per pallet`) are placeholders. For a real client, replace with their actual lane-rate table, fuel levy, and surcharge rules. Offer a 1-week "pricing calibration" service when upselling.

## Example input (full production form)

```json
POST /webhook/demo10-logistics-quote
{
  "demoMode": "0",
  "company": "Karoo Craft Beverages",
  "contactName": "Pieter de Villiers",
  "contactEmail": "pieter@karoocraft.co.za",
  "contactPhone": "+27 82 555 0132",
  "origin": "Port Elizabeth, EC",
  "destination": "Midrand, GP",
  "weightKg": 4200,
  "palletCount": 6,
  "cargoType": "Ambient beverages (glass bottles)",
  "pickupDate": "2026-04-25",
  "notes": "Prefer arrival before 08:00 on 25 April."
}
```

## Example output quote email

> Subject: Quote Q-2026-4827 — Port Elizabeth, EC -> Midrand, GP
>
> Hi Pieter,
>
> Thanks for the request — here is our indicative rate for the PE -> Midrand lane:
>
> **Estimate: R 82,300 (incl. VAT)**
> **Transit: 2 days** (pickup 25 April, arrival before 08:00 on 27 April)
>
> Based on ~1,100 km at standard pallet rate, +20% for glass handling, plus overnight surcharge for the pre-08:00 arrival.
>
> If the number works, reply "book" and I will hold the truck.
>
> Ian

## Error handling

- AI estimate unparseable -> falls back to deterministic calc (R18/km × pallets × 1.15 VAT).
- Missing weight/pallets -> defaults to 1 pallet so the workflow still produces a number.
- Gmail fails -> Sheet row still created, audit row records error.

## Upsell path

- Live lane-rate tie-in (client's own rate table via Sheet)
- Google Maps distance lookup (dynamic km instead of baked ranges)
- Integrate with Transporter/Afrigis for driver availability check
- Dashboard: quote win rate by lane / customer / weight bucket

## Run it

```bash
python tools/deploy_demo_10_logistics_quotes.py deploy

curl -X POST https://ianimmelman89.app.n8n.cloud/webhook/demo10-logistics-quote \
  -H "Content-Type: application/json" -d '{"demoMode":"1"}'
```
