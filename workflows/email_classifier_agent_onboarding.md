# 🟢 AI Email Classifier — Agent Onboarding Guide

> **Service:** AI-Powered Email Management for Real Estate Agents
> **Provider:** AnyVision Media (`ian@anyvisionmedia.com`)
> **Platform:** Microsoft Outlook + n8n Automation
> **AI Model:** GPT-5.1 via OpenRouter

---

## 📊 What You're Getting

Your AI Email Assistant automatically handles your Outlook inbox:

| Feature | What It Does |
|---------|-------------|
| 📧 **Smart Classification** | Every incoming email is analyzed and sorted by department (Finance, Sales, Support, Management, etc.) |
| 🏷️ **Auto-Categorization** | Color-coded Outlook categories applied instantly — no manual sorting |
| 🚨 **Urgency Detection** | Urgent emails flagged immediately so nothing falls through the cracks |
| ✉️ **Draft Replies** | AI writes professional draft replies in your Outlook Drafts — you review and send |
| 📊 **Activity Logging** | Every email logged to a central dashboard for tracking and reporting |
| 🏠 **Lead Detection** | New sales leads automatically captured and tracked |
| 📅 **Follow-Up Reminders** | Calendar events created for leads requiring follow-up |

> 💡 **Important:** The AI creates **draft** replies — it never sends anything without your approval. You always have the final say.

---

## ⏱️ Onboarding Timeline

| Phase | What Happens | Time | Who Does It |
|-------|-------------|------|-------------|
| 🔵 Phase 1 | You authorize your Outlook + create categories | ~5 min | 👤 You |
| 🟣 Phase 2 | We connect your account to the system | ~10 min | 🤖 AnyVision Media |
| 🟢 Phase 3 | We test together and go live | ~10 min | 👥 Both |

**Total onboarding time: ~25 minutes**

---

## 🔵 PHASE 1 — Your Setup (What You Need to Do)

*Complete these two steps before your onboarding call. Takes about 5 minutes total.*

---

### Step 1️⃣ — Authorize Your Outlook Account

> 🕐 **Time:** ~2 minutes
> 👤 **Owner:** You

We've already set up the connection app on our end. All you need to do is click a link and sign in.

| # | Action | Details |
|---|--------|---------|
| 🅰️ | **Click the authorization link** we send you | You'll receive it via email from AnyVision Media |
| 🅱️ | **Sign in** with your Microsoft 365 account | Use the email address you want monitored |
| 🅲️ | **Review the permissions** Microsoft shows you | You'll see what the AI is allowed to do (read emails, create drafts, manage calendar) |
| 🅳️ | **Click "Accept"** | That's it — your account is now connected |

> 🔒 **What you're granting access to:**

| Permission | What It Means |
|------------|---------------|
| Read and manage your mail | The AI can read incoming emails and apply category labels |
| Send mail on your behalf | The AI can create draft replies (it never sends without your approval) |
| Read and manage your calendar | The AI can create follow-up events for sales leads |

> 💡 **You can revoke access at any time** — go to `myapps.microsoft.com` → find "AnyVision Email Classifier" → click "Revoke".

> 🔒 **Security note:** We cannot read your email content — the AI processes emails in real-time and does not store them. Your data stays in your Outlook.

---

### Step 2️⃣ — Create Your Outlook Categories

> 🕐 **Time:** ~3 minutes
> 👤 **Owner:** You
> 📍 **Where:** Outlook (web or desktop app)

The AI uses color-coded categories to organize your emails. You need to create them in your Outlook so the system can apply them.

**In Outlook Web (outlook.office.com):**

| # | Action | Details |
|---|--------|---------|
| 🅰️ | Click the **⚙️ Settings** gear icon | Top-right corner |
| 🅱️ | Go to **General → Categories** | You'll see a list of existing categories |
| 🅲️ | Create each category below | Click "Create category", enter the name, pick the color |

**Categories to create:**

| Category Name | Suggested Color | Used For |
|---------------|----------------|----------|
| `Junk` | 🔴 Red | Spam and irrelevant emails |
| `Accounting_Finance` | 🟠 Orange | Invoices, payments, billing |
| `Customer_Support` | 🔵 Blue | Client complaints, service issues |
| `Sales` | 🟢 Green | New leads, pricing inquiries |
| `Management` | 🟣 Purple | Strategy, legal, partnerships |
| `General` | ⚪ Gray | Admin, documentation, misc |
| `Urgent` | 🔴 Red | Time-sensitive / high-priority items |

> 💡 **Tip:** Type the names exactly as shown (with underscores). The AI looks for these exact names when applying categories.

> ✅ **You're done!** Let AnyVision Media know you've completed Steps 1 and 2, and we'll take it from here.

---

## 🟣 PHASE 2 — Our Setup (What AnyVision Media Does)

*You don't need to do anything in this phase. This is what happens on our end after you've authorized your account.*

---

### Step 3️⃣ — We Create Your n8n Credential

> 🕐 **Time:** ~2 minutes
> 👤 **Owner:** AnyVision Media

| # | Action | Details |
|---|--------|---------|
| 🅰️ | Create your Microsoft Outlook OAuth2 credential in n8n | Using the authorization you completed in Step 1 |
| 🅱️ | Name it `Outlook - [Your Name]` | Following our naming convention |
| 🅲️ | Verify the connection is working | Quick test to confirm we can access your inbox |

---

### Step 4️⃣ — We Deploy Your Workflow

> 🕐 **Time:** ~5 minutes
> 👤 **Owner:** AnyVision Media

| # | Action | Details |
|---|--------|---------|
| 🅰️ | Duplicate the agent template workflow | Creates your personal copy |
| 🅱️ | Rename to `Email Classifier - [Your Name]` | Easy to identify in our system |
| 🅲️ | Set your agent name and email in the code | So your emails are tagged correctly in our logs |
| 🅳️ | Connect your Outlook credential to all nodes | 12 Outlook action nodes get your credential |
| 🅴️ | Link to the master AI classification engine | Connects your workflow to the shared AI brain |

---

### Step 5️⃣ — We Run Initial Tests

> 🕐 **Time:** ~3 minutes
> 👤 **Owner:** AnyVision Media

We send test emails to verify every part of the system works:

| Test | What We Check |
|------|---------------|
| 📧 Finance email | "Accounting_Finance" category applied correctly |
| 📧 Sales inquiry | "Sales" category + lead detection + calendar follow-up |
| 📧 Support request | "Customer_Support" category + draft reply created |
| 📧 Spam email | "Junk" category + marked as read automatically |
| 📧 Urgent email | "Urgent" category applied as additional flag |
| 📧 No-reply email | Detected and marked as read (no draft created) |

> ✅ All 6 tests must pass before we proceed.

---

## 🟢 PHASE 3 — Go Live (Together)

*A quick check-in call or screen share to confirm everything is working.*

---

### Step 6️⃣ — Joint Verification

> 🕐 **Time:** ~5 minutes
> 👤 **Owner:** Both

| # | Action | Details |
|---|--------|---------|
| 🅰️ | You send a test email to your own inbox | Use a different email account, or have a colleague send one |
| 🅱️ | Wait 1 minute | The system checks for new emails every 60 seconds |
| 🅲️ | Check your Outlook | You should see a category label on the email |
| 🅳️ | Check your Drafts folder | If the AI determined a reply was needed, you'll see a draft |
| 🅴️ | Check your Calendar | If it was a sales lead, you'll see a follow-up event |

---

### Step 7️⃣ — Activate and Monitor

> 🕐 **Time:** ~5 minutes
> 👤 **Owner:** AnyVision Media

| # | Action | Details |
|---|--------|---------|
| 🅰️ | Activate your workflow | Emails start being processed automatically |
| 🅱️ | Monitor for the first 24 hours | We watch for any errors or missed emails |
| 🅲️ | Send you a confirmation | "You're live!" email with your reference info |

> 🎉 **Congratulations — you're live!** Your AI Email Assistant is now working 24/7.

---

## 📖 How It Works (Day-to-Day)

Once you're live, here's what happens automatically every time you get an email:

```
📧 New email arrives in your Outlook inbox
     ↓
🤖 AI reads and classifies it (< 30 seconds)
     ↓
🏷️ Outlook category applied (Finance, Sales, Support, etc.)
     ↓
🚨 If urgent → extra "Urgent" category added
     ↓
✉️ If reply needed → draft created in your Drafts folder
     ↓
📊 Email logged to your activity dashboard
     ↓
🏠 If sales lead → captured + calendar follow-up created
```

**What you need to do:**

| Task | How Often | Time |
|------|-----------|------|
| Review and send draft replies | As they appear | ~30 sec each |
| Check your calendar for follow-ups | Daily | ~2 min |
| Review the activity dashboard | Weekly | ~5 min |

> 💡 **That's it.** The AI handles the sorting, categorizing, and drafting. You handle the relationships.

---

## 🛡️ Your Data & Privacy

| Question | Answer |
|----------|--------|
| Can AnyVision Media read my emails? | No. The AI processes emails in real-time on our secure automation platform. We do not store email content. |
| What data is logged? | Sender name, subject line, department classification, urgency level, and agent name. Email body is NOT stored. |
| Who can see my logs? | Only you and AnyVision Media administrators. Logs are filtered by agent name. |
| Can I opt out? | Yes. We deactivate your workflow instantly. Your Outlook returns to normal. |
| What about attachments? | The AI notes whether attachments exist but does not open or store them. |
| Where does the AI run? | On n8n Cloud (EU/US servers) via encrypted connections. Emails are processed and forgotten — not stored for training. |

---

## ❓ Troubleshooting

### "My emails aren't being categorized"

**Checklist:**
1. ✅ Is your workflow active? (Ask AnyVision Media to check)
2. ✅ Did you create all 7 categories in Outlook? (Check Settings → Categories)
3. ✅ Are the category names spelled exactly right? (Underscores matter: `Customer_Support` not `Customer Support`)
4. ✅ Has your Microsoft credential expired? (Azure secrets expire after 24 months)

**Fix:** Contact AnyVision Media — we can diagnose remotely in under 5 minutes.

---

### "I'm getting categories but no draft replies"

**Possible causes:**
- The email was from a no-reply address (drafts aren't created for these)
- The AI determined no action was required (informational emails)
- The email was classified as spam

**Check:** Look at the email's category. If it says "Junk", the AI correctly skipped the draft.

---

### "My Outlook is asking me to sign in again"

**Cause:** Your Microsoft OAuth session expired.

**Fix:**
1. Contact AnyVision Media
2. We'll re-authorize your credential in n8n (~2 minutes)
3. You may see a Microsoft sign-in prompt — click "Accept"

---

### "I want to change how the AI classifies certain emails"

**How:** Tell AnyVision Media what change you need. Examples:
- "Mark emails from `vendor@example.com` as Finance instead of General"
- "Don't create draft replies for newsletters"
- "Add a new category for 'Property Listings'"

We update the shared AI classification engine and all agents benefit from the improvement.

---

## 📋 Quick Reference

### Your Onboarding Checklist

| # | Task | Status |
|---|------|--------|
| 1 | Click authorization link and sign in with Microsoft | ⬜ |
| 2 | Create 7 Outlook categories | ⬜ |
| 3 | Let AnyVision Media know you're ready | ⬜ |
| 4 | Joint verification call | ⬜ |
| 5 | Go live! | ⬜ |

### Key Links

| What | URL |
|------|-----|
| Outlook Web | `https://outlook.office.com` |
| Revoke Access (if needed) | `https://myapps.microsoft.com` |
| AnyVision Media | `https://anyvisionmedia.com` |
| Support Email | `ian@anyvisionmedia.com` |

### Your 7 Outlook Categories

```
Junk
Accounting_Finance
Customer_Support
Sales
Management
General
Urgent
```

---

## 🔄 Adding More Agents to Your Team

If you manage a team and want to onboard additional agents:

1. **Send each agent the authorization link** — they click it and sign in (~2 min each)
2. **Each agent creates their 7 Outlook categories** (~3 min each)
3. **Let us know they're ready** — we batch-deploy all agents at once (~5 min per agent on our end)
4. **Group verification call** — test 2-3 agents live, rest verified automatically

> 💡 **Bulk pricing available** for teams of 10+ agents. Contact ian@anyvisionmedia.com.

---

> **AnyVision Media** — AI-Powered Transformation for Your Business
> 📧 ian@anyvisionmedia.com | 🌐 anyvisionmedia.com
