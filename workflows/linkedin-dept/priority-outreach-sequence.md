# Priority Outreach Send Sequence

> **Goal:** Send 14 verified priority leads (10 unique accounts + 4 multi-threads) over 5 weeks so it reads as "Ian is doing thoughtful BD on a handful of accounts at a time" — not as a batch blast from an automated tool.
>
> **Paired with:** [priority-outreach-drafts.md](./priority-outreach-drafts.md) (the actual message bodies)
>
> **Built:** 2026-04-14 (Tuesday). Expanded 2026-04-14 to include 6 new unique accounts + 4 multi-thread parallel contacts. Roundr/Jansen on conditional checkpoint (re-check 2026-04-21).
>
> **Pipeline at a glance:** 14 records / 10 unique companies / 5 industries (proptech, marketing agencies, recruiting/staffing, financial advisory, accounting, legal tech, subscription DTC) / mix of SA + US targets / 4 confirmed-live hiring hooks.

---

## Cadence Principles (why this schedule works)

1. **Max 1 send per calendar day.** Two in one day reads as a batch even if the messages are different.
2. **Tuesday–Thursday only.** Friday inboxes go unopened, Monday inboxes are chaos.
3. **Morning local time for the recipient** (09:00–11:00 their TZ). Milan and Eric are US-based so their windows are in *your* afternoon.
4. **JHB targets get the connect-first play.** For SA peers, a connection invite + short note (hybrid, LinkedIn lets you attach a note up to 300 chars) is warmer than a cold InMail and gets ~3x higher accept rate.
5. **US targets get the cold-DM play.** Milan and Eric get 50+ cold InMails daily — the *message itself* is the quality signal, not the connection warmth.
6. **Each send has a 5-minute pre-flight ritual** (see below). Skip it and the message looks generic even when it isn't.

---

## Pre-Flight Ritual (every send, 5 min)

Before hitting send on ANY of the 4:

1. **Open the target's LinkedIn profile** — scroll the last 14 days of activity.
2. **Find one post, comment, or shared article** to reference in your opening line. If you can't find one, reference a recent company announcement, press, or podcast appearance. **No generic opener.**
3. **Spot-check the hook is still valid** — for Talent Sam and Sweat Pants Agency, check the Himalayas job post is still live (use the verifier: `python tools/verify_priority_accounts.py`).
4. **Paste from the drafts file, then personalize the first line** — leave the rest of the body as-is (it's already tight).
5. **Update the Airtable record** with status + timestamp after sending (see Response Tracking section).

If any step fails (no recent activity, hook died, can't find a hook): **do not send**. Come back tomorrow with a different angle or skip the target.

---

## The Schedule (5 weeks, 14 records, 1-send-per-day max)

### Quick reference table

| Date | Day | Lead ID | Target | Account | Channel | Send window |
|---|---|---|---|---|---|---|
| **Tue 04-14** | TODAY | LI-PRIORITY-003 | Luke Marthinusen | MO Agency | LI connect+note | 11:00–11:30 SAST |
| Wed 04-15 | Day 2 | LI-PRIORITY-002 | Milan Levy | Talent Sam | LI cold DM | 15:30 SAST (09:30 EDT) |
| Thu 04-16 | Day 3 | LI-PRIORITY-005 | Eric Carlson | Sweat Pants Agency | LI cold DM | 15:30 SAST (09:30 EDT) |
| Tue 04-21 | Day 8 | LI-PRIORITY-004 | Mel Muller | Kontak Recruitment | LI connect+note | 09:30 SAST |
| Tue 04-21 | — | LI-PRIORITY-001 | **Roundr / Jansen Myburgh** — connection checkpoint | Roundr | (re-check accept) | 09:30 SAST |
| Wed 04-22 | Day 9 | LI-PRIORITY-006 | Gil Sperling | Flow (proptech) | LI cold DM | 09:30 SAST |
| Thu 04-23 | Day 10 | LI-PRIORITY-010 | Steven Szaronos | Bespoke Post | LI cold DM | 15:30 SAST (09:30 EDT) |
| Tue 04-28 | Day 15 | LI-PRIORITY-007 | Magnus Heystek | Brenthurst Wealth | LI connect+note | 09:30 SAST |
| Wed 04-29 | Day 16 | LI-PRIORITY-009 | Yusha Davidson | BriefCo / Legal Lens | LI cold DM | 09:30 SAST |
| Thu 04-30 | Day 17 | LI-PRIORITY-008 | Willem Haarhoff | DoughGetters Accounting | LI connect+note | 09:30 SAST |
| Tue 05-05 | Day 22 | LI-PRIORITY-003B | Petrumarié Jacobs | MO Agency *(if Luke silent)* | LI cold DM | 09:30 SAST |
| Wed 05-06 | Day 23 | LI-PRIORITY-002B | Daniel Schwartz | Talent Sam *(if Milan silent)* | LI cold DM | 15:30 SAST |
| Thu 05-07 | Day 24 | LI-PRIORITY-005B | Landon Shaw II | Sweat Pants *(if Eric silent)* | LI cold DM | 15:30 SAST |
| Tue 05-12 | Day 29 | LI-PRIORITY-004B | Angie Le Roux | Kontak *(if Mel silent)* | LI connect+note | 09:30 SAST |

**Hard rules:**

- Multi-thread sends (`-B` records) are **conditional**. If the primary contact at the same company responds positively before the multi-thread send date, **DO NOT SEND** the multi-thread message. Let the primary become the champion who loops in colleagues internally.
- All "Tue/Wed/Thu only" — Fri/Sat/Sun/Mon are deliberately empty (see "Cadence Principles" above).
- Randomize seconds within each send window (10:03, 10:17, 10:41 — never on the :00).
- After every send, update the record's `Source Metadata` `send_log` array (see Response Tracking section).

### Detailed plays per week

---

### 📅 Week 1 — Tier 1 Originals (the strongest hooks)

#### Day 1 — Tuesday 2026-04-14 (TODAY) — Luke Marthinusen / MO Agency

**Send window:** **TODAY 11:00–11:30 SAST** *(sends now while his inbox is still in morning-focus mode)*
**Channel:** LinkedIn **connection invite with note** *(not InMail — the hybrid is warmer for SA peers)*
**Why first:** Local, SA-based, highest-LTV retainer-expansion pitch, lowest downside if the timing is wrong. Starts the week with the warmest-cold target on the list.

**Message (paste into LinkedIn connect note, max 300 chars):**

> Hi Luke — [1 sentence referencing a recent post of his]. Running AVM Media in JHB, building Apify + Claude pipelines for SA marketing teams. Saw MO's Elite HubSpot tier with Investec/Mazda and thought there was a retainer-expansion play worth 20 min. Would love to connect.

**If note limit is too tight:** Send plain connection invite (no note), wait for accept, then send the full draft from `priority-outreach-drafts.md` Priority 3 as a follow-up DM within 24h of accept.

**Update Airtable after send:** See Response Tracking.

---

### 📅 Day 2 — Wednesday 2026-04-15 — Milan Levy / Talent Sam

**Send window:** **15:30–16:00 SAST** *(= 09:30–10:00 EDT, Milan's NYC prime inbox time)*
**Channel:** LinkedIn **direct DM** *(Milan's profile is open and active, no need for connect-first)*
**Why second:** 24h gap from Luke, different region so can't be read as a batch. Milan is a multi-venture entrepreneur — async framing already built into the draft.

**Action:** Paste the full Priority 1 first-touch message from `priority-outreach-drafts.md`. The booking link + Loom framing is already optimized for him — the only personalization is the opening line.

**Personalize:** Check Milan's LinkedIn for a recent post about remote hiring / SA talent / Talent Sam milestones → reference in opening line. If nothing in last 14 days, reference his recent podcast appearance on "Recruiting Headlines #116" which is documented in research.

**Update Airtable after send.**

---

### 📅 Day 3 — Thursday 2026-04-16 — Eric Carlson / Sweat Pants Agency

**Send window:** **15:30–16:00 SAST** *(= 09:30–10:00 EDT)*
**Channel:** LinkedIn **direct DM** *(Eric's profile is public and indexed — cold DM is standard)*
**Why third:** 24h after Milan. Both are US-based but in different sub-industries (staffing vs DTC growth), so sequential sends don't look like a US-agencies-blast.

**Action:** Paste the full Priority 2 first-touch message from `priority-outreach-drafts.md`. The Cold Outreach Ops hook is still live (verified 2026-04-14 10:31) and the pipeline build offer is already time-boxed.

**Personalize:** Check Eric's LinkedIn for recent posts on subscription DTC / growth marketing / Inc #1 brands (Hunt A Killer, SnapNurse). Reference the most recent one.

**Update Airtable after send.**

---

### 📅 Days 4–7 — Friday 04-17 → Monday 04-20 — NO SENDS

Deliberate silence. If you send Friday or Monday:

- **Friday:** Message gets buried under weekend catch-up. Reply rate ~30% lower than Tue/Wed/Thu.
- **Saturday/Sunday:** Obvious weekend send = reads as "this person is working weekends to hit a quota," which is exactly the wrong signal.
- **Monday:** Target opens 60-200 unread messages, yours gets skimmed and archived.

**Do during this window instead:**

- **Fri 04-17:** Check Airtable for replies on Luke, Milan, Eric. Log any responses.
- **Fri 04-17 afternoon:** If any of those three have read-not-replied, prep the Follow-up #1 from drafts for next Tuesday.
- **Sat/Sun:** Off. No LinkedIn activity tied to your business account.
- **Mon 04-20:** Still off. Let Mel's inbox calm down.

---

### 📅 Day 8 — Tuesday 2026-04-21 — Mel Muller / Kontak Recruitment + Roundr Checkpoint

**Send window:** **09:30–10:00 SAST** *(Mel's JHB morning)*
**Channel:** LinkedIn **connection invite with note** *(same hybrid play as Luke)*
**Why last:** Longer sales cycle target, less urgency on the hook. Tuesday-morning fresh-week energy suits a recruiter's inbox (Monday was CV-intake chaos, Tuesday is when they actually respond to non-placement messages).

**Message (connection note, 300 char max):**

> Hi Mel — [1 sentence referencing a recent post of hers]. Running AVM Media in JHB. Been watching the AI-first recruiting shops (Serra, Weekday) eat market share in 2026 and thought there was a defensive play for Kontak's 15yr track record. Worth 15 min?

**If no recent post:** Fallback reference — "Saw Kontak just crossed 15 years this year" (real — founded 2009). It's mild but valid.

**Same day, same session (09:30 SAST):** Also do the Roundr checkpoint:

1. Open Jansen Myburgh's LinkedIn profile
2. Did he accept the connection invite from 2026-04-14?
   - **Yes, accepted:** Send the Priority 5 first-touch from drafts file as a DM (the "Market Pulse module" pitch)
   - **No, still pending:** Deprioritize Roundr, update Airtable `connection_status` to `declined`, drop from active list
3. Update Airtable LI-PRIORITY-001 with outcome.

---

### 📅 Day 9 — Wednesday 2026-04-22 — Gil Sperling / Flow (proptech)

**Lead ID:** LI-PRIORITY-006 — full pain hypothesis in Airtable Source Metadata
**Send window:** **09:30–10:00 SAST** *(JHB)*
**Channel:** LinkedIn cold DM *(Gil's individual profile is publicly indexed — verifier returned 200)*
**Why this slot:** 24h after Mel, JHB-to-JHB peer outreach. Same morning rhythm as Mel without batching.

**Hook + pitch (the 60-second version):**

> Flow already scrapes estate agency listings to build social ads. They have 6,000+ agents on the platform but no agent-facing intelligence layer. Pitch: a daily Property24 + PrivateProperty "hot leads digest" per agent suburb, white-labeled inside Flow. New product, zero engineering cost to Flow, retainer expansion play.

**Critical positioning:** Gil sold Popimedia to Publicis in 2015 — he's a sophisticated buyer with exit money. **Lead with technical specificity, not AI hype.** Reference Popimedia in the opening line as proof you know who he is. Skip generic "AI for proptech" framing — he'll smell it instantly.

**Action before send:**

1. Open <https://www.linkedin.com/in/gilsperling/>, find a recent post (last 14 days) on proptech / property tech / Flow growth
2. Draft the message using the AVM formula: *answer first → 1-line positioning (boutique build outfit, not competitor) → concrete pitch in 5 bullets → POC offer → CTA*
3. Skeleton: "Hi Gil — followed Flow since the Popimedia exit. [Reference recent post]. Built something Flow doesn't have yet but agents would pay for: [hot leads digest pitch]. Free POC for 1 estate agency client of yours, 2 weeks. If the data quality lands, we figure out a vendor relationship. 20 min?"
4. Send within window. Update Airtable `send_log`.

---

### 📅 Day 10 — Thursday 2026-04-23 — Steven Szaronos / Bespoke Post

**Lead ID:** LI-PRIORITY-010
**Send window:** **15:30–16:00 SAST** *(= 09:30–10:00 EDT)*
**Channel:** LinkedIn cold DM
**Why this slot:** US target after a JHB target — different region, no batch tell. End of Week 2 push.

**Hook + pitch:**

> Bespoke Post is at the inflection point where they've grown enough to need data tooling but probably haven't staffed a data team yet (per Wellfound: more marketing roles open than at any time in past 6 months). Pitch: "data team in a box" — Apify scraping of competitor box brands monthly, Reddit/Trustpilot/AppStore review aggregation for sentiment, churn cohort analysis via Shopify+Recharge. The thing an in-house data team would build, at 10% of the cost.

**Critical positioning:** Subscription DTC operators are obsessed with churn. Lead with churn metrics. Ignore everything else.

**Action before send:**

1. Open <https://www.linkedin.com/in/stevenszaronos/>, find recent post on subscription, Bespoke Post growth, or DTC trends
2. Draft skeleton: "Hi Steven — [recent post reference]. Built a churn-cohort + competitor-monitoring layer that gives subscription DTC brands what an in-house data team would, at 10% of the cost. Specifically for Bespoke Post: [3 concrete data points the tool would surface]. Free POC for 1 month, your call on which cohort. 20 min?"
3. Send within window. Update Airtable.

---

### 📅 Days 11–14 — Friday 04-24 → Monday 04-27 — NO SENDS (Week 2 silence)

Same rules as Days 4–7. Use the time to:

- Check Airtable for replies on Mel, Gil, Steven (Week 2 sends)
- Track which of Luke/Milan/Eric have responded vs gone silent (Week 1 sends, now ~10 days out)
- Prep Follow-up #1 messages for any Week 1 sends that are read-no-reply
- Update `send_log` entries with response status

---

### 📅 Day 15 — Tuesday 2026-04-28 — Magnus Heystek / Brenthurst Wealth

**Lead ID:** LI-PRIORITY-007
**Send window:** **09:30–10:00 SAST** *(JHB)*
**Channel:** LinkedIn **connection invite with note** *(Magnus is in his 60s, established advisor — connect-first hybrid is appropriate, cold DM would feel rushed)*
**Why this slot:** First send of Week 3, after a clean weekend silence. Magnus's audience reads on Tuesday mornings — his Daily Investor / BusinessTech columns drop early in the week.

**Hook + pitch:**

> Magnus is an EX-INVESTMENT-JOURNALIST who built R17B AUM by publishing constantly (Daily Investor, BusinessTech, Biznews). He's a publisher first, advisor second. Pitch: "turn your column into 1,000 personal client letters with no extra hours" — a tool that takes his published commentary + each client's portfolio + market data, and auto-generates monthly per-client briefings. Each client feels like Magnus wrote them personally.

**Critical positioning:** Don't pitch "AI for advisors" — Magnus has seen 100 of those. Pitch the SPECIFIC problem of "your column reaches all clients identically when each client has different portfolio exposure." He'll get it instantly.

**Connection note skeleton (300 char max):**

> Hi Magnus — [reference his most recent Daily Investor column]. Built a tool that turns your published commentary into a per-client monthly briefing, auto-personalized to each portfolio. Same insight you publish, scaled to feel personal across all R17B in AUM. 20 min?

**Action before send:** Read Magnus's last 2-3 Daily Investor columns. Reference one specifically. Send within window.

---

### 📅 Day 16 — Wednesday 2026-04-29 — Yusha Davidson / BriefCo + Legal Lens

**Lead ID:** LI-PRIORITY-009
**Send window:** **09:30–10:00 SAST** *(Cape Town)*
**Channel:** LinkedIn cold DM *(Yusha is mid-career legal tech founder, comfortable with cold DMs from peers)*
**Why this slot:** 24h after Magnus, both SA, both sophisticated buyers, no batch tell.

**Hook + pitch:**

> Yusha already runs AI/ML for legal cost analysis at BriefCo + Legal Lens — they're an AI-native shop. Don't pitch them "AI." Pitch them DATA INFRASTRUCTURE: SAFLII + court judgment scraping pipeline that fuels their existing models. They have the brain, they need the food.

**Critical positioning:** Frame AVM as "the data layer that fuels your existing AI" — explicitly NOT a replacement model, a complementary infrastructure layer. They are a Cycad Group company with Imvelo Ventures funding (Capitec-backed) — they have real budget and real sophistication.

**Skeleton:** "Hi Yusha — saw BriefCo's Feb 2026 sales intern hire and the Imvelo round. AI/ML for legal cost analysis is hard because the data layer is fragmented (SAFLII, court records, opposing counsel filings, local rules). Built a Apify + Claude pipeline that does scrape + structure + classify on legal docs at scale — feeds your existing models, not replaces them. 15 min to compare data infrastructure notes?"

---

### 📅 Day 17 — Thursday 2026-04-30 — Willem Haarhoff / DoughGetters Accounting

**Lead ID:** LI-PRIORITY-008
**Send window:** **09:30–10:00 SAST**
**Channel:** LinkedIn **connection invite with note** *(Willem is ex-Big 4 CA, more conservative, connect-first is the right warmth)*

**Hook + pitch:**

> DoughGetters is the FIRST accounting franchise in South Africa. Franchise = systematized = automation-hungry by design. Pitch: standardized franchisee onboarding pipeline (Xero practice spin-up, client migration scripts, monthly reporting templates). "Reduce franchisee onboarding from 3 weeks to 3 days." Sells the franchise growth story.

**Critical positioning:** Willem is a CA + ex-Big 4. He thinks in process, controls, systematization. **Avoid AI hype words entirely.** Use language like: "standardized templates," "process automation," "franchisee onboarding pipeline," "audit-trail compatible." Speak the CA language.

**Connection note skeleton (300 char):**

> Hi Willem — building a franchisee onboarding automation layer for accounting practices. DoughGetters being SA's first accounting franchise is the perfect proving ground. Cuts franchisee setup from 3 weeks to 3 days, audit-trail compatible. 15 min to walk through the pipeline?

---

### 📅 Days 18–21 — Friday 05-01 → Monday 05-04 — NO SENDS (Week 3 silence)

Standard Fri/Sat/Sun/Mon silence. Use to:

- Track Week 1 + 2 send responses (now ~14-21 days from initial sends)
- Send Follow-up #2 messages for any Week 1 read-no-reply targets
- Decide on multi-thread sends for Week 4 based on which primaries went silent

---

### 📅 Week 4 — Conditional Multi-Thread Sends

**These sends are CONDITIONAL.** Before sending each, check the corresponding primary contact's response status in Airtable. Rule:

- **Primary responded positively** → DO NOT SEND multi-thread. Let the primary loop in colleagues.
- **Primary read-no-reply or never opened** → SEND multi-thread with a different angle.
- **Primary explicitly declined** → DO NOT SEND multi-thread. Burn risk on the account.

| Date | Multi-thread | Primary to check | Different angle from primary |
|---|---|---|---|
| **Tue 05-05 09:30 SAST** | Petrumarié Jacobs (LI-PRIORITY-003B) | Luke (LI-PRIORITY-003) | BD/hunter sales-weapon, not strategic AEO thesis |
| **Wed 05-06 15:30 SAST** | Daniel Schwartz (LI-PRIORITY-002B) | Milan (LI-PRIORITY-002) | CEO/CFO bottom-line ROI math, not visionary framing |
| **Thu 05-07 15:30 SAST** | Landon Shaw II (LI-PRIORITY-005B) | Eric (LI-PRIORITY-005) | Co-founder operations angle, not strategic vision |

**Hook caveat:** By Week 4, the original Himalayas hiring posts (Talent Sam Junior Recruiter, Sweat Pants Cold Outreach Ops) may be filled. **Re-run `python tools/verify_priority_accounts.py` on Mon 05-04** to confirm hook URLs are still live. If a hook is dead, rewrite the multi-thread message body to use a non-hook angle (founder's recent post, company milestone, mutual connection).

---

### 📅 Days 25–28 — Friday 05-08 → Monday 05-11 — NO SENDS (Week 4 silence)

---

### 📅 Day 29 — Tuesday 2026-05-12 — Angie Le Roux / Kontak (CONDITIONAL)

**Lead ID:** LI-PRIORITY-004B
**Send only if:** Mel Muller (LI-PRIORITY-004) is read-no-reply or never opened. If Mel responded positively, DO NOT SEND.

**Different angle from Mel:** Mel got the strategic "adopt-or-lose-share" pitch. Angie is the operator — pitch her on team productivity. **The current draft body in priority-outreach-drafts.md Priority 4 was written for Mel and needs a rewrite for Angie before sending.**

**Skeleton:**

> Hi Angie — Recruitment Director with 17 years means you've felt every minute of the manual sourcing grind across IT, finance, and senior leadership specs. Built a nightly automation: scrapes LinkedIn + PNet + CareerJunction against your active job specs, Claude shortlists each candidate with a "why matched" one-liner, delivered as a morning email per recruiter. Saves ~3 hours per recruiter per day. 15 min to see what it looks like?

**Channel:** LinkedIn connection invite with note (matches Mel's channel for consistency)
**Send window:** 09:30–10:00 SAST

---

## Response Tracking (log in Airtable after every send)

The `LI_Leads` table `Status` field is a fixed singleSelect — we can't add "Sent" or "Awaiting Reply" without admin access. Instead, **log in Source Metadata JSON** using the tool below.

**For each send, update the record's Source Metadata with:**

```json
{
  "...existing metadata...": "...",
  "send_log": [
    {
      "sent_at": "2026-04-14T11:00:00+02:00",
      "channel": "linkedin_connect_with_note",
      "draft_version": "priority-outreach-drafts.md Priority 3",
      "personalization": "Referenced Luke's 2026-04-12 post about HubSpot AI in SA",
      "response": null,
      "response_at": null
    }
  ]
}
```

**Update when a reply comes in:**

```json
{
  "response": "positive | neutral | negative | auto_reply",
  "response_at": "2026-04-15T09:15:00+02:00",
  "next_action": "send_loom_within_48h | 30_day_nurture | log_reason_and_close"
}
```

To avoid hand-editing JSON, you can do this via the Airtable UI (edit record → Source Metadata field → paste updated JSON) or via the MCP tool from within a Claude session.

---

## If-Then Response Handling

| Scenario | Day | Action |
|---|---|---|
| Positive reply ("tell me more", "book in") | Any | Within 4 hours: send Loom + 3 calendar slots. Priority response. |
| Connection accepted but no reply (Luke, Mel) | Day +2 | Send full pitch DM (from drafts file) as a follow-up to the connect note |
| Read-no-reply (message opened, no response) | Day +4 | Send Follow-up #1 from drafts file |
| Read-no-reply | Day +10 | Send Follow-up #2 from drafts file |
| Never opened after 10 days | Day +10 | Pause, try same target via email in 30 days (if email is ever sourced) |
| Connection declined | Any | Log reason `declined`, move to 90-day cooldown, try co-founder (Landon Shaw for Sweat Pants, Angie Le Roux for Kontak, Daniel Schwartz for Talent Sam) |
| Auto-reply "I'm OOO" | Any | Re-send original message +1 day after OOO return date |
| Polite decline ("not a fit right now") | Any | "Thanks, I'll circle back in 90 days with a different angle" — log and set a calendar reminder |
| Hostile / unsubscribe request | Any | Stop immediately, log `do_not_contact`, remove from all future sequences |

---

## Why This Cadence Doesn't Look Like a Blast

A real human sending 4 cold outreach messages over 8 days does **exactly this pattern**:

- They find a target, they obsess over the personalization for 20 minutes, they send it
- Then they go do other work
- Next day they remember "oh, I wanted to reach out to X too" and send another
- They don't touch it on Friday because they're tired
- Monday they're catching up on their own inbox
- Tuesday they remember "oh, I never sent the Kontak one" and send it

That's the rhythm of a small business owner doing targeted BD, and it's the rhythm of the schedule above. The automation shows up only in the **preparation** (pain-point analysis, verification, draft quality) — not in the sending. That's the right place for it.

**The one tell to avoid:** Sending all 4 messages at 10:00:00 SAST exactly. Randomize within the window. 10:03, 10:17, 10:41 — not 10:00, 10:00, 10:00.

---

## Today's Immediate Next Action (Day 1, Tue 2026-04-14)

1. [ ] Open LinkedIn, navigate to Luke Marthinusen's profile: <https://za.linkedin.com/in/lukemarthinusen>
2. [ ] Scroll his activity feed — find one post from the last 14 days worth referencing
3. [ ] Click "Connect" → "Add a note"
4. [ ] Paste the Day 1 connection note above, replace `[1 sentence referencing a recent post of his]` with your actual reference
5. [ ] Send **before 11:30 SAST today**
6. [ ] Update Airtable `LI-PRIORITY-003` Source Metadata with the send_log entry
7. [ ] Close LinkedIn — don't touch it until tomorrow afternoon for the Milan send

That's it. One send today. Everything else waits.
