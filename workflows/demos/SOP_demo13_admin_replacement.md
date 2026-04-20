# DEMO-13 — Admin Replacement System

> **Headline result:** *"Replace 3 admin jobs with one automation."*

## Business problem

Every SMB has three unfilled admin seats: the person who replies to emails, the person who updates the CRM, the person who schedules follow-ups. Most owners do all three themselves, badly, for 4 hours a day. This workflow replaces all three with ONE trigger, narrating the story visually — three parallel branches light up at the same time, each clearly labelled with the job it's replacing.

This is the strong-opinion pitch closer: *"I'm not selling you 'AI tools'. I'm selling you 3 fewer admin jobs."*

## Target client

Business owners who do their own admin. Consultants, agency founders, boutique service firms. The kind of prospect who says "I don't need tech, I need time back." This is the demo that converts them.

## Demo scenario (90s)

1. "Every lead that comes through your site creates 3 jobs. Here they are."
2. Open the n8n canvas. Point at the three labelled branches: `[A] Send Reply`, `[B] Upsert CRM Client`, `[C] Slack Ping + Schedule Follow-Up`.
3. Fire fixture payload. Watch all 3 branches light up simultaneously.
4. Tab through the 3 outputs:
   - Gmail sent: personalised reply to the lead.
   - `CRM_Clients` tab: row populated with industry + score.
   - Slack channel: "New lead :fire: ...".
   - `Follow_Ups` tab: 48h nurture row scheduled.
5. "One webhook. Three admin jobs. Done."

## Architecture

```
Webhook Trigger
  -> Demo Config
     -> DEMO_MODE Switch
        -> demo: Load Fixture Lead
        -> live: Normalise Live Input
     -> Merge Sources
     -> Build Prompt
     -> AI Classify + Draft (Sonnet)
     -> Parse Output
        -> [parallel fan-out — all 3 fire simultaneously]
           [A] Send Reply (Gmail)  ->  [A] Log Lead (Leads_Log)
           [B] Upsert CRM Client (Sheets appendOrUpdate)
           [C] Slack Ping Sales  ->  [C] Schedule 48h Follow-Up
        -> Merge Branches
        -> Audit Log
        -> Respond
```

Node labelling is deliberate: `[A]` / `[B]` / `[C]` prefixes make the three jobs visually obvious on the n8n canvas. That's the pitch device.

## Demo narration (beats)

1. **0:00** "You do 3 jobs every time a lead comes in. Reply. Update CRM. Schedule follow-up. Right?"
2. **0:10** "Watch one workflow do all three. At the same time." Fire the webhook.
3. **0:20** Tab to Gmail: reply sent.
4. **0:30** Tab to CRM Sheet: row updated.
5. **0:40** Tab to Slack: new-lead alert with score.
6. **0:55** Tab to Follow_Ups: auto-scheduled for 48h.
7. **1:20** "That was one automation doing three admin jobs. Every lead. Every day. Forever."

### Best opening shot
n8n canvas zoomed on the post-AI fan-out — three branches labelled [A], [B], [C] visibly splitting from one parent node. Gold for screen recording.

### Before-vs-After angle
- **Before:** 3 seats, 3 hours a day, 3 places leads fall through the cracks.
- **After:** 0 seats, 15 seconds per lead, 0 missed handoffs.

## Credentials checklist

| Branch | Demo | Production |
|---|---|---|
| [A] Gmail OAuth | shared | client OAuth |
| [A] Google Sheets (Leads_Log) | demo | client workbook |
| [B] Google Sheets (CRM_Clients) | demo | client workbook |
| [C] Slack webhook | shared | client workspace webhook |
| [C] Google Sheets (Follow_Ups) | demo | client workbook |
| AI | OpenRouter shared | per-client budget |

## Example input

```json
POST /webhook/demo13-admin-replacement
{
  "demoMode": "1"
}
```

Live mode: full form payload same shape as DEMO-12.

## Example outputs (simultaneous)

**Gmail** — Subject: `Re: NextGen Installs — automation + admin`
```html
<p>Sbu — great timing. We ship a full lead + admin automation pack in
your ballpark (R15k/mo Standard). 2-week setup, live in week 3. Free
Tuesday 10:00 for a 20-min walkthrough?</p>
<p>Ian</p>
```

**CRM_Clients row:**
| Client_ID | Name | Company | Email | Phone | Last_Contacted | Ask | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| CLT-1745... | Sibusiso Ndlovu | NextGen Installs | sbu@nextgen-installs.co.za | +27 82 555 0177 | 2026-04-20T08:42 | Automate lead replies + admin... | hot | industry=Solar installation score=8 |

**Slack:** `New lead :fire: (8/10, hot) — Sibusiso Ndlovu (NextGen Installs): Automate lead replies + admin. R15k/mo budget.`

**Follow_Ups row:** `FU-CLT-1745...`, Scheduled_For=2026-04-22, Type=lead-nurture, Status=due.

## Error handling

- AI fails -> safe-default values (`intent=question`, `score=5`, generic reply). Still fans out to all 3 branches so the demo narrative holds.
- Any branch fails -> others complete. Merge node appends whatever arrives. Audit logs whichever leg errored.
- Duplicate lead (same email) -> `[B]` upsert updates instead of inserting; `[A]` + `[C]` still fire.

## Upsell path

- Add a 4th branch: Notion "pipeline" page updated for visual kanban
- Add a 5th branch: WhatsApp message to the lead's number for hot-intent (score ≥ 9)
- Weekly "admin replacement dashboard": hours saved × hourly rate = monthly value
- Per-industry prompt tuning (legal, logistics, beauty, health)

## Run it

```bash
python tools/deploy_demo_13_admin_replacement.py deploy

curl -X POST https://ianimmelman89.app.n8n.cloud/webhook/demo13-admin-replacement \
  -H "Content-Type: application/json" -d '{"demoMode":"1"}'
```
