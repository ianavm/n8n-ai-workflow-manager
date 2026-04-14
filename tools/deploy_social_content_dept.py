"""
Social Content Trend Replication - Workflow Builder & Deployer

Builds all Social Content workflows as n8n workflow JSON files,
and optionally deploys them to the n8n instance.

Workflows:
    SC-01: Trend Discovery (Daily 6AM SAST, orchestrator)
    SC-02: Script Extraction (sub-workflow, called by SC-01)
    SC-03: Brand Adaptation (sub-workflow, called by SC-01)
    SC-04: Video Production (Daily 7AM SAST + webhook)
    SC-05: Distribution (Daily 8AM SAST + webhook)

Usage:
    python tools/deploy_social_content_dept.py build              # Build all JSONs
    python tools/deploy_social_content_dept.py build sc01         # Build SC-01 only
    python tools/deploy_social_content_dept.py deploy             # Build + Deploy
    python tools/deploy_social_content_dept.py activate           # Build + Deploy + Activate
"""

import json
import sys
import uuid
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))
from credentials import (
    CRED_AIRTABLE,
    CRED_BLOTATO,
    CRED_OPENAI,
    CRED_GMAIL,
)

# Use the working OpenRouter Bearer credential (same as LinkedIn dept)
CRED_OPENROUTER = {"id": "87T4lIBmU8si87Ms", "name": "OpenRouter Bearer"}

# -- Airtable IDs ---------------------------------------------------------

AIRTABLE_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")

TABLE_TRENDING = os.getenv("SC_TABLE_TRENDING", "REPLACE_WITH_TABLE_ID")
TABLE_SCRIPTS = os.getenv("SC_TABLE_SCRIPTS", "REPLACE_WITH_TABLE_ID")
TABLE_PRODUCTION_LOG = os.getenv("SC_TABLE_PRODUCTION_LOG", "REPLACE_WITH_TABLE_ID")

# -- External APIs ---------------------------------------------------------

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "REPLACE_WITH_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", os.getenv("GOOGLE_PLACES_API_KEY", "REPLACE_WITH_KEY"))
AIRTABLE_API_TOKEN = os.getenv("AIRTABLE_API_TOKEN", "REPLACE_WITH_TOKEN")
REMOTION_RENDER_URL = os.getenv("REMOTION_RENDER_URL", "https://social-render.up.railway.app")

# Sub-workflow IDs (set after first deploy, used by SC-01 orchestrator)
SC02_WORKFLOW_ID = os.getenv("SC02_WORKFLOW_ID", "REPLACE_AFTER_DEPLOY")
SC03_WORKFLOW_ID = os.getenv("SC03_WORKFLOW_ID", "REPLACE_AFTER_DEPLOY")

# -- Blotato Account IDs --------------------------------------------------

BLOTATO_ACCOUNTS = {
    # Real AVM Blotato account IDs — queried from /v2/users/me/accounts on 2026-04-13
    "instagram": {"accountId": "35463", "name": "Instagram (anyvision.media)"},
    "linkedin": {"accountId": "15167", "name": "LinkedIn (Ian Immelman)"},
    "tiktok": {"accountId": "33677", "name": "TikTok (anyvision.media)"},
    "facebook": {"accountId": "23022", "name": "Facebook (Ian Immelman)"},
    "twitter": {"accountId": "14195", "name": "Twitter (AnyVisionMedia)"},
    "youtube": {"accountId": "33524", "name": "YouTube (AnyVision Media Brand Account)"},
    # Not currently connected in Blotato — reconnect in Blotato dashboard to enable:
    "threads": {"accountId": "NOT_CONNECTED", "name": "Threads"},
    "bluesky": {"accountId": "NOT_CONNECTED", "name": "Bluesky"},
    "pinterest": {"accountId": "NOT_CONNECTED", "name": "Pinterest"},
}

# -- Search Queries --------------------------------------------------------

TREND_SEARCH_QUERIES = [
    "digital marketing tips",
    "social media marketing 2026",
    "AI marketing automation",
    "content creation tips",
    "agency growth strategies",
]

INSTAGRAM_HASHTAGS = [
    "digitalmarketing",
    "marketingtips",
    "socialmediamarketing",
    "aimarketing",
    "contentcreation",
]


# -- AI Prompts ------------------------------------------------------------

SCRIPT_EXTRACTION_PROMPT = """You are a viral content analyst. Analyze this trending social media content and extract the reusable template.

## Input
Platform: {platform}
Creator: {creator}
Title: {title}
Engagement: {views} views, {likes} likes, {comments} comments
Content text/transcript:
{transcript}

## Task
Extract the structural template that makes this content viral. Identify the hook pattern, body structure, and CTA placement.

## Output (JSON only, no markdown, no backticks):
{{
  "template_pattern": "Hook: [describe pattern] -> Body: [describe structure] -> CTA: [describe CTA type]",
  "content_category": "How-to|Listicle|Quote|Stat-graphic|Reaction|Story|Tutorial",
  "virality_factors": ["factor1", "factor2", "factor3"],
  "video_type_recommendation": "Text-on-screen|Quote-card|Stat-graphic|Talking-head-script",
  "adaptability_score": 85,
  "key_elements": ["element1", "element2"]
}}"""

BRAND_ADAPTATION_PROMPT = """You are the Creative Director for AnyVision Media, a South African digital marketing and AI automation agency. Adapt this proven viral content template for the AnyVision Media brand while maintaining the structural elements that made the original go viral.

## Brand Guidelines
- Company: AnyVision Media
- Owner: Ian Immelman
- Primary color: #FF6D5A
- Voice: Professional but approachable, tech-savvy, innovation-focused
- Services: AI workflow automation, web development, social media management
- Target: South African SMBs looking to automate and scale
- Core narrative: "Building SA's First Million-Dollar AI Company"
- South African English (lounge not living room, braai not barbecue)
- Currency: ZAR
- No emojis in scripts

## Content Pillars (rotate evenly):
1. Journey (40%): Daily updates, revenue milestones, wins, failures, lessons
2. Value (35%): How-to guides, frameworks, tools, industry insights
3. Aspiration (25%): Vision casting, client results, before/after transformations

## Original Trending Content
Platform: {platform}
Template pattern: {template_pattern}
Content category: {content_category}
Original transcript: {transcript}
Engagement: {views} views, {likes} likes, {comments} comments

## Task
1. Adapt this template for AnyVision Media's digital marketing niche
2. Replace specific examples with AVM-relevant examples (AI automation, n8n workflows, client results)
3. Keep the EXACT structural pattern that made it viral (hook timing, pacing, CTA placement)
4. Write for approximately {duration}s video duration
5. Determine the best video type: text-on-screen, quote-card, stat-graphic, or talking-head-script

## Output (JSON only, no markdown, no backticks):
{{
  "script_text": "full script with line breaks separating scenes",
  "hook": "first 3 seconds text (under 100 chars)",
  "cta": "call to action text",
  "video_type": "Text-on-screen|Quote-card|Stat-graphic|Talking-head-script",
  "visual_notes": "scene-by-scene visual directions",
  "content_pillar": "Journey|Value|Aspiration",
  "estimated_duration_sec": 30,
  "quality_score": 85
}}"""

CAPTION_GENERATION_PROMPT = """Generate platform-specific captions for this video script by AnyVision Media, a South African digital marketing agency.

Script: {script_text}
Video type: {video_type}
Content pillar: {content_pillar}
Hook: {hook}

## Output (JSON only, no markdown, no backticks):
{{
  "caption_instagram": "max 2200 chars, include line breaks for readability, end with CTA, include 3-5 hashtags inline",
  "caption_linkedin": "professional tone, max 1300 chars, include insights and a question to drive engagement",
  "caption_youtube": "SEO-optimized title + description, include keywords, max 500 chars for description",
  "hashtags": "#digitalmarketing #aiautomation #southafrica #agencylife #marketingtips",
  "thumbnail_prompt": "Gemini image prompt for a bold social media thumbnail: subject + style + brand colors"
}}"""


def uid() -> str:
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ==================================================================
# SC-01: TREND DISCOVERY (Orchestrator)
# ==================================================================

def build_sc01_nodes() -> list[dict]:
    """Build all nodes for SC-01 Trend Discovery."""
    nodes = []

    # -- Schedule Trigger (Daily 6AM SAST = 4AM UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"triggerAtHour": 4}],
            },
        },
        "id": uid(),
        "name": "Daily 6AM SAST",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 400],
        "typeVersion": 1.2,
    })

    # -- Manual Trigger --
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 600],
        "typeVersion": 1,
    })

    # -- Search Config --
    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "todayDate", "value": "={{ $now.toFormat('yyyy-MM-dd') }}", "type": "string"},
                    {"id": uid(), "name": "searchQueries", "value": json.dumps(TREND_SEARCH_QUERIES), "type": "string"},
                    {"id": uid(), "name": "instagramHashtags", "value": json.dumps(INSTAGRAM_HASHTAGS), "type": "string"},
                    {"id": uid(), "name": "youtubeApiKey", "value": YOUTUBE_API_KEY, "type": "string"},
                    {"id": uid(), "name": "apifyToken", "value": APIFY_API_TOKEN, "type": "string"},
                ],
            },
        },
        "id": uid(),
        "name": "Search Config",
        "type": "n8n-nodes-base.set",
        "position": [460, 400],
        "typeVersion": 3.4,
    })

    # -- YouTube Discovery (HTTP Request to YouTube Data API) --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "https://www.googleapis.com/youtube/v3/search",
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {"name": "part", "value": "snippet"},
                    {"name": "type", "value": "video"},
                    {"name": "videoDuration", "value": "short"},
                    {"name": "order", "value": "viewCount"},
                    {"name": "maxResults", "value": "10"},
                    {"name": "q", "value": "={{ $json.searchQueries ? JSON.parse($json.searchQueries).join(' OR ') : 'digital marketing tips' }}"},
                    {"name": "key", "value": "={{ $json.youtubeApiKey }}"},
                    {"name": "publishedAfter", "value": "={{ $now.minus({days: 7}).toISO() }}"},
                    {"name": "relevanceLanguage", "value": "en"},
                ],
            },
            "options": {"timeout": 15000},
        },
        "id": uid(),
        "name": "YouTube Search",
        "type": "n8n-nodes-base.httpRequest",
        "position": [720, 200],
        "typeVersion": 4.2,
    })

    # -- YouTube Stats (get view/like counts) --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "https://www.googleapis.com/youtube/v3/videos",
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {"name": "part", "value": "statistics,snippet,contentDetails"},
                    {"name": "id", "value": "={{ $json.items ? $json.items.map(i => i.id.videoId).join(',') : '' }}"},
                    {"name": "key", "value": "={{ $('Search Config').first().json.youtubeApiKey }}"},
                ],
            },
            "options": {"timeout": 15000},
        },
        "id": uid(),
        "name": "YouTube Stats",
        "type": "n8n-nodes-base.httpRequest",
        "position": [960, 200],
        "typeVersion": 4.2,
    })

    # -- Parse YouTube Results --
    nodes.append({
        "parameters": {
            "jsCode": """const items = $input.first().json.items || [];
const today = new Date().toISOString();

const results = items
  .filter(item => {
    // Filter for Shorts (under 60s)
    const duration = (item.contentDetails && item.contentDetails.duration) || '';
    const match = duration.match(/PT(?:(\\d+)M)?(?:(\\d+)S)?/);
    if (!match) return false;
    const totalSec = (parseInt(match[1] || '0') * 60) + parseInt(match[2] || '0');
    return totalSec <= 60;
  })
  .map(item => {
    const stats = item.statistics || {};
    const views = parseInt(stats.viewCount || '0');
    const likes = parseInt(stats.likeCount || '0');
    const comments = parseInt(stats.commentCount || '0');
    const engRate = views > 0 ? ((likes + comments * 2) / views * 100) : 0;

    return {
      platform: 'YouTube',
      sourceUrl: 'https://youtube.com/shorts/' + item.id,
      sourceCreator: (item.snippet && item.snippet.channelTitle) || 'Unknown',
      title: (item.snippet && item.snippet.title) || '',
      viewCount: views,
      likeCount: likes,
      commentCount: comments,
      engagementRate: Math.round(engRate * 100) / 100,
      discoveredAt: today,
    };
  })
  .sort((a, b) => b.viewCount - a.viewCount)
  .slice(0, 5);

const output = results.map(r => ({ json: r }));
return output.length > 0 ? output : [{ json: { _empty: true, platform: 'YouTube', sourceUrl: '' } }];""",
        },
        "id": uid(),
        "name": "Parse YouTube",
        "type": "n8n-nodes-base.code",
        "position": [1200, 200],
        "typeVersion": 2,
    })

    # -- Instagram Apify (HTTP Request to Apify) --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://api.apify.com/v2/acts/apify~instagram-hashtag-scraper/run-sync-get-dataset-items",
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {"name": "token", "value": "={{ $('Search Config').first().json.apifyToken }}"},
                ],
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '={{ JSON.stringify({ "hashtags": JSON.parse($("Search Config").first().json.instagramHashtags), "resultsLimit": 25, "resultsType": "posts" }) }}',
            "options": {"timeout": 60000},
        },
        "id": uid(),
        "name": "Instagram Apify",
        "type": "n8n-nodes-base.httpRequest",
        "position": [720, 400],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # -- Parse Instagram Results --
    nodes.append({
        "parameters": {
            "jsCode": """const items = Array.isArray($input.first().json) ? $input.first().json : ($input.all() || []).map(i => i.json);
const today = new Date().toISOString();

const results = items
  .filter(item => item.type === 'Video' || item.videoUrl)
  .map(item => {
    const views = item.videoViewCount || item.viewCount || 0;
    const likes = item.likesCount || 0;
    const comments = item.commentsCount || 0;
    const engRate = views > 0 ? ((likes + comments * 2) / views * 100) : 0;

    return {
      platform: 'Instagram',
      sourceUrl: item.url || item.shortCode ? ('https://instagram.com/reel/' + item.shortCode) : '',
      sourceCreator: item.ownerUsername || 'Unknown',
      title: (item.caption || '').slice(0, 200),
      viewCount: views,
      likeCount: likes,
      commentCount: comments,
      engagementRate: Math.round(engRate * 100) / 100,
      transcript: item.caption || '',
      discoveredAt: today,
    };
  })
  .filter(r => r.sourceUrl)
  .sort((a, b) => b.engagementRate - a.engagementRate)
  .slice(0, 5);

return results.length > 0 ? results.map(r => ({ json: r })) : [{ json: { platform: 'Instagram', _empty: true } }];""",
        },
        "id": uid(),
        "name": "Parse Instagram",
        "type": "n8n-nodes-base.code",
        "position": [1200, 400],
        "typeVersion": 2,
    })

    # -- LinkedIn Tavily Search --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://api.tavily.com/search",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f'{{"api_key": "REDACTED_TAVILY_KEY", "query": "site:linkedin.com digital marketing tips OR AI automation OR agency growth 2026", "max_results": 10, "search_depth": "basic", "include_domains": ["linkedin.com"], "days": 7}}',
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "LinkedIn Tavily",
        "type": "n8n-nodes-base.httpRequest",
        "position": [720, 600],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # -- Parse LinkedIn Results --
    nodes.append({
        "parameters": {
            "jsCode": """const response = $input.first().json;
const results = (response.results || [])
  .filter(r => r.url && r.url.includes('linkedin.com'))
  .map(r => ({
    platform: 'LinkedIn',
    sourceUrl: r.url,
    sourceCreator: r.title ? r.title.split(' - ')[0] || 'Unknown' : 'Unknown',
    title: (r.title || '').slice(0, 200),
    viewCount: 0,
    likeCount: 0,
    commentCount: 0,
    engagementRate: r.score ? Math.round(r.score * 100) : 50,
    transcript: r.content || '',
    discoveredAt: new Date().toISOString(),
  }))
  .slice(0, 5);

return results.length > 0 ? results.map(r => ({ json: r })) : [{ json: { platform: 'LinkedIn', _empty: true } }];""",
        },
        "id": uid(),
        "name": "Parse LinkedIn",
        "type": "n8n-nodes-base.code",
        "position": [1200, 600],
        "typeVersion": 2,
    })

    # -- Merge All Platforms --
    nodes.append({
        "parameters": {
            "mode": "append",
            "options": {},
        },
        "id": uid(),
        "name": "Merge Platforms",
        "type": "n8n-nodes-base.merge",
        "position": [1500, 300],
        "typeVersion": 3,
    })

    # -- Read Existing Trends (last 30 days for dedup) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_TRENDING},
            "filterByFormula": f"=AND(IS_AFTER({{Discovered At}}, DATEADD(TODAY(), -30, 'days')))",
            "options": {"fields": ["Trend ID", "Source URL"]},
        },
        "id": uid(),
        "name": "Read Existing Trends",
        "type": "n8n-nodes-base.airtable",
        "position": [1500, 700],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Wait for Both (Merge Platforms + Existing Trends) --
    nodes.append({
        "parameters": {
            "mode": "append",
            "options": {},
        },
        "id": uid(),
        "name": "Wait for All",
        "type": "n8n-nodes-base.merge",
        "position": [1740, 500],
        "typeVersion": 3,
    })

    # -- Dedup & Score --
    nodes.append({
        "parameters": {
            "jsCode": """// Get existing URLs for dedup — from input (merged data)
const allInputs = $input.all();
const existingUrls = new Set();
// Items from Read Existing Trends have fields.Source URL pattern
allInputs.forEach(item => {
  const url = (item.json.fields && item.json.fields['Source URL']) || '';
  if (url && !item.json.platform) existingUrls.add(url);
});

// Get all discovered items (items with a platform field are trending items)
const allItems = allInputs.filter(i => i.json.platform && !i.json.fields);

// Filter out empties, dupes, and score
const newItems = allItems
  .filter(item => {
    const j = item.json;
    if (j._empty) return false;
    if (!j.sourceUrl) return false;
    if (existingUrls.has(j.sourceUrl)) return false;
    return true;
  })
  .map(item => {
    const j = item.json;
    const views = j.viewCount || 0;
    const likes = j.likeCount || 0;
    const comments = j.commentCount || 0;
    // Virality score: weighted engagement normalized to 0-100
    const rawScore = views > 0
      ? ((likes + comments * 2) / views * 1000)
      : j.engagementRate || 0;
    const viralityScore = Math.min(100, Math.round(rawScore));

    return {
      json: {
        ...j,
        viralityScore,
      }
    };
  })
  .sort((a, b) => b.json.viralityScore - a.json.viralityScore)
  .slice(0, 10);

return newItems;""",
        },
        "id": uid(),
        "name": "Dedup and Score",
        "type": "n8n-nodes-base.code",
        "position": [1800, 400],
        "typeVersion": 2,
    })

    # -- Write to Airtable --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_TRENDING},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Trend ID": "={{ 'TR-' + $now.toFormat('yyyyMMdd-HHmmssSSS') + '-' + $json.platform.slice(0,2).toUpperCase() + '-' + $runIndex }}",
                    "Platform": "={{ $json.platform }}",
                    "Source URL": "={{ $json.sourceUrl }}",
                    "Source Creator": "={{ $json.sourceCreator }}",
                    "Title": "={{ $json.title }}",
                    "View Count": "={{ $json.viewCount }}",
                    "Like Count": "={{ $json.likeCount }}",
                    "Comment Count": "={{ $json.commentCount }}",
                    "Engagement Rate": "={{ $json.engagementRate }}",
                    "Virality Score": "={{ $json.viralityScore }}",
                    "Status": "Discovered",
                    "Discovered At": "={{ $now.toISO() }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write Trending",
        "type": "n8n-nodes-base.airtable",
        "position": [2280, 300],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Call SC-02 Script Extraction --
    nodes.append({
        "parameters": {
            "workflowId": {"__rl": True, "mode": "id", "value": SC02_WORKFLOW_ID},
            "options": {"waitForSubWorkflow": True},
        },
        "id": uid(),
        "name": "Call SC-02 Extract",
        "type": "n8n-nodes-base.executeWorkflow",
        "position": [2520, 300],
        "typeVersion": 1.2,
    })

    # -- Call SC-03 Brand Adaptation --
    nodes.append({
        "parameters": {
            "workflowId": {"__rl": True, "mode": "id", "value": SC03_WORKFLOW_ID},
            "options": {"waitForSubWorkflow": True},
        },
        "id": uid(),
        "name": "Call SC-03 Adapt",
        "type": "n8n-nodes-base.executeWorkflow",
        "position": [2760, 300],
        "typeVersion": 1.2,
    })

    # -- No Results Note --
    nodes.append({
        "parameters": {
            "content": "No new trending content found today — all discovered URLs already in Airtable.",
        },
        "id": uid(),
        "name": "No Results Note",
        "type": "n8n-nodes-base.stickyNote",
        "position": [2280, 500],
        "typeVersion": 1,
    })

    # -- Error Trigger --
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 900],
        "typeVersion": 1,
    })

    # -- Error Gmail --
    nodes.append({
        "parameters": {
            "operation": "send",
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "SC-01 Trend Discovery FAILED",
            "message": "=SC-01 Trend Discovery failed at {{ $now.toFormat('yyyy-MM-dd HH:mm') }} SAST.\n\nError: {{ $json.execution.error.message }}\n\nWorkflow: {{ $json.execution.url }}",
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 900],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    return nodes


def build_sc01_connections() -> dict:
    """Build connections for SC-01."""
    return {
        "Daily 6AM SAST": {"main": [[{"node": "Search Config", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Search Config", "type": "main", "index": 0}]]},
        "Search Config": {"main": [[
            {"node": "YouTube Search", "type": "main", "index": 0},
            {"node": "Instagram Apify", "type": "main", "index": 0},
            {"node": "LinkedIn Tavily", "type": "main", "index": 0},
            {"node": "Read Existing Trends", "type": "main", "index": 0},
        ]]},
        "YouTube Search": {"main": [[{"node": "YouTube Stats", "type": "main", "index": 0}]]},
        "YouTube Stats": {"main": [[{"node": "Parse YouTube", "type": "main", "index": 0}]]},
        "Instagram Apify": {"main": [[{"node": "Parse Instagram", "type": "main", "index": 0}]]},
        "LinkedIn Tavily": {"main": [[{"node": "Parse LinkedIn", "type": "main", "index": 0}]]},
        "Parse YouTube": {"main": [[{"node": "Merge Platforms", "type": "main", "index": 0}]]},
        "Parse Instagram": {"main": [[{"node": "Merge Platforms", "type": "main", "index": 0}]]},
        "Parse LinkedIn": {"main": [[{"node": "Merge Platforms", "type": "main", "index": 0}]]},
        "Merge Platforms": {"main": [[{"node": "Wait for All", "type": "main", "index": 0}]]},
        "Read Existing Trends": {"main": [[{"node": "Wait for All", "type": "main", "index": 1}]]},
        "Wait for All": {"main": [[{"node": "Dedup and Score", "type": "main", "index": 0}]]},
        "Dedup and Score": {"main": [[{"node": "Write Trending", "type": "main", "index": 0}]]},
        "Write Trending": {"main": [[{"node": "Call SC-02 Extract", "type": "main", "index": 0}]]},
        "Call SC-02 Extract": {"main": [[{"node": "Call SC-03 Adapt", "type": "main", "index": 0}]]},
        "Error Trigger": {"main": [[{"node": "Error Notification", "type": "main", "index": 0}]]},
    }


# ==================================================================
# SC-02: SCRIPT EXTRACTION (Sub-workflow)
# ==================================================================

def build_sc02_nodes() -> list[dict]:
    """Build all nodes for SC-02 Script Extraction."""
    nodes = []

    # -- Execute Workflow Trigger --
    nodes.append({
        "parameters": {"inputSource": "passthrough"},
        "id": uid(),
        "name": "Execute Workflow Trigger",
        "type": "n8n-nodes-base.executeWorkflowTrigger",
        "position": [200, 400],
        "typeVersion": 1.1,
    })

    # -- Read Discovered Trends --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_TRENDING},
            "filterByFormula": "={Status}='Discovered'",
            "returnAll": False,
            "limit": 20,
            "options": {},
        },
        "id": uid(),
        "name": "Read Discovered",
        "type": "n8n-nodes-base.airtable",
        "position": [440, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "executeOnce": True,
    })

    # -- Platform Router --
    nodes.append({
        "parameters": {
            "rules": {
                "values": [
                    {"conditions": {"conditions": [{"id": uid(), "leftValue": "={{ $json.Platform || ($json.fields && $json.fields.Platform) }}", "rightValue": "YouTube", "operator": {"type": "string", "operation": "equals"}}]}},
                    {"conditions": {"conditions": [{"id": uid(), "leftValue": "={{ $json.Platform || ($json.fields && $json.fields.Platform) }}", "rightValue": "Instagram", "operator": {"type": "string", "operation": "equals"}}]}},
                    {"conditions": {"conditions": [{"id": uid(), "leftValue": "={{ $json.Platform || ($json.fields && $json.fields.Platform) }}", "rightValue": "LinkedIn", "operator": {"type": "string", "operation": "equals"}}]}},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Platform Router",
        "type": "n8n-nodes-base.switch",
        "position": [920, 400],
        "typeVersion": 3.2,
    })

    # -- YouTube Captions --
    nodes.append({
        "parameters": {
            "jsCode": """const items = $input.all();
return items.map(i => {
  const item = i.json;
  const fields = item.fields || item;
  const recordId = item.id || '';
  const sourceUrl = fields['Source URL'] || '';
  const url = fields['Source URL'] || '';
  const parts = url.split('/shorts/');
  const videoId = parts.length > 1 ? parts[1].split('?')[0] : '';
  return {
    json: {
      recordId,
      sourceUrl,
      platform: fields.Platform || 'YouTube',
      title: fields.Title || '',
      sourceCreator: fields['Source Creator'] || 'Unknown',
      viewCount: fields['View Count'] || 0,
      likeCount: fields['Like Count'] || 0,
      commentCount: fields['Comment Count'] || 0,
      transcript: fields.Title || 'No transcript available',
      videoId,
    }
  };
});""",
        },
        "id": uid(),
        "name": "YouTube Captions",
        "type": "n8n-nodes-base.code",
        "position": [1200, 200],
        "typeVersion": 2,
    })

    # -- Instagram Text --
    nodes.append({
        "parameters": {
            "jsCode": """const items = $input.all();
return items.map(i => {
  const item = i.json;
  const fields = item.fields || item;
  const recordId = item.id || '';
  const sourceUrl = fields['Source URL'] || '';
  const transcript = fields.Transcript || fields.Title || '';
  return {
    json: {
      recordId,
      sourceUrl,
      platform: fields.Platform || 'Instagram',
      title: fields.Title || '',
      sourceCreator: fields['Source Creator'] || 'Unknown',
      viewCount: fields['View Count'] || 0,
      likeCount: fields['Like Count'] || 0,
      commentCount: fields['Comment Count'] || 0,
      transcript: transcript || 'No caption available',
    }
  };
});""",
        },
        "id": uid(),
        "name": "Instagram Text",
        "type": "n8n-nodes-base.code",
        "position": [1200, 400],
        "typeVersion": 2,
    })

    # -- LinkedIn Text --
    nodes.append({
        "parameters": {
            "jsCode": """const items = $input.all();
return items.map(i => {
  const item = i.json;
  const fields = item.fields || item;
  const recordId = item.id || '';
  const sourceUrl = fields['Source URL'] || '';
  const transcript = fields.Transcript || fields.Title || '';
  return {
    json: {
      recordId,
      sourceUrl,
      platform: fields.Platform || 'LinkedIn',
      title: fields.Title || '',
      sourceCreator: fields['Source Creator'] || 'Unknown',
      viewCount: fields['View Count'] || 0,
      likeCount: fields['Like Count'] || 0,
      commentCount: fields['Comment Count'] || 0,
      transcript: transcript || 'No content available',
    }
  };
});""",
        },
        "id": uid(),
        "name": "LinkedIn Text",
        "type": "n8n-nodes-base.code",
        "position": [1200, 600],
        "typeVersion": 2,
    })

    # -- Merge Extraction --
    nodes.append({
        "parameters": {"mode": "append", "options": {}},
        "id": uid(),
        "name": "Merge Extraction",
        "type": "n8n-nodes-base.merge",
        "position": [1500, 400],
        "typeVersion": 3,
    })

    # -- Build Extraction Prompt (Code node to build prompt safely) --
    nodes.append({
        "parameters": {
            "jsCode": """const items = $input.all();
return items.map(i => {
  const d = i.json;
  const platform = d.platform || 'Unknown';
  const creator = d.sourceCreator || 'Unknown';
  const title = d.title || '';
  const views = d.viewCount || 0;
  const likes = d.likeCount || 0;
  const comments = d.commentCount || 0;
  const transcript = (d.transcript || '').slice(0, 2000);
  const recordId = d.recordId || '';
  const sourceUrl = d.sourceUrl || d['Source URL'] || '';

  const prompt = 'You are a viral content analyst. Analyze this trending social media content and extract the reusable template.\\n\\n' +
    'Platform: ' + platform + '\\n' +
    'Creator: ' + creator + '\\n' +
    'Title: ' + title + '\\n' +
    'Engagement: ' + views + ' views, ' + likes + ' likes, ' + comments + ' comments\\n' +
    'Content: ' + transcript + '\\n\\n' +
    'Extract the structural template. Identify the hook pattern, body structure, and CTA placement.\\n\\n' +
    'Output JSON only (no markdown, no backticks):\\n' +
    '{\"template_pattern\":\"Hook: [pattern] -> Body: [structure] -> CTA: [type]\",' +
    '\"content_category\":\"How-to|Listicle|Quote|Stat-graphic|Reaction|Story|Tutorial\",' +
    '\"virality_factors\":[\"factor1\",\"factor2\"],' +
    '\"video_type_recommendation\":\"Text-on-screen|Quote-card|Stat-graphic|Talking-head-script\",' +
    '\"adaptability_score\":85}';

  return { json: { recordId, sourceUrl, platform, transcript, prompt } };
});""",
        },
        "id": uid(),
        "name": "Build Extraction Prompt",
        "type": "n8n-nodes-base.code",
        "position": [1740, 400],
        "typeVersion": 2,
    })

    # -- AI Template Analysis (simple HTTP call using built prompt) --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ model: 'anthropic/claude-haiku-4-5', max_tokens: 500, temperature: 0.3, messages: [{role: 'user', content: $json.prompt}] }) }}",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "AI Template Analysis",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1980, 400],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Parse AI Response --
    nodes.append({
        "parameters": {
            "jsCode": """const responses = $input.all();
const promptItems = $('Build Extraction Prompt').all();

return responses.map((resp, idx) => {
  const choices = resp.json.choices || [];
  const msg = choices.length > 0 ? choices[0].message || {} : {};
  const content = msg.content || '{}';

  let analysis = {
    template_pattern: 'Unknown',
    content_category: 'How-to',
    virality_factors: [],
    video_type_recommendation: 'Text-on-screen',
    adaptability_score: 50,
  };
  try {
    analysis = JSON.parse(content);
  } catch (e) {
    try {
      const jsonMatch = content.match(/\\{[\\s\\S]*?\\}/);
      if (jsonMatch) analysis = JSON.parse(jsonMatch[0]);
    } catch (e2) {
      // Keep defaults
    }
  }

  const promptData = promptItems[idx] ? promptItems[idx].json : {};
  const recordId = promptData.recordId || '';
  const sourceUrl = promptData.sourceUrl || '';

  // Validate Content Category against allowed singleSelect values
  const validCategories = ['How-to', 'Listicle', 'Quote', 'Stat-graphic', 'Reaction', 'Story', 'Tutorial'];
  let category = analysis.content_category || 'How-to';
  if (!validCategories.includes(category)) {
    category = 'How-to';
  }

  return {
    json: {
      id: recordId,
      'Source URL': sourceUrl,
      Transcript: promptData.transcript || '',
      'Template Pattern': analysis.template_pattern || '',
      'Content Category': category,
      Status: 'Extracted',
    }
  };
});""",
        },
        "id": uid(),
        "name": "Parse AI Response",
        "type": "n8n-nodes-base.code",
        "position": [1980, 400],
        "typeVersion": 2,
    })

    # -- Update Airtable (Extracted) - HTTP Request + upsert by Source URL --
    nodes.append({
        "parameters": {
            "method": "PATCH",
            "url": f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{TABLE_TRENDING}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": f"Bearer {AIRTABLE_API_TOKEN}"},
                    {"name": "Content-Type", "value": "application/json"},
                ],
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={{ JSON.stringify({
  performUpsert: { fieldsToMergeOn: ['Source URL'] },
  records: [{
    fields: {
      'Source URL': $json['Source URL'],
      'Transcript': $json.Transcript,
      'Template Pattern': $json['Template Pattern'],
      'Content Category': $json['Content Category'],
      'Status': 'Extracted'
    }
  }]
}) }}""",
            "options": {"timeout": 15000},
        },
        "id": uid(),
        "name": "Update Extracted",
        "type": "n8n-nodes-base.httpRequest",
        "position": [2220, 400],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # -- Loop back --
    # (The splitInBatches done output connects back, handled in connections)

    return nodes


def build_sc02_connections() -> dict:
    """Build connections for SC-02."""
    return {
        "Execute Workflow Trigger": {"main": [[{"node": "Read Discovered", "type": "main", "index": 0}]]},
        "Read Discovered": {"main": [[{"node": "Platform Router", "type": "main", "index": 0}]]},
        "Platform Router": {"main": [
            [{"node": "YouTube Captions", "type": "main", "index": 0}],
            [{"node": "Instagram Text", "type": "main", "index": 0}],
            [{"node": "LinkedIn Text", "type": "main", "index": 0}],
            [],
        ]},
        "YouTube Captions": {"main": [[{"node": "Merge Extraction", "type": "main", "index": 0}]]},
        "Instagram Text": {"main": [[{"node": "Merge Extraction", "type": "main", "index": 0}]]},
        "LinkedIn Text": {"main": [[{"node": "Merge Extraction", "type": "main", "index": 0}]]},
        "Merge Extraction": {"main": [[{"node": "Build Extraction Prompt", "type": "main", "index": 0}]]},
        "Build Extraction Prompt": {"main": [[{"node": "AI Template Analysis", "type": "main", "index": 0}]]},
        "AI Template Analysis": {"main": [[{"node": "Parse AI Response", "type": "main", "index": 0}]]},
        "Parse AI Response": {"main": [[{"node": "Update Extracted", "type": "main", "index": 0}]]},
        "Update Extracted": {"main": [[]]},
    }


# ==================================================================
# SC-03: BRAND ADAPTATION (Sub-workflow)
# ==================================================================

def build_sc03_nodes() -> list[dict]:
    """Build all nodes for SC-03 Brand Adaptation."""
    nodes = []

    # -- Execute Workflow Trigger --
    nodes.append({
        "parameters": {"inputSource": "passthrough"},
        "id": uid(),
        "name": "Execute Workflow Trigger",
        "type": "n8n-nodes-base.executeWorkflowTrigger",
        "position": [200, 400],
        "typeVersion": 1.1,
    })

    # -- Read Extracted Trends --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_TRENDING},
            "filterByFormula": "={Status}='Extracted'",
            "returnAll": False,
            "limit": 20,
            "options": {},
        },
        "id": uid(),
        "name": "Read Extracted",
        "type": "n8n-nodes-base.airtable",
        "position": [440, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "executeOnce": True,
    })

    # -- Build Adapt Prompt (Code node) --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const items = $input.all();\n"
                "return items.map(i => {\n"
                "  // Airtable node flattens fields to top level in some versions\n"
                "  const fields = i.json.fields || i.json;\n"
                "  const recordId = i.json.id || '';\n"
                "  const platform = fields.Platform || 'Unknown';\n"
                "  const template = fields['Template Pattern'] || 'Unknown';\n"
                "  const category = fields['Content Category'] || 'How-to';\n"
                "  const transcript = (fields.Transcript || '').slice(0, 1000);\n"
                "  const views = fields['View Count'] || 0;\n"
                "  const likes = fields['Like Count'] || 0;\n"
                "  const trendId = fields['Trend ID'] || '';\n"
                "  const sourceUrl = fields['Source URL'] || '';\n"
                "\n"
                "  const prompt = 'Adapt this trending content for AnyVision Media brand.\\n\\n' +\n"
                "    'Brand: AnyVision Media, South African digital marketing & AI automation agency. Voice: Professional, tech-savvy, innovation-focused. SA English. No emojis. Primary color: #FF6D5A.\\n' +\n"
                "    'Content pillars: Journey 40%, Value 35%, Aspiration 25%.\\n\\n' +\n"
                "    'Original platform: ' + platform + '\\n' +\n"
                "    'Template: ' + template + '\\n' +\n"
                "    'Category: ' + category + '\\n' +\n"
                "    'Views: ' + views + ', Likes: ' + likes + '\\n' +\n"
                "    'Transcript: ' + transcript + '\\n\\n' +\n"
                "    'Write for ~30s video. Keep the EXACT structural pattern that made it viral. Output JSON only:\\n' +\n"
                "    '{\"script_text\":\"full script\",\"hook\":\"under 100 chars\",\"cta\":\"call to action\",\"video_type\":\"Text-on-screen|Quote-card|Stat-graphic|Talking-head-script\",\"visual_notes\":\"scene directions\",\"content_pillar\":\"Journey|Value|Aspiration\",\"estimated_duration_sec\":30,\"quality_score\":85}';\n"
                "\n"
                "  return { json: { recordId, trendId, sourceUrl, platform, prompt } };\n"
                "});"
            ),
        },
        "id": uid(),
        "name": "Build Adapt Prompt",
        "type": "n8n-nodes-base.code",
        "position": [680, 400],
        "typeVersion": 2,
    })

    # -- AI Brand Adaptation --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ model: 'anthropic/claude-haiku-4-5', max_tokens: 800, temperature: 0.7, messages: [{role: 'user', content: $json.prompt}] }) }}",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "AI Adapt Script",
        "type": "n8n-nodes-base.httpRequest",
        "position": [920, 400],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Parse Adapt Response + Build Caption Prompt (Code node) --
    nodes.append({
        "parameters": {
            "jsCode": """const responses = $input.all();
const promptItems = $('Build Adapt Prompt').all();

return responses.map((resp, idx) => {
  const choices = resp.json.choices || [];
  const content = choices.length > 0 ? (choices[0].message || {}).content || '{}' : '{}';
  let adapted = {};
  try { adapted = JSON.parse(content); }
  catch (e) {
    try {
      const m = content.match(/\\{[\\s\\S]*?\\}/);
      adapted = m ? JSON.parse(m[0]) : {};
    } catch (e2) {
      adapted = {};
    }
  }

  const pi = promptItems[idx] ? promptItems[idx].json : {};
  const recordId = pi.recordId || '';
  const trendId = pi.trendId || '';
  const sourceUrl = pi.sourceUrl || '';

  const script = (adapted.script_text || '').slice(0, 500);
  const videoType = adapted.video_type || 'Text-on-screen';
  const hook = adapted.hook || '';

  const capPrompt = 'Generate platform-specific captions for AnyVision Media (SA digital marketing agency).\\n\\n' +
    'Script: ' + script + '\\n' +
    'Video type: ' + videoType + '\\n' +
    'Hook: ' + hook + '\\n\\n' +
    'Output JSON only:\\n' +
    '{\"caption_instagram\":\"max 2200 chars with line breaks, end with CTA, 3-5 hashtags inline\",' +
    '\"caption_linkedin\":\"professional, max 1300 chars, end with engaging question\",' +
    '\"caption_youtube\":\"SEO title + description, max 500 chars\",' +
    '\"hashtags\":\"#digitalmarketing #aiautomation #southafrica\",' +
    '\"thumbnail_prompt\":\"Gemini image prompt for bold thumbnail with #FF6D5A accent\"}';

  return {
    json: {
      recordId,
      trendId,
      sourceUrl,
      adapted,
      capPrompt,
    }
  };
});""",
        },
        "id": uid(),
        "name": "Build Caption Prompt",
        "type": "n8n-nodes-base.code",
        "position": [1160, 400],
        "typeVersion": 2,
    })

    # -- AI Captions --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ model: 'anthropic/claude-haiku-4-5', max_tokens: 500, temperature: 0.5, messages: [{role: 'user', content: $json.capPrompt}] }) }}",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "AI Captions",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1400, 400],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Build Adapted Record --
    nodes.append({
        "parameters": {
            "jsCode": """// Parse caption response
const capItems = $input.all();
const buildItems = $('Build Caption Prompt').all();

return capItems.map((capItem, idx) => {
  const capResponse = capItem.json;
  const capChoices = capResponse.choices || [];
  const capContent = capChoices.length > 0 ? (capChoices[0].message || {}).content || '{}' : '{}';
  let captions = {};
  try { captions = JSON.parse(capContent); }
  catch (e) {
    try {
      const m = capContent.match(/\\{[\\s\\S]*?\\}/);
      captions = m ? JSON.parse(m[0]) : {};
    } catch (e2) {
      captions = {};
    }
  }

  // Get the corresponding adapted data from Build Caption Prompt output
  const buildData = buildItems[idx] ? buildItems[idx].json : {};
  const adapted = buildData.adapted || {};
  const trendId = buildData.trendId || 'UNKNOWN';
  const trendRecordId = buildData.recordId || '';
  const sourceUrl = buildData.sourceUrl || '';

  // Determine composition
  const COMP_MAP = {
    'Text-on-screen': 'TextOnScreen',
    'Quote-card': 'QuoteCard',
    'Stat-graphic': 'StatGraphic',
    'Talking-head-script': 'TalkingHeadOverlay',
  };
  const validVideoTypes = Object.keys(COMP_MAP);
  let videoType = adapted.video_type || 'Text-on-screen';
  if (!validVideoTypes.includes(videoType)) {
    videoType = 'Text-on-screen';
  }
  const composition = COMP_MAP[videoType];
  const isTalkingHead = videoType === 'Talking-head-script';

  // Build Remotion props
  const remotionProps = {
    compositionId: composition,
    title: adapted.hook || '',
    script: (adapted.script_text || '').split('\\n').filter(Boolean),
    brandColor: '#FF6D5A',
    brandName: 'AnyVision Media',
    cta: adapted.cta || '',
    aspectRatio: '9:16',
    fps: 30,
    durationSec: adapted.estimated_duration_sec || 30,
    visualNotes: adapted.visual_notes || '',
  };

  return {
    json: {
      id: trendRecordId,
      trendId,
      trendRecordId,
      sourceUrl,
      scriptText: adapted.script_text || '',
      hook: adapted.hook || '',
      cta: adapted.cta || '',
      videoType,
      visualNotes: adapted.visual_notes || '',
      captionInstagram: captions.caption_instagram || '',
      captionLinkedin: captions.caption_linkedin || '',
      captionYoutube: captions.caption_youtube || '',
      hashtags: captions.hashtags || '',
      thumbnailPrompt: captions.thumbnail_prompt || '',
      estimatedDuration: adapted.estimated_duration_sec || 30,
      remotionComposition: composition,
      remotionPropsJson: JSON.stringify(remotionProps),
      qualityScore: adapted.quality_score || 70,
      status: isTalkingHead ? 'Script_Ready' : 'Adapted',
    }
  };
});""",
        },
        "id": uid(),
        "name": "Build Adapted Record",
        "type": "n8n-nodes-base.code",
        "position": [1400, 400],
        "typeVersion": 2,
    })

    # -- Write Adapted Script to Airtable --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_SCRIPTS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Script ID": "={{ 'SCR-' + $now.toFormat('yyyyMMdd-HHmmssSSS') + '-' + $runIndex + '-' + $itemIndex }}",
                    "Source Trend ID": "={{ $json.trendId }}",
                    "Video Type": "={{ $json.videoType }}",
                    "Script Text": "={{ $json.scriptText }}",
                    "Hook": "={{ $json.hook }}",
                    "CTA": "={{ $json.cta }}",
                    "Visual Notes": "={{ $json.visualNotes }}",
                    "Caption Instagram": "={{ $json.captionInstagram }}",
                    "Caption LinkedIn": "={{ $json.captionLinkedin }}",
                    "Caption YouTube": "={{ $json.captionYoutube }}",
                    "Hashtags": "={{ $json.hashtags }}",
                    "Thumbnail Prompt": "={{ $json.thumbnailPrompt }}",
                    "Estimated Duration Sec": "={{ $json.estimatedDuration }}",
                    "Remotion Composition": "={{ $json.remotionComposition }}",
                    "Remotion Props JSON": "={{ $json.remotionPropsJson }}",
                    "Quality Score": "={{ $json.qualityScore }}",
                    "Status": "={{ $json.status }}",
                    "Created At": "={{ $now.toISO() }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write Adapted Script",
        "type": "n8n-nodes-base.airtable",
        "position": [1640, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Update Trend Status - HTTP Request + upsert by Source URL --
    nodes.append({
        "parameters": {
            "method": "PATCH",
            "url": f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{TABLE_TRENDING}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": f"Bearer {AIRTABLE_API_TOKEN}"},
                    {"name": "Content-Type", "value": "application/json"},
                ],
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={{ JSON.stringify({
  performUpsert: { fieldsToMergeOn: ['Source URL'] },
  records: [{
    fields: {
      'Source URL': $json.sourceUrl,
      'Status': 'Adapted'
    }
  }]
}) }}""",
            "options": {"timeout": 15000},
        },
        "id": uid(),
        "name": "Update Trend Adapted",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1880, 400],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    return nodes


def build_sc03_connections() -> dict:
    """Build connections for SC-03."""
    return {
        "Execute Workflow Trigger": {"main": [[{"node": "Read Extracted", "type": "main", "index": 0}]]},
        "Read Extracted": {"main": [[{"node": "Build Adapt Prompt", "type": "main", "index": 0}]]},
        "Build Adapt Prompt": {"main": [[{"node": "AI Adapt Script", "type": "main", "index": 0}]]},
        "AI Adapt Script": {"main": [[{"node": "Build Caption Prompt", "type": "main", "index": 0}]]},
        "Build Caption Prompt": {"main": [[{"node": "AI Captions", "type": "main", "index": 0}]]},
        "AI Captions": {"main": [[{"node": "Build Adapted Record", "type": "main", "index": 0}]]},
        "Build Adapted Record": {"main": [[{"node": "Write Adapted Script", "type": "main", "index": 0}]]},
        "Write Adapted Script": {"main": [[{"node": "Update Trend Adapted", "type": "main", "index": 0}]]},
        "Update Trend Adapted": {"main": [[]]},
    }


# ==================================================================
# SC-04: VIDEO PRODUCTION
# ==================================================================

def build_sc04_nodes() -> list[dict]:
    """Build all nodes for SC-04 Video Production."""
    nodes = []

    # -- Schedule Trigger (Daily 7AM SAST = 5AM UTC) --
    nodes.append({
        "parameters": {"rule": {"interval": [{"triggerAtHour": 5}]}},
        "id": uid(),
        "name": "Daily 7AM SAST",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 400],
        "typeVersion": 1.2,
    })

    # -- Manual Trigger --
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 600],
        "typeVersion": 1,
    })

    # -- Read Adapted Scripts --
    # Cap batch size at 5 per run to avoid overwhelming Railway render server
    # (in-memory job store gets wiped on container restart)
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_SCRIPTS},
            "filterByFormula": "={Status}='Adapted'",
            "returnAll": False,
            "limit": 5,
            "options": {},
        },
        "id": uid(),
        "name": "Read Adapted",
        "type": "n8n-nodes-base.airtable",
        "position": [460, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "executeOnce": True,
    })

    # -- Has Records? --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{"id": uid(), "leftValue": "={{ $json.id }}", "rightValue": "", "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Has Records?",
        "type": "n8n-nodes-base.if",
        "position": [700, 400],
        "typeVersion": 2.2,
    })

    # -- Update Status Rendering (HTTP upsert by Script ID) --
    nodes.append({
        "parameters": {
            "method": "PATCH",
            "url": f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{TABLE_SCRIPTS}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": f"Bearer {AIRTABLE_API_TOKEN}"},
                    {"name": "Content-Type", "value": "application/json"},
                ],
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={{ JSON.stringify({
  performUpsert: { fieldsToMergeOn: ['Script ID'] },
  records: [{
    fields: {
      'Script ID': $json['Script ID'],
      'Status': 'Rendering'
    }
  }]
}) }}""",
            "options": {"timeout": 15000},
        },
        "id": uid(),
        "name": "Status Rendering",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1180, 400],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # -- Call Render Server --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": f"{REMOTION_RENDER_URL}/render",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "x-api-key", "value": os.getenv("RENDER_API_KEY", "dev-key")},
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "bypass-tunnel-reminder", "value": "1"},
                ],
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={{ JSON.stringify({
  compositionId: $('Read Adapted').item.json['Remotion Composition'] || 'TextOnScreen',
  props: JSON.parse($('Read Adapted').item.json['Remotion Props JSON'] || '{}'),
  outputFormat: 'mp4'
}) }}""",
            "options": {"timeout": 120000},
        },
        "id": uid(),
        "name": "Render Video",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1420, 400],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # -- Wait for Render (3 min — Railway is slower than local) --
    nodes.append({
        "parameters": {"amount": 180, "unit": "seconds"},
        "id": uid(),
        "name": "Wait 30s",
        "type": "n8n-nodes-base.wait",
        "position": [1660, 400],
        "typeVersion": 1.1,
    })

    # -- Poll Render Status --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "={{ '" + REMOTION_RENDER_URL + "/render/' + $('Render Video').first().json.jobId }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "x-api-key", "value": os.getenv("RENDER_API_KEY", "dev-key")},
                    {"name": "bypass-tunnel-reminder", "value": "1"},
                ],
            },
            "options": {"timeout": 15000},
        },
        "id": uid(),
        "name": "Poll Render",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1900, 400],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # -- Check Render Complete --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{"id": uid(), "leftValue": "={{ $json.status }}", "rightValue": "complete", "operator": {"type": "string", "operation": "equals"}}],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Render Complete?",
        "type": "n8n-nodes-base.if",
        "position": [2140, 400],
        "typeVersion": 2.2,
    })

    # -- Update Rendered (HTTP upsert by Script ID) --
    nodes.append({
        "parameters": {
            "method": "PATCH",
            "url": f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{TABLE_SCRIPTS}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": f"Bearer {AIRTABLE_API_TOKEN}"},
                    {"name": "Content-Type", "value": "application/json"},
                ],
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={{ JSON.stringify({
  performUpsert: { fieldsToMergeOn: ['Script ID'] },
  records: [{
    fields: {
      'Script ID': $('Read Adapted').item.json['Script ID'],
      'Video URL': $json.videoUrl || '',
      'Thumbnail URL': $json.thumbnailUrl || '',
      'Status': 'Rendered'
    }
  }]
}) }}""",
            "options": {"timeout": 15000},
        },
        "id": uid(),
        "name": "Update Rendered",
        "type": "n8n-nodes-base.httpRequest",
        "position": [2380, 300],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # -- Update Failed (HTTP upsert by Script ID) --
    nodes.append({
        "parameters": {
            "method": "PATCH",
            "url": f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{TABLE_SCRIPTS}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": f"Bearer {AIRTABLE_API_TOKEN}"},
                    {"name": "Content-Type", "value": "application/json"},
                ],
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={{ JSON.stringify({
  performUpsert: { fieldsToMergeOn: ['Script ID'] },
  records: [{
    fields: {
      'Script ID': $('Read Adapted').item.json['Script ID'],
      'Status': 'Failed',
      'Error Message': (typeof $json.error === 'string' ? $json.error : (($json.error && $json.error.message) || JSON.stringify($json.error || {}))).slice(0, 500) || 'Render did not complete'
    }
  }]
}) }}""",
            "options": {"timeout": 15000},
        },
        "id": uid(),
        "name": "Update Failed",
        "type": "n8n-nodes-base.httpRequest",
        "position": [2380, 500],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # -- Log Production --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_PRODUCTION_LOG},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Log ID": "={{ 'LOG-' + $now.toFormat('yyyyMMdd-HHmmss') + '-' + $runIndex }}",
                    "Script ID": "={{ $('Read Adapted').item.json['Script ID'] || '' }}",
                    "Action": "={{ $json.status === 'complete' ? 'Render_Complete' : 'Render_Failed' }}",
                    "Created At": "={{ $now.toISO() }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Production",
        "type": "n8n-nodes-base.airtable",
        "position": [2620, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    return nodes


def build_sc04_connections() -> dict:
    """Build connections for SC-04."""
    return {
        "Daily 7AM SAST": {"main": [[{"node": "Read Adapted", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Read Adapted", "type": "main", "index": 0}]]},
        "Read Adapted": {"main": [[{"node": "Has Records?", "type": "main", "index": 0}]]},
        "Has Records?": {"main": [
            [{"node": "Status Rendering", "type": "main", "index": 0}],
            [],
        ]},
        "Status Rendering": {"main": [[{"node": "Render Video", "type": "main", "index": 0}]]},
        "Render Video": {"main": [[{"node": "Wait 30s", "type": "main", "index": 0}]]},
        "Wait 30s": {"main": [[{"node": "Poll Render", "type": "main", "index": 0}]]},
        "Poll Render": {"main": [[{"node": "Render Complete?", "type": "main", "index": 0}]]},
        "Render Complete?": {"main": [
            [{"node": "Update Rendered", "type": "main", "index": 0}],
            [{"node": "Update Failed", "type": "main", "index": 0}],
        ]},
        "Update Rendered": {"main": [[{"node": "Log Production", "type": "main", "index": 0}]]},
        "Update Failed": {"main": [[{"node": "Log Production", "type": "main", "index": 0}]]},
        "Log Production": {"main": [[]]},
    }


# ==================================================================
# SC-05: DISTRIBUTION
# ==================================================================

def build_sc05_nodes() -> list[dict]:
    """Build all nodes for SC-05 Distribution."""
    nodes = []

    # -- Schedule Trigger (Daily 8AM SAST = 6AM UTC) --
    nodes.append({
        "parameters": {"rule": {"interval": [{"triggerAtHour": 6}]}},
        "id": uid(),
        "name": "Daily 8AM SAST",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 400],
        "typeVersion": 1.2,
    })

    # -- Manual Trigger --
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 600],
        "typeVersion": 1,
    })

    # -- Read Rendered Scripts --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_SCRIPTS},
            "filterByFormula": "={Status}='Rendered'",
            "returnAll": False,
            "limit": 3,
            "options": {},
        },
        "id": uid(),
        "name": "Read Rendered",
        "type": "n8n-nodes-base.airtable",
        "position": [460, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "executeOnce": True,
    })

    # -- Has Records? --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{"id": uid(), "leftValue": "={{ $json.id }}", "rightValue": "", "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Has Records?",
        "type": "n8n-nodes-base.if",
        "position": [700, 400],
        "typeVersion": 2.2,
    })

    # -- Format for Blotato --
    nodes.append({
        "parameters": {
            "jsCode": """const items = $input.all();
return items.map(i => {
  const fields = i.json.fields || i.json;
  const recordId = i.json.id || '';
  return {
    json: {
      recordId,
      videoUrl: fields['Video URL'] || '',
      captionInstagram: fields['Caption Instagram'] || '',
      captionLinkedin: fields['Caption LinkedIn'] || '',
      captionYoutube: fields['Caption YouTube'] || '',
      hashtags: fields.Hashtags || '',
      scriptId: fields['Script ID'] || '',
      hook: fields.Hook || 'AnyVision Media',
    }
  };
});""",
        },
        "id": uid(),
        "name": "Format for Blotato",
        "type": "n8n-nodes-base.code",
        "position": [1180, 400],
        "typeVersion": 2,
    })

    # -- Upload Media to Blotato --
    # Blotato requires media to be uploaded to its own CDN (database.blotato.com)
    # before it can be referenced in Post Create. This 2-step flow is required
    # for Instagram/TikTok/Pinterest/YouTube per Blotato docs.
    nodes.append({
        "parameters": {
            "resource": "media",
            "operation": "upload",
            "useBinaryData": False,
            "mediaUrl": "={{ $json.videoUrl }}",
        },
        "id": uid(),
        "name": "Upload to Blotato",
        "type": "@blotato/n8n-nodes-blotato.blotato",
        "position": [1320, 400],
        "typeVersion": 2,
        "credentials": {"blotatoApi": CRED_BLOTATO},
        "onError": "continueRegularOutput",
    })

    # -- Merge Upload Result with Source Data --
    # Blotato upload returns {url: "https://database.blotato.com/..."}
    # We need to combine this with the original captions from Format for Blotato
    nodes.append({
        "parameters": {
            "jsCode": """const uploadResp = $input.first().json;
const source = $('Format for Blotato').first().json;

// Blotato media upload response has the URL at top level
const blotatoUrl = uploadResp.url || uploadResp.mediaUrl || '';

return [{
  json: {
    ...source,
    blotatoMediaUrl: blotatoUrl,
  }
}];""",
        },
        "id": uid(),
        "name": "Merge Upload Result",
        "type": "n8n-nodes-base.code",
        "position": [1400, 400],
        "typeVersion": 2,
    })

    # -- Platform publish nodes (only include connected accounts) --
    # Account IDs are queried from Blotato /v2/users/me/accounts
    # YouTube is not currently connected in Blotato — skipped until user reconnects

    def _is_connected(platform_key: str) -> bool:
        return BLOTATO_ACCOUNTS[platform_key]["accountId"] != "NOT_CONNECTED"

    # -- Instagram Blotato --
    if _is_connected("instagram"):
        ig = BLOTATO_ACCOUNTS["instagram"]
        nodes.append({
            "parameters": {
                "resource": "post",
                "operation": "create",
                "platform": "instagram",
                "accountId": {"__rl": True, "mode": "list", "value": ig["accountId"]},
                "postContentText": "={{ $json.captionInstagram }}",
                "postContentMediaUrls": "={{ $json.blotatoMediaUrl }}",
                "options": {},
            },
            "id": uid(),
            "name": "Instagram",
            "type": "@blotato/n8n-nodes-blotato.blotato",
            "position": [1560, 200],
            "typeVersion": 2,
            "credentials": {"blotatoApi": CRED_BLOTATO},
            "onError": "continueRegularOutput",
        })

    # -- LinkedIn Blotato --
    if _is_connected("linkedin"):
        li = BLOTATO_ACCOUNTS["linkedin"]
        nodes.append({
            "parameters": {
                "resource": "post",
                "operation": "create",
                "platform": "linkedin",
                "accountId": {"__rl": True, "mode": "list", "value": li["accountId"]},
                "postContentText": "={{ $json.captionLinkedin }}",
                "postContentMediaUrls": "={{ $json.blotatoMediaUrl }}",
                "options": {},
            },
            "id": uid(),
            "name": "LinkedIn",
            "type": "@blotato/n8n-nodes-blotato.blotato",
            "position": [1560, 400],
            "typeVersion": 2,
            "credentials": {"blotatoApi": CRED_BLOTATO},
            "onError": "continueRegularOutput",
        })

    # -- YouTube Blotato --
    if _is_connected("youtube"):
        yt = BLOTATO_ACCOUNTS["youtube"]
        nodes.append({
            "parameters": {
                "resource": "post",
                "operation": "create",
                "platform": "youtube",
                "accountId": {"__rl": True, "mode": "list", "value": yt["accountId"]},
                "postContentText": "={{ $json.captionYoutube }}",
                "postContentMediaUrls": "={{ $json.blotatoMediaUrl }}",
                "postCreateYoutubeOptionTitle": "={{ $json.hook || 'AnyVision Media' }}",
                "postCreateYoutubeOptionPrivacyStatus": "public",
                "postCreateYoutubeOptionShouldNotifySubscribers": True,
                "postCreateYoutubeOptionMadeForKids": False,
                "postCreateYoutubeOptionContainsSyntheticMedia": True,
                "options": {},
            },
            "id": uid(),
            "name": "YouTube",
            "type": "@blotato/n8n-nodes-blotato.blotato",
            "position": [1560, 600],
            "typeVersion": 2,
            "credentials": {"blotatoApi": CRED_BLOTATO},
            "onError": "continueRegularOutput",
        })

    # -- Merge Results --
    nodes.append({
        "parameters": {"mode": "append", "options": {}},
        "id": uid(),
        "name": "Merge Results",
        "type": "n8n-nodes-base.merge",
        "position": [1780, 400],
        "typeVersion": 3,
    })

    # -- Process Results --
    nodes.append({
        "parameters": {
            "jsCode": """const results = $input.all();
const source = $('Format for Blotato').first().json;
const platforms = results.map(r => {
  const platform = r.json?.platform || 'Unknown';
  const success = !r.json?.error;
  return platform + ': ' + (success ? 'OK' : 'FAILED');
}).join(', ');

return [{
  json: {
    recordId: source.recordId,
    scriptId: source.scriptId,
    publishResults: platforms,
  }
}];""",
        },
        "id": uid(),
        "name": "Process Results",
        "type": "n8n-nodes-base.code",
        "position": [2020, 400],
        "typeVersion": 2,
        "executeOnce": True,
    })

    # -- Update Published (HTTP upsert by Script ID) --
    nodes.append({
        "parameters": {
            "method": "PATCH",
            "url": f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{TABLE_SCRIPTS}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": f"Bearer {AIRTABLE_API_TOKEN}"},
                    {"name": "Content-Type", "value": "application/json"},
                ],
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={{ JSON.stringify({
  performUpsert: { fieldsToMergeOn: ['Script ID'] },
  records: [{
    fields: {
      'Script ID': $json.scriptId,
      'Status': 'Published',
      'Published At': $now.toISO()
    }
  }]
}) }}""",
            "options": {"timeout": 15000},
        },
        "id": uid(),
        "name": "Update Published",
        "type": "n8n-nodes-base.httpRequest",
        "position": [2260, 400],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "executeOnce": True,
    })

    # -- Log Distribution --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_PRODUCTION_LOG},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Log ID": "={{ 'LOG-' + $now.toFormat('yyyyMMdd-HHmmss') + '-dist-' + $runIndex }}",
                    "Script ID": "={{ $json.scriptId }}",
                    "Action": "Publish_Success",
                    "Response": "={{ $json.publishResults }}",
                    "Created At": "={{ $now.toISO() }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Distribution",
        "type": "n8n-nodes-base.airtable",
        "position": [2500, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "executeOnce": True,
    })

    return nodes


def build_sc05_connections() -> dict:
    """Build connections for SC-05 — dynamically includes only connected platforms."""
    connected_platforms = [
        ("instagram", "Instagram"),
        ("linkedin", "LinkedIn"),
        ("youtube", "YouTube"),
    ]
    platform_targets = []
    for key, name in connected_platforms:
        if BLOTATO_ACCOUNTS[key]["accountId"] != "NOT_CONNECTED":
            platform_targets.append({"node": name, "type": "main", "index": 0})

    base_connections = {
        "Daily 8AM SAST": {"main": [[{"node": "Read Rendered", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Read Rendered", "type": "main", "index": 0}]]},
        "Read Rendered": {"main": [[{"node": "Has Records?", "type": "main", "index": 0}]]},
        "Has Records?": {"main": [
            [{"node": "Format for Blotato", "type": "main", "index": 0}],
            [],
        ]},
        "Format for Blotato": {"main": [[{"node": "Upload to Blotato", "type": "main", "index": 0}]]},
        "Upload to Blotato": {"main": [[{"node": "Merge Upload Result", "type": "main", "index": 0}]]},
        "Merge Upload Result": {"main": [platform_targets]},
        "Merge Results": {"main": [[{"node": "Process Results", "type": "main", "index": 0}]]},
        "Process Results": {"main": [[{"node": "Update Published", "type": "main", "index": 0}]]},
        "Update Published": {"main": [[{"node": "Log Distribution", "type": "main", "index": 0}]]},
        "Log Distribution": {"main": [[]]},
    }

    # Add connections from each connected platform to Merge Results
    for key, name in connected_platforms:
        if BLOTATO_ACCOUNTS[key]["accountId"] != "NOT_CONNECTED":
            base_connections[name] = {"main": [[{"node": "Merge Results", "type": "main", "index": 0}]]}

    return base_connections


# ==================================================================
# WORKFLOW DEFINITIONS
# ==================================================================

WORKFLOW_DEFS = {
    "sc01": {
        "name": "Social Content - Trend Discovery (SC-01)",
        "build_nodes": build_sc01_nodes,
        "build_connections": build_sc01_connections,
    },
    "sc02": {
        "name": "Social Content - Script Extraction (SC-02)",
        "build_nodes": build_sc02_nodes,
        "build_connections": build_sc02_connections,
    },
    "sc03": {
        "name": "Social Content - Brand Adaptation (SC-03)",
        "build_nodes": build_sc03_nodes,
        "build_connections": build_sc03_connections,
    },
    "sc04": {
        "name": "Social Content - Video Production (SC-04)",
        "build_nodes": build_sc04_nodes,
        "build_connections": build_sc04_connections,
    },
    "sc05": {
        "name": "Social Content - Distribution (SC-05)",
        "build_nodes": build_sc05_nodes,
        "build_connections": build_sc05_connections,
    },
}

WORKFLOW_FILENAMES = {
    "sc01": "sc01_trend_discovery.json",
    "sc02": "sc02_script_extraction.json",
    "sc03": "sc03_brand_adaptation.json",
    "sc04": "sc04_video_production.json",
    "sc05": "sc05_distribution.json",
}


# ==================================================================
# BUILD / DEPLOY / ACTIVATE
# ==================================================================

def build_workflow(wf_id: str) -> dict:
    """Assemble a complete workflow JSON."""
    if wf_id not in WORKFLOW_DEFS:
        raise ValueError(f"Unknown workflow: {wf_id}. Valid: {', '.join(WORKFLOW_DEFS.keys())}")

    wf_def = WORKFLOW_DEFS[wf_id]
    nodes = wf_def["build_nodes"]()
    connections = wf_def["build_connections"]()

    settings = {
        "executionOrder": "v1",
        "saveManualExecutions": True,
        "callerPolicy": "workflowsFromSameOwner",
    }

    return {
        "name": wf_def["name"],
        "nodes": nodes,
        "connections": connections,
        "settings": settings,
        "staticData": None,
        "meta": {"templateCredsSetupCompleted": True},
        "pinData": {},
        "tags": [],
    }


def save_workflow(wf_id: str, workflow: dict) -> Path:
    """Save workflow JSON to file."""
    output_dir = Path(__file__).parent.parent / "workflows" / "social-content-dept"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / WORKFLOW_FILENAMES[wf_id]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)

    return output_path


def print_workflow_stats(wf_id: str, workflow: dict) -> None:
    """Print workflow statistics."""
    all_nodes = workflow["nodes"]
    func_nodes = [n for n in all_nodes if n["type"] != "n8n-nodes-base.stickyNote"]
    note_nodes = [n for n in all_nodes if n["type"] == "n8n-nodes-base.stickyNote"]
    conn_count = len(workflow["connections"])

    print(f"  Name: {workflow['name']}")
    print(f"  Nodes: {len(func_nodes)} functional + {len(note_nodes)} sticky notes")
    print(f"  Connections: {conn_count}")


def main() -> None:
    args = sys.argv[1:]
    action = args[0] if args else "build"
    target = args[1] if len(args) > 1 else "all"

    print("=" * 60)
    print("SOCIAL CONTENT TREND REPLICATION - WORKFLOW BUILDER")
    print("=" * 60)

    # Determine which workflows to build
    valid_wfs = list(WORKFLOW_DEFS.keys())
    if target == "all":
        workflow_ids = valid_wfs
    elif target in valid_wfs:
        workflow_ids = [target]
    else:
        print(f"ERROR: Unknown target '{target}'. Use: all, {', '.join(valid_wfs)}")
        sys.exit(1)

    # Check Airtable config
    if "REPLACE" in TABLE_TRENDING:
        print()
        print("WARNING: Airtable IDs not configured!")
        print("  Run: python tools/setup_social_content_airtable.py")
        print("  Then set SC_TABLE_TRENDING, SC_TABLE_SCRIPTS, SC_TABLE_PRODUCTION_LOG in .env")
        print()
        if action in ("deploy", "activate"):
            print("Cannot deploy with placeholder IDs. Aborting.")
            sys.exit(1)
        print("Continuing build with placeholder IDs (for preview only)...")
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

                # Check if workflow already exists (by name)
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

                if action == "activate" and deployed_ids.get(wf_id):
                    print(f"  Activating {wf_id}...")
                    client.activate_workflow(deployed_ids[wf_id])
                    print("  Activated!")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print()
    print("Workflows:")
    for wf_id in workflow_ids:
        wf_label = WORKFLOW_DEFS[wf_id]["name"]
        print(f"  {wf_id}: {wf_label}")

    print()
    print("Next steps:")
    print("  1. Run: python tools/setup_social_content_airtable.py --seed")
    print("  2. Set table IDs in .env (SC_TABLE_TRENDING, SC_TABLE_SCRIPTS, SC_TABLE_PRODUCTION_LOG)")
    print("  3. Set APIFY_API_TOKEN and YOUTUBE_API_KEY in .env")
    print("  4. Deploy Remotion render server and set REMOTION_RENDER_URL")
    print("  5. Test SC-01 with Manual Trigger")
    print("  6. Verify data in Airtable tables")
    print("  7. Test SC-04 + SC-05 with Manual Trigger")
    print("  8. Once verified, activate schedule triggers")


if __name__ == "__main__":
    main()
