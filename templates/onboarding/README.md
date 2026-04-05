# Onboarding Email Templates

7 behavioral emails sent over 14 days to guide new clients from signup to activation.

## Sequence

| # | Key | Trigger | Subject |
|---|-----|---------|---------|
| 1 | `welcome` | Signup (immediate) | Welcome to AnyVision, {{first_name}} |
| 2 | `day1_checklist` | 24h + onboarding incomplete | 3 steps to get your business on autopilot |
| 3 | `first_connection` | First integration connected | You're connected! Here's what happens next |
| 4 | `day3_nudge` | 72h + no integration | Connect your tools in 60 seconds |
| 5 | `first_win` | First successful workflow | Your first automation just ran! |
| 6 | `day7_value` | Day 7 | Week 1: {{leads}} leads, {{hours_saved}} hours saved |
| 7 | `trial_ending` | 5 days before trial end | Your trial ends in 5 days |

## Template Variables

All templates support these variables (replaced by n8n Code nodes):

- `{{first_name}}` — Client's first name
- `{{email}}` — Client's email
- `{{company_name}}` — Company name
- `{{portal_url}}` — Portal login URL (https://portal.anyvisionmedia.com)
- `{{unsubscribe_url}}` — Unsubscribe URL
- `{{subject}}` — Email subject line

Template-specific variables listed in each file.

## Usage in n8n

1. Read template HTML from file or inline in Code node
2. Replace `{{variables}}` with client data from Supabase query
3. Send via Gmail node (credential: CRED_GMAIL)
4. Log send in `email_sequence_events` table

## Design

- Sender: "Ian from AnyVision" (ian@anyvisionmedia.com)
- One CTA per email
- Mobile-first (560px max width)
- Dark theme matching portal (#0A0F1C background)
- POPIA compliant: unsubscribe link in every email
