# HeyGen Video Pipeline

Automated property walkthrough video generation and social media distribution using HeyGen AI avatars.

## Architecture

```
Airtable (Video_Jobs)           HeyGen API
  Status: Pending          +---> POST /v2/video/generate
       |                   |        |
  VIDEO-01 (Producer)  ----+        | (10-30 min processing)
  Daily 11:00 SAST                  v
  + On-demand webhook        HeyGen Webhook Callback
                                    |
                               VIDEO-02 (Distributor)
                                    |
                          +---------+---------+
                          |         |         |
                       TikTok  Instagram  Facebook
                        (9:16)   (9:16)    (9:16)
                          |         |         |
                          +----+----+----+----+
                               |
                          Distribution Log
                          + Email Notification
```

## Workflows

### VIDEO-01: Property Video Producer
- **Trigger**: Schedule (daily 11:00 SAST) + Webhook (on-demand)
- **Nodes**: ~15
- **Flow**:
  1. Fetch all Airtable records with Status = "Pending"
  2. For each job: generate walkthrough script via Claude/OpenRouter
  3. Generate social media caption + hashtags
  4. Call HeyGen API to create avatar video
  5. Update Airtable: Status -> "Generating", store HeyGen video_id

### VIDEO-02: HeyGen Callback & Distributor
- **Trigger**: Webhook (HeyGen sends callback when video is ready)
- **Nodes**: ~18
- **Flow**:
  1. Receive HeyGen webhook (avatar_video.success or .fail)
  2. Lookup video job in Airtable by HeyGen Video ID
  3. If success: update status to "Ready", publish to Blotato (TikTok/IG/FB)
  4. If fail: update status to "Failed", send alert email
  5. Log distribution results, send success notification

## Setup

### 1. Create HeyGen Account
- Sign up at [heygen.com](https://heygen.com)
- Creator plan ($29/mo) recommended to start
- Create your custom avatar (2 min of footage) or pick a stock avatar
- Get your API key from Settings -> API

### 2. Create Airtable Table
```bash
python tools/setup_heygen_airtable.py --seed
```
Copy the table ID to your `.env` as `HEYGEN_TABLE_VIDEO_JOBS`.

### 3. Create n8n Credential
In n8n UI -> Settings -> Credentials:
- Type: Header Auth
- Header Name: `X-Api-Key`
- Header Value: Your HeyGen API key
- Save and note the credential ID

### 4. Set Environment Variables
Add to `.env`:
```
HEYGEN_API_KEY=your_key
HEYGEN_AVATAR_ID=your_avatar_id
HEYGEN_VOICE_ID=your_voice_id
HEYGEN_TABLE_VIDEO_JOBS=tblXXX
N8N_CRED_HEYGEN=credential_id_from_n8n
```

### 5. Deploy Workflows
```bash
python tools/deploy_heygen_video.py build      # Preview JSON
python tools/deploy_heygen_video.py deploy     # Push to n8n (inactive)
python tools/deploy_heygen_video.py activate   # Push + activate
```

### 6. Register HeyGen Webhook
After VIDEO-02 is active, register the callback URL with HeyGen:
```bash
curl -X POST https://api.heygen.com/v1/webhook/endpoint.add \
  -H "X-Api-Key: YOUR_HEYGEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://ianimmelman89.app.n8n.cloud/webhook/heygen-callback", "events": ["avatar_video.success", "avatar_video.fail"]}'
```

## Usage

### Automatic (Daily)
1. Add a new record to `Video_Jobs` in Airtable with Status = "Pending"
2. Fill in: Property Name, Address, Price, Key Features, Property Photos (URLs)
3. VIDEO-01 runs daily at 11:00 SAST, picks up pending jobs
4. Videos are auto-published to TikTok/Instagram/Facebook when ready

### On-Demand
POST to webhook to trigger immediately:
```bash
curl -X POST https://ianimmelman89.app.n8n.cloud/webhook/heygen-produce
```

## Credit Usage

| Avatar Type | Rate | 60-sec video cost |
|-------------|------|-------------------|
| Standard | 1 credit/min | 1 credit |
| Avatar IV | 1 credit/10 sec | 6 credits |

Creator plan: 200 credits/month = ~33 standard videos or ~33 minutes of Avatar IV.

## Files

| File | Purpose |
|------|---------|
| `tools/setup_heygen_airtable.py` | Create Video_Jobs table in Airtable |
| `tools/deploy_heygen_video.py` | Build + deploy both workflows to n8n |
| `workflows/heygen-video/video01_*.json` | VIDEO-01 workflow JSON |
| `workflows/heygen-video/video02_*.json` | VIDEO-02 workflow JSON |
| `config.json` -> `heygen_video` | Configuration section |
| `.env.template` -> HeyGen section | Required environment variables |
