# AnyVision Media — Client Portal Setup Guide

## Architecture

- **Frontend + Backend**: Next.js 16 (App Router) deployed to Vercel
- **Database + Auth**: Supabase (PostgreSQL with Row-Level Security)
- **Charts**: Recharts
- **Domain**: `portal.anyvisionmedia.com`

---

## Step 1: Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Note your **Project URL** and **API keys** from Settings > API:
   - `NEXT_PUBLIC_SUPABASE_URL` — Project URL
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` — anon/public key
   - `SUPABASE_SERVICE_ROLE_KEY` — service_role key (keep secret!)

## Step 2: Run Database Migration

1. Open the Supabase SQL Editor (Dashboard > SQL Editor)
2. Copy the entire contents of `supabase/migrations/001_initial_schema.sql`
3. Paste and run it — this creates all 7 tables, indexes, RLS policies, and helper functions

## Step 3: Configure Environment Variables

1. Copy `.env.local.example` to `.env.local`:
   ```bash
   cp .env.local.example .env.local
   ```
2. Fill in your Supabase values:
   ```env
   NEXT_PUBLIC_SUPABASE_URL=https://your-project-id.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
   SUPABASE_SERVICE_ROLE_KEY=eyJ...
   NEXT_PUBLIC_APP_URL=https://portal.anyvisionmedia.com
   MAIN_SITE_URL=https://www.anyvisionmedia.com
   ```

## Step 4: Create Your First Admin Account

1. In Supabase Dashboard, go to **Authentication > Users** and click "Add User"
2. Enter your email and a password, check "Auto Confirm"
3. Copy the user's UUID
4. In the SQL Editor, run:
   ```sql
   INSERT INTO admin_users (auth_user_id, email, full_name, role)
   VALUES ('YOUR-AUTH-USER-UUID', 'ian@anyvisionmedia.com', 'Ian Immelman', 'owner');
   ```
5. You can now log in at `/admin/login`

## Step 5: Deploy to Vercel

1. Push the `client-portal` directory to a GitHub repository
2. Go to [vercel.com](https://vercel.com) and import the repo
3. Set the **Root Directory** to `client-portal`
4. Add all environment variables from `.env.local`
5. Deploy
6. In Vercel > Settings > Domains, add `portal.anyvisionmedia.com`
7. In your DNS provider, add a CNAME record:
   - Name: `portal`
   - Value: `cname.vercel-dns.com`

## Step 6: Configure Supabase Email (for password resets)

1. In Supabase Dashboard > Authentication > URL Configuration:
   - Set **Site URL** to `https://portal.anyvisionmedia.com`
   - Add `https://portal.anyvisionmedia.com/portal/login` to **Redirect URLs**
2. Optionally configure a custom SMTP provider in Authentication > Email Templates

---

## How to Create Client Accounts

### Option A: Via Admin Dashboard
1. Log in at `/admin/login`
2. Go to **Management**
3. Click **Create Client** — enter name, email, temporary password
4. The client receives their API key, which you'll need for workflow integration
5. Share the login URL with the client: `https://portal.anyvisionmedia.com/portal/login`

### Option B: Via SQL (direct)
```sql
-- First create auth user in Supabase Dashboard, then:
INSERT INTO clients (auth_user_id, email, full_name, company_name, created_by)
VALUES ('auth-user-uuid', 'client@company.com', 'Client Name', 'Company', 'your-admin-id');
```

---

## How to Connect Automation Workflows

Each client gets a unique **API Key** (UUID) stored in the `clients` table. Use this key in the `X-API-Key` header when posting data from your automation tools.

### Endpoints

| Endpoint | Description |
|---|---|
| `POST /api/stats/message-received` | Log an inbound message |
| `POST /api/stats/message-sent` | Log an outbound message |
| `POST /api/stats/lead-created` | Log a new lead |
| `POST /api/stats/workflow-crash` | Log a workflow error |

### Example: n8n HTTP Request Node

```
Method: POST
URL: https://portal.anyvisionmedia.com/api/stats/lead-created
Headers:
  X-API-Key: client-api-key-uuid
  Content-Type: application/json
Body:
  {
    "workflow_id": "optional-workflow-uuid",
    "metadata": {
      "lead_name": "John Doe",
      "lead_email": "john@example.com"
    }
  }
```

### Example: curl
```bash
curl -X POST https://portal.anyvisionmedia.com/api/stats/message-received \
  -H "X-API-Key: your-client-api-key" \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"source": "whatsapp"}}'
```

### Example: Make/Zapier Webhook
1. Add an HTTP module/action
2. Set URL to the endpoint above
3. Set method to POST
4. Add header `X-API-Key` with the client's API key
5. Set body to JSON with optional `workflow_id` and `metadata`

---

## Employee Accounts

To add an employee with limited access:

1. Create an auth user in Supabase Dashboard
2. Run SQL:
   ```sql
   INSERT INTO admin_users (auth_user_id, email, full_name, role)
   VALUES ('auth-user-uuid', 'employee@anyvisionmedia.com', 'Employee Name', 'employee');
   ```

**Employee restrictions**: Employees cannot delete clients or modify billing (enforced via role checks in API routes).

---

## Local Development

```bash
cd client-portal
npm install
cp .env.local.example .env.local
# Fill in your Supabase credentials
npm run dev
```

Open `http://localhost:3000/portal/login` or `http://localhost:3000/admin/login`.
