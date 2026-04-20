# DEMO-07 — Meeting Notes → Action Machine

> **Headline result:** *"Meeting notes turned into action items instantly."*

## Business problem

Every meeting creates 3-8 action items. Nobody writes them down properly; half get lost; someone texts someone "who was doing X?" the next day. This workflow takes a raw transcript (paste, Otter/Fireflies export, or manual notes), extracts each action with owner + due date, emails every attendee a digest, logs each item in a shared Sheet, and drops a one-line summary into Slack.

## Target client

Consultancies, sales teams, agencies running weekly client syncs, any team that lives in meetings. Upsell from DEMO-05/13 when the client says "yeah but the bigger problem is actually follow-through."

## Demo scenario (90s)

1. Open the `Meeting_Actions` tab — empty.
2. Paste the fixture transcript (or a real one from your last call) into the webhook body.
3. ~20 seconds — every attendee gets a digest email with a table of actions, owners, due dates.
4. Sheet tab fills row-by-row.
5. Slack channel gets a one-liner: "Fourways Fitness kickoff — 4 actions captured."
6. "This is the fastest way to get team accountability. No note-taker needed."

## Architecture

```
Webhook Trigger (transcript)
  -> Demo Config (fixture meeting payload)
     -> DEMO_MODE Switch
        -> demo: Load Fixture Meeting
        -> live: Extract Live Meeting
     -> Merge Meeting Sources
     -> Build Extract Prompt
     -> AI Extract Actions (Sonnet 4, JSON)
     -> Parse & Fan Out Actions (one item per action + 1 summary header)
        -> Filter Actions Only
           -> Log Meeting Action (one row per action, Sheets append)
        -> Build Digest (HTML table + Slack text)
           -> Email Digest to Attendees (Gmail)
           -> Slack Digest
     -> Merge Branches
     -> Audit Log
     -> Respond
```

## Demo narration (beats)

1. **0:00** "I just left a kickoff call. 3 people, 15 min transcript. Watch what happens."
2. **0:15** Paste transcript, hit send.
3. **0:30** "Sheet is filling with the actions — Thandi owns the export by Wednesday, Ian owns the bot draft by Friday..."
4. **0:55** Switch to Gmail — digest email shows up. "Every attendee just got this table. They can't say they forgot."
5. **1:15** Slack channel buzzes. "Team lead sees the summary without opening the doc."

### Best opening shot
Empty Sheet + empty inbox side-by-side, with the transcript in a pre-composed Postman request.

### Before-vs-After angle
- **Before:** 20 min typing up notes after every call. Half the actions never make it to the tracker.
- **After:** Zero typing. Every action captured, assigned, and broadcast in under a minute.

## Credentials checklist

| Layer | Demo | Production |
|---|---|---|
| Gmail OAuth | `2IuycrTIgWJZEjBE` | client's OAuth |
| Google Sheets | demo sheet | client workbook |
| OpenRouter | shared | per-client |
| Slack | shared webhook | client workspace webhook |

## Example input

```json
POST /webhook/demo07-meeting-notes
{
  "demoMode": "1"
}
```

Live mode:
```json
{
  "demoMode": "0",
  "meetingTitle": "Weekly sync — ACME",
  "meetingDate": "2026-04-20",
  "attendees": [
    {"name":"Ian","email":"ian@anyvisionmedia.com"},
    {"name":"Pam","email":"pam@acme.co.za"}
  ],
  "transcript": "Full text or Otter/Fireflies export..."
}
```

## Example output row in `Meeting_Actions`

| Timestamp | Meeting_Title | Attendees | Action_Item | Owner | Due_Date | Status | Run_ID |
|---|---|---|---|---|---|---|---|
| 2026-04-20T08:24 | AnyVision <> Fourways kickoff | Ian, Kagiso, Thandi | Export last month of WhatsApp enquiries | Thandi | 2026-04-22 | open | RUN-... |

## Error handling

- AI returns malformed JSON -> Parse falls back to summary with 0 actions. Digest email still sends with the summary text.
- No attendees provided -> Gmail send fails soft (`onError: continueRegularOutput`). Slack still fires.
- Large transcripts (>6k tokens) -> AI prompt auto-truncated by the model; works up to ~20k tokens.

## Upsell path

- Connect to Fireflies / Otter / Fathom via their webhook so the meeting fires this automatically
- Sync actions into Asana / Notion / Linear tickets
- Weekly rollup report: "This week your team captured 47 actions, 31 completed"
- AI-graded action-item quality scoring (warn when someone is habitually missing deadlines)

## Run it

```bash
python tools/deploy_demo_07_meeting_notes.py deploy

curl -X POST https://ianimmelman89.app.n8n.cloud/webhook/demo07-meeting-notes \
  -H "Content-Type: application/json" -d '{"demoMode":"1"}'
```
