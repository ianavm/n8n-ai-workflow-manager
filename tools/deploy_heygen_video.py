"""
HeyGen Video Pipeline - Workflow Builder & Deployer

Builds 2 n8n workflows for automated property video creation and distribution.

Workflows:
    VIDEO-01: Property Video Producer (Schedule daily 11:00 SAST + Webhook on-demand)
        - Fetches listings with Status=Pending from Video_Jobs Airtable
        - Generates property walkthrough script via Claude/OpenRouter
        - Calls HeyGen API to create avatar video
        - Stores HeyGen video_id, updates status to Generating
        - 15 nodes

    VIDEO-02: HeyGen Callback & Distributor (Webhook trigger from HeyGen)
        - Receives HeyGen webhook callback (avatar_video.success/fail)
        - Looks up video job in Airtable by HeyGen Video ID
        - Downloads video URL from HeyGen response
        - Publishes to TikTok, Instagram, Facebook via Blotato
        - Logs distribution results, sends notification email
        - 18 nodes

Pipeline:
    Airtable (new listing) -> Claude (script) -> HeyGen API (video)
       -> HeyGen webhook -> Download -> Blotato (TikTok/IG/FB)
       -> Log to Airtable + Email notification

Usage:
    python tools/deploy_heygen_video.py build              # Build all JSONs
    python tools/deploy_heygen_video.py build video01      # Build VIDEO-01 only
    python tools/deploy_heygen_video.py deploy             # Build + Deploy (inactive)
    python tools/deploy_heygen_video.py activate           # Build + Deploy + Activate
"""

import json
import sys
import uuid
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# -- Credential Constants --
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail AVM"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable PAT"}
CRED_BLOTATO = {"id": "hhRiqZrWNlqvmYZR", "name": "Blotato AVM"}
# HeyGen uses httpHeaderAuth - create in n8n UI with header: X-Api-Key
CRED_HEYGEN = {"id": os.getenv("N8N_CRED_HEYGEN", "REPLACE_AFTER_SETUP"), "name": "HeyGen API"}

# -- Airtable IDs --
MARKETING_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
TABLE_VIDEO_JOBS = os.getenv("HEYGEN_TABLE_VIDEO_JOBS", "REPLACE_AFTER_SETUP")
TABLE_DISTRIBUTION_LOG = os.getenv("MARKETING_TABLE_DISTRIBUTION_LOG", "tblLI70ZD0DkJKXvI")

# -- Blotato Account IDs --
BLOTATO_ACCOUNTS = {
    "tiktok": {"accountId": "27801", "name": "TikTok"},
    "instagram": {"accountId": "29194", "name": "Instagram"},
    "facebook": {"accountId": "369", "subAccountId": "161711670360847", "name": "Facebook"},
}

# -- HeyGen Config --
HEYGEN_API_BASE = "https://api.heygen.com"
HEYGEN_AVATAR_ID = os.getenv("HEYGEN_AVATAR_ID", "REPLACE_WITH_YOUR_AVATAR_ID")
HEYGEN_VOICE_ID = os.getenv("HEYGEN_VOICE_ID", "REPLACE_WITH_YOUR_VOICE_ID")

# -- Config --
ALERT_EMAIL = os.getenv("SELFHEALING_ALERT_EMAIL", "ian@anyvisionmedia.com")
OPENROUTER_MODEL = "anthropic/claude-sonnet-4-20250514"

# -- Webhook URL (n8n cloud) --
N8N_WEBHOOK_BASE = os.getenv("N8N_WEBHOOK_BASE", "https://ianimmelman89.app.n8n.cloud/webhook")


def uid():
    """Generate UUID for node IDs."""
    return str(uuid.uuid4())


# ======================================================================
# AI PROMPTS
# ======================================================================

SCRIPT_GENERATION_PROMPT = """You are a professional real estate video script writer for AnyVision Media, a digital media agency in South Africa.

Write a compelling, natural-sounding video script for a property walkthrough presentation. The avatar presenter will stand in front of property photos and narrate.

PROPERTY DETAILS:
- Name: {{property_name}}
- Type: {{property_type}}
- Address: {{property_address}}
- Price: R{{listing_price}}
- Key Features: {{key_features}}

REQUIREMENTS:
1. Script should be 30-60 seconds when spoken (roughly 75-150 words)
2. Open with an attention-grabbing hook (first 3 seconds matter for social media)
3. Highlight the top 3-4 features naturally
4. Include the price and location
5. End with a clear call-to-action (DM, call, link in bio)
6. Tone: {{script_tone}}
7. Use South African English (e.g., "lounge" not "living room", "garden" not "yard")
8. Do NOT use emojis in the script
9. Do NOT include stage directions or camera cues - just the spoken words

OUTPUT FORMAT:
Return ONLY the script text, nothing else. No headers, no labels, just the words the presenter will say."""

CAPTION_GENERATION_PROMPT = """You are a social media expert for AnyVision Media, a real estate-focused digital media agency in South Africa.

Write a short, engaging social media caption for a property video post.

PROPERTY: {{property_name}} in {{property_address}}
PRICE: R{{listing_price}}
TYPE: {{property_type}}
FEATURES: {{key_features}}

REQUIREMENTS:
1. Max 150 characters for the caption text (before hashtags)
2. Attention-grabbing, create urgency or curiosity
3. Include the price
4. South African English
5. Add 5-8 relevant hashtags on a new line

OUTPUT FORMAT:
Line 1: Caption text
Line 2: Hashtags (space-separated, starting with #)"""


# ======================================================================
# CODE NODE SCRIPTS
# ======================================================================

VIDEO01_PREPARE_HEYGEN_PAYLOAD = r"""
// Build HeyGen API v2 video generation payload
const job = $input.first().json;
const script = $('Generate Script').first().json.message.content || $('Generate Script').first().json.choices[0].message.content;
const caption = $('Generate Caption').first().json.message.content || $('Generate Caption').first().json.choices[0].message.content;

// Parse caption into text + hashtags
const captionLines = caption.trim().split('\n').filter(l => l.trim());
const captionText = captionLines[0] || '';
const hashtags = captionLines.find(l => l.includes('#')) || '';

// Determine dimensions from aspect ratio
const aspectRatio = job['Aspect Ratio'] || '9:16';
const dimensions = {
  '9:16': { width: 1080, height: 1920 },
  '16:9': { width: 1920, height: 1080 },
  '1:1':  { width: 1080, height: 1080 },
};
const dim = dimensions[aspectRatio] || dimensions['9:16'];

// Get avatar/voice config
const avatarId = job['Avatar ID'] || '""" + HEYGEN_AVATAR_ID + r"""';
const voiceId = job['HeyGen Voice ID'] || '""" + HEYGEN_VOICE_ID + r"""';

// Build the HeyGen v2 payload
const payload = {
  video_inputs: [
    {
      character: {
        type: "avatar",
        avatar_id: avatarId,
        avatar_style: "normal",
      },
      voice: {
        type: "text",
        input_text: script.trim(),
        voice_id: voiceId,
        speed: 1.0,
      },
      background: {
        type: "color",
        value: "#FFFFFF",
      },
    },
  ],
  dimension: dim,
  aspect_ratio: null,
  test: false,
};

// If property photos exist, use first as background
const photos = (job['Property Photos'] || '').split('\n').filter(u => u.trim().startsWith('http'));
if (photos.length > 0) {
  payload.video_inputs[0].background = {
    type: "image",
    url: photos[0].trim(),
  };
}

return {
  json: {
    heygenPayload: payload,
    script: script.trim(),
    caption: captionText.trim(),
    hashtags: hashtags.trim(),
    jobId: job['Job ID'] || job.id,
    recordId: job.id,
    propertyName: job['Property Name'] || '',
    aspectRatio: aspectRatio,
  }
};
"""

VIDEO02_PROCESS_CALLBACK = r"""
// Process HeyGen webhook callback
const callback = $input.first().json;
const body = callback.body || callback;

// HeyGen webhook payload structure
const eventType = body.event_type || body.type || '';
const videoId = body.video_id || body.data?.video_id || '';
const videoUrl = body.video_url || body.data?.video_url || body.url || '';
const thumbnailUrl = body.thumbnail_url || body.data?.thumbnail_url || '';
const duration = body.duration || body.data?.duration || 0;
const status = body.status || body.data?.status || '';

const isSuccess = eventType === 'avatar_video.success' || status === 'completed';
const isFail = eventType === 'avatar_video.fail' || status === 'failed';

return {
  json: {
    heygenVideoId: videoId,
    videoUrl: videoUrl,
    thumbnailUrl: thumbnailUrl,
    duration: duration,
    isSuccess: isSuccess,
    isFail: isFail,
    eventType: eventType,
    rawStatus: status,
    errorMessage: isFail ? (body.error || body.data?.error || 'Video generation failed') : '',
  }
};
"""

VIDEO02_FORMAT_FOR_BLOTATO = r"""
// Format video data for Blotato publishing
const videoData = $('Process Callback').first().json;
const jobData = $('Lookup Video Job').first().json;

const caption = jobData.Caption || jobData['Property Name'] || 'Check out this property!';
const hashtags = jobData.Hashtags || '#realestate #property #southafrica #johannesburg';
const postText = caption + '\n\n' + hashtags;

return {
  json: {
    postText: postText,
    videoUrl: videoData.videoUrl,
    thumbnailUrl: videoData.thumbnailUrl,
    jobId: jobData['Job ID'] || '',
    recordId: jobData.id || '',
    propertyName: jobData['Property Name'] || '',
    caption: caption,
    hashtags: hashtags,
  }
};
"""

VIDEO02_PROCESS_DISTRIBUTION = r"""
// Aggregate Blotato publish results
const items = $input.all();
const platforms = ['TikTok', 'Instagram', 'Facebook'];
const jobData = $('Format for Blotato').first().json;
const now = new Date().toISOString();

let successCount = 0;
let failCount = 0;
const publishedPlatforms = [];

const logEntries = items.map((item, i) => {
  const platform = platforms[i] || 'Unknown';
  const hasError = !!(item.json.error || item.json.statusCode >= 400);
  if (hasError) {
    failCount++;
  } else {
    successCount++;
    publishedPlatforms.push(platform);
  }
  return {
    json: {
      'Log ID': `VLOG-${Date.now()}-${platform}`,
      'Content ID': jobData.jobId,
      'Platform': platform,
      'Published At': now,
      'Status': hasError ? 'Failed' : 'Success',
      'Response': JSON.stringify(item.json).substring(0, 200),
      _recordId: jobData.recordId,
      _successCount: successCount,
      _failCount: failCount,
      _publishedPlatforms: publishedPlatforms.join(', '),
    }
  };
});

return logEntries;
"""


# ======================================================================
# WORKFLOW BUILDERS
# ======================================================================

def build_video01():
    """
    VIDEO-01: Property Video Producer

    Schedule (daily 11:00 SAST = 09:00 UTC) + Webhook on-demand
    -> Fetch Pending jobs from Airtable
    -> Loop over each job
    -> Generate script via Claude/OpenRouter
    -> Generate caption via Claude/OpenRouter
    -> Prepare HeyGen API payload
    -> Call HeyGen API to create video
    -> Update Airtable with video_id + status
    """
    nodes = []
    connections = {}

    # -- Schedule Trigger (daily 11:00 SAST = 09:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "0 9 * * *"}]
            },
        },
        "id": uid(), "name": "Daily 11:00 SAST",
        "type": "n8n-nodes-base.scheduleTrigger", "position": [220, 300], "typeVersion": 1.2,
    })

    # -- Webhook Trigger (on-demand) --
    nodes.append({
        "parameters": {
            "httpMethod": "POST",
            "path": "heygen-produce",
            "options": {"responseMode": "lastNode"},
        },
        "id": uid(), "name": "On-Demand Trigger",
        "type": "n8n-nodes-base.webhook", "position": [220, 500], "typeVersion": 2,
    })

    # -- Merge triggers --
    nodes.append({
        "parameters": {"mode": "append"},
        "id": uid(), "name": "Merge Triggers",
        "type": "n8n-nodes-base.merge", "position": [460, 400], "typeVersion": 3,
    })

    # -- Fetch Pending Video Jobs --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": MARKETING_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_VIDEO_JOBS},
            "filterByFormula": "={Status} = 'Pending'",
            "options": {"fields": [
                "Job ID", "Property Name", "Property Type", "Property Address",
                "Listing Price ZAR", "Key Features", "Property Photos",
                "Aspect Ratio", "Avatar Type", "Avatar ID", "Script Tone",
                "Target Platforms", "Source Listing ID",
            ]},
        },
        "id": uid(), "name": "Fetch Pending Jobs",
        "type": "n8n-nodes-base.airtable", "position": [700, 400], "typeVersion": 2.1,
        "alwaysOutputData": True, "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Check if any jobs --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [{
                    "leftValue": "={{ $input.all().length }}",
                    "rightValue": 0,
                    "operator": {"type": "number", "operation": "gt"},
                }],
                "combinator": "and",
            },
        },
        "id": uid(), "name": "Has Pending Jobs?",
        "type": "n8n-nodes-base.if", "position": [940, 400], "typeVersion": 2,
    })

    # -- No-op for empty --
    nodes.append({
        "parameters": {},
        "id": uid(), "name": "No Jobs",
        "type": "n8n-nodes-base.noOp", "position": [1180, 600], "typeVersion": 1,
    })

    # -- Loop over jobs --
    nodes.append({
        "parameters": {"options": {}},
        "id": uid(), "name": "Loop Over Jobs",
        "type": "n8n-nodes-base.splitInBatches", "position": [1180, 300], "typeVersion": 3,
    })

    # -- Generate Script via OpenRouter --
    prompt_with_placeholders = (
        SCRIPT_GENERATION_PROMPT
        .replace("{{property_name}}", "{{ $json['Property Name'] }}")
        .replace("{{property_type}}", "{{ $json['Property Type'] }}")
        .replace("{{property_address}}", "{{ $json['Property Address'] }}")
        .replace("{{listing_price}}", "{{ $json['Listing Price ZAR'] }}")
        .replace("{{key_features}}", "{{ $json['Key Features'] }}")
        .replace("{{script_tone}}", "{{ $json['Script Tone'] || 'professional, warm, aspirational' }}")
    )

    nodes.append({
        "parameters": {
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": json.dumps({
                "model": OPENROUTER_MODEL,
                "max_tokens": 500,
                "temperature": 0.7,
                "messages": [
                    {"role": "user", "content": "PLACEHOLDER_SCRIPT_PROMPT"}
                ],
            }),
            "options": {},
        },
        "id": uid(), "name": "Generate Script",
        "type": "n8n-nodes-base.httpRequest", "position": [1460, 300], "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # Fix: Replace placeholder with n8n expression (can't nest JSON in json.dumps)
    for node in nodes:
        if node["name"] == "Generate Script":
            body_str = json.dumps({
                "model": OPENROUTER_MODEL,
                "max_tokens": 500,
                "temperature": 0.7,
                "messages": [{"role": "user", "content": prompt_with_placeholders}],
            })
            node["parameters"]["jsonBody"] = body_str

    # -- Generate Caption via OpenRouter --
    caption_prompt = (
        CAPTION_GENERATION_PROMPT
        .replace("{{property_name}}", "{{ $('Loop Over Jobs').item.json['Property Name'] }}")
        .replace("{{property_type}}", "{{ $('Loop Over Jobs').item.json['Property Type'] }}")
        .replace("{{property_address}}", "{{ $('Loop Over Jobs').item.json['Property Address'] }}")
        .replace("{{listing_price}}", "{{ $('Loop Over Jobs').item.json['Listing Price ZAR'] }}")
        .replace("{{key_features}}", "{{ $('Loop Over Jobs').item.json['Key Features'] }}")
    )

    nodes.append({
        "parameters": {
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": json.dumps({
                "model": OPENROUTER_MODEL,
                "max_tokens": 300,
                "temperature": 0.7,
                "messages": [{"role": "user", "content": caption_prompt}],
            }),
            "options": {},
        },
        "id": uid(), "name": "Generate Caption",
        "type": "n8n-nodes-base.httpRequest", "position": [1740, 300], "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Prepare HeyGen Payload --
    nodes.append({
        "parameters": {"jsCode": VIDEO01_PREPARE_HEYGEN_PAYLOAD},
        "id": uid(), "name": "Prepare HeyGen Payload",
        "type": "n8n-nodes-base.code", "position": [2020, 300], "typeVersion": 2,
    })

    # -- Call HeyGen API --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": f"{HEYGEN_API_BASE}/v2/video/generate",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($json.heygenPayload) }}",
            "options": {
                "response": {"response": {"responseFormat": "json"}},
            },
        },
        "id": uid(), "name": "Create HeyGen Video",
        "type": "n8n-nodes-base.httpRequest", "position": [2300, 300], "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_HEYGEN},
        "onError": "continueRegularOutput",
    })

    # -- Update Airtable with video_id + script + caption --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": MARKETING_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_VIDEO_JOBS},
            "columns": {
                "value": {
                    "Status": "={{ $('Create HeyGen Video').first().json.error ? 'Failed' : 'Generating' }}",
                    "HeyGen Video ID": "={{ $('Create HeyGen Video').first().json.data?.video_id || '' }}",
                    "HeyGen Status": "={{ $('Create HeyGen Video').first().json.error ? 'error' : 'processing' }}",
                    "Script": "={{ $json.script }}",
                    "Caption": "={{ $json.caption }}",
                    "Hashtags": "={{ $json.hashtags }}",
                    "Error Message": "={{ $('Create HeyGen Video').first().json.error?.message || '' }}",
                },
                "schema": [
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "HeyGen Video ID", "type": "string", "display": True, "displayName": "HeyGen Video ID"},
                    {"id": "HeyGen Status", "type": "string", "display": True, "displayName": "HeyGen Status"},
                    {"id": "Script", "type": "string", "display": True, "displayName": "Script"},
                    {"id": "Caption", "type": "string", "display": True, "displayName": "Caption"},
                    {"id": "Hashtags", "type": "string", "display": True, "displayName": "Hashtags"},
                    {"id": "Error Message", "type": "string", "display": True, "displayName": "Error Message"},
                ],
                "mappingMode": "defineBelow", "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(), "name": "Update Job Status",
        "type": "n8n-nodes-base.airtable", "position": [2580, 300], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Loop back --
    # The splitInBatches node loops automatically

    # Build connections
    node_names = [n["name"] for n in nodes]

    def conn(from_name, to_name, from_idx=0, to_idx=0):
        """Helper to build a connection."""
        if from_name not in connections:
            connections[from_name] = {"main": []}
        while len(connections[from_name]["main"]) <= from_idx:
            connections[from_name]["main"].append([])
        connections[from_name]["main"][from_idx].append({"node": to_name, "type": "main", "index": to_idx})

    # Schedule + Webhook -> Merge -> Fetch -> If
    conn("Daily 11:00 SAST", "Merge Triggers", 0, 0)
    conn("On-Demand Trigger", "Merge Triggers", 0, 1)
    conn("Merge Triggers", "Fetch Pending Jobs")
    conn("Fetch Pending Jobs", "Has Pending Jobs?")

    # If true -> Loop, If false -> No-op
    conn("Has Pending Jobs?", "Loop Over Jobs", 0)
    conn("Has Pending Jobs?", "No Jobs", 1)

    # Loop -> Generate Script -> Generate Caption -> Prepare -> HeyGen API -> Update -> Loop back
    conn("Loop Over Jobs", "Generate Script", 1)  # output 1 = each item
    conn("Generate Script", "Generate Caption")
    conn("Generate Caption", "Prepare HeyGen Payload")
    conn("Prepare HeyGen Payload", "Create HeyGen Video")
    conn("Create HeyGen Video", "Update Job Status")
    conn("Update Job Status", "Loop Over Jobs")  # loop back to batch node

    return {
        "name": "VIDEO-01: Property Video Producer",
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
            "errorWorkflow": "",
        },
    }


def build_video02():
    """
    VIDEO-02: HeyGen Callback & Distributor

    Webhook (HeyGen callback) -> Process -> Lookup job -> If success:
      -> Format for Blotato -> Publish to TikTok/IG/FB -> Log -> Update Airtable -> Email
    If fail:
      -> Update Airtable with error -> Email alert
    """
    nodes = []
    connections = {}

    # -- Webhook Trigger (HeyGen callback) --
    nodes.append({
        "parameters": {
            "httpMethod": "POST",
            "path": "heygen-callback",
            "options": {},
        },
        "id": uid(), "name": "HeyGen Callback",
        "type": "n8n-nodes-base.webhook", "position": [220, 400], "typeVersion": 2,
    })

    # -- Process Callback --
    nodes.append({
        "parameters": {"jsCode": VIDEO02_PROCESS_CALLBACK},
        "id": uid(), "name": "Process Callback",
        "type": "n8n-nodes-base.code", "position": [480, 400], "typeVersion": 2,
    })

    # -- Lookup Video Job in Airtable by HeyGen Video ID --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": MARKETING_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_VIDEO_JOBS},
            "filterByFormula": "=({HeyGen Video ID} = '{{ $json.heygenVideoId }}')",
            "options": {},
        },
        "id": uid(), "name": "Lookup Video Job",
        "type": "n8n-nodes-base.airtable", "position": [740, 400], "typeVersion": 2.1,
        "alwaysOutputData": True, "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Check success/fail --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [{
                    "leftValue": "={{ $('Process Callback').first().json.isSuccess }}",
                    "rightValue": True,
                    "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                }],
                "combinator": "and",
            },
        },
        "id": uid(), "name": "Video Success?",
        "type": "n8n-nodes-base.if", "position": [1000, 400], "typeVersion": 2,
    })

    # ===================== SUCCESS PATH (top) =====================

    # -- Update Airtable: Ready --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": MARKETING_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_VIDEO_JOBS},
            "columns": {
                "value": {
                    "Status": "Ready",
                    "HeyGen Status": "completed",
                    "Video URL": "={{ $('Process Callback').first().json.videoUrl }}",
                    "Thumbnail URL": "={{ $('Process Callback').first().json.thumbnailUrl }}",
                    "Video Duration Sec": "={{ $('Process Callback').first().json.duration }}",
                    "Completed At": "={{ $now.toISO() }}",
                },
                "schema": [
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "HeyGen Status", "type": "string", "display": True, "displayName": "HeyGen Status"},
                    {"id": "Video URL", "type": "string", "display": True, "displayName": "Video URL"},
                    {"id": "Thumbnail URL", "type": "string", "display": True, "displayName": "Thumbnail URL"},
                    {"id": "Video Duration Sec", "type": "number", "display": True, "displayName": "Video Duration Sec"},
                    {"id": "Completed At", "type": "string", "display": True, "displayName": "Completed At"},
                ],
                "mappingMode": "defineBelow", "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(), "name": "Mark Ready",
        "type": "n8n-nodes-base.airtable", "position": [1280, 200], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Format for Blotato --
    nodes.append({
        "parameters": {"jsCode": VIDEO02_FORMAT_FOR_BLOTATO},
        "id": uid(), "name": "Format for Blotato",
        "type": "n8n-nodes-base.code", "position": [1560, 200], "typeVersion": 2,
    })

    # -- 3 Blotato platform nodes --
    platforms = [
        ("TikTok", "tiktok", [1840, 60]),
        ("Instagram", "instagram", [1840, 240]),
        ("Facebook", "facebook", [1840, 420]),
    ]
    for platform_name, platform_key, position in platforms:
        account = BLOTATO_ACCOUNTS[platform_key]
        params = {
            "platform": platform_key,
            "accountId": {"__rl": True, "mode": "list", "value": account["accountId"]},
            "postContentText": "={{ $json.postText }}",
            "postContentVideoUrl": "={{ $json.videoUrl }}",
            "options": {},
        }
        if platform_key == "facebook" and "subAccountId" in account:
            params["facebookPageId"] = {"__rl": True, "mode": "list", "value": account["subAccountId"]}
        nodes.append({
            "parameters": params, "id": uid(), "name": f"{platform_name} [BLOTATO]",
            "type": "@blotato/n8n-nodes-blotato.blotato", "position": position,
            "typeVersion": 2, "credentials": {"blotatoApi": CRED_BLOTATO}, "onError": "continueRegularOutput",
        })

    # -- Merge platform results --
    nodes.append({
        "parameters": {"mode": "append"},
        "id": uid(), "name": "Merge Platform Results",
        "type": "n8n-nodes-base.merge", "position": [2120, 240], "typeVersion": 3,
    })

    # -- Process distribution results --
    nodes.append({
        "parameters": {"jsCode": VIDEO02_PROCESS_DISTRIBUTION},
        "id": uid(), "name": "Process Distribution",
        "type": "n8n-nodes-base.code", "position": [2380, 240], "typeVersion": 2, "alwaysOutputData": True,
    })

    # -- Store Distribution Log --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": MARKETING_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_DISTRIBUTION_LOG},
            "columns": {
                "value": {
                    "Log ID": "={{ $json['Log ID'] }}", "Content ID": "={{ $json['Content ID'] }}",
                    "Platform": "={{ $json['Platform'] }}", "Published At": "={{ $json['Published At'] }}",
                    "Status": "={{ $json['Status'] }}", "Response": "={{ $json['Response'] }}",
                },
                "schema": [
                    {"id": "Log ID", "type": "string", "display": True, "displayName": "Log ID"},
                    {"id": "Content ID", "type": "string", "display": True, "displayName": "Content ID"},
                    {"id": "Platform", "type": "string", "display": True, "displayName": "Platform"},
                    {"id": "Published At", "type": "string", "display": True, "displayName": "Published At"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Response", "type": "string", "display": True, "displayName": "Response"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(), "name": "Store Distribution Log",
        "type": "n8n-nodes-base.airtable", "position": [2640, 240], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Update Job: Published --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": MARKETING_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_VIDEO_JOBS},
            "columns": {
                "value": {
                    "Status": "Published",
                    "Published At": "={{ $now.toISO() }}",
                    "Published Platforms": "={{ $json._publishedPlatforms }}",
                },
                "schema": [
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Published At", "type": "string", "display": True, "displayName": "Published At"},
                    {"id": "Published Platforms", "type": "string", "display": True, "displayName": "Published Platforms"},
                ],
                "mappingMode": "defineBelow", "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(), "name": "Mark Published",
        "type": "n8n-nodes-base.airtable", "position": [2900, 240], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Success Notification Email --
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=Video Published: {{ $('Lookup Video Job').first().json['Property Name'] || 'Property Video' }}",
            "emailType": "text",
            "message": (
                "=Property video has been published!\n\n"
                "Property: {{ $('Lookup Video Job').first().json['Property Name'] }}\n"
                "Video URL: {{ $('Process Callback').first().json.videoUrl }}\n"
                "Platforms: {{ $json._publishedPlatforms }}\n"
                "Published: {{ $now.toFormat('yyyy-MM-dd HH:mm') }}\n\n"
                "Check Airtable Video_Jobs table for full details."
            ),
            "options": {},
        },
        "id": uid(), "name": "Success Email",
        "type": "n8n-nodes-base.gmail", "position": [3160, 240], "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ===================== FAILURE PATH (bottom) =====================

    # -- Update Airtable: Failed --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": MARKETING_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_VIDEO_JOBS},
            "columns": {
                "value": {
                    "Status": "Failed",
                    "HeyGen Status": "failed",
                    "Error Message": "={{ $('Process Callback').first().json.errorMessage }}",
                },
                "schema": [
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "HeyGen Status", "type": "string", "display": True, "displayName": "HeyGen Status"},
                    {"id": "Error Message", "type": "string", "display": True, "displayName": "Error Message"},
                ],
                "mappingMode": "defineBelow", "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(), "name": "Mark Failed",
        "type": "n8n-nodes-base.airtable", "position": [1280, 600], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Failure Alert Email --
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=VIDEO FAILED: {{ $('Lookup Video Job').first().json['Property Name'] || 'Property Video' }}",
            "emailType": "text",
            "message": (
                "=HeyGen video generation FAILED.\n\n"
                "Property: {{ $('Lookup Video Job').first().json['Property Name'] }}\n"
                "Job ID: {{ $('Lookup Video Job').first().json['Job ID'] }}\n"
                "Error: {{ $('Process Callback').first().json.errorMessage }}\n"
                "Event: {{ $('Process Callback').first().json.eventType }}\n\n"
                "Check HeyGen dashboard and Airtable Video_Jobs for details."
            ),
            "options": {},
        },
        "id": uid(), "name": "Failure Alert Email",
        "type": "n8n-nodes-base.gmail", "position": [1560, 600], "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # Build connections
    def conn(from_name, to_name, from_idx=0, to_idx=0):
        if from_name not in connections:
            connections[from_name] = {"main": []}
        while len(connections[from_name]["main"]) <= from_idx:
            connections[from_name]["main"].append([])
        connections[from_name]["main"][from_idx].append({"node": to_name, "type": "main", "index": to_idx})

    # Main flow
    conn("HeyGen Callback", "Process Callback")
    conn("Process Callback", "Lookup Video Job")
    conn("Lookup Video Job", "Video Success?")

    # Success path (output 0)
    conn("Video Success?", "Mark Ready", 0)
    conn("Mark Ready", "Format for Blotato")

    # Blotato fan-out
    conn("Format for Blotato", "TikTok [BLOTATO]")
    conn("Format for Blotato", "Instagram [BLOTATO]")
    conn("Format for Blotato", "Facebook [BLOTATO]")

    # Merge results
    conn("TikTok [BLOTATO]", "Merge Platform Results", 0, 0)
    conn("Instagram [BLOTATO]", "Merge Platform Results", 0, 1)
    conn("Facebook [BLOTATO]", "Merge Platform Results", 0, 2)

    # Process + Log + Update + Email
    conn("Merge Platform Results", "Process Distribution")
    conn("Process Distribution", "Store Distribution Log")
    conn("Store Distribution Log", "Mark Published")
    conn("Mark Published", "Success Email")

    # Failure path (output 1)
    conn("Video Success?", "Mark Failed", 1)
    conn("Mark Failed", "Failure Alert Email")

    return {
        "name": "VIDEO-02: HeyGen Callback & Distributor",
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
            "errorWorkflow": "",
        },
    }


# ======================================================================
# WORKFLOW DEFINITIONS
# ======================================================================

WORKFLOW_DEFS = {
    "video01": {
        "builder": build_video01,
        "description": "Property Video Producer (schedule + on-demand)",
        "trigger": "Daily 11:00 SAST + Webhook",
        "nodes_est": 15,
    },
    "video02": {
        "builder": build_video02,
        "description": "HeyGen Callback & Distributor",
        "trigger": "HeyGen webhook callback",
        "nodes_est": 18,
    },
}


def build_workflow(wf_id):
    """Build a single workflow by ID."""
    wf_def = WORKFLOW_DEFS[wf_id]
    return wf_def["builder"]()


def save_workflow(wf_id, workflow):
    """Save workflow JSON to file."""
    output_dir = Path(__file__).parent.parent / "workflows" / "heygen-video"
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{wf_id}_{workflow['name'].lower().replace(' ', '_').replace(':', '').replace('-', '_')}.json"
    output_path = output_dir / filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2)

    return output_path


def print_workflow_stats(wf_id, workflow):
    """Print workflow statistics."""
    wf_def = WORKFLOW_DEFS[wf_id]
    node_count = len(workflow["nodes"])
    conn_count = sum(
        len(targets)
        for outputs in workflow["connections"].values()
        for output_list in outputs.get("main", [])
        for targets in [output_list]
    )
    print(f"  Name: {workflow['name']}")
    print(f"  Description: {wf_def['description']}")
    print(f"  Trigger: {wf_def['trigger']}")
    print(f"  Nodes: {node_count} (est: {wf_def['nodes_est']})")
    print(f"  Connections: {conn_count}")


def main():
    args = sys.argv[1:]
    action = args[0] if args else "build"
    target = args[1] if len(args) > 1 else "all"

    if action not in ("build", "deploy", "activate"):
        print(f"Usage: python {Path(__file__).name} [build|deploy|activate] [video01|video02|all]")
        sys.exit(1)

    sys.path.insert(0, str(Path(__file__).parent))

    print("=" * 60)
    print("HEYGEN VIDEO PIPELINE - WORKFLOW BUILDER")
    print("=" * 60)

    valid_wfs = list(WORKFLOW_DEFS.keys())
    if target == "all":
        workflow_ids = valid_wfs
    elif target in valid_wfs:
        workflow_ids = [target]
    else:
        print(f"ERROR: Unknown target '{target}'. Use: all, {', '.join(valid_wfs)}")
        sys.exit(1)

    # Check table config
    if "REPLACE" in TABLE_VIDEO_JOBS:
        print()
        print("WARNING: Airtable Video_Jobs table ID not configured!")
        print("  Run: python tools/setup_heygen_airtable.py")
        print("  Then set HEYGEN_TABLE_VIDEO_JOBS in .env")
        print()
        if action in ("deploy", "activate"):
            print("Cannot deploy with placeholder IDs. Aborting.")
            sys.exit(1)
        print("Continuing build with placeholder IDs (for preview only)...")
        print()

    # Check HeyGen cred
    if "REPLACE" in CRED_HEYGEN["id"]:
        print("NOTE: N8N_CRED_HEYGEN not set. Create httpHeaderAuth credential in n8n UI first.")
        print("  Header Name: X-Api-Key")
        print("  Header Value: Your HeyGen API key")
        print()

    # Build workflows
    workflows = {}
    for wf_id in workflow_ids:
        print(f"\nBuilding {wf_id}...")
        workflow = build_workflow(wf_id)
        output_path = save_workflow(wf_id, workflow)
        workflows[wf_id] = workflow
        print_workflow_stats(wf_id, workflow)
        print(f"  Saved to: {output_path}")

    if action == "build":
        print("\nBuild complete. Run with 'deploy' to push to n8n.")
        return

    # Deploy to n8n
    if action in ("deploy", "activate"):
        from n8n_client import N8nClient

        api_key = os.getenv("N8N_API_KEY")
        base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")

        if not api_key:
            print("ERROR: N8N_API_KEY not set in .env")
            sys.exit(1)

        print(f"\nConnecting to {base_url}...")

        with N8nClient(base_url, api_key, timeout=30) as client:
            health = client.health_check()
            if not health["connected"]:
                print(f"  ERROR: Cannot connect to n8n: {health.get('error')}")
                sys.exit(1)
            print("  Connected!")

            deployed_ids = {}

            for wf_id, workflow in workflows.items():
                print(f"\nDeploying {wf_id}...")

                existing = None
                try:
                    all_wfs = client.list_workflows()
                    for wf in all_wfs:
                        if wf["name"] == workflow["name"]:
                            existing = wf
                            break
                except Exception:
                    pass

                if existing:
                    update_payload = {
                        "name": workflow["name"],
                        "nodes": workflow["nodes"],
                        "connections": workflow["connections"],
                        "settings": workflow["settings"],
                    }
                    result = client.update_workflow(existing["id"], update_payload)
                    deployed_ids[wf_id] = result.get("id")
                    print(f"  Updated: {result.get('name')} (ID: {result.get('id')})")
                else:
                    create_payload = {
                        "name": workflow["name"],
                        "nodes": workflow["nodes"],
                        "connections": workflow["connections"],
                        "settings": workflow["settings"],
                    }
                    result = client.create_workflow(create_payload)
                    deployed_ids[wf_id] = result.get("id")
                    print(f"  Created: {result.get('name')} (ID: {result.get('id')})")

            if action == "activate":
                print("\nActivating workflows...")
                # Activate VIDEO-02 first (webhook receiver must be ready)
                activate_order = ["video02", "video01"]
                for wf_id in activate_order:
                    if wf_id in deployed_ids and deployed_ids[wf_id]:
                        try:
                            client.activate_workflow(deployed_ids[wf_id])
                            print(f"  Activated: {wf_id} ({deployed_ids[wf_id]})")
                        except Exception as e:
                            print(f"  ERROR activating {wf_id}: {e}")

            print("\n" + "=" * 60)
            print("DEPLOYMENT SUMMARY")
            print("=" * 60)
            for wf_id, n8n_id in deployed_ids.items():
                print(f"  {wf_id}: {n8n_id}")

            # Print webhook URLs
            print("\nWebhook URLs (after activation):")
            if "video01" in deployed_ids:
                print(f"  On-demand trigger: {N8N_WEBHOOK_BASE}/heygen-produce")
            if "video02" in deployed_ids:
                print(f"  HeyGen callback:   {N8N_WEBHOOK_BASE}/heygen-callback")
                print()
                print("IMPORTANT: Register this callback URL in HeyGen:")
                print(f"  POST {HEYGEN_API_BASE}/v1/webhook/endpoint.add")
                print(f"  Body: {{\"url\": \"{N8N_WEBHOOK_BASE}/heygen-callback\",")
                print(f'         "events": ["avatar_video.success", "avatar_video.fail"]}}')


if __name__ == "__main__":
    main()
