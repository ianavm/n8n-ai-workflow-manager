# DEMO-06 — Smart Lead Reply Bot (Inbox)

> **Headline result:** *"Every inbox lead gets a draft reply in 10 seconds."*

## Business problem

The blank reply box is where deals die. Your inbox has 30 unread lead emails, each wants a thoughtful response, and the "I'll reply properly later" bucket is a graveyard. This workflow writes the first draft for you — thread-aware, brand-voiced — then saves it AS A DRAFT (not sent). You review, tweak, click send. 80% of the work is done; the last mile stays human.

Different from DEMO-05 (which auto-sends from a webform). This one plugs into your actual inbox, respects the drafts folder, and is positioned for operators who don't trust full automation yet.

## Target client

Solo operators, consultants, boutique firms, lawyers, anyone who reads and personally replies to leads. The "I want help but not autopilot" crowd. Very easy upsell from DEMO-05.

## Demo scenario (60s)

1. Screenshare Gmail, point at an unread "lead" email labelled `leads`.
2. Fire webhook (or wait for the next Gmail Trigger poll — 60s).
3. Switch back to Gmail Drafts — new draft appears in the same thread, 3 sentences, answering the lead's actual questions.
4. Open the Google Sheet `Gmail_Drafts_Log` tab — row added, status=pending-review.
5. "You've gone from 0 to 80% done without touching a keyboard."

## Architecture

```
Gmail Trigger (INBOX) ----\
Webhook Trigger ----------+-> Demo Config
                              -> DEMO_MODE Switch
                                 -> demo: Load Fixture Thread
                                 -> live: Extract Live Thread
                              -> Merge Thread Sources
                              -> Build Draft Prompt
                              -> AI Draft Reply (Sonnet, thread-aware)
                              -> Parse Draft
                              -> Save Draft in Thread (Gmail draft op)
                              -> Log Draft (Gmail_Drafts_Log)
                              -> Log Lead (Leads_Log)
                              -> Audit Log
```

## Demo narration (beats)

1. **0:00** "Here's my inbox. 12 unread leads. Each would take me 5 minutes to reply properly."
2. **0:10** "Now watch." Trigger fires.
3. **0:25** Open drafts folder. "That's 11 drafts ready. I review, tweak the one that needs it, click send."
4. **0:50** "30 seconds of review vs an hour of drafting. That's the real ROI."

### Best opening shot
Gmail inbox with 10+ unread lead emails. The drafts-filling-in moment is the wow.

### Before-vs-After angle
- **Before:** Blank reply box, 5 minutes of context-gathering per email, burn-out by noon.
- **After:** Drafts are waiting. You edit, don't write. Inbox zero by 10:00.

## Credentials checklist

| Layer | Demo | Production |
|---|---|---|
| Gmail OAuth | `2IuycrTIgWJZEjBE` (AVM) | client's own OAuth |
| Gmail label filter | `INBOX` | client-created `leads` label |
| Google Sheets | demo sheet | client workbook |
| OpenRouter | shared cred | per-client budget cap |

## Example fixture

```json
{
  "threadId": "thread-fx-06-001",
  "from": {"name": "Thandi Dlamini", "email": "thandi@greenleaf.co.za"},
  "subject": "Re: Interested in automation",
  "latestMessage": {
    "body": "Do you integrate with Shopify? Pricing for a team of 6?",
    "date": "2026-04-20T08:43:00Z"
  },
  "priorMessages": [...]
}
```

## Example draft output

Subject: `Re: Interested in automation`
Body:
```html
<p>Hi Thandi, quick answers — yes, we integrate with Shopify (webhooks + a
custom Orders tab). For a team of 6, our Standard tier at R7,500/mo covers
full admin automation plus 2 check-ins a month. Happy to walk it through
Thursday at 14:00 if that suits?</p>
<p>Ian</p>
```

## Error handling

- Gmail trigger polling disabled automatically if the cred is invalid. Webhook still works for on-demand demos.
- AI returns invalid JSON -> fallback draft "Thanks for the note — will respond shortly" is saved so the thread still has a draft.

## Upsell path

- Add AI-generated agenda for the proposed call (Calendar event draft)
- Sentiment check on the thread; escalate negative-sentiment replies to a human-only queue
- Auto-pull 2 recent product-updates into the draft (content-aware)
- Team rules: drafts signed by the owner of the lead's account manager (team inbox)

## Run it

```bash
python tools/deploy_demo_06_inbox_reply_bot.py deploy
python tools/deploy_demo_06_inbox_reply_bot.py activate   # enables Gmail polling

curl -X POST https://ianimmelman89.app.n8n.cloud/webhook/demo06-inbox-reply-bot \
  -H "Content-Type: application/json" -d '{"demoMode":"1"}'
```
