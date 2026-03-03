"""
Marketing Department - Workflow Builder & Deployer

Builds all Marketing Department workflows as n8n workflow JSON files,
and optionally deploys them to the n8n instance.

Workflows:
    WF-01: Intelligence & Research (weekly competitor/RSS monitoring + AI analysis)
    WF-02: Strategy & Campaign Planning (weekly content calendar generation)
    WF-03: Content Production (daily AI content generation)
    WF-04: Distribution (daily multi-platform publishing via Blotato)

Usage:
    python tools/deploy_marketing_dept.py build              # Build all workflow JSONs
    python tools/deploy_marketing_dept.py build wf01         # Build WF-01 only
    python tools/deploy_marketing_dept.py build wf02         # Build WF-02 only
    python tools/deploy_marketing_dept.py build wf03         # Build WF-03 only
    python tools/deploy_marketing_dept.py build wf04         # Build WF-04 only
    python tools/deploy_marketing_dept.py deploy             # Build + Deploy (inactive)
    python tools/deploy_marketing_dept.py activate           # Build + Deploy + Activate
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

# ── Credential Constants ──────────────────────────────────────
# Same IDs used across all tools in this project

CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_BLOTATO = {"id": "hhRiqZrWNlqvmYZR", "name": "Blotato AVM"}

# Airtable credential — uses the existing token API credential
# If you created a new credential for the marketing base, update this ID
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable account"}

# ── Airtable IDs ──────────────────────────────────────────────
# UPDATE THESE after running setup_marketing_airtable.py

AIRTABLE_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "REPLACE_WITH_BASE_ID")
TABLE_CONTENT_CALENDAR = os.getenv("MARKETING_TABLE_CONTENT_CALENDAR", "REPLACE_WITH_TABLE_ID")
TABLE_CONTENT = os.getenv("MARKETING_TABLE_CONTENT", "REPLACE_WITH_TABLE_ID")
TABLE_PUBLISH_QUEUE = os.getenv("MARKETING_TABLE_PUBLISH_QUEUE", "REPLACE_WITH_TABLE_ID")
TABLE_DISTRIBUTION_LOG = os.getenv("MARKETING_TABLE_DISTRIBUTION_LOG", "REPLACE_WITH_TABLE_ID")
TABLE_SYSTEM_STATE = os.getenv("MARKETING_TABLE_SYSTEM_STATE", "REPLACE_WITH_TABLE_ID")
TABLE_RESEARCH_CONFIG = os.getenv("MARKETING_TABLE_RESEARCH_CONFIG", "REPLACE_WITH_TABLE_ID")
TABLE_RESEARCH_INSIGHTS = os.getenv("MARKETING_TABLE_RESEARCH_INSIGHTS", "REPLACE_WITH_TABLE_ID")

# ── Blotato Account IDs ──────────────────────────────────────
# These are from the existing "1 Post Everywhere" workflow
# Update if your Blotato accounts differ

BLOTATO_ACCOUNTS = {
    "tiktok": {"accountId": "27801", "name": "TikTok"},
    "instagram": {"accountId": "29194", "name": "Instagram"},
    "facebook": {"accountId": "369", "subAccountId": "161711670360847", "name": "Facebook"},
    "linkedin": {"accountId": "4590", "name": "LinkedIn"},
    "twitter": {"accountId": "38", "name": "Twitter"},
    "youtube": {"accountId": "111", "name": "YouTube"},
    "threads": {"accountId": "3", "name": "Threads"},
    "bluesky": {"accountId": "8", "name": "Bluesky"},
    "pinterest": {"accountId": "358", "name": "Pinterest"},
}

# ── AI Prompts ────────────────────────────────────────────────

SOCIAL_POST_SYSTEM_PROMPT = """You are the Social Media Content Writer for AnyVision Media, a digital media and AI automation agency based in South Africa.

## Brand Voice
- Professional but approachable
- Tech-savvy, innovation-focused
- Confident without being arrogant
- Use clear, jargon-free language when possible
- Always provide actionable value

## Company Context
- Services: AI workflow automation, web development, social media management, real estate tech solutions
- Owner: Ian Immelman
- Target audience: Small to medium businesses looking to automate and scale
- Brand color: #FF6D5A

## Platform-Specific Rules
- LinkedIn: Professional insights, thought leadership, 150-250 words. End with a question for engagement.
- Twitter: Punchy, max 280 chars total (including hashtags). Use 1-2 hashtags max.
- Instagram: Visual-first caption, 100-200 words. Use 5-10 relevant hashtags at the end.
- TikTok: Script-style, conversational, hook in first line. 50-100 words.
- Facebook: Storytelling format, 100-200 words. Encourage comments.
- YouTube: Community post style, 50-150 words.
- Threads: Conversational, 50-100 words. No hashtags.
- Bluesky: Similar to Twitter, max 250 chars total. 1-2 hashtags max.
- Pinterest: SEO-rich description, 100-200 words with keywords.

## Output Format (JSON only, no markdown, no backticks):
{
  "hook": "The attention-grabbing first line",
  "body": "The main content after the hook",
  "cta": "Call to action sentence",
  "hashtags": "#hashtag1 #hashtag2 #hashtag3"
}

## Rules
- Never use excessive exclamation marks (1 max per post)
- Never use emojis excessively (1-2 max per post)
- Always include a clear call-to-action
- Make the hook specific and curiosity-driven, not generic
- Reference real pain points of the target audience
- The hook should work standalone as the first thing people see"""

HOOK_OPTIMIZER_PROMPT = """You are a social media hook optimization expert. Given a hook and the post topic, generate 3 alternative hooks that are more engaging.

## Rules
- Each hook must be different in approach (question, statistic, bold claim)
- Keep each hook under 100 characters
- Score each 1-10 for engagement potential
- Select the best one

## Output Format (JSON only, no markdown, no backticks):
{
  "variations": ["hook 1", "hook 2", "hook 3"],
  "scores": [8, 7, 9],
  "best_index": 2
}"""


TREND_ANALYSIS_SYSTEM_PROMPT = """You are a Market Intelligence Analyst for AnyVision Media, a digital media and AI automation agency in South Africa.

## Your Task
Analyze the provided competitor content and RSS feed articles to identify actionable trends and content opportunities.

## Company Context
- Services: AI workflow automation, web development, social media management, real estate tech
- Target audience: Small to medium businesses looking to automate and scale
- Competitors: Zapier, Make.com, n8n (platform provider)

## Analysis Framework
1. **Trends**: What themes or topics are trending in the automation/AI space?
2. **Competitor Moves**: What are competitors focusing on? New features, positioning shifts?
3. **Content Opportunities**: What gaps exist that AnyVision Media can fill with unique content?

## Output Format (JSON only, no markdown, no backticks):
{
  "trends": [
    {"topic": "trend description", "relevance": 8, "source": "where you found it"}
  ],
  "competitor_moves": [
    {"competitor": "name", "move": "what they did", "our_angle": "how we can respond"}
  ],
  "opportunities": [
    {"topic": "content topic idea", "angle": "unique AnyVision angle", "priority": "high/medium/low", "platforms": ["LinkedIn", "Twitter"]}
  ],
  "summary": "2-3 sentence executive summary of the intelligence landscape this week"
}

## Rules
- Focus on actionable insights, not generic observations
- Prioritize topics relevant to SMBs and automation
- Identify at least 3 content opportunities
- Score relevance 1-10 (10 = directly impacts our business)"""

STRATEGY_SYSTEM_PROMPT = """You are the Content Strategist for AnyVision Media, a digital media and AI automation agency in South Africa.

## Your Task
Create a 7-day social media content calendar based on the provided research insights and performance data.

## Company Context
- Services: AI workflow automation, web development, social media management, real estate tech
- Owner: Ian Immelman
- Target audience: Small to medium businesses looking to automate and scale
- Brand color: #FF6D5A

## Content Mix Guidelines
- Educational (40%): Tips, how-tos, industry insights
- Engagement (30%): Questions, polls, behind-the-scenes, stories
- Promotional (30%): Case studies, service highlights, testimonials

## Platform Strategy
- LinkedIn: Thought leadership, case studies (Mon, Wed, Fri)
- Twitter/X: Quick tips, industry commentary (daily)
- Instagram: Visual content, carousels, stories (Tue, Thu, Sat)
- TikTok: Quick tips, trending hooks (Wed, Fri, Sun)
- Facebook: Community engagement, stories (Mon, Thu)
- YouTube: Community posts only for now (Wed)
- Threads: Conversational takes (Tue, Sat)
- Bluesky: Mirror Twitter strategy (daily)
- Pinterest: Evergreen how-to content (Mon, Thu)

## Output Format (JSON array only, no markdown, no backticks):
[
  {
    "date": "YYYY-MM-DD",
    "topic": "Specific, actionable topic title",
    "content_type": "social_post",
    "platforms": ["LinkedIn", "Twitter", "Instagram"],
    "brief": "2-3 sentence brief explaining the angle, key points to hit, and target audience segment",
    "campaign": "General Brand Awareness"
  }
]

## Rules
- Each day MUST have a unique angle — no repeated topics within the week
- Reference specific trends or competitor gaps from the research when possible
- Not every post goes to all 9 platforms — be strategic about platform selection
- Avoid topics already covered in the performance data (last 7 days)
- If research insights mention high-relevance trends, prioritize those
- Include a mix of evergreen and timely content
- Every brief must be specific enough for an AI writer to produce the content without further context"""


def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ══════════════════════════════════════════════════════════════
# COMBINED WORKFLOW HELPERS
# ══════════════════════════════════════════════════════════════

def rename_in_value(value, rename_map):
    """Recursively replace $('OldName') with $('NewName') in all strings."""
    if isinstance(value, str):
        for old_name, new_name in rename_map.items():
            value = value.replace(f"$('{old_name}')", f"$('{new_name}')")
        return value
    if isinstance(value, dict):
        return {k: rename_in_value(v, rename_map) for k, v in value.items()}
    if isinstance(value, list):
        return [rename_in_value(item, rename_map) for item in value]
    return value


def apply_offset(nodes, x_offset=0, y_offset=0):
    """Shift all node positions by the given offsets."""
    for node in nodes:
        if "position" in node:
            pos = node["position"]
            node["position"] = [pos[0] + x_offset, pos[1] + y_offset]
    return nodes


def make_separator_note(content, y_pos, note_id):
    """Create a large separator sticky note."""
    return {
        "parameters": {
            "content": content,
            "width": 3600,
            "height": 120,
        },
        "id": note_id,
        "name": f"Separator {note_id[:8]}",
        "type": "n8n-nodes-base.stickyNote",
        "position": [0, y_pos],
        "typeVersion": 1,
    }


def load_wf04_from_json():
    """Load WF-04 nodes and connections from the hand-crafted JSON file."""
    json_path = Path(__file__).parent.parent / "workflows" / "marketing-dept" / "wf04_distribution.json"
    with open(json_path, "r", encoding="utf-8") as f:
        wf = json.load(f)
    return wf.get("nodes", []), wf.get("connections", {})


def _process_workflow_for_combined(nodes, connections, prefix, rename_map, x_offset=0, y_offset=0):
    """Rename conflicting nodes, update refs, offset positions, strip error nodes."""
    import copy
    nodes = copy.deepcopy(nodes)
    connections = copy.deepcopy(connections)

    # Remove Error Trigger + Error Notification nodes
    nodes = [n for n in nodes if n.get("name") not in ("Error Trigger", "Error Notification")]

    # Rename conflicting node names in node definitions
    for node in nodes:
        old_name = node.get("name")
        if old_name in rename_map:
            node["name"] = rename_map[old_name]
        # Prefix sticky note names to avoid duplicates across workflows
        elif node.get("type") == "n8n-nodes-base.stickyNote" and old_name:
            node["name"] = f"{prefix} {old_name}"

    # Update $() references in all node parameters
    for node in nodes:
        if "parameters" in node:
            node["parameters"] = rename_in_value(node["parameters"], rename_map)

    # Apply position offsets
    apply_offset(nodes, x_offset, y_offset)

    # Rename connection keys and values
    new_connections = {}
    for source_name, conn_data in connections.items():
        if source_name in ("Error Trigger", "Error Notification"):
            continue
        new_source = rename_map.get(source_name, source_name)
        new_conn = copy.deepcopy(conn_data)
        # Rename target node names in connection outputs
        if "main" in new_conn:
            for output_list in new_conn["main"]:
                for target in output_list:
                    old_target = target.get("node", "")
                    if old_target in ("Error Trigger", "Error Notification"):
                        continue
                    target["node"] = rename_map.get(old_target, old_target)
        new_connections[new_source] = new_conn

    return nodes, new_connections


def build_combined_nodes():
    """Build all nodes for the combined 4-in-1 workflow."""
    all_nodes = []

    # Define rename maps per workflow (only conflicting names)
    wf_configs = [
        {
            "prefix": "WF-01",
            "nodes_fn": lambda: build_wf01_nodes(),
            "rename": {
                "Manual Trigger": "WF-01 Manual Trigger",
                "System Config": "WF-01 System Config",
            },
            "x_offset": 0, "y_offset": 0,
            "separator": "# WF-01: Intelligence & Research\n**Schedule:** Monday 7:30 AM SAST | **Trigger:** Weekly Monday 7:30AM\n**Purpose:** Scrapes competitors, reads RSS feeds, runs AI trend analysis, stores insights.",
            "sep_y": 0,
        },
        {
            "prefix": "WF-02",
            "nodes_fn": lambda: build_wf02_nodes(),
            "rename": {
                "Manual Trigger": "WF-02 Manual Trigger",
                "System Config": "WF-02 System Config",
            },
            "x_offset": 0, "y_offset": 1200,
            "separator": "# WF-02: Strategy & Campaign Planning\n**Schedule:** Monday 8:30 AM SAST | **Trigger:** Weekly Monday 8:30AM\n**Purpose:** Reads research insights, generates weekly content calendar via AI strategist.",
            "sep_y": 1200,
        },
        {
            "prefix": "WF-03",
            "nodes_fn": lambda: build_wf03_nodes(),
            "rename": {
                "Manual Trigger": "WF-03 Manual Trigger",
                "System Config": "WF-03 System Config",
            },
            "x_offset": 0, "y_offset": 2400,
            "separator": "# WF-03: Content Production\n**Schedule:** Daily 9:00 AM SAST | **Trigger:** Daily 9AM Trigger\n**Purpose:** Reads content calendar, generates social posts via AI, quality gates, queues for publishing.",
            "sep_y": 2400,
        },
        {
            "prefix": "WF-04",
            "nodes_fn": None,  # loaded from JSON
            "rename": {
                "Manual Trigger": "WF-04 Manual Trigger",
            },
            "x_offset": 1700, "y_offset": 3800,
            "separator": "# WF-04: Distribution & Publishing\n**Schedule:** Daily 10:00 AM SAST | **Trigger:** Daily 10AM Trigger\n**Purpose:** Reads publish queue, posts to 9 platforms via Blotato, logs results.",
            "sep_y": 3600,
        },
    ]

    all_connections = {}

    for cfg in wf_configs:
        # Get nodes and connections
        if cfg["nodes_fn"] is None:
            nodes, connections = load_wf04_from_json()
        else:
            nodes = cfg["nodes_fn"]()
            # Get connections from the matching builder
            if cfg["prefix"] == "WF-01":
                connections = build_wf01_connections()
            elif cfg["prefix"] == "WF-02":
                connections = build_wf02_connections()
            elif cfg["prefix"] == "WF-03":
                connections = build_wf03_connections()

        # Process: rename, offset, strip error nodes
        nodes, connections = _process_workflow_for_combined(
            nodes, connections, cfg["prefix"], cfg["rename"],
            cfg["x_offset"], cfg["y_offset"],
        )

        all_nodes.extend(nodes)
        all_connections.update(connections)

        # Add separator note
        all_nodes.append(make_separator_note(cfg["separator"], cfg["sep_y"], uid()))

    # Add shared Error Trigger + Error Notification at the bottom
    all_nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 5500],
        "typeVersion": 1,
    })
    all_nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "MARKETING ERROR - {{ $json.workflow.name }}",
            "message": (
                "=<h2>Marketing Department Error</h2>\n"
                "<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n"
                "<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n"
                "<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n"
                "<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>"
            ),
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 5500],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # Add error separator note
    all_nodes.append(make_separator_note(
        "# Shared Error Handler\nCatches errors from ALL workflow sections above. "
        "Email includes the failing node name for quick identification.",
        5380, uid(),
    ))

    return all_nodes, all_connections


def build_combined_connections():
    """Build connections for the combined workflow (called by build_combined_nodes)."""
    # This is a no-op — build_combined_nodes returns both nodes AND connections.
    # The build_workflow function handles this special case.
    return {}


# ══════════════════════════════════════════════════════════════
# WF-01: INTELLIGENCE & RESEARCH
# ══════════════════════════════════════════════════════════════

def build_wf01_nodes():
    """Build all nodes for the Intelligence & Research workflow."""
    nodes = []

    # ── Triggers ──

    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "30 7 * * 1"}]
            }
        },
        "id": uid(),
        "name": "Weekly Monday 7:30AM",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 400],
        "typeVersion": 1.2,
    })

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 600],
        "typeVersion": 1,
    })

    # ── System Config ──

    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "todayDate", "value": "={{ $now.format('yyyy-MM-dd') }}", "type": "string"},
                    {"id": uid(), "name": "weekNumber", "value": "={{ $now.format('yyyy') + '-W' + $now.format('WW') }}", "type": "string"},
                    {"id": uid(), "name": "aiModel", "value": "anthropic/claude-sonnet-4-20250514", "type": "string"},
                    {"id": uid(), "name": "companyName", "value": "AnyVision Media", "type": "string"},
                ]
            },
        },
        "id": uid(),
        "name": "System Config",
        "type": "n8n-nodes-base.set",
        "position": [440, 500],
        "typeVersion": 3.4,
    })

    # ── Read Research Config ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_RESEARCH_CONFIG},
            "filterByFormula": "=({Active} = TRUE())",
        },
        "id": uid(),
        "name": "Read Research Config",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 500],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── Gather Intelligence (single node: scrape + RSS + merge) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const items = $input.all();\n"
                "const crypto = require('crypto');\n"
                "\n"
                "// ── 1. Categorize sources ──\n"
                "const competitors = items.filter(i => i.json.Type === 'competitor').map(c => ({ key: c.json.Key, url: c.json.URL, label: c.json.Label }));\n"
                "const rssFeeds = items.filter(i => i.json.Type === 'rss_feed').map(r => ({ key: r.json.Key, url: r.json.URL, label: r.json.Label }));\n"
                "const keywords = items.filter(i => i.json.Type === 'keyword').map(k => ({ key: k.json.Key, label: k.json.Label }));\n"
                "\n"
                "// ── 2. Scrape competitors ──\n"
                "const competitorResults = [];\n"
                "for (const comp of competitors) {\n"
                "  try {\n"
                "    const response = await this.helpers.httpRequest({\n"
                "      method: 'GET',\n"
                "      url: comp.url,\n"
                "      timeout: 10000,\n"
                "      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; AnyVisionBot/1.0)' },\n"
                "      returnFullResponse: true\n"
                "    });\n"
                "    const html = typeof response === 'string' ? response : (response.body || '');\n"
                "    const newHash = crypto.createHash('sha256').update(html).digest('hex');\n"
                "    const text = html\n"
                "      .replace(/<script[^>]*>[\\s\\S]*?<\\/script>/gi, '')\n"
                "      .replace(/<style[^>]*>[\\s\\S]*?<\\/style>/gi, '')\n"
                "      .replace(/<[^>]+>/g, ' ')\n"
                "      .replace(/\\s+/g, ' ')\n"
                "      .trim()\n"
                "      .substring(0, 3000);\n"
                "    competitorResults.push({ source: comp.label, url: comp.url, type: 'competitor', content: text, hash: newHash, hashKey: `content_hash_${comp.key}`, success: true });\n"
                "  } catch(e) {\n"
                "    competitorResults.push({ source: comp.label, url: comp.url, type: 'competitor', content: `Failed to scrape: ${e.message}`, hash: '', hashKey: `content_hash_${comp.key}`, success: false });\n"
                "  }\n"
                "  await new Promise(r => setTimeout(r, 2000));\n"
                "}\n"
                "\n"
                "// ── 3. Fetch RSS feeds ──\n"
                "const rssResults = [];\n"
                "for (const feed of rssFeeds) {\n"
                "  try {\n"
                "    const xml = await this.helpers.httpRequest({\n"
                "      method: 'GET',\n"
                "      url: feed.url,\n"
                "      timeout: 10000,\n"
                "      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; AnyVisionBot/1.0)' }\n"
                "    });\n"
                "    const itemRegex = /<item[^>]*>([\\s\\S]*?)<\\/item>/gi;\n"
                "    const titleRegex = /<title[^>]*>(?:<!\\[CDATA\\[)?(.*?)(?:\\]\\]>)?<\\/title>/i;\n"
                "    const linkRegex = /<link[^>]*>(?:<!\\[CDATA\\[)?(.*?)(?:\\]\\]>)?<\\/link>/i;\n"
                "    const descRegex = /<description[^>]*>(?:<!\\[CDATA\\[)?(.*?)(?:\\]\\]>)?<\\/description>/i;\n"
                "    const dateRegex = /<pubDate[^>]*>(.*?)<\\/pubDate>/i;\n"
                "    const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);\n"
                "    let match;\n"
                "    let itemCount = 0;\n"
                "    while ((match = itemRegex.exec(xml)) !== null && itemCount < 10) {\n"
                "      const itemXml = match[1];\n"
                "      const title = (titleRegex.exec(itemXml) || [])[1] || '';\n"
                "      const link = (linkRegex.exec(itemXml) || [])[1] || '';\n"
                "      const desc = (descRegex.exec(itemXml) || [])[1] || '';\n"
                "      const dateStr = (dateRegex.exec(itemXml) || [])[1] || '';\n"
                "      const pubDate = dateStr ? new Date(dateStr) : null;\n"
                "      if (pubDate && pubDate < sevenDaysAgo) continue;\n"
                "      const cleanDesc = desc.replace(/<[^>]+>/g, '').trim().substring(0, 500);\n"
                "      rssResults.push({ source: feed.label, url: link, type: 'rss', title: title.trim(), content: cleanDesc, date: dateStr, success: true });\n"
                "      itemCount++;\n"
                "    }\n"
                "  } catch(e) {\n"
                "    rssResults.push({ source: feed.label, url: feed.url, type: 'rss', title: 'Failed to fetch', content: e.message, date: '', success: false });\n"
                "  }\n"
                "  await new Promise(r => setTimeout(r, 1000));\n"
                "}\n"
                "\n"
                "// ── 4. Build AI input ──\n"
                "let aiInput = 'COMPETITOR INTELLIGENCE:\\n';\n"
                "for (const c of competitorResults) {\n"
                "  if (c.success) aiInput += `\\n--- ${c.source} (${c.url}) ---\\n${c.content}\\n`;\n"
                "}\n"
                "aiInput += '\\n\\nRSS FEED ARTICLES (Last 7 Days):\\n';\n"
                "for (const r of rssResults) {\n"
                "  if (r.success) aiInput += `\\n- [${r.source}] ${r.title}: ${r.content}\\n`;\n"
                "}\n"
                "aiInput += '\\n\\nTARGET KEYWORDS: ' + keywords.map(k => k.label).join(', ');\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    competitors: competitorResults,\n"
                "    rssArticles: rssResults,\n"
                "    keywords: keywords,\n"
                "    totalSources: competitorResults.length + rssResults.length,\n"
                "    aiInput: aiInput.substring(0, 8000),\n"
                "    hashUpdates: competitorResults.filter(c => c.success).map(c => ({ key: c.hashKey, hash: c.hash }))\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Gather Intelligence",
        "type": "n8n-nodes-base.code",
        "position": [920, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # ── AI Trend Analysis ──

    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={\n"
                "  \"model\": \"{{ $('System Config').item.json.aiModel }}\",\n"
                "  \"max_tokens\": 1500,\n"
                "  \"temperature\": 0.5,\n"
                "  \"messages\": [\n"
                "    {\n"
                "      \"role\": \"system\",\n"
                f"      \"content\": {json.dumps(TREND_ANALYSIS_SYSTEM_PROMPT)}\n"
                "    },\n"
                "    {\n"
                "      \"role\": \"user\",\n"
                "      \"content\": {{ JSON.stringify($json.aiInput) }}\n"
                "    }\n"
                "  ]\n"
                "}",
            "options": {"timeout": 60000},
        },
        "id": uid(),
        "name": "AI Trend Analysis",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1740, 500],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 3000,
    })

    # ── Parse AI Response ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const mergedData = $('Gather Intelligence').first().json;\n"
                "const weekNumber = $('System Config').first().json.weekNumber;\n"
                "const todayDate = $('System Config').first().json.todayDate;\n"
                "\n"
                "let analysis;\n"
                "try {\n"
                "  const content = input.choices[0].message.content;\n"
                "  const cleaned = content\n"
                "    .replace(/```json\\n?/g, '')\n"
                "    .replace(/```\\n?/g, '')\n"
                "    .trim();\n"
                "  const jsonMatch = cleaned.match(/\\{[\\s\\S]*\\}/);\n"
                "  analysis = JSON.parse(jsonMatch ? jsonMatch[0] : cleaned);\n"
                "} catch(e) {\n"
                "  analysis = {\n"
                "    trends: [{ topic: 'AI automation continues to grow', relevance: 7, source: 'general' }],\n"
                "    competitor_moves: [],\n"
                "    opportunities: [{ topic: 'Share automation tips for SMBs', angle: 'Practical how-to content', priority: 'medium', platforms: ['LinkedIn', 'Twitter'] }],\n"
                "    summary: 'Unable to fully parse AI analysis. Using fallback content opportunities.'\n"
                "  };\n"
                "}\n"
                "\n"
                "// Build insight records for Airtable\n"
                "const insights = [];\n"
                "\n"
                "// Add trend insights\n"
                "for (const trend of (analysis.trends || [])) {\n"
                "  insights.push({\n"
                "    title: trend.topic,\n"
                "    sourceType: 'trend',\n"
                "    source: trend.source || 'AI Analysis',\n"
                "    summary: analysis.summary || '',\n"
                "    keyThemes: JSON.stringify(analysis.trends.map(t => t.topic)),\n"
                "    contentOpportunities: JSON.stringify(analysis.opportunities || []),\n"
                "    relevanceScore: trend.relevance || 5,\n"
                "    week: weekNumber,\n"
                "    createdAt: todayDate\n"
                "  });\n"
                "}\n"
                "\n"
                "// Add competitor move insights\n"
                "for (const move of (analysis.competitor_moves || [])) {\n"
                "  insights.push({\n"
                "    title: `${move.competitor}: ${move.move}`,\n"
                "    sourceType: 'competitor',\n"
                "    source: move.competitor,\n"
                "    summary: move.our_angle || '',\n"
                "    keyThemes: JSON.stringify([move.move]),\n"
                "    contentOpportunities: JSON.stringify([{ topic: move.our_angle, angle: 'Competitive response' }]),\n"
                "    relevanceScore: 7,\n"
                "    week: weekNumber,\n"
                "    createdAt: todayDate\n"
                "  });\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    analysis: analysis,\n"
                "    insights: insights,\n"
                "    hashUpdates: mergedData.hashUpdates || [],\n"
                "    tokensUsed: input.usage ? input.usage.total_tokens : 0,\n"
                "    totalSources: mergedData.totalSources\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Parse Analysis",
        "type": "n8n-nodes-base.code",
        "position": [1980, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # ── Store Research Insights (loop) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const { insights } = $input.first().json;\n"
                "\n"
                "// Return each insight as a separate item for batch Airtable create\n"
                "return insights.map(insight => ({\n"
                "  json: {\n"
                "    'Title': insight.title.substring(0, 100),\n"
                "    'Source Type': insight.sourceType,\n"
                "    'Source': insight.source,\n"
                "    'Summary': insight.summary,\n"
                "    'Key Themes': insight.keyThemes,\n"
                "    'Content Opportunities': insight.contentOpportunities,\n"
                "    'Relevance Score': insight.relevanceScore,\n"
                "    'Week': insight.week,\n"
                "    'Created At': insight.createdAt\n"
                "  }\n"
                "}));"
            ),
        },
        "id": uid(),
        "name": "Format Insights",
        "type": "n8n-nodes-base.code",
        "position": [2220, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_RESEARCH_INSIGHTS},
            "columns": {
                "value": {
                    "Title": "={{ $json['Title'] }}",
                    "Source Type": "={{ $json['Source Type'] }}",
                    "Source": "={{ $json['Source'] }}",
                    "Summary": "={{ $json['Summary'] }}",
                    "Key Themes": "={{ $json['Key Themes'] }}",
                    "Content Opportunities": "={{ $json['Content Opportunities'] }}",
                    "Relevance Score": "={{ $json['Relevance Score'] }}",
                    "Week": "={{ $json['Week'] }}",
                    "Created At": "={{ $json['Created At'] }}",
                },
                "schema": [
                    {"id": "Title", "type": "string", "display": True, "displayName": "Title"},
                    {"id": "Source Type", "type": "string", "display": True, "displayName": "Source Type"},
                    {"id": "Source", "type": "string", "display": True, "displayName": "Source"},
                    {"id": "Summary", "type": "string", "display": True, "displayName": "Summary"},
                    {"id": "Key Themes", "type": "string", "display": True, "displayName": "Key Themes"},
                    {"id": "Content Opportunities", "type": "string", "display": True, "displayName": "Content Opportunities"},
                    {"id": "Relevance Score", "type": "number", "display": True, "displayName": "Relevance Score"},
                    {"id": "Week", "type": "string", "display": True, "displayName": "Week"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Title"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Store Insights",
        "type": "n8n-nodes-base.airtable",
        "position": [2460, 500],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── Update Hash Store ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const data = $('Parse Analysis').first().json;\n"
                "const hashUpdates = data.hashUpdates || [];\n"
                "\n"
                "if (hashUpdates.length === 0) {\n"
                "  return { json: { message: 'No hash updates needed' } };\n"
                "}\n"
                "\n"
                "// Return hash updates as items for System State upsert\n"
                "return hashUpdates.map(h => ({\n"
                "  json: {\n"
                "    'Key': h.key,\n"
                "    'Value': JSON.stringify({ hash: h.hash, checked_at: new Date().toISOString() }),\n"
                "    'Updated At': new Date().toISOString().split('T')[0],\n"
                "    'Updated By': 'WF-01 Intelligence'\n"
                "  }\n"
                "}));"
            ),
        },
        "id": uid(),
        "name": "Format Hash Updates",
        "type": "n8n-nodes-base.code",
        "position": [2700, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SYSTEM_STATE},
            "columns": {
                "value": {
                    "Key": "={{ $json['Key'] }}",
                    "Value": "={{ $json['Value'] }}",
                    "Updated At": "={{ $json['Updated At'] }}",
                    "Updated By": "={{ $json['Updated By'] }}",
                },
                "schema": [
                    {"id": "Key", "type": "string", "display": True, "displayName": "Key"},
                    {"id": "Value", "type": "string", "display": True, "displayName": "Value"},
                    {"id": "Updated At", "type": "string", "display": True, "displayName": "Updated At"},
                    {"id": "Updated By", "type": "string", "display": True, "displayName": "Updated By"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Key"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Hash Store",
        "type": "n8n-nodes-base.airtable",
        "position": [2940, 500],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── Summary Email ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const data = $('Parse Analysis').first().json;\n"
                "const now = new Date().toLocaleString('en-ZA', { timeZone: 'Africa/Johannesburg' });\n"
                "const analysis = data.analysis || {};\n"
                "\n"
                "const trendsHtml = (analysis.trends || []).map(t =>\n"
                "  `<li><strong>${t.topic}</strong> (relevance: ${t.relevance}/10) — ${t.source || 'mixed'}</li>`\n"
                ").join('\\n');\n"
                "\n"
                "const movesHtml = (analysis.competitor_moves || []).map(m =>\n"
                "  `<li><strong>${m.competitor}:</strong> ${m.move}<br>Our angle: ${m.our_angle}</li>`\n"
                ").join('\\n');\n"
                "\n"
                "const oppsHtml = (analysis.opportunities || []).map(o =>\n"
                "  `<li><strong>[${o.priority}]</strong> ${o.topic} — ${o.angle}<br>Platforms: ${(o.platforms || []).join(', ')}</li>`\n"
                ").join('\\n');\n"
                "\n"
                "const estimatedCost = ((data.tokensUsed || 0) / 1000000 * 3).toFixed(4);\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    subject: `Weekly Intelligence: ${(analysis.trends || []).length} trends, ${(analysis.opportunities || []).length} opportunities`,\n"
                "    body: [\n"
                "      '<h2>Weekly Intelligence Report</h2>',\n"
                "      `<p><strong>Date:</strong> ${now}</p>`,\n"
                "      `<p><strong>Sources analyzed:</strong> ${data.totalSources || 0}</p>`,\n"
                "      '<hr>',\n"
                "      `<p><em>${analysis.summary || 'No summary available'}</em></p>`,\n"
                "      '<h3>Trends</h3>',\n"
                "      `<ul>${trendsHtml || '<li>None identified</li>'}</ul>`,\n"
                "      '<h3>Competitor Moves</h3>',\n"
                "      `<ul>${movesHtml || '<li>None detected</li>'}</ul>`,\n"
                "      '<h3>Content Opportunities</h3>',\n"
                "      `<ul>${oppsHtml || '<li>None identified</li>'}</ul>`,\n"
                "      '<hr>',\n"
                "      `<p><strong>Tokens Used:</strong> ${(data.tokensUsed || 0).toLocaleString()}</p>`,\n"
                "      `<p><strong>Estimated Cost:</strong> $${estimatedCost}</p>`,\n"
                "      '<p>Insights stored in Research Insights table. WF-02 Strategy will use these on Monday 8:30 AM.</p>',\n"
                "    ].join('\\n')\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Build Summary",
        "type": "n8n-nodes-base.code",
        "position": [3180, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "={{ $json.subject }}",
            "emailType": "html",
            "message": "={{ $json.body }}",
            "options": {},
        },
        "id": uid(),
        "name": "Send Intelligence Report",
        "type": "n8n-nodes-base.gmail",
        "position": [3420, 500],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # ── Error Handling ──

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 880],
        "typeVersion": 1,
    })

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "MARKETING ERROR - Intelligence & Research",
            "emailType": "html",
            "message": "=<h2>Intelligence & Research Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 880],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ── Sticky Notes ──

    notes = [
        {
            "content": "## WF-01: Intelligence & Research\n\n**Schedule:** Monday 7:30 AM SAST\n**Purpose:** Scrapes competitor blogs, parses RSS feeds, runs AI trend analysis.\n**AI Model:** Claude Sonnet via OpenRouter\n**Output:** Research Insights table + weekly intelligence email",
            "position": [140, 220], "width": 400, "height": 160,
        },
        {
            "content": "## Data Collection\n\nCompetitor scraping (SHA-256 hash for change detection)\n+ RSS feed parsing (regex XML, last 7 days only)\n\n2s delay between competitor scrapes\n1s delay between RSS feeds",
            "position": [1140, 200], "width": 340, "height": 140,
        },
        {
            "content": "## AI Analysis\n\nSingle batched OpenRouter call:\n- 1500 max tokens\n- Temperature 0.5 (factual)\n- Identifies trends, competitor moves, content opportunities\n- JSON output with fallback",
            "position": [1680, 320], "width": 300, "height": 140,
        },
        {
            "content": "## Storage & Reporting\n\nInsights stored in Research Insights table\nContent hashes updated in System State\nWeekly intelligence email to Ian",
            "position": [2400, 340], "width": 300, "height": 120,
        },
    ]

    for i, note in enumerate(notes):
        nodes.append({
            "parameters": {
                "content": note["content"],
                "height": note.get("height", 140),
                "width": note.get("width", 340),
            },
            "id": f"wf01-note-{i+1}",
            "type": "n8n-nodes-base.stickyNote",
            "position": note["position"],
            "typeVersion": 1,
            "name": f"Note {i+1}",
        })

    return nodes


def build_wf01_connections():
    """Build connections for the Intelligence & Research workflow."""
    return {
        "Weekly Monday 7:30AM": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "System Config": {
            "main": [[{"node": "Read Research Config", "type": "main", "index": 0}]],
        },
        "Read Research Config": {
            "main": [[{"node": "Gather Intelligence", "type": "main", "index": 0}]],
        },
        "Gather Intelligence": {
            "main": [[{"node": "AI Trend Analysis", "type": "main", "index": 0}]],
        },
        "AI Trend Analysis": {
            "main": [[{"node": "Parse Analysis", "type": "main", "index": 0}]],
        },
        "Parse Analysis": {
            "main": [[{"node": "Format Insights", "type": "main", "index": 0}]],
        },
        "Format Insights": {
            "main": [[{"node": "Store Insights", "type": "main", "index": 0}]],
        },
        "Store Insights": {
            "main": [[{"node": "Format Hash Updates", "type": "main", "index": 0}]],
        },
        "Format Hash Updates": {
            "main": [[{"node": "Update Hash Store", "type": "main", "index": 0}]],
        },
        "Update Hash Store": {
            "main": [[{"node": "Build Summary", "type": "main", "index": 0}]],
        },
        "Build Summary": {
            "main": [[{"node": "Send Intelligence Report", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }


# ══════════════════════════════════════════════════════════════
# WF-02: STRATEGY & CAMPAIGN PLANNING
# ══════════════════════════════════════════════════════════════

def build_wf02_nodes():
    """Build all nodes for the Strategy & Campaign Planning workflow."""
    nodes = []

    # ── Triggers ──

    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "30 8 * * 1"}]
            }
        },
        "id": uid(),
        "name": "Weekly Monday 8:30AM",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 400],
        "typeVersion": 1.2,
    })

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 600],
        "typeVersion": 1,
    })

    # ── System Config ──

    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "todayDate", "value": "={{ $now.format('yyyy-MM-dd') }}", "type": "string"},
                    {"id": uid(), "name": "weekNumber", "value": "={{ $now.format('yyyy') + '-W' + $now.format('WW') }}", "type": "string"},
                    {"id": uid(), "name": "weekStartDate", "value": "={{ $now.startOf('week').format('yyyy-MM-dd') }}", "type": "string"},
                    {"id": uid(), "name": "weekEndDate", "value": "={{ $now.endOf('week').format('yyyy-MM-dd') }}", "type": "string"},
                    {"id": uid(), "name": "aiModel", "value": "anthropic/claude-sonnet-4-20250514", "type": "string"},
                    {"id": uid(), "name": "companyName", "value": "AnyVision Media", "type": "string"},
                ]
            },
        },
        "id": uid(),
        "name": "System Config",
        "type": "n8n-nodes-base.set",
        "position": [440, 500],
        "typeVersion": 3.4,
    })

    # ── Read Latest Research Insights ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_RESEARCH_INSIGHTS},
            "filterByFormula": "=({Week} = \"{{ $json.weekNumber }}\")",
        },
        "id": uid(),
        "name": "Read Research Insights",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 380],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── Read Last Week Distribution Performance ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_DISTRIBUTION_LOG},
            "filterByFormula": "=IS_AFTER({Published At}, DATEADD(TODAY(), -7, 'days'))",
        },
        "id": uid(),
        "name": "Read Last Week Performance",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 540],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── Read Last Week Content ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT},
            "filterByFormula": "=IS_AFTER({Created At}, DATEADD(TODAY(), -7, 'days'))",
        },
        "id": uid(),
        "name": "Read Last Week Content",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 700],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── Check Existing Plans This Week ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT_CALENDAR},
            "filterByFormula": "=AND(IS_AFTER({Date}, DATEADD(TODAY(), -1, 'days')), IS_BEFORE({Date}, DATEADD(TODAY(), 7, 'days')))",
        },
        "id": uid(),
        "name": "Check Existing Plans",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 860],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── Build Strategy Context ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const config = $('System Config').first().json;\n"
                "\n"
                "// Gather research insights\n"
                "let researchData = [];\n"
                "try {\n"
                "  researchData = $('Read Research Insights').all().map(i => i.json);\n"
                "} catch(e) {}\n"
                "\n"
                "// Gather performance data\n"
                "let perfData = [];\n"
                "try {\n"
                "  perfData = $('Read Last Week Performance').all().map(i => i.json);\n"
                "} catch(e) {}\n"
                "\n"
                "// Gather last week's content\n"
                "let lastContent = [];\n"
                "try {\n"
                "  lastContent = $('Read Last Week Content').all().map(i => i.json);\n"
                "} catch(e) {}\n"
                "\n"
                "// Gather existing plans\n"
                "let existingPlans = [];\n"
                "try {\n"
                "  existingPlans = $('Check Existing Plans').all().map(i => i.json);\n"
                "} catch(e) {}\n"
                "\n"
                "// Build context string for AI\n"
                "let context = `CONTENT STRATEGY CONTEXT\\n`;\n"
                "context += `Week: ${config.weekNumber} (${config.weekStartDate} to ${config.weekEndDate})\\n\\n`;\n"
                "\n"
                "// Research insights\n"
                "context += `RESEARCH INSIGHTS (from WF-01 Intelligence):\\n`;\n"
                "if (researchData.length > 0) {\n"
                "  for (const insight of researchData) {\n"
                "    context += `- [${insight['Source Type']}] ${insight.Title} (relevance: ${insight['Relevance Score']}/10)\\n`;\n"
                "    if (insight.Summary) context += `  Summary: ${insight.Summary}\\n`;\n"
                "    if (insight['Content Opportunities']) {\n"
                "      try {\n"
                "        const opps = JSON.parse(insight['Content Opportunities']);\n"
                "        for (const opp of opps) {\n"
                "          context += `  Opportunity: ${opp.topic || opp} — ${opp.angle || ''}\\n`;\n"
                "        }\n"
                "      } catch(e) {}\n"
                "    }\n"
                "  }\n"
                "} else {\n"
                "  context += `No research insights available this week. Use general industry knowledge.\\n`;\n"
                "}\n"
                "\n"
                "// Performance data\n"
                "context += `\\nLAST WEEK DISTRIBUTION PERFORMANCE:\\n`;\n"
                "if (perfData.length > 0) {\n"
                "  const successCount = perfData.filter(p => p.Status === 'Success').length;\n"
                "  const failCount = perfData.filter(p => p.Status === 'Failed').length;\n"
                "  const platforms = [...new Set(perfData.map(p => p.Platform))];\n"
                "  context += `- Total posts: ${perfData.length} (${successCount} success, ${failCount} failed)\\n`;\n"
                "  context += `- Platforms used: ${platforms.join(', ')}\\n`;\n"
                "} else {\n"
                "  context += `No distribution data from last week.\\n`;\n"
                "}\n"
                "\n"
                "// Last week's content topics (to avoid repetition)\n"
                "context += `\\nLAST WEEK CONTENT TOPICS (avoid repeating):\\n`;\n"
                "if (lastContent.length > 0) {\n"
                "  for (const content of lastContent.slice(0, 10)) {\n"
                "    context += `- ${content.Title || 'Untitled'}\\n`;\n"
                "  }\n"
                "} else {\n"
                "  context += `No content from last week.\\n`;\n"
                "}\n"
                "\n"
                "// Existing plans\n"
                "const existingDates = existingPlans.map(p => p.Date).filter(Boolean);\n"
                "context += `\\nEXISTING PLANS THIS WEEK:\\n`;\n"
                "if (existingDates.length > 0) {\n"
                "  context += `Already planned dates: ${existingDates.join(', ')}\\n`;\n"
                "  context += `Only generate content for UNPLANNED dates.\\n`;\n"
                "} else {\n"
                "  context += `No existing plans — generate content for all 7 days.\\n`;\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    strategyContext: context,\n"
                "    weekStart: config.weekStartDate,\n"
                "    weekEnd: config.weekEndDate,\n"
                "    existingDates: existingDates,\n"
                "    researchCount: researchData.length,\n"
                "    perfCount: perfData.length\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Build Strategy Context",
        "type": "n8n-nodes-base.code",
        "position": [1000, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # ── AI Strategist ──

    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={\n"
                "  \"model\": \"{{ $('System Config').item.json.aiModel }}\",\n"
                "  \"max_tokens\": 2000,\n"
                "  \"temperature\": 0.7,\n"
                "  \"messages\": [\n"
                "    {\n"
                "      \"role\": \"system\",\n"
                f"      \"content\": {json.dumps(STRATEGY_SYSTEM_PROMPT)}\n"
                "    },\n"
                "    {\n"
                "      \"role\": \"user\",\n"
                "      \"content\": {{ JSON.stringify($json.strategyContext) }}\n"
                "    }\n"
                "  ]\n"
                "}",
            "options": {"timeout": 60000},
        },
        "id": uid(),
        "name": "AI Strategist",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1280, 500],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 3000,
    })

    # ── Parse Strategy Response ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const contextData = $('Build Strategy Context').first().json;\n"
                "const existingDates = contextData.existingDates || [];\n"
                "\n"
                "let strategy;\n"
                "try {\n"
                "  const content = input.choices[0].message.content;\n"
                "  const cleaned = content\n"
                "    .replace(/```json\\n?/g, '')\n"
                "    .replace(/```\\n?/g, '')\n"
                "    .trim();\n"
                "  const jsonMatch = cleaned.match(/\\[[\\s\\S]*\\]/);\n"
                "  strategy = JSON.parse(jsonMatch ? jsonMatch[0] : cleaned);\n"
                "} catch(e) {\n"
                "  // Fallback: generate basic 7-day plan\n"
                "  const today = new Date();\n"
                "  strategy = [];\n"
                "  const fallbackTopics = [\n"
                "    'How AI automation helps small businesses save time',\n"
                "    'Behind the scenes: Building automated workflows',\n"
                "    'Top 3 tasks every business should automate',\n"
                "    'Client success story: Automation ROI',\n"
                "    'The future of AI in business operations',\n"
                "    'Quick tip: Automate your lead follow-up',\n"
                "    'Weekly wrap-up: Automation insights'\n"
                "  ];\n"
                "  for (let i = 0; i < 7; i++) {\n"
                "    const date = new Date(today);\n"
                "    date.setDate(date.getDate() + i);\n"
                "    const dateStr = date.toISOString().split('T')[0];\n"
                "    strategy.push({\n"
                "      date: dateStr,\n"
                "      topic: fallbackTopics[i],\n"
                "      content_type: 'social_post',\n"
                "      platforms: ['LinkedIn', 'Twitter', 'Instagram'],\n"
                "      brief: `Create engaging content about: ${fallbackTopics[i]}. Target SMBs interested in automation.`,\n"
                "      campaign: 'General Brand Awareness'\n"
                "    });\n"
                "  }\n"
                "}\n"
                "\n"
                "// Filter out dates that already have plans\n"
                "const filtered = strategy.filter(entry => !existingDates.includes(entry.date));\n"
                "\n"
                "// Return each entry as a separate item for batch Airtable create\n"
                "if (filtered.length === 0) {\n"
                "  return { json: { message: 'All dates already planned', entries: 0 } };\n"
                "}\n"
                "\n"
                "return filtered.map(entry => ({\n"
                "  json: {\n"
                "    title: `${entry.date}: ${(entry.topic || '').substring(0, 50)}`,\n"
                "    date: entry.date,\n"
                "    contentType: entry.content_type || 'social_post',\n"
                "    topic: entry.topic,\n"
                "    platforms: entry.platforms || ['LinkedIn', 'Twitter'],\n"
                "    brief: entry.brief,\n"
                "    campaign: entry.campaign || 'General Brand Awareness',\n"
                "    tokensUsed: (input.usage ? input.usage.total_tokens : 0)\n"
                "  }\n"
                "}));"
            ),
        },
        "id": uid(),
        "name": "Parse Strategy",
        "type": "n8n-nodes-base.code",
        "position": [1540, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # ── Create Calendar Entries ──

    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT_CALENDAR},
            "columns": {
                "value": {
                    "Title": "={{ $json.title }}",
                    "Date": "={{ $json.date }}",
                    "Content Type": "={{ $json.contentType }}",
                    "Topic": "={{ $json.topic }}",
                    "Platform": "={{ $json.platforms }}",
                    "Status": "Planned",
                    "Brief": "={{ $json.brief }}",
                    "Campaign": "={{ $json.campaign }}",
                },
                "schema": [
                    {"id": "Title", "type": "string", "display": True, "displayName": "Title"},
                    {"id": "Date", "type": "string", "display": True, "displayName": "Date"},
                    {"id": "Content Type", "type": "string", "display": True, "displayName": "Content Type"},
                    {"id": "Topic", "type": "string", "display": True, "displayName": "Topic"},
                    {"id": "Platform", "type": "array", "display": True, "displayName": "Platform"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Brief", "type": "string", "display": True, "displayName": "Brief"},
                    {"id": "Campaign", "type": "string", "display": True, "displayName": "Campaign"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Title"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Calendar Entries",
        "type": "n8n-nodes-base.airtable",
        "position": [1800, 500],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── Strategy Summary ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const now = new Date().toLocaleString('en-ZA', { timeZone: 'Africa/Johannesburg' });\n"
                "const contextData = $('Build Strategy Context').first().json;\n"
                "\n"
                "let entries = [];\n"
                "let totalTokens = 0;\n"
                "try {\n"
                "  entries = $('Parse Strategy').all().map(i => i.json);\n"
                "  totalTokens = entries.reduce((sum, e) => sum + (e.tokensUsed || 0), 0);\n"
                "} catch(e) {}\n"
                "\n"
                "const entriesHtml = entries.map(e =>\n"
                "  `<tr><td>${e.date || 'N/A'}</td><td>${e.topic || 'N/A'}</td><td>${(e.platforms || []).join(', ')}</td></tr>`\n"
                ").join('\\n');\n"
                "\n"
                "const estimatedCost = (totalTokens / 1000000 * 3).toFixed(4);\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    subject: `Weekly Strategy: ${entries.length} calendar entries created`,\n"
                "    body: [\n"
                "      '<h2>Weekly Content Strategy Report</h2>',\n"
                "      `<p><strong>Date:</strong> ${now}</p>`,\n"
                "      `<p><strong>Research insights used:</strong> ${contextData.researchCount || 0}</p>`,\n"
                "      `<p><strong>Last week performance records:</strong> ${contextData.perfCount || 0}</p>`,\n"
                "      '<hr>',\n"
                "      '<h3>Content Calendar (This Week)</h3>',\n"
                "      '<table border=\"1\" cellpadding=\"6\" style=\"border-collapse:collapse\">',\n"
                "      '<tr><th>Date</th><th>Topic</th><th>Platforms</th></tr>',\n"
                "      entriesHtml || '<tr><td colspan=\"3\">No entries created</td></tr>',\n"
                "      '</table>',\n"
                "      '<hr>',\n"
                "      `<p><strong>Tokens Used:</strong> ${totalTokens.toLocaleString()}</p>`,\n"
                "      `<p><strong>Estimated Cost:</strong> $${estimatedCost}</p>`,\n"
                "      '<p>Content Calendar populated. WF-03 will generate content daily at 9:00 AM.</p>',\n"
                "    ].join('\\n')\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Build Strategy Summary",
        "type": "n8n-nodes-base.code",
        "position": [2060, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "={{ $json.subject }}",
            "emailType": "html",
            "message": "={{ $json.body }}",
            "options": {},
        },
        "id": uid(),
        "name": "Send Strategy Report",
        "type": "n8n-nodes-base.gmail",
        "position": [2300, 500],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # ── Error Handling ──

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 880],
        "typeVersion": 1,
    })

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "MARKETING ERROR - Strategy & Planning",
            "emailType": "html",
            "message": "=<h2>Strategy & Planning Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 880],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ── Sticky Notes ──

    notes = [
        {
            "content": "## WF-02: Strategy & Campaign Planning\n\n**Schedule:** Monday 8:30 AM SAST (after WF-01)\n**Purpose:** Reads research insights + performance data, AI generates 7-day content plan.\n**AI Model:** Claude Sonnet via OpenRouter\n**Output:** Content Calendar entries + weekly strategy email",
            "position": [140, 220], "width": 420, "height": 160,
        },
        {
            "content": "## Data Gathering\n\n4 parallel Airtable reads:\n1. Research Insights (this week)\n2. Distribution Log (last 7 days)\n3. Content (last 7 days, avoid repeats)\n4. Content Calendar (existing plans)",
            "position": [620, 200], "width": 340, "height": 140,
        },
        {
            "content": "## AI Strategy\n\n2000 max tokens, temp 0.7\nGenerates 7-day content calendar\nFilters dates with existing plans\nWrites directly to Content Calendar",
            "position": [1220, 320], "width": 300, "height": 140,
        },
    ]

    for i, note in enumerate(notes):
        nodes.append({
            "parameters": {
                "content": note["content"],
                "height": note.get("height", 140),
                "width": note.get("width", 340),
            },
            "id": f"wf02-note-{i+1}",
            "type": "n8n-nodes-base.stickyNote",
            "position": note["position"],
            "typeVersion": 1,
            "name": f"Note {i+1}",
        })

    return nodes


def build_wf02_connections():
    """Build connections for the Strategy & Campaign Planning workflow."""
    return {
        "Weekly Monday 8:30AM": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "System Config": {
            "main": [[
                {"node": "Read Research Insights", "type": "main", "index": 0},
                {"node": "Read Last Week Performance", "type": "main", "index": 0},
                {"node": "Read Last Week Content", "type": "main", "index": 0},
                {"node": "Check Existing Plans", "type": "main", "index": 0},
            ]],
        },
        "Read Research Insights": {
            "main": [[{"node": "Build Strategy Context", "type": "main", "index": 0}]],
        },
        "Read Last Week Performance": {
            "main": [[{"node": "Build Strategy Context", "type": "main", "index": 0}]],
        },
        "Read Last Week Content": {
            "main": [[{"node": "Build Strategy Context", "type": "main", "index": 0}]],
        },
        "Check Existing Plans": {
            "main": [[{"node": "Build Strategy Context", "type": "main", "index": 0}]],
        },
        "Build Strategy Context": {
            "main": [[{"node": "AI Strategist", "type": "main", "index": 0}]],
        },
        "AI Strategist": {
            "main": [[{"node": "Parse Strategy", "type": "main", "index": 0}]],
        },
        "Parse Strategy": {
            "main": [[{"node": "Create Calendar Entries", "type": "main", "index": 0}]],
        },
        "Create Calendar Entries": {
            "main": [[{"node": "Build Strategy Summary", "type": "main", "index": 0}]],
        },
        "Build Strategy Summary": {
            "main": [[{"node": "Send Strategy Report", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }


# ══════════════════════════════════════════════════════════════
# WF-03: CONTENT PRODUCTION
# ══════════════════════════════════════════════════════════════

def build_wf03_nodes():
    """Build all nodes for the Content Production workflow."""
    nodes = []

    # ── Triggers ──

    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "hours", "triggerAtHour": 9}]
            }
        },
        "id": uid(),
        "name": "Daily 9AM Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 400],
        "typeVersion": 1.2,
    })

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 600],
        "typeVersion": 1,
    })

    # ── System Config ──

    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "todayDate", "value": "={{ $now.format('yyyy-MM-dd') }}", "type": "string"},
                    {"id": uid(), "name": "companyName", "value": "AnyVision Media", "type": "string"},
                    {"id": uid(), "name": "ownerName", "value": "Ian Immelman", "type": "string"},
                    {"id": uid(), "name": "aiModel", "value": "anthropic/claude-sonnet-4-20250514", "type": "string"},
                ]
            },
        },
        "id": uid(),
        "name": "System Config",
        "type": "n8n-nodes-base.set",
        "position": [440, 500],
        "typeVersion": 3.4,
    })

    # ── Read Content Calendar ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT_CALENDAR},
            "filterByFormula": "=AND({Date} = \"{{ $json.todayDate }}\", {Status} = \"Planned\")",
        },
        "id": uid(),
        "name": "Read Content Calendar",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 500],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── Check if items exist ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "strict"},
                "combinator": "and",
                "conditions": [
                    {"id": uid(), "operator": {"type": "object", "operation": "notEmpty", "singleValue": True}, "leftValue": "={{ $json.id }}", "rightValue": ""},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Has Calendar Items?",
        "type": "n8n-nodes-base.if",
        "position": [920, 500],
        "typeVersion": 2.2,
    })

    # ── Loop Over Content Items ──

    nodes.append({
        "parameters": {"options": {"batchSize": 1}},
        "id": uid(),
        "name": "Loop Over Content",
        "type": "n8n-nodes-base.splitInBatches",
        "position": [1160, 400],
        "typeVersion": 3,
    })

    # ── Update Calendar Status to "In Production" ──

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT_CALENDAR},
            "columns": {
                "value": {"Status": "In Production"},
                "schema": [{"id": "Status", "type": "string", "display": True, "displayName": "Status"}],
                "mappingMode": "defineBelow",
                "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Mark In Production",
        "type": "n8n-nodes-base.airtable",
        "position": [1400, 600],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── AI Generate Social Post ──
    # Uses OpenRouter via HTTP Request (same pattern as Lead Scraper)

    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={\n"
                "  \"model\": \"{{ $('System Config').item.json.aiModel }}\",\n"
                "  \"max_tokens\": 500,\n"
                "  \"temperature\": 0.7,\n"
                "  \"messages\": [\n"
                "    {\n"
                "      \"role\": \"system\",\n"
                f"      \"content\": {json.dumps(SOCIAL_POST_SYSTEM_PROMPT)}\n"
                "    },\n"
                "    {\n"
                "      \"role\": \"user\",\n"
                "      \"content\": \"Write a social media post for the following:\\n\\n"
                "Topic: {{ $json.Topic }}\\n"
                "Platform: {{ $json.Platform }}\\n"
                "Brief: {{ $json.Brief }}\\n\\n"
                "Generate content optimized for the specified platform.\"\n"
                "    }\n"
                "  ]\n"
                "}",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "AI Generate Social Post",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1640, 600],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 2000,
    })

    # ── AI Hook Optimizer (second pass) ──

    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={\n"
                "  \"model\": \"{{ $('System Config').item.json.aiModel }}\",\n"
                "  \"max_tokens\": 300,\n"
                "  \"temperature\": 0.8,\n"
                "  \"messages\": [\n"
                "    {\n"
                "      \"role\": \"system\",\n"
                f"      \"content\": {json.dumps(HOOK_OPTIMIZER_PROMPT)}\n"
                "    },\n"
                "    {\n"
                "      \"role\": \"user\",\n"
                "      \"content\": \"Original hook: {{ $json.parsedContent.hook }}\\n"
                "Topic: {{ $('Loop Over Content').item.json.Topic }}\"\n"
                "    }\n"
                "  ]\n"
                "}",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "AI Hook Optimizer",
        "type": "n8n-nodes-base.httpRequest",
        "position": [2120, 600],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 2000,
    })

    # ── Parse AI Response (post generation) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const calendarItem = $('Loop Over Content').item.json;\n"
                "\n"
                "let parsed;\n"
                "try {\n"
                "  const content = input.choices[0].message.content;\n"
                "  const cleaned = content\n"
                "    .replace(/```json\\n?/g, '')\n"
                "    .replace(/```\\n?/g, '')\n"
                "    .trim();\n"
                "  const jsonMatch = cleaned.match(/\\{[\\s\\S]*\\}/);\n"
                "  parsed = JSON.parse(jsonMatch ? jsonMatch[0] : cleaned);\n"
                "} catch (e) {\n"
                "  // Fallback content\n"
                "  parsed = {\n"
                "    hook: `Discover how ${calendarItem.Topic || 'automation'} can transform your business`,\n"
                "    body: `At AnyVision Media, we help businesses automate and scale. ${calendarItem.Brief || ''}`,\n"
                "    cta: 'Want to learn more? Drop us a message.',\n"
                "    hashtags: '#automation #AI #business'\n"
                "  };\n"
                "}\n"
                "\n"
                "// Calculate quality score (1-10)\n"
                "let score = 5; // baseline\n"
                "const fullText = `${parsed.hook} ${parsed.body} ${parsed.cta}`;\n"
                "if (parsed.hook && parsed.hook.length > 10) score += 1;\n"
                "if (parsed.body && parsed.body.length > 50) score += 1;\n"
                "if (parsed.cta && parsed.cta.length > 10) score += 1;\n"
                "if (parsed.hashtags && parsed.hashtags.split('#').length > 2) score += 1;\n"
                "if (fullText.length > 100 && fullText.length < 1000) score += 1;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    parsedContent: parsed,\n"
                "    qualityScore: score,\n"
                "    calendarId: calendarItem.id,\n"
                "    topic: calendarItem.Topic,\n"
                "    platform: (calendarItem.Platform || []).join(', '),\n"
                "    tokensUsed: input.usage ? input.usage.total_tokens : 0\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Parse Post Response",
        "type": "n8n-nodes-base.code",
        "position": [1880, 600],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # ── Parse Hook Optimizer Response ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const postData = $('Parse Post Response').item.json;\n"
                "\n"
                "let hookData;\n"
                "try {\n"
                "  const content = input.choices[0].message.content;\n"
                "  const cleaned = content\n"
                "    .replace(/```json\\n?/g, '')\n"
                "    .replace(/```\\n?/g, '')\n"
                "    .trim();\n"
                "  const jsonMatch = cleaned.match(/\\{[\\s\\S]*\\}/);\n"
                "  hookData = JSON.parse(jsonMatch ? jsonMatch[0] : cleaned);\n"
                "} catch (e) {\n"
                "  hookData = {\n"
                "    variations: [postData.parsedContent.hook],\n"
                "    scores: [7],\n"
                "    best_index: 0\n"
                "  };\n"
                "}\n"
                "\n"
                "// Use the best hook\n"
                "const bestIndex = hookData.best_index || 0;\n"
                "const bestHook = hookData.variations[bestIndex] || postData.parsedContent.hook;\n"
                "\n"
                "// Compose the full post text\n"
                "const fullPost = [bestHook, postData.parsedContent.body, postData.parsedContent.cta]\n"
                "  .filter(Boolean)\n"
                "  .join('\\n\\n');\n"
                "\n"
                "const fullPostWithHashtags = postData.parsedContent.hashtags\n"
                "  ? fullPost + '\\n\\n' + postData.parsedContent.hashtags\n"
                "  : fullPost;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    title: bestHook,\n"
                "    body: fullPostWithHashtags,\n"
                "    hashtags: postData.parsedContent.hashtags || '',\n"
                "    hookVariations: JSON.stringify(hookData.variations || []),\n"
                "    selectedHook: bestIndex,\n"
                "    qualityScore: postData.qualityScore,\n"
                "    calendarId: postData.calendarId,\n"
                "    topic: postData.topic,\n"
                "    platform: postData.platform,\n"
                "    tokensUsed: postData.tokensUsed + (input.usage ? input.usage.total_tokens : 0)\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Parse Hook Response",
        "type": "n8n-nodes-base.code",
        "position": [2360, 600],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # ── Store Content in Airtable ──

    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT},
            "columns": {
                "value": {
                    "Title": "={{ $json.title }}",
                    "Calendar Entry ID": "={{ $json.calendarId }}",
                    "Content Type": "social_post",
                    "Body": "={{ $json.body }}",
                    "Hashtags": "={{ $json.hashtags }}",
                    "Hook Variations": "={{ $json.hookVariations }}",
                    "Selected Hook": "={{ $json.selectedHook }}",
                    "Status": "Draft",
                    "Quality Score": "={{ $json.qualityScore }}",
                    "Platform": "={{ $json.platform }}",
                    "Created At": "={{ $now.format('yyyy-MM-dd') }}",
                },
                "schema": [
                    {"id": "Title", "type": "string", "display": True, "displayName": "Title"},
                    {"id": "Calendar Entry ID", "type": "string", "display": True, "displayName": "Calendar Entry ID"},
                    {"id": "Content Type", "type": "string", "display": True, "displayName": "Content Type"},
                    {"id": "Body", "type": "string", "display": True, "displayName": "Body"},
                    {"id": "Hashtags", "type": "string", "display": True, "displayName": "Hashtags"},
                    {"id": "Hook Variations", "type": "string", "display": True, "displayName": "Hook Variations"},
                    {"id": "Selected Hook", "type": "number", "display": True, "displayName": "Selected Hook"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Quality Score", "type": "number", "display": True, "displayName": "Quality Score"},
                    {"id": "Platform", "type": "string", "display": True, "displayName": "Platform"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Title"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Store Content",
        "type": "n8n-nodes-base.airtable",
        "position": [2600, 600],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── Quality Gate ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "strict"},
                "combinator": "and",
                "conditions": [
                    {"id": uid(), "operator": {"type": "number", "operation": "gte"}, "leftValue": "={{ $('Parse Hook Response').item.json.qualityScore }}", "rightValue": 6},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Quality Score >= 6?",
        "type": "n8n-nodes-base.if",
        "position": [2840, 600],
        "typeVersion": 2.2,
    })

    # ── Queue for Publishing (quality passed) ──

    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_PUBLISH_QUEUE},
            "columns": {
                "value": {
                    "Queue ID": "={{ 'PQ-' + $now.format('yyyyMMdd') + '-' + $json.id }}",
                    "Content ID": "={{ $json.id }}",
                    "Channel": "blotato_social",
                    "Scheduled For": "={{ $now.format('yyyy-MM-dd') }}",
                    "Status": "Queued",
                },
                "schema": [
                    {"id": "Queue ID", "type": "string", "display": True, "displayName": "Queue ID"},
                    {"id": "Content ID", "type": "string", "display": True, "displayName": "Content ID"},
                    {"id": "Channel", "type": "string", "display": True, "displayName": "Channel"},
                    {"id": "Scheduled For", "type": "string", "display": True, "displayName": "Scheduled For"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Queue ID"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Queue for Publishing",
        "type": "n8n-nodes-base.airtable",
        "position": [3080, 500],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── Update Calendar to Ready ──

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT_CALENDAR},
            "columns": {
                "value": {"Status": "Ready"},
                "schema": [{"id": "Status", "type": "string", "display": True, "displayName": "Status"}],
                "mappingMode": "defineBelow",
                "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Calendar -> Ready",
        "type": "n8n-nodes-base.airtable",
        "position": [3320, 500],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── Update Calendar to Draft (quality failed) ──

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT_CALENDAR},
            "columns": {
                "value": {"Status": "Draft"},
                "schema": [{"id": "Status", "type": "string", "display": True, "displayName": "Status"}],
                "mappingMode": "defineBelow",
                "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Calendar -> Draft",
        "type": "n8n-nodes-base.airtable",
        "position": [3080, 780],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── Update Content Status to Ready ──

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT},
            "columns": {
                "value": {"Status": "Ready"},
                "schema": [{"id": "Status", "type": "string", "display": True, "displayName": "Status"}],
                "mappingMode": "defineBelow",
                "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Content -> Ready",
        "type": "n8n-nodes-base.airtable",
        "position": [3320, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── Back to Loop (from both quality paths) ──
    # Both Calendar -> Ready and Calendar -> Draft feed back into the loop

    # ── Summary Aggregation ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "// This runs after the loop completes (or when no items)\n"
                "const now = new Date().toLocaleString('en-ZA', { timeZone: 'Africa/Johannesburg' });\n"
                "\n"
                "// Try to count processed items\n"
                "let totalProcessed = 0;\n"
                "let totalTokens = 0;\n"
                "try {\n"
                "  const items = $('Parse Hook Response').all();\n"
                "  totalProcessed = items.length;\n"
                "  totalTokens = items.reduce((sum, i) => sum + (i.json.tokensUsed || 0), 0);\n"
                "} catch(e) {\n"
                "  // No items processed\n"
                "}\n"
                "\n"
                "const estimatedCost = (totalTokens / 1000000 * 3).toFixed(4); // ~$3/MTok for Claude Sonnet\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    subject: `Marketing Content: ${totalProcessed} posts generated`,\n"
                "    body: [\n"
                "      '<h2>Daily Content Production Report</h2>',\n"
                "      `<p><strong>Date:</strong> ${now}</p>`,\n"
                "      '<hr>',\n"
                "      `<p><strong>Posts Generated:</strong> ${totalProcessed}</p>`,\n"
                "      `<p><strong>Total Tokens Used:</strong> ${totalTokens.toLocaleString()}</p>`,\n"
                "      `<p><strong>Estimated Cost:</strong> $${estimatedCost}</p>`,\n"
                "      '<hr>',\n"
                "      '<p>Content has been queued for distribution at 10:00 AM.</p>',\n"
                "    ].join('\\n')\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Aggregate Results",
        "type": "n8n-nodes-base.code",
        "position": [3560, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # ── Send Summary Email ──

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "={{ $json.subject }}",
            "emailType": "html",
            "message": "={{ $json.body }}",
            "options": {},
        },
        "id": uid(),
        "name": "Send Summary",
        "type": "n8n-nodes-base.gmail",
        "position": [3800, 500],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # ── Error Handling ──

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 880],
        "typeVersion": 1,
    })

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "MARKETING ERROR - Content Production",
            "emailType": "html",
            "message": "=<h2>Content Production Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 880],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ── Sticky Notes ──

    notes = [
        {
            "content": "## WF-03: Content Production\n\n**Schedule:** Daily at 9:00 AM SAST\n**Purpose:** Reads content calendar, generates social posts via AI, optimizes hooks, queues for distribution.\n**AI Model:** Claude Sonnet via OpenRouter\n**Quality Gate:** Score >= 6 auto-queues; < 6 held as Draft",
            "position": [140, 220], "width": 380, "height": 160,
        },
        {
            "content": "## AI Content Generation\n\nTwo-pass AI pipeline:\n1. Generate post (hook, body, CTA, hashtags)\n2. Optimize hook (3 variations, pick best)\n\nJSON-only output, markdown-strip fallback.",
            "position": [1580, 400], "width": 340, "height": 140,
        },
        {
            "content": "## Quality Gate & Storage\n\nScore >= 6: Auto-queue for publishing\nScore < 6: Held as Draft for human review\n\nAll content stored in Airtable regardless of score.",
            "position": [2780, 380], "width": 320, "height": 120,
        },
        {
            "content": "## Error Handling\n\nAll external API nodes have:\n- continueOnFail\n- retryOnFail (AI calls)\n\nUncaught errors -> Gmail alert",
            "position": [140, 800], "width": 260, "height": 100,
        },
    ]

    for i, note in enumerate(notes):
        nodes.append({
            "parameters": {
                "content": note["content"],
                "height": note.get("height", 140),
                "width": note.get("width", 340),
            },
            "id": f"wf03-note-{i+1}",
            "type": "n8n-nodes-base.stickyNote",
            "position": note["position"],
            "typeVersion": 1,
            "name": f"Note {i+1}",
        })

    return nodes


def build_wf03_connections():
    """Build connections for the Content Production workflow."""
    return {
        "Daily 9AM Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "System Config": {
            "main": [[{"node": "Read Content Calendar", "type": "main", "index": 0}]],
        },
        "Read Content Calendar": {
            "main": [[{"node": "Has Calendar Items?", "type": "main", "index": 0}]],
        },
        "Has Calendar Items?": {
            "main": [
                [{"node": "Loop Over Content", "type": "main", "index": 0}],  # true
                [{"node": "Aggregate Results", "type": "main", "index": 0}],  # false (no items)
            ],
        },
        "Loop Over Content": {
            "main": [
                [{"node": "Aggregate Results", "type": "main", "index": 0}],  # done
                [{"node": "Mark In Production", "type": "main", "index": 0}],  # loop body
            ],
        },
        "Mark In Production": {
            "main": [[{"node": "AI Generate Social Post", "type": "main", "index": 0}]],
        },
        "AI Generate Social Post": {
            "main": [[{"node": "Parse Post Response", "type": "main", "index": 0}]],
        },
        "Parse Post Response": {
            "main": [[{"node": "AI Hook Optimizer", "type": "main", "index": 0}]],
        },
        "AI Hook Optimizer": {
            "main": [[{"node": "Parse Hook Response", "type": "main", "index": 0}]],
        },
        "Parse Hook Response": {
            "main": [[{"node": "Store Content", "type": "main", "index": 0}]],
        },
        "Store Content": {
            "main": [[{"node": "Quality Score >= 6?", "type": "main", "index": 0}]],
        },
        "Quality Score >= 6?": {
            "main": [
                [  # true — queue for publishing + update statuses
                    {"node": "Content -> Ready", "type": "main", "index": 0},
                    {"node": "Queue for Publishing", "type": "main", "index": 0},
                ],
                [{"node": "Calendar -> Draft", "type": "main", "index": 0}],  # false
            ],
        },
        "Queue for Publishing": {
            "main": [[{"node": "Calendar -> Ready", "type": "main", "index": 0}]],
        },
        "Calendar -> Ready": {
            "main": [[{"node": "Loop Over Content", "type": "main", "index": 0}]],
        },
        "Calendar -> Draft": {
            "main": [[{"node": "Loop Over Content", "type": "main", "index": 0}]],
        },
        "Content -> Ready": {
            "main": [],  # Terminal — runs in parallel with Queue for Publishing
        },
        "Aggregate Results": {
            "main": [[{"node": "Send Summary", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }


# ══════════════════════════════════════════════════════════════
# WF-04: DISTRIBUTION & PUBLISHING
# ══════════════════════════════════════════════════════════════

def build_wf04_nodes():
    """Build all nodes for the Distribution workflow."""
    nodes = []

    # ── Triggers ──

    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "hours", "triggerAtHour": 10}]
            }
        },
        "id": uid(),
        "name": "Daily 10AM Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 400],
        "typeVersion": 1.2,
    })

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 600],
        "typeVersion": 1,
    })

    # ── Read Publish Queue ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_PUBLISH_QUEUE},
            "filterByFormula": "=({Status} = \"Queued\")",
        },
        "id": uid(),
        "name": "Read Publish Queue",
        "type": "n8n-nodes-base.airtable",
        "position": [440, 500],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── Check if items exist ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "strict"},
                "combinator": "and",
                "conditions": [
                    {"id": uid(), "operator": {"type": "object", "operation": "notEmpty", "singleValue": True}, "leftValue": "={{ $json.id }}", "rightValue": ""},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Has Queue Items?",
        "type": "n8n-nodes-base.if",
        "position": [680, 500],
        "typeVersion": 2.2,
    })

    # ── Loop Over Queue Items ──

    nodes.append({
        "parameters": {"options": {"batchSize": 1}},
        "id": uid(),
        "name": "Loop Over Queue",
        "type": "n8n-nodes-base.splitInBatches",
        "position": [920, 400],
        "typeVersion": 3,
    })

    # ── Read Content by ID ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT},
            "filterByFormula": "=({Title} = \"{{ $json['Content ID'] }}\")",
        },
        "id": uid(),
        "name": "Read Content",
        "type": "n8n-nodes-base.airtable",
        "position": [1160, 600],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── Format for Blotato ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const content = $input.first().json;\n"
                "const queueItem = $('Loop Over Queue').item.json;\n"
                "\n"
                "// Build the post text from content fields\n"
                "const postText = content.Body || content.Title || 'Check out our latest update!';\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    postText: postText,\n"
                "    contentId: content.id || queueItem['Content ID'],\n"
                "    queueId: queueItem.id,\n"
                "    calendarId: content['Calendar Entry ID'] || '',\n"
                "    title: content.Title || '',\n"
                "    platform: content.Platform || 'all'\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Format for Blotato",
        "type": "n8n-nodes-base.code",
        "position": [1400, 600],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # ── Post to Each Platform via Blotato ──
    # Using the Blotato community node (same as "1 Post Everywhere")

    platforms = [
        ("TikTok", "tiktok", [1700, 200]),
        ("Instagram", "instagram", [1700, 340]),
        ("Facebook", "facebook", [1700, 480]),
        ("LinkedIn", "linkedin", [1700, 620]),
        ("Twitter", "twitter", [1700, 760]),
        ("YouTube", "youtube", [1700, 900]),
        ("Threads", "threads", [1700, 1040]),
        ("Bluesky", "bluesky", [1700, 1180]),
        ("Pinterest", "pinterest", [1700, 1320]),
    ]

    for platform_name, platform_key, position in platforms:
        account = BLOTATO_ACCOUNTS[platform_key]
        params = {
            "platform": platform_key,
            "accountId": {"__rl": True, "mode": "list", "value": account["accountId"]},
            "postContentText": "={{ $json.postText }}",
            "options": {},
        }

        # Facebook needs facebookPageId (resource locator)
        if platform_key == "facebook" and "subAccountId" in account:
            params["facebookPageId"] = {
                "__rl": True, "mode": "list", "value": account["subAccountId"],
            }

        # YouTube needs a title
        if platform_key == "youtube":
            params["postCreateYoutubeOptionTitle"] = "={{ $json.title }}"

        nodes.append({
            "parameters": params,
            "id": uid(),
            "name": f"{platform_name} [BLOTATO]",
            "type": "@blotato/n8n-nodes-blotato.blotato",
            "position": position,
            "typeVersion": 2,
            "credentials": {"blotatoApi": CRED_BLOTATO},
            "onError": "continueRegularOutput",
        })

    # ── Merge Platform Results (scatter-gather sync barrier) ──

    nodes.append({
        "parameters": {"mode": "append"},
        "id": uid(),
        "name": "Merge Platform Results",
        "type": "n8n-nodes-base.merge",
        "position": [2000, 600],
        "typeVersion": 3,
    })

    # ── Process Results (replaces Collect Results + Format Log Entries) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "// Process merged results from all 9 platform posting attempts\n"
                "const items = $input.all();\n"
                "const platforms = ['TikTok', 'Instagram', 'Facebook', 'LinkedIn',\n"
                "                   'Twitter', 'YouTube', 'Threads', 'Bluesky', 'Pinterest'];\n"
                "const formatData = $('Format for Blotato').first().json;\n"
                "const now = new Date().toISOString().split('T')[0];\n"
                "let successCount = 0;\n"
                "let failCount = 0;\n"
                "\n"
                "const logEntries = items.map((item, i) => {\n"
                "  const platform = platforms[i] || 'Unknown';\n"
                "  const hasError = !!(item.json.error || item.json.statusCode >= 400);\n"
                "  if (hasError) { failCount++; } else { successCount++; }\n"
                "  return {\n"
                "    json: {\n"
                "      'Log ID': `LOG-${Date.now()}-${platform}`,\n"
                "      'Content ID': formatData.contentId || '',\n"
                "      'Platform': platform,\n"
                "      'Published At': now,\n"
                "      'Status': hasError ? 'Failed' : 'Success',\n"
                "      'Response': JSON.stringify(item.json).substring(0, 200),\n"
                "      _queueId: formatData.queueId || '',\n"
                "      _contentId: formatData.contentId || '',\n"
                "      _successCount: successCount,\n"
                "      _failCount: failCount,\n"
                "    }\n"
                "  };\n"
                "});\n"
                "return logEntries;"
            ),
        },
        "id": uid(),
        "name": "Process Results",
        "type": "n8n-nodes-base.code",
        "position": [2240, 600],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_DISTRIBUTION_LOG},
            "columns": {
                "value": {
                    "Log ID": "={{ $json['Log ID'] }}",
                    "Content ID": "={{ $json['Content ID'] }}",
                    "Platform": "={{ $json['Platform'] }}",
                    "Published At": "={{ $json['Published At'] }}",
                    "Status": "={{ $json['Status'] }}",
                    "Response": "={{ $json['Response'] }}",
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
                "matchingColumns": ["Log ID"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Store Distribution Log",
        "type": "n8n-nodes-base.airtable",
        "position": [2480, 600],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── Update Publish Queue Status ──

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_PUBLISH_QUEUE},
            "columns": {
                "value": {
                    "Status": "Published",
                    "Published At": "={{ $now.format('yyyy-MM-dd') }}",
                    "Platform Results": "={{ $json._successCount + '/' + ($json._successCount + $json._failCount) + ' platforms succeeded' }}",
                },
                "schema": [
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Published At", "type": "string", "display": True, "displayName": "Published At"},
                    {"id": "Platform Results", "type": "string", "display": True, "displayName": "Platform Results"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Queue Status",
        "type": "n8n-nodes-base.airtable",
        "position": [2720, 600],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── Update Content Status to Published ──

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT},
            "columns": {
                "value": {"Status": "Published"},
                "schema": [{"id": "Status", "type": "string", "display": True, "displayName": "Status"}],
                "mappingMode": "defineBelow",
                "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Content -> Published",
        "type": "n8n-nodes-base.airtable",
        "position": [2960, 600],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── Summary ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const now = new Date().toLocaleString('en-ZA', { timeZone: 'Africa/Johannesburg' });\n"
                "let totalPublished = 0;\n"
                "let totalFailed = 0;\n"
                "\n"
                "try {\n"
                "  const items = $('Process Results').all();\n"
                "  for (const item of items) {\n"
                "    totalPublished += item.json._successCount || 0;\n"
                "    totalFailed += item.json._failCount || 0;\n"
                "  }\n"
                "} catch(e) {}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    subject: `Marketing Distribution: ${totalPublished} posts published`,\n"
                "    body: [\n"
                "      '<h2>Daily Distribution Report</h2>',\n"
                "      `<p><strong>Date:</strong> ${now}</p>`,\n"
                "      '<hr>',\n"
                "      `<p><strong>Successful Posts:</strong> ${totalPublished}</p>`,\n"
                "      `<p><strong>Failed Posts:</strong> ${totalFailed}</p>`,\n"
                "      '<hr>',\n"
                "      '<p>Check your Airtable Distribution Log for per-platform details.</p>',\n"
                "    ].join('\\n')\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Aggregate Distribution",
        "type": "n8n-nodes-base.code",
        "position": [3440, 400],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "={{ $json.subject }}",
            "emailType": "html",
            "message": "={{ $json.body }}",
            "options": {},
        },
        "id": uid(),
        "name": "Send Distribution Summary",
        "type": "n8n-nodes-base.gmail",
        "position": [3680, 400],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # ── Error Handling ──

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 880],
        "typeVersion": 1,
    })

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "MARKETING ERROR - Distribution",
            "emailType": "html",
            "message": "=<h2>Distribution Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 880],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ── Sticky Notes ──

    notes = [
        {
            "content": "## WF-04: Distribution & Publishing\n\n**Schedule:** Daily at 10:00 AM SAST\n**Purpose:** Reads publish queue, posts to 9 platforms via Blotato, logs results.\n**No AI tokens used** — pure distribution.",
            "position": [140, 220], "width": 380, "height": 140,
        },
        {
            "content": "## Platform Posting (Blotato)\n\nPosts in parallel to:\nTikTok, Instagram, Facebook, LinkedIn,\nTwitter, YouTube, Threads, Bluesky, Pinterest\n\ncontinueOnFail on each platform node.",
            "position": [1640, 60], "width": 320, "height": 130,
        },
        {
            "content": "## Result Logging\n\nMerge node collects all 9 platform results.\nPer-platform results stored in Distribution Log.\nQueue and Content status updated to Published.",
            "position": [2180, 400], "width": 300, "height": 120,
        },
    ]

    for i, note in enumerate(notes):
        nodes.append({
            "parameters": {
                "content": note["content"],
                "height": note.get("height", 140),
                "width": note.get("width", 340),
            },
            "id": f"wf04-note-{i+1}",
            "type": "n8n-nodes-base.stickyNote",
            "position": note["position"],
            "typeVersion": 1,
            "name": f"Note {i+1}",
        })

    return nodes


def build_wf04_connections():
    """Build connections for the Distribution workflow (scatter-gather pattern)."""
    connections = {
        "Daily 10AM Trigger": {
            "main": [[{"node": "Read Publish Queue", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "Read Publish Queue", "type": "main", "index": 0}]],
        },
        "Read Publish Queue": {
            "main": [[{"node": "Has Queue Items?", "type": "main", "index": 0}]],
        },
        "Has Queue Items?": {
            "main": [
                [{"node": "Loop Over Queue", "type": "main", "index": 0}],  # true
                [{"node": "Aggregate Distribution", "type": "main", "index": 0}],  # false
            ],
        },
        "Loop Over Queue": {
            "main": [
                [{"node": "Aggregate Distribution", "type": "main", "index": 0}],  # done
                [{"node": "Read Content", "type": "main", "index": 0}],  # loop body
            ],
        },
        "Read Content": {
            "main": [[{"node": "Format for Blotato", "type": "main", "index": 0}]],
        },
        # Fan-out: Format for Blotato → 9 Blotato nodes ONLY (no extra nodes)
        "Format for Blotato": {
            "main": [[
                {"node": "TikTok [BLOTATO]", "type": "main", "index": 0},
                {"node": "Instagram [BLOTATO]", "type": "main", "index": 0},
                {"node": "Facebook [BLOTATO]", "type": "main", "index": 0},
                {"node": "LinkedIn [BLOTATO]", "type": "main", "index": 0},
                {"node": "Twitter [BLOTATO]", "type": "main", "index": 0},
                {"node": "YouTube [BLOTATO]", "type": "main", "index": 0},
                {"node": "Threads [BLOTATO]", "type": "main", "index": 0},
                {"node": "Bluesky [BLOTATO]", "type": "main", "index": 0},
                {"node": "Pinterest [BLOTATO]", "type": "main", "index": 0},
            ]],
        },
        # Gather: Each Blotato node → Merge at a different input index (0-8)
        "TikTok [BLOTATO]": {
            "main": [[{"node": "Merge Platform Results", "type": "main", "index": 0}]],
        },
        "Instagram [BLOTATO]": {
            "main": [[{"node": "Merge Platform Results", "type": "main", "index": 1}]],
        },
        "Facebook [BLOTATO]": {
            "main": [[{"node": "Merge Platform Results", "type": "main", "index": 2}]],
        },
        "LinkedIn [BLOTATO]": {
            "main": [[{"node": "Merge Platform Results", "type": "main", "index": 3}]],
        },
        "Twitter [BLOTATO]": {
            "main": [[{"node": "Merge Platform Results", "type": "main", "index": 4}]],
        },
        "YouTube [BLOTATO]": {
            "main": [[{"node": "Merge Platform Results", "type": "main", "index": 5}]],
        },
        "Threads [BLOTATO]": {
            "main": [[{"node": "Merge Platform Results", "type": "main", "index": 6}]],
        },
        "Bluesky [BLOTATO]": {
            "main": [[{"node": "Merge Platform Results", "type": "main", "index": 7}]],
        },
        "Pinterest [BLOTATO]": {
            "main": [[{"node": "Merge Platform Results", "type": "main", "index": 8}]],
        },
        # Sequential: Merge → Process → Log → Update → Mark Published → Loop back
        "Merge Platform Results": {
            "main": [[{"node": "Process Results", "type": "main", "index": 0}]],
        },
        "Process Results": {
            "main": [[{"node": "Store Distribution Log", "type": "main", "index": 0}]],
        },
        "Store Distribution Log": {
            "main": [[{"node": "Update Queue Status", "type": "main", "index": 0}]],
        },
        "Update Queue Status": {
            "main": [[{"node": "Content -> Published", "type": "main", "index": 0}]],
        },
        "Content -> Published": {
            "main": [[{"node": "Loop Over Queue", "type": "main", "index": 0}]],
        },
        "Aggregate Distribution": {
            "main": [[{"node": "Send Distribution Summary", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }

    return connections


# ══════════════════════════════════════════════════════════════
# WORKFLOW ASSEMBLY
# ══════════════════════════════════════════════════════════════

WORKFLOW_DEFS = {
    "wf01": {
        "name": "Marketing Dept - Intelligence & Research (WF-01)",
        "build_nodes": lambda: build_wf01_nodes(),
        "build_connections": lambda: build_wf01_connections(),
    },
    "wf02": {
        "name": "Marketing Dept - Strategy & Planning (WF-02)",
        "build_nodes": lambda: build_wf02_nodes(),
        "build_connections": lambda: build_wf02_connections(),
    },
    "wf03": {
        "name": "Marketing Dept - Content Production (WF-03)",
        "build_nodes": lambda: build_wf03_nodes(),
        "build_connections": lambda: build_wf03_connections(),
    },
    "wf04": {
        "name": "Marketing Dept - Distribution (WF-04)",
        "build_nodes": lambda: build_wf04_nodes(),
        "build_connections": lambda: build_wf04_connections(),
    },
    "combined": {
        "name": "Marketing Dept - All Workflows",
        "build_nodes": lambda: build_combined_nodes(),
        "build_connections": lambda: build_combined_connections(),
    },
}


def build_workflow(wf_id):
    """Assemble a complete workflow JSON."""
    if wf_id not in WORKFLOW_DEFS:
        raise ValueError(f"Unknown workflow: {wf_id}. Valid: {', '.join(WORKFLOW_DEFS.keys())}")

    wf_def = WORKFLOW_DEFS[wf_id]

    # Combined workflow returns (nodes, connections) from build_nodes
    if wf_id == "combined":
        nodes, connections = wf_def["build_nodes"]()
    else:
        nodes = wf_def["build_nodes"]()
        connections = wf_def["build_connections"]()

    return {
        "name": wf_def["name"],
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "staticData": None,
        "meta": {"templateCredsSetupCompleted": True},
        "pinData": {},
        "tags": [],
    }


def save_workflow(wf_id, workflow):
    """Save workflow JSON to file."""
    filenames = {
        "wf01": "wf01_intelligence.json",
        "wf02": "wf02_strategy.json",
        "wf03": "wf03_content_production.json",
        "wf04": "wf04_distribution.json",
        "combined": "combined_all_workflows.json",
    }

    output_dir = Path(__file__).parent.parent / "workflows" / "marketing-dept"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filenames[wf_id]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)

    return output_path


def print_workflow_stats(wf_id, workflow):
    """Print workflow statistics."""
    all_nodes = workflow["nodes"]
    func_nodes = [n for n in all_nodes if n["type"] != "n8n-nodes-base.stickyNote"]
    note_nodes = [n for n in all_nodes if n["type"] == "n8n-nodes-base.stickyNote"]
    conn_count = len(workflow["connections"])

    print(f"  Name: {workflow['name']}")
    print(f"  Nodes: {len(func_nodes)} functional + {len(note_nodes)} sticky notes")
    print(f"  Connections: {conn_count}")


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]
    action = args[0] if args else "build"
    target = args[1] if len(args) > 1 else "all"

    # Add tools dir to path
    sys.path.insert(0, str(Path(__file__).parent))

    print("=" * 60)
    print("MARKETING DEPARTMENT - WORKFLOW BUILDER")
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
    if "REPLACE" in AIRTABLE_BASE_ID:
        print()
        print("WARNING: Airtable IDs not configured!")
        print("  Run setup_marketing_airtable.py first, then set these env vars:")
        print("  - MARKETING_AIRTABLE_BASE_ID")
        print("  - MARKETING_TABLE_CONTENT_CALENDAR")
        print("  - MARKETING_TABLE_CONTENT")
        print("  - MARKETING_TABLE_PUBLISH_QUEUE")
        print("  - MARKETING_TABLE_DISTRIBUTION_LOG")
        print("  - MARKETING_TABLE_SYSTEM_STATE")
        print("  - MARKETING_TABLE_RESEARCH_CONFIG")
        print("  - MARKETING_TABLE_RESEARCH_INSIGHTS")
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
        from config_loader import load_config
        from n8n_client import N8nClient

        config = load_config()
        api_key = config["api_keys"]["n8n"]
        base_url = config["n8n"]["base_url"]

        print(f"\nConnecting to {base_url}...")

        with N8nClient(
            base_url,
            api_key,
            timeout=config["n8n"].get("timeout_seconds", 30),
            cache_dir=config["paths"]["cache_dir"],
        ) as client:
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
                    # Update existing
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
                    # Create new — only send fields the n8n API accepts
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
                    print(f"  Activated!")

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
    print("  1. Open each workflow in n8n UI to verify node connections")
    print("  2. Verify credential bindings (OpenRouter, Airtable, Gmail, Blotato)")
    print("  3. Seed Content Calendar with test entries")
    print("  4. Test WF-03 with Manual Trigger -> check Airtable for generated content")
    print("  5. Test WF-04 with Manual Trigger -> check platforms for published posts")
    print("  6. Once verified, activate schedule triggers")


if __name__ == "__main__":
    main()
