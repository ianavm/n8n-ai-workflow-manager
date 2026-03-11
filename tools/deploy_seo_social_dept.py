"""
SEO + Social Growth Engine - Workflow Builder & Deployer

Builds all SEO + Social Growth Engine workflows as n8n workflow JSON files,
and optionally deploys them to the n8n instance.

Workflows:
    WF-SCORE: Scoring & Decision Engine (sub-workflow)
    WF-05: Trend & Keyword Discovery (Mon/Thu 6AM SAST)
    WF-06: SEO Content Production (Daily 9:30AM SAST)
    WF-07: Publishing & Scheduling (Daily 10:30AM SAST)
    WF-08: Engagement & Community (Every 30min 5AM-7PM UTC)
    WF-09: Lead Capture & Attribution (Webhook + Daily batch)
    WF-10: SEO Maintenance (Weekly Sun 2AM SAST)
    WF-11: Analytics & Reporting (Weekly Mon 6AM SAST)

Usage:
    python tools/deploy_seo_social_dept.py build              # Build all workflow JSONs
    python tools/deploy_seo_social_dept.py build wf_score     # Build WF-SCORE only
    python tools/deploy_seo_social_dept.py build wf05         # Build WF-05 only
    python tools/deploy_seo_social_dept.py build wf06         # Build WF-06 only
    python tools/deploy_seo_social_dept.py build wf07         # Build WF-07 only
    python tools/deploy_seo_social_dept.py build wf08         # Build WF-08 only
    python tools/deploy_seo_social_dept.py build wf09         # Build WF-09 only
    python tools/deploy_seo_social_dept.py build wf10         # Build WF-10 only
    python tools/deploy_seo_social_dept.py build wf11         # Build WF-11 only
    python tools/deploy_seo_social_dept.py deploy             # Build + Deploy (inactive)
    python tools/deploy_seo_social_dept.py activate           # Build + Deploy + Activate
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

# -- Credential Constants -------------------------------------------------

CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_BLOTATO = {"id": "hhRiqZrWNlqvmYZR", "name": "Blotato AVM"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable account"}
# Google Custom Search API (free alternative to SerpAPI)
# Requires: GOOGLE_PLACES_API_KEY (reused) + GOOGLE_CSE_ID (custom search engine ID)
GOOGLE_CSE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")

# -- Airtable IDs ---------------------------------------------------------

AIRTABLE_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "REPLACE_WITH_BASE_ID")

# SEO-specific tables
TABLE_KEYWORDS = os.getenv("SEO_TABLE_KEYWORDS", "REPLACE_WITH_TABLE_ID")
TABLE_SERP_SNAPSHOTS = os.getenv("SEO_TABLE_SERP_SNAPSHOTS", "REPLACE_WITH_TABLE_ID")
TABLE_ENGAGEMENT_LOG = os.getenv("SEO_TABLE_ENGAGEMENT_LOG", "REPLACE_WITH_TABLE_ID")
TABLE_LEADS = os.getenv("SEO_TABLE_LEADS", "REPLACE_WITH_TABLE_ID")
TABLE_SEO_AUDITS = os.getenv("SEO_TABLE_SEO_AUDITS", "REPLACE_WITH_TABLE_ID")
TABLE_ANALYTICS_SNAPSHOTS = os.getenv("SEO_TABLE_ANALYTICS_SNAPSHOTS", "REPLACE_WITH_TABLE_ID")
TABLE_SCORING_LOG = os.getenv("SEO_TABLE_SCORING_LOG", "REPLACE_WITH_TABLE_ID")
TABLE_CONTENT_TOPICS = os.getenv("SEO_TABLE_CONTENT_TOPICS", "REPLACE_WITH_TABLE_ID")

# Shared marketing tables
TABLE_CONTENT_CALENDAR = os.getenv("MARKETING_TABLE_CONTENT_CALENDAR", "REPLACE_WITH_TABLE_ID")
TABLE_CONTENT = os.getenv("MARKETING_TABLE_CONTENT", "REPLACE_WITH_TABLE_ID")
TABLE_PUBLISH_QUEUE = os.getenv("MARKETING_TABLE_PUBLISH_QUEUE", "REPLACE_WITH_TABLE_ID")
TABLE_DISTRIBUTION_LOG = os.getenv("MARKETING_TABLE_DISTRIBUTION_LOG", "REPLACE_WITH_TABLE_ID")
TABLE_RESEARCH_CONFIG = os.getenv("MARKETING_TABLE_RESEARCH_CONFIG", "REPLACE_WITH_TABLE_ID")

# -- Blotato Account IDs --------------------------------------------------

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

# -- AI Prompts ------------------------------------------------------------

SEO_KEYWORD_CLUSTERING_PROMPT = """You are an SEO & keyword research analyst for AnyVision Media, a digital media and AI automation agency based in South Africa.

## Your Task
Analyze the provided SERP data and trend signals. Cluster keywords by intent and topic, score difficulty, and identify quick-win opportunities.

## Company Context
- Services: AI workflow automation, web development, social media management, real estate tech
- Target audience: South African SMBs looking to automate and scale
- Primary market: Johannesburg, Gauteng, South Africa
- Competitors: Zapier, Make.com, local digital agencies

## Analysis Framework
1. **Keyword Clusters**: Group related keywords by topic and search intent (informational, navigational, transactional)
2. **Difficulty Scoring**: Rate each cluster 1-100 (100 = hardest to rank for)
3. **Opportunity Score**: Rate each cluster 1-100 based on relevance x volume / difficulty
4. **Quick Wins**: Keywords with difficulty < 40 and relevance > 60

## Output Format (JSON only, no markdown, no backticks):
{
  "clusters": [
    {
      "name": "cluster name",
      "keywords": ["kw1", "kw2"],
      "intent": "informational|navigational|transactional",
      "difficulty": 45,
      "opportunity": 72,
      "volume_estimate": "medium",
      "recommended_content_type": "blog|landing_page|social"
    }
  ],
  "quick_wins": [
    {"keyword": "keyword", "difficulty": 30, "opportunity": 80, "suggested_action": "action"}
  ],
  "trends": [
    {"trend": "description", "relevance": 8, "timeframe": "rising|stable|declining"}
  ],
  "summary": "2-3 sentence executive summary"
}

## Rules
- Focus on South African market context (use .co.za domains, ZAR currency references)
- Prioritize keywords relevant to AI automation and digital transformation
- Include at least 3 clusters and 2 quick wins
- Score difficulty honestly based on SERP competition data"""

SEO_CONTENT_BRIEF_PROMPT = """You are an SEO content strategist for AnyVision Media, a digital media and AI automation agency in South Africa.

## Your Task
Generate SEO-optimized content based on the provided brief, target keywords, and content topic data. The content should be ready for multi-platform distribution.

## Company Context
- Brand: AnyVision Media
- Owner: Ian Immelman
- Services: AI workflow automation, web development, social media management
- Target: South African SMBs
- Brand color: #FF6D5A
- Tone: Professional but approachable, tech-savvy, innovation-focused

## Content Requirements
1. Hook: Attention-grabbing opening line (under 100 chars)
2. Body: Main content optimized for the target platform(s)
3. SEO elements: Include target keywords naturally (2-3% density)
4. CTA: Clear call-to-action relevant to the topic
5. Meta: Suggested title tag (under 60 chars) and meta description (under 160 chars)

## Output Format (JSON only, no markdown, no backticks):
{
  "hook": "attention-grabbing first line",
  "body": "main content body with SEO keywords integrated naturally",
  "cta": "call to action",
  "hashtags": "#relevant #hashtags",
  "meta_title": "SEO title tag under 60 chars",
  "meta_description": "Meta description under 160 chars",
  "target_keywords": ["primary", "secondary"],
  "quality_score": 8,
  "word_count": 250
}

## Rules
- Never keyword-stuff; integrate naturally
- Reference South African business context where relevant
- Include at least one data point or statistic
- Make the hook specific and curiosity-driven
- Every piece must provide actionable value"""

SEO_AUDIT_ANALYSIS_PROMPT = """You are a technical SEO auditor for AnyVision Media, a digital media and AI automation agency in South Africa.

## Your Task
Analyze the provided crawl data (page speed, broken links, content structure) and generate actionable SEO recommendations.

## Analysis Areas
1. **Performance**: Page speed scores, Core Web Vitals
2. **Technical**: Broken links, redirect chains, crawl errors
3. **Content**: Thin content, duplicate content, missing meta tags
4. **Mobile**: Mobile-friendliness, responsive issues
5. **Authority**: Internal linking structure, link equity distribution

## Output Format (JSON only, no markdown, no backticks):
{
  "overall_score": 72,
  "issues": [
    {
      "severity": "critical|warning|info",
      "category": "performance|technical|content|mobile|authority",
      "description": "what is wrong",
      "recommendation": "how to fix it",
      "impact": "high|medium|low",
      "effort": "quick_fix|moderate|major"
    }
  ],
  "quick_wins": [
    {"action": "what to do", "expected_impact": "description", "priority": 1}
  ],
  "summary": "2-3 sentence executive summary of site health"
}

## Rules
- Prioritize issues by impact (critical first)
- Include at least 3 actionable quick wins
- Reference South African hosting/CDN context where relevant
- Be specific about recommendations, not generic"""

ENGAGEMENT_REPLY_PROMPT = """You are a community manager for AnyVision Media, a digital media and AI automation agency in South Africa.

## Your Task
Generate suggested replies to social media engagement (comments, mentions, messages) that maintain brand voice and encourage further interaction.

## Brand Voice
- Professional but approachable
- Tech-savvy, innovation-focused
- Helpful and generous with knowledge
- Never dismissive or robotic

## Output Format (JSON only, no markdown, no backticks):
{
  "replies": [
    {
      "platform": "platform name",
      "original_comment": "what they said",
      "suggested_reply": "what we should say",
      "tone": "thankful|helpful|engaging|promotional",
      "priority": "high|medium|low"
    }
  ],
  "engagement_summary": "brief summary of engagement patterns"
}

## Rules
- Keep replies concise (under 200 chars for Twitter, under 500 for others)
- Always acknowledge the person by context, not generic thanks
- Include a follow-up question or CTA when appropriate
- Flag any negative sentiment for human review
- Never promise specific outcomes or guarantees"""

ANALYTICS_INSIGHTS_PROMPT = """You are a digital analytics strategist for AnyVision Media, a digital media and AI automation agency in South Africa.

## Your Task
Analyze the provided KPIs and generate actionable insights and recommendations for the coming week.

## KPI Categories
1. **Content Performance**: Engagement rate, reach, impressions
2. **SEO Health**: Keyword rankings, organic traffic, page speed scores
3. **Lead Generation**: New leads, lead quality scores, conversion rates
4. **Social Growth**: Follower growth, engagement trends, platform performance

## Output Format (JSON only, no markdown, no backticks):
{
  "highlights": [
    {"metric": "name", "value": "current", "change": "+15%", "assessment": "positive|negative|neutral"}
  ],
  "insights": [
    {"finding": "what we discovered", "implication": "what it means", "action": "what to do about it"}
  ],
  "recommendations": [
    {"priority": 1, "action": "specific action", "expected_impact": "description", "timeframe": "this_week|next_week|this_month"}
  ],
  "summary": "3-4 sentence executive summary"
}

## Rules
- Focus on actionable insights, not vanity metrics
- Compare week-over-week where data allows
- Identify both wins and areas for improvement
- Recommendations should be specific and measurable
- South African business context (ZAR, local market trends)"""

MONTHLY_STRATEGY_PROMPT = """You are the Chief Digital Strategist for AnyVision Media, a digital media and AI automation agency in South Africa.

## Your Task
Conduct a deep monthly strategy review based on the provided 30-day performance data. Identify strategic shifts, emerging opportunities, and resource allocation recommendations.

## Strategic Framework
1. **Performance Review**: What worked, what didn't, and why
2. **Market Position**: How we compare to competitors and market trends
3. **Content Strategy**: What content types and topics drive results
4. **Channel Strategy**: Which platforms deliver ROI vs. which need adjustment
5. **Growth Opportunities**: New channels, partnerships, or content formats to explore

## Output Format (JSON only, no markdown, no backticks):
{
  "executive_summary": "5-6 sentence strategic overview",
  "performance_review": {
    "wins": ["win 1", "win 2"],
    "challenges": ["challenge 1", "challenge 2"],
    "surprises": ["unexpected finding"]
  },
  "strategic_recommendations": [
    {
      "priority": 1,
      "recommendation": "detailed recommendation",
      "rationale": "why this matters",
      "resources_needed": "what it takes",
      "expected_outcome": "what we expect to achieve",
      "timeline": "1_week|2_weeks|1_month"
    }
  ],
  "content_adjustments": [
    {"current_approach": "what we do now", "suggested_change": "what to change", "reason": "why"}
  ],
  "channel_recommendations": [
    {"channel": "platform", "current_performance": "assessment", "recommendation": "action"}
  ],
  "kpi_targets_next_month": {
    "engagement_rate": "target",
    "new_leads": "target",
    "content_pieces": "target",
    "seo_score": "target"
  }
}

## Rules
- Be strategic, not tactical (save tactics for weekly reports)
- Reference South African market conditions and trends
- Include at least 3 strategic recommendations ranked by impact
- Be honest about underperforming areas
- Suggest at least one bold, innovative idea"""


def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ==================================================================
# WF-SCORE: SCORING & DECISION ENGINE (Sub-workflow)
# ==================================================================

def build_wf_score_nodes():
    """Build all nodes for the Scoring & Decision Engine sub-workflow."""
    nodes = []

    # -- Execute Workflow Trigger --
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Execute Workflow Trigger",
        "type": "n8n-nodes-base.executeWorkflowTrigger",
        "position": [200, 400],
        "typeVersion": 1.1,
    })

    # -- System Config --
    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "todayDate", "value": "={{ $now.format('yyyy-MM-dd') }}", "type": "string"},
                    {"id": uid(), "name": "companyName", "value": "AnyVision Media", "type": "string"},
                ]
            },
        },
        "id": uid(),
        "name": "System Config",
        "type": "n8n-nodes-base.set",
        "position": [440, 400],
        "typeVersion": 3.4,
    })

    # -- Switch by Entity Type --
    nodes.append({
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "conditions": [
                                {"leftValue": "={{ $json.entity_type }}", "rightValue": "Content",
                                 "operator": {"type": "string", "operation": "equals"}}
                            ]
                        },
                        "renameOutput": True, "outputKey": "Content"
                    },
                    {
                        "conditions": {
                            "conditions": [
                                {"leftValue": "={{ $json.entity_type }}", "rightValue": "Lead",
                                 "operator": {"type": "string", "operation": "equals"}}
                            ]
                        },
                        "renameOutput": True, "outputKey": "Lead"
                    },
                    {
                        "conditions": {
                            "conditions": [
                                {"leftValue": "={{ $json.entity_type }}", "rightValue": "Keyword",
                                 "operator": {"type": "string", "operation": "equals"}}
                            ]
                        },
                        "renameOutput": True, "outputKey": "Keyword"
                    },
                    {
                        "conditions": {
                            "conditions": [
                                {"leftValue": "={{ $json.entity_type }}", "rightValue": "Page",
                                 "operator": {"type": "string", "operation": "equals"}}
                            ]
                        },
                        "renameOutput": True, "outputKey": "Page"
                    },
                ]
            }
        },
        "id": uid(),
        "name": "Route by Type",
        "type": "n8n-nodes-base.switch",
        "position": [680, 400],
        "typeVersion": 3.2,
    })

    # -- Content Score --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const metrics = $json.metrics || {};\n"
                "// Content scoring: engagement (40%), reach (25%), quality (20%), SEO (15%)\n"
                "const engagementScore = Math.min(100, (metrics.likes || 0) * 2 + (metrics.comments || 0) * 5 + (metrics.shares || 0) * 10);\n"
                "const reachScore = Math.min(100, (metrics.impressions || 0) / 100);\n"
                "const qualityScore = Math.min(100, (metrics.quality_rating || 5) * 10);\n"
                "const seoScore = Math.min(100, (metrics.keyword_density || 0) * 20 + (metrics.has_meta || 0) * 30 + (metrics.word_count || 0) / 10);\n"
                "\n"
                "const composite = Math.round(\n"
                "  engagementScore * 0.40 +\n"
                "  reachScore * 0.25 +\n"
                "  qualityScore * 0.20 +\n"
                "  seoScore * 0.15\n"
                ");\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    entity_type: 'Content',\n"
                "    entity_id: $json.entity_id,\n"
                "    scores: { engagement: engagementScore, reach: reachScore, quality: qualityScore, seo: seoScore },\n"
                "    composite_score: composite,\n"
                "    grade: composite >= 80 ? 'A' : composite >= 60 ? 'B' : composite >= 40 ? 'C' : 'D',\n"
                "    scored_at: $now.format('yyyy-MM-dd HH:mm:ss')\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Score Content",
        "type": "n8n-nodes-base.code",
        "position": [960, 200],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # -- Lead Score --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const metrics = $json.metrics || {};\n"
                "// Lead scoring: engagement (30%), fit (30%), recency (20%), source (20%)\n"
                "const engagementScore = Math.min(100, (metrics.page_views || 0) * 5 + (metrics.email_opens || 0) * 10 + (metrics.clicks || 0) * 15);\n"
                "const fitScore = Math.min(100, (metrics.company_size_match || 0) * 25 + (metrics.industry_match || 0) * 25 + (metrics.location_match || 0) * 25 + (metrics.budget_match || 0) * 25);\n"
                "const daysSince = metrics.days_since_last_activity || 30;\n"
                "const recencyScore = Math.max(0, 100 - daysSince * 3);\n"
                "const sourceScores = { organic: 80, referral: 70, social: 60, paid: 50, direct: 40 };\n"
                "const sourceScore = sourceScores[metrics.source] || 30;\n"
                "\n"
                "const composite = Math.round(\n"
                "  engagementScore * 0.30 +\n"
                "  fitScore * 0.30 +\n"
                "  recencyScore * 0.20 +\n"
                "  sourceScore * 0.20\n"
                ");\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    entity_type: 'Lead',\n"
                "    entity_id: $json.entity_id,\n"
                "    scores: { engagement: engagementScore, fit: fitScore, recency: recencyScore, source: sourceScore },\n"
                "    composite_score: composite,\n"
                "    grade: composite >= 80 ? 'Hot' : composite >= 50 ? 'Warm' : 'Cold',\n"
                "    scored_at: $now.format('yyyy-MM-dd HH:mm:ss')\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Score Lead",
        "type": "n8n-nodes-base.code",
        "position": [960, 400],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # -- Keyword Score --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const metrics = $json.metrics || {};\n"
                "// Keyword scoring: opportunity (35%), relevance (30%), difficulty_inv (20%), trend (15%)\n"
                "const relevanceScore = Math.min(100, (metrics.relevance || 5) * 10);\n"
                "const difficultyInv = Math.max(0, 100 - (metrics.difficulty || 50));\n"
                "const trendScore = metrics.trend === 'rising' ? 90 : metrics.trend === 'stable' ? 50 : 20;\n"
                "const opportunityScore = Math.min(100, (metrics.search_volume || 0) / 50 + difficultyInv * 0.5);\n"
                "\n"
                "const composite = Math.round(\n"
                "  opportunityScore * 0.35 +\n"
                "  relevanceScore * 0.30 +\n"
                "  difficultyInv * 0.20 +\n"
                "  trendScore * 0.15\n"
                ");\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    entity_type: 'Keyword',\n"
                "    entity_id: $json.entity_id,\n"
                "    scores: { opportunity: opportunityScore, relevance: relevanceScore, difficulty_inv: difficultyInv, trend: trendScore },\n"
                "    composite_score: composite,\n"
                "    grade: composite >= 70 ? 'Target' : composite >= 40 ? 'Monitor' : 'Ignore',\n"
                "    scored_at: $now.format('yyyy-MM-dd HH:mm:ss')\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Score Keyword",
        "type": "n8n-nodes-base.code",
        "position": [960, 600],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # -- Page Score --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const metrics = $json.metrics || {};\n"
                "// Page scoring: speed (30%), seo (30%), content (20%), links (20%)\n"
                "const speedScore = Math.min(100, (metrics.pagespeed_score || 50));\n"
                "const seoScore = Math.min(100, (metrics.has_title || 0) * 20 + (metrics.has_meta || 0) * 20 + (metrics.has_h1 || 0) * 20 + (metrics.has_schema || 0) * 20 + (metrics.is_mobile_friendly || 0) * 20);\n"
                "const contentScore = Math.min(100, (metrics.word_count || 0) / 20 + (metrics.has_images || 0) * 20 + (metrics.readability || 50));\n"
                "const linkScore = Math.min(100, 100 - (metrics.broken_links || 0) * 20 + (metrics.internal_links || 0) * 5);\n"
                "\n"
                "const composite = Math.round(\n"
                "  speedScore * 0.30 +\n"
                "  seoScore * 0.30 +\n"
                "  contentScore * 0.20 +\n"
                "  linkScore * 0.20\n"
                ");\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    entity_type: 'Page',\n"
                "    entity_id: $json.entity_id,\n"
                "    scores: { speed: speedScore, seo: seoScore, content: contentScore, links: linkScore },\n"
                "    composite_score: composite,\n"
                "    grade: composite >= 80 ? 'Healthy' : composite >= 60 ? 'Needs Work' : composite >= 40 ? 'Poor' : 'Critical',\n"
                "    scored_at: $now.format('yyyy-MM-dd HH:mm:ss')\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Score Page",
        "type": "n8n-nodes-base.code",
        "position": [960, 800],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # -- Merge Scores --
    nodes.append({
        "parameters": {"mode": "append"},
        "id": uid(),
        "name": "Merge Scores",
        "type": "n8n-nodes-base.merge",
        "position": [1240, 400],
        "typeVersion": 3,
    })

    # -- Log to Scoring Log --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SCORING_LOG},
            "columns": {
                "value": {
                    "Entity Type": "={{ $json.entity_type }}",
                    "Entity ID": "={{ $json.entity_id }}",
                    "Composite Score": "={{ $json.composite_score }}",
                    "Grade": "={{ $json.grade }}",
                    "Score Details": "={{ JSON.stringify($json.scores) }}",
                    "Scored At": "={{ $json.scored_at }}",
                },
                "schema": [
                    {"id": "Entity Type", "type": "string", "display": True, "displayName": "Entity Type"},
                    {"id": "Entity ID", "type": "string", "display": True, "displayName": "Entity ID"},
                    {"id": "Composite Score", "type": "number", "display": True, "displayName": "Composite Score"},
                    {"id": "Grade", "type": "string", "display": True, "displayName": "Grade"},
                    {"id": "Score Details", "type": "string", "display": True, "displayName": "Score Details"},
                    {"id": "Scored At", "type": "string", "display": True, "displayName": "Scored At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Score",
        "type": "n8n-nodes-base.airtable",
        "position": [1480, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Error Handling --
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
            "subject": "SEO/SOCIAL ERROR - Scoring Engine",
            "emailType": "html",
            "message": "=<h2>Scoring Engine Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 880],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Notes --
    notes = [
        {
            "content": "## WF-SCORE: Scoring & Decision Engine\n\n**Type:** Sub-workflow (called by other workflows)\n**Purpose:** Computes weighted scores (0-100) for Content, Lead, Keyword, and Page entities.\n**Output:** Composite score + grade logged to Scoring Log table.",
            "position": [140, 220], "width": 420, "height": 160,
        },
    ]
    for i, note in enumerate(notes):
        nodes.append({
            "parameters": {"content": note["content"], "height": note.get("height", 140), "width": note.get("width", 340)},
            "id": f"wf-score-note-{i+1}",
            "type": "n8n-nodes-base.stickyNote",
            "position": note["position"],
            "typeVersion": 1,
            "name": f"Note {i+1}",
        })

    return nodes


def build_wf_score_connections():
    """Build connections for the Scoring Engine sub-workflow."""
    return {
        "Execute Workflow Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "System Config": {
            "main": [[{"node": "Route by Type", "type": "main", "index": 0}]],
        },
        "Route by Type": {
            "main": [
                [{"node": "Score Content", "type": "main", "index": 0}],
                [{"node": "Score Lead", "type": "main", "index": 0}],
                [{"node": "Score Keyword", "type": "main", "index": 0}],
                [{"node": "Score Page", "type": "main", "index": 0}],
            ],
        },
        "Score Content": {
            "main": [[{"node": "Merge Scores", "type": "main", "index": 0}]],
        },
        "Score Lead": {
            "main": [[{"node": "Merge Scores", "type": "main", "index": 1}]],
        },
        "Score Keyword": {
            "main": [[{"node": "Merge Scores", "type": "main", "index": 2}]],
        },
        "Score Page": {
            "main": [[{"node": "Merge Scores", "type": "main", "index": 3}]],
        },
        "Merge Scores": {
            "main": [[{"node": "Log Score", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }


# ==================================================================
# WF-05: TREND & KEYWORD DISCOVERY
# ==================================================================

def build_wf05_nodes():
    """Build all nodes for the Trend & Keyword Discovery workflow."""
    nodes = []

    # -- Triggers --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "0 4 * * 1,4"}]
            }
        },
        "id": uid(),
        "name": "Mon/Thu 6AM SAST",
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

    # -- System Config --
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

    # -- Read Keywords --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_KEYWORDS},
            "filterByFormula": "=({Status} = 'Active')",
        },
        "id": uid(),
        "name": "Read Keywords",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 400],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Read Research Config --
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
        "position": [680, 600],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Scrape Trends --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const keywordItems = $('Read Keywords').all();\n"
                "const configItems = $('Read Research Config').all();\n"
                "const crypto = require('crypto');\n"
                "\n"
                "// Extract competitor URLs from research config\n"
                "const competitors = configItems.filter(i => i.json.Type === 'competitor').map(c => ({ key: c.json.Key, url: c.json.URL, label: c.json.Label }));\n"
                "const rssFeeds = configItems.filter(i => i.json.Type === 'rss_feed').map(r => ({ key: r.json.Key, url: r.json.URL, label: r.json.Label }));\n"
                "\n"
                "// Scrape competitor pages\n"
                "const competitorResults = [];\n"
                "for (const comp of competitors.slice(0, 5)) {\n"
                "  try {\n"
                "    const response = await this.helpers.httpRequest({\n"
                "      method: 'GET', url: comp.url, timeout: 10000,\n"
                "      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; AnyVisionBot/1.0)' },\n"
                "      returnFullResponse: true\n"
                "    });\n"
                "    const html = typeof response === 'string' ? response : (response.body || '');\n"
                "    const text = html.replace(/<script[^>]*>[\\s\\S]*?<\\/script>/gi, '')\n"
                "      .replace(/<style[^>]*>[\\s\\S]*?<\\/style>/gi, '')\n"
                "      .replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim().substring(0, 2000);\n"
                "    competitorResults.push({ source: comp.label, content: text, success: true });\n"
                "  } catch(e) {\n"
                "    competitorResults.push({ source: comp.label, content: `Failed: ${e.message}`, success: false });\n"
                "  }\n"
                "  await new Promise(r => setTimeout(r, 2000));\n"
                "}\n"
                "\n"
                "// Parse RSS feeds\n"
                "const rssResults = [];\n"
                "for (const feed of rssFeeds.slice(0, 5)) {\n"
                "  try {\n"
                "    const xml = await this.helpers.httpRequest({ method: 'GET', url: feed.url, timeout: 10000 });\n"
                "    const itemRegex = /<item[^>]*>([\\s\\S]*?)<\\/item>/gi;\n"
                "    const titleRegex = /<title[^>]*>(?:<!\\[CDATA\\[)?(.*?)(?:\\]\\]>)?<\\/title>/i;\n"
                "    let match, count = 0;\n"
                "    while ((match = itemRegex.exec(xml)) !== null && count < 5) {\n"
                "      const title = (titleRegex.exec(match[1]) || [])[1] || '';\n"
                "      rssResults.push({ source: feed.label, title: title.trim(), success: true });\n"
                "      count++;\n"
                "    }\n"
                "  } catch(e) {\n"
                "    rssResults.push({ source: feed.label, title: `Failed: ${e.message}`, success: false });\n"
                "  }\n"
                "  await new Promise(r => setTimeout(r, 1000));\n"
                "}\n"
                "\n"
                "// Build keywords list for SERP query\n"
                "const keywords = keywordItems.map(k => k.json.Keyword || k.json.Label || '').filter(Boolean);\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    competitorData: competitorResults,\n"
                "    rssData: rssResults,\n"
                "    keywords: keywords.slice(0, 20),\n"
                "    serpQuery: keywords.slice(0, 5).join(' OR '),\n"
                "    totalSources: competitorResults.length + rssResults.length\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Scrape Trends",
        "type": "n8n-nodes-base.code",
        "position": [960, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # -- Google Custom Search API (free SerpAPI alternative) --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": f"https://www.googleapis.com/customsearch/v1",
            "authentication": "none",
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {"name": "q", "value": "={{ $json.serpQuery }}"},
                    {"name": "key", "value": GOOGLE_CSE_API_KEY},
                    {"name": "cx", "value": GOOGLE_CSE_ID},
                    {"name": "gl", "value": "za"},
                    {"name": "hl", "value": "en"},
                    {"name": "num", "value": "10"},
                ]
            },
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Google Search",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1200, 500],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 3000,
    })

    # -- AI Keyword Clustering --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={\n"
                "  \"model\": \"{{ $('System Config').first().json.aiModel }}\",\n"
                "  \"max_tokens\": 1500,\n"
                "  \"temperature\": 0.5,\n"
                "  \"messages\": [\n"
                "    {\n"
                "      \"role\": \"system\",\n"
                f"      \"content\": {json.dumps(SEO_KEYWORD_CLUSTERING_PROMPT)}\n"
                "    },\n"
                "    {\n"
                "      \"role\": \"user\",\n"
                "      \"content\": {{ JSON.stringify('SERP DATA: ' + JSON.stringify($json.items || []).substring(0, 3000) + '\\n\\nTREND DATA: ' + JSON.stringify($('Scrape Trends').first().json.competitorData || []).substring(0, 2000) + '\\n\\nRSS: ' + JSON.stringify($('Scrape Trends').first().json.rssData || []).substring(0, 1000) + '\\n\\nTARGET KEYWORDS: ' + ($('Scrape Trends').first().json.keywords || []).join(', ')) }}\n"
                "    }\n"
                "  ]\n"
                "}",
            "options": {"timeout": 60000},
        },
        "id": uid(),
        "name": "AI Keyword Clustering",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1440, 500],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 3000,
    })

    # -- Parse AI Response --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const trendData = $('Scrape Trends').first().json;\n"
                "const config = $('System Config').first().json;\n"
                "\n"
                "let analysis;\n"
                "try {\n"
                "  const content = input.choices[0].message.content;\n"
                "  const cleaned = content.replace(/```json\\n?/g, '').replace(/```\\n?/g, '').trim();\n"
                "  const jsonMatch = cleaned.match(/\\{[\\s\\S]*\\}/);\n"
                "  analysis = JSON.parse(jsonMatch ? jsonMatch[0] : cleaned);\n"
                "} catch(e) {\n"
                "  analysis = {\n"
                "    clusters: [{ name: 'AI automation', keywords: ['ai automation', 'workflow automation'], intent: 'informational', difficulty: 50, opportunity: 60, volume_estimate: 'medium', recommended_content_type: 'blog' }],\n"
                "    quick_wins: [{ keyword: 'n8n automation south africa', difficulty: 25, opportunity: 75, suggested_action: 'Create targeted landing page' }],\n"
                "    trends: [{ trend: 'AI adoption growing in SA SMBs', relevance: 8, timeframe: 'rising' }],\n"
                "    summary: 'Fallback analysis: AI automation remains a growing opportunity in South Africa.'\n"
                "  };\n"
                "}\n"
                "\n"
                "// Build keyword records for upsert\n"
                "const keywordRecords = [];\n"
                "for (const cluster of (analysis.clusters || [])) {\n"
                "  for (const kw of (cluster.keywords || [])) {\n"
                "    keywordRecords.push({\n"
                "      keyword: kw,\n"
                "      cluster: cluster.name,\n"
                "      intent: cluster.intent,\n"
                "      difficulty: cluster.difficulty,\n"
                "      opportunity: cluster.opportunity,\n"
                "      volume: cluster.volume_estimate,\n"
                "      contentType: cluster.recommended_content_type\n"
                "    });\n"
                "  }\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    analysis: analysis,\n"
                "    keywordRecords: keywordRecords,\n"
                "    serpRawCount: (input.items || []).length,\n"
                "    tokensUsed: input.usage ? input.usage.total_tokens : 0,\n"
                "    week: config.weekNumber,\n"
                "    date: config.todayDate\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Parse Clustering",
        "type": "n8n-nodes-base.code",
        "position": [1680, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # -- Format Keywords for Upsert --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const data = $input.first().json;\n"
                "const records = data.keywordRecords || [];\n"
                "if (records.length === 0) {\n"
                "  return { json: { Keyword: 'no-keywords-found', Cluster: 'none', Intent: 'none', Difficulty: 0, Opportunity: 0, Volume: 'none', 'Content Type': 'none', Status: 'Active', 'Last Updated': data.date } };\n"
                "}\n"
                "return records.map(r => ({\n"
                "  json: {\n"
                "    Keyword: r.keyword,\n"
                "    Cluster: r.cluster,\n"
                "    Intent: r.intent,\n"
                "    Difficulty: r.difficulty,\n"
                "    Opportunity: r.opportunity,\n"
                "    Volume: r.volume,\n"
                "    'Content Type': r.contentType,\n"
                "    Status: 'Active',\n"
                "    'Last Updated': data.date\n"
                "  }\n"
                "}));"
            ),
        },
        "id": uid(),
        "name": "Format Keywords",
        "type": "n8n-nodes-base.code",
        "position": [1920, 400],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # -- Upsert Keywords --
    nodes.append({
        "parameters": {
            "operation": "upsert",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_KEYWORDS},
            "columns": {
                "value": {
                    "Keyword": "={{ $json.Keyword }}",
                    "Cluster": "={{ $json.Cluster }}",
                    "Intent": "={{ $json.Intent }}",
                    "Difficulty": "={{ $json.Difficulty }}",
                    "Opportunity": "={{ $json.Opportunity }}",
                    "Volume": "={{ $json.Volume }}",
                    "Content Type": "={{ $json['Content Type'] }}",
                    "Status": "={{ $json.Status }}",
                    "Last Updated": "={{ $json['Last Updated'] }}",
                },
                "schema": [
                    {"id": "Keyword", "type": "string", "display": True, "displayName": "Keyword"},
                    {"id": "Cluster", "type": "string", "display": True, "displayName": "Cluster"},
                    {"id": "Intent", "type": "string", "display": True, "displayName": "Intent"},
                    {"id": "Difficulty", "type": "number", "display": True, "displayName": "Difficulty"},
                    {"id": "Opportunity", "type": "number", "display": True, "displayName": "Opportunity"},
                    {"id": "Volume", "type": "string", "display": True, "displayName": "Volume"},
                    {"id": "Content Type", "type": "string", "display": True, "displayName": "Content Type"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Last Updated", "type": "string", "display": True, "displayName": "Last Updated"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Keyword"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Upsert Keywords",
        "type": "n8n-nodes-base.airtable",
        "position": [2160, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Store SERP Snapshot --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SERP_SNAPSHOTS},
            "columns": {
                "value": {
                    "Query": "={{ $('Scrape Trends').first().json.serpQuery }}",
                    "Date": "={{ $('System Config').first().json.todayDate }}",
                    "Week": "={{ $('System Config').first().json.weekNumber }}",
                    "Results Count": "={{ $('Parse Clustering').first().json.serpRawCount }}",
                    "Clusters": "={{ JSON.stringify($('Parse Clustering').first().json.analysis.clusters || []) }}",
                    "Quick Wins": "={{ JSON.stringify($('Parse Clustering').first().json.analysis.quick_wins || []) }}",
                    "Summary": "={{ $('Parse Clustering').first().json.analysis.summary || '' }}",
                },
                "schema": [
                    {"id": "Query", "type": "string", "display": True, "displayName": "Query"},
                    {"id": "Date", "type": "string", "display": True, "displayName": "Date"},
                    {"id": "Week", "type": "string", "display": True, "displayName": "Week"},
                    {"id": "Results Count", "type": "number", "display": True, "displayName": "Results Count"},
                    {"id": "Clusters", "type": "string", "display": True, "displayName": "Clusters"},
                    {"id": "Quick Wins", "type": "string", "display": True, "displayName": "Quick Wins"},
                    {"id": "Summary", "type": "string", "display": True, "displayName": "Summary"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Store SERP Snapshot",
        "type": "n8n-nodes-base.airtable",
        "position": [2160, 600],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Build Report --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const data = $('Parse Clustering').first().json;\n"
                "const analysis = data.analysis || {};\n"
                "const now = new Date().toLocaleString('en-ZA', { timeZone: 'Africa/Johannesburg' });\n"
                "\n"
                "const clustersHtml = (analysis.clusters || []).map(c =>\n"
                "  `<li><strong>${c.name}</strong> (${c.intent}) - Difficulty: ${c.difficulty}, Opportunity: ${c.opportunity}<br>Keywords: ${(c.keywords || []).join(', ')}</li>`\n"
                ").join('\\n');\n"
                "\n"
                "const winsHtml = (analysis.quick_wins || []).map(w =>\n"
                "  `<li><strong>${w.keyword}</strong> - Difficulty: ${w.difficulty}, Opportunity: ${w.opportunity}<br>${w.suggested_action}</li>`\n"
                ").join('\\n');\n"
                "\n"
                "const trendsHtml = (analysis.trends || []).map(t =>\n"
                "  `<li>${t.trend} (relevance: ${t.relevance}/10, ${t.timeframe})</li>`\n"
                ").join('\\n');\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    subject: `SEO Keyword Discovery: ${(analysis.clusters || []).length} clusters, ${(analysis.quick_wins || []).length} quick wins`,\n"
                "    body: [\n"
                "      '<h2 style=\"color:#FF6D5A\">Trend & Keyword Discovery Report</h2>',\n"
                "      `<p><strong>Date:</strong> ${now}</p>`,\n"
                "      `<p><strong>Sources analyzed:</strong> ${data.serpRawCount || 0} SERP results</p>`,\n"
                "      '<hr>',\n"
                "      `<p><em>${analysis.summary || 'No summary available'}</em></p>`,\n"
                "      '<h3>Keyword Clusters</h3>',\n"
                "      `<ul>${clustersHtml || '<li>None identified</li>'}</ul>`,\n"
                "      '<h3>Quick Wins</h3>',\n"
                "      `<ul>${winsHtml || '<li>None identified</li>'}</ul>`,\n"
                "      '<h3>Trends</h3>',\n"
                "      `<ul>${trendsHtml || '<li>None identified</li>'}</ul>`,\n"
                "      '<hr>',\n"
                "      `<p><strong>Tokens Used:</strong> ${(data.tokensUsed || 0).toLocaleString()}</p>`,\n"
                "    ].join('\\n')\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Build Report",
        "type": "n8n-nodes-base.code",
        "position": [2400, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # -- Send Report --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "={{ $json.subject }}",
            "emailType": "html",
            "message": "={{ $json.body }}",
            "options": {},
        },
        "id": uid(),
        "name": "Send Discovery Report",
        "type": "n8n-nodes-base.gmail",
        "position": [2640, 500],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # -- Error Handling --
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
            "subject": "SEO/SOCIAL ERROR - {{ $json.workflow.name }}",
            "emailType": "html",
            "message": "=<h2>SEO + Social Engine Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 880],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Notes --
    notes = [
        {
            "content": "## WF-05: Trend & Keyword Discovery\n\n**Schedule:** Mon/Thu 6AM SAST\n**Purpose:** Scrape competitors, fetch SERP data via Google Custom Search API, AI keyword clustering.\n**Output:** Keywords table updated + SERP snapshots + discovery email.",
            "position": [140, 220], "width": 420, "height": 160,
        },
    ]
    for i, note in enumerate(notes):
        nodes.append({
            "parameters": {"content": note["content"], "height": note.get("height", 140), "width": note.get("width", 340)},
            "id": f"wf05-note-{i+1}",
            "type": "n8n-nodes-base.stickyNote",
            "position": note["position"],
            "typeVersion": 1,
            "name": f"Note {i+1}",
        })

    return nodes


def build_wf05_connections():
    """Build connections for the Trend & Keyword Discovery workflow."""
    return {
        "Mon/Thu 6AM SAST": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "System Config": {
            "main": [[
                {"node": "Read Keywords", "type": "main", "index": 0},
                {"node": "Read Research Config", "type": "main", "index": 0},
            ]],
        },
        "Read Keywords": {
            "main": [[{"node": "Scrape Trends", "type": "main", "index": 0}]],
        },
        "Read Research Config": {
            "main": [[{"node": "Scrape Trends", "type": "main", "index": 0}]],
        },
        "Scrape Trends": {
            "main": [[{"node": "Google Search", "type": "main", "index": 0}]],
        },
        "Google Search": {
            "main": [[{"node": "AI Keyword Clustering", "type": "main", "index": 0}]],
        },
        "AI Keyword Clustering": {
            "main": [[{"node": "Parse Clustering", "type": "main", "index": 0}]],
        },
        "Parse Clustering": {
            "main": [[
                {"node": "Format Keywords", "type": "main", "index": 0},
                {"node": "Store SERP Snapshot", "type": "main", "index": 0},
            ]],
        },
        "Format Keywords": {
            "main": [[{"node": "Upsert Keywords", "type": "main", "index": 0}]],
        },
        "Upsert Keywords": {
            "main": [[{"node": "Build Report", "type": "main", "index": 0}]],
        },
        "Store SERP Snapshot": {
            "main": [[{"node": "Build Report", "type": "main", "index": 0}]],
        },
        "Build Report": {
            "main": [[{"node": "Send Discovery Report", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }



# ==================================================================
# WF-06: SEO CONTENT PRODUCTION
# ==================================================================

def build_wf06_nodes():
    """Build all nodes for the SEO Content Production workflow."""
    nodes = []

    # -- Triggers --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "30 7 * * *"}]
            }
        },
        "id": uid(),
        "name": "Daily 9:30AM SAST",
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

    # -- System Config --
    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "todayDate", "value": "={{ $now.format('yyyy-MM-dd') }}", "type": "string"},
                    {"id": uid(), "name": "aiModel", "value": "anthropic/claude-sonnet-4-20250514", "type": "string"},
                    {"id": uid(), "name": "companyName", "value": "AnyVision Media", "type": "string"},
                    {"id": uid(), "name": "ownerName", "value": "Ian Immelman", "type": "string"},
                ]
            },
        },
        "id": uid(),
        "name": "System Config",
        "type": "n8n-nodes-base.set",
        "position": [440, 500],
        "typeVersion": 3.4,
    })

    # -- Read Content Calendar --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT_CALENDAR},
            "filterByFormula": "=AND({Status} = 'Planned', IS_SAME({Date}, '{{ $json.todayDate }}', 'day'))",
            "returnAll": False,
            "limit": 5,
            "sort": {"property": [{"field": "Date", "direction": "asc"}]},
        },
        "id": uid(),
        "name": "Read Content Calendar",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 400],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Read Keywords --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_KEYWORDS},
            "filterByFormula": "=({Status} = 'Active')",
        },
        "id": uid(),
        "name": "Read Keywords",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 560],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Read Content Topics --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT_TOPICS},
            "filterByFormula": "=({Status} = 'Active')",
        },
        "id": uid(),
        "name": "Read Content Topics",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 720],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Has Items? --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "strict"},
                "conditions": [
                    {"operator": {"type": "object", "operation": "notEmpty", "singleValue": True}, "leftValue": "={{ $json.id }}", "rightValue": ""},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Has Calendar Items?",
        "type": "n8n-nodes-base.if",
        "position": [960, 500],
        "typeVersion": 2.2,
    })

    # -- Loop Over Content --
    nodes.append({
        "parameters": {"options": {"batchSize": 1}},
        "id": uid(),
        "name": "Loop Over Content",
        "type": "n8n-nodes-base.splitInBatches",
        "position": [1200, 400],
        "typeVersion": 3,
    })

    # -- Build SEO Brief --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const calendarItem = $json;\n"
                "let keywords = [];\n"
                "try { keywords = $('Read Keywords').all().map(k => k.json.Keyword || k.json.Label).filter(Boolean).slice(0, 10); } catch(e) {}\n"
                "let topics = [];\n"
                "try { topics = $('Read Content Topics').all().map(t => t.json.Topic || t.json.Name).filter(Boolean).slice(0, 5); } catch(e) {}\n"
                "\n"
                "const brief = [\n"
                "  `CONTENT BRIEF`,\n"
                "  `Topic: ${calendarItem.Topic || calendarItem.Title || 'General content'}`,\n"
                "  `Platform: ${Array.isArray(calendarItem.Platform) ? calendarItem.Platform.join(', ') : calendarItem.Platform || 'all'}`,\n"
                "  `Brief: ${calendarItem.Brief || 'Create engaging, SEO-optimized content'}`,\n"
                "  `Target Keywords: ${keywords.join(', ')}`,\n"
                "  `Related Topics: ${topics.join(', ')}`,\n"
                "  `Content Type: ${calendarItem['Content Type'] || 'social_post'}`,\n"
                "  `Date: ${calendarItem.Date || $('System Config').first().json.todayDate}`,\n"
                "].join('\\n');\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    seoBrief: brief,\n"
                "    calendarId: calendarItem.id,\n"
                "    topic: calendarItem.Topic || calendarItem.Title,\n"
                "    platform: calendarItem.Platform,\n"
                "    keywords: keywords\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Build SEO Brief",
        "type": "n8n-nodes-base.code",
        "position": [1440, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # -- AI Content Generation --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={\n"
                "  \"model\": \"{{ $('System Config').first().json.aiModel }}\",\n"
                "  \"max_tokens\": 2000,\n"
                "  \"temperature\": 0.7,\n"
                "  \"messages\": [\n"
                "    {\n"
                "      \"role\": \"system\",\n"
                f"      \"content\": {json.dumps(SEO_CONTENT_BRIEF_PROMPT)}\n"
                "    },\n"
                "    {\n"
                "      \"role\": \"user\",\n"
                "      \"content\": {{ JSON.stringify($json.seoBrief) }}\n"
                "    }\n"
                "  ]\n"
                "}",
            "options": {"timeout": 60000},
        },
        "id": uid(),
        "name": "AI Content Generation",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1680, 500],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 3000,
    })

    # -- Parse & Quality Gate --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const briefData = $('Build SEO Brief').first().json;\n"
                "\n"
                "let parsed;\n"
                "try {\n"
                "  const content = input.choices[0].message.content;\n"
                "  const cleaned = content.replace(/```json\\n?/g, '').replace(/```\\n?/g, '').trim();\n"
                "  const jsonMatch = cleaned.match(/\\{[\\s\\S]*\\}/);\n"
                "  parsed = JSON.parse(jsonMatch ? jsonMatch[0] : cleaned);\n"
                "} catch(e) {\n"
                "  parsed = {\n"
                "    hook: `Discover how ${briefData.topic || 'automation'} can transform your business`,\n"
                "    body: `At AnyVision Media, we help businesses automate and scale.`,\n"
                "    cta: 'Want to learn more? Drop us a message.',\n"
                "    hashtags: '#automation #AI #business #SouthAfrica',\n"
                "    meta_title: (briefData.topic || 'AnyVision Media').substring(0, 60),\n"
                "    meta_description: 'Learn how AnyVision Media helps South African businesses automate.',\n"
                "    target_keywords: briefData.keywords || [],\n"
                "    quality_score: 5,\n"
                "    word_count: 100\n"
                "  };\n"
                "}\n"
                "\n"
                "let score = parsed.quality_score || 5;\n"
                "const fullText = `${parsed.hook || ''} ${parsed.body || ''} ${parsed.cta || ''}`;\n"
                "if (!parsed.quality_score) {\n"
                "  if (parsed.hook && parsed.hook.length > 10) score += 1;\n"
                "  if (parsed.body && parsed.body.length > 100) score += 1;\n"
                "  if (parsed.meta_title) score += 1;\n"
                "  if (parsed.meta_description) score += 1;\n"
                "  if (fullText.length > 200) score += 1;\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    parsedContent: parsed,\n"
                "    qualityScore: Math.min(10, score),\n"
                "    passesQualityGate: score >= 6,\n"
                "    calendarId: briefData.calendarId,\n"
                "    topic: briefData.topic,\n"
                "    platform: briefData.platform,\n"
                "    tokensUsed: input.usage ? input.usage.total_tokens : 0\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Parse & Quality Gate",
        "type": "n8n-nodes-base.code",
        "position": [1920, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # -- Quality Check --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "strict"},
                "conditions": [
                    {"operator": {"type": "number", "operation": "gte"}, "leftValue": "={{ $json.qualityScore }}", "rightValue": 6},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Quality Pass?",
        "type": "n8n-nodes-base.if",
        "position": [2160, 500],
        "typeVersion": 2.2,
    })

    # -- Hook Optimizer --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={\n"
                "  \"model\": \"{{ $('System Config').first().json.aiModel }}\",\n"
                "  \"max_tokens\": 300,\n"
                "  \"temperature\": 0.8,\n"
                "  \"messages\": [\n"
                "    {\"role\": \"system\", \"content\": \"You are a social media hook optimization expert. Given a hook and topic, generate 3 alternative hooks. Output JSON: {variations: [str], scores: [int], best_index: int}\"},\n"
                "    {\"role\": \"user\", \"content\": \"Hook: {{ $json.parsedContent.hook }}\\nTopic: {{ $json.topic }}\"}\n"
                "  ]\n"
                "}",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Hook Optimizer",
        "type": "n8n-nodes-base.httpRequest",
        "position": [2400, 400],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 2000,
    })

    # -- Build Final Content --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const hookInput = $input.first().json;\n"
                "const postData = $('Parse & Quality Gate').first().json;\n"
                "const parsed = postData.parsedContent;\n"
                "\n"
                "let bestHook = parsed.hook;\n"
                "try {\n"
                "  const content = hookInput.choices[0].message.content;\n"
                "  const cleaned = content.replace(/```json\\n?/g, '').replace(/```\\n?/g, '').trim();\n"
                "  const jsonMatch = cleaned.match(/\\{[\\s\\S]*\\}/);\n"
                "  const hookData = JSON.parse(jsonMatch ? jsonMatch[0] : cleaned);\n"
                "  bestHook = hookData.variations[hookData.best_index || 0] || parsed.hook;\n"
                "} catch(e) {}\n"
                "\n"
                "const fullPost = [bestHook, parsed.body, parsed.cta].filter(Boolean).join('\\n\\n');\n"
                "const fullPostWithHashtags = parsed.hashtags ? fullPost + '\\n\\n' + parsed.hashtags : fullPost;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    title: bestHook,\n"
                "    body: fullPostWithHashtags,\n"
                "    hashtags: parsed.hashtags || '',\n"
                "    metaTitle: parsed.meta_title || '',\n"
                "    metaDescription: parsed.meta_description || '',\n"
                "    qualityScore: postData.qualityScore,\n"
                "    calendarId: postData.calendarId,\n"
                "    topic: postData.topic,\n"
                "    platform: Array.isArray(postData.platform) ? postData.platform.join(', ') : postData.platform || 'all',\n"
                "    status: 'Approved',\n"
                "    tokensUsed: postData.tokensUsed\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Build Final Content",
        "type": "n8n-nodes-base.code",
        "position": [2640, 400],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # -- Store Content --
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
                    "Meta Title": "={{ $json.metaTitle }}",
                    "Meta Description": "={{ $json.metaDescription }}",
                    "Status": "={{ $json.status }}",
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
                    {"id": "Meta Title", "type": "string", "display": True, "displayName": "Meta Title"},
                    {"id": "Meta Description", "type": "string", "display": True, "displayName": "Meta Description"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Quality Score", "type": "number", "display": True, "displayName": "Quality Score"},
                    {"id": "Platform", "type": "string", "display": True, "displayName": "Platform"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Store Content",
        "type": "n8n-nodes-base.airtable",
        "position": [2880, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Update Calendar --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT_CALENDAR},
            "columns": {
                "value": {"Status": "Content Ready"},
                "schema": [{"id": "Status", "type": "string", "display": True, "displayName": "Status"}],
                "mappingMode": "defineBelow",
                "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Calendar Ready",
        "type": "n8n-nodes-base.airtable",
        "position": [3120, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Add to Queue --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_PUBLISH_QUEUE},
            "columns": {
                "value": {
                    "Content ID": "={{ $('Build Final Content').first().json.title }}",
                    "Status": "Queued",
                    "Scheduled Date": "={{ $('System Config').first().json.todayDate }}",
                    "Platform": "={{ $('Build Final Content').first().json.platform }}",
                },
                "schema": [
                    {"id": "Content ID", "type": "string", "display": True, "displayName": "Content ID"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Scheduled Date", "type": "string", "display": True, "displayName": "Scheduled Date"},
                    {"id": "Platform", "type": "string", "display": True, "displayName": "Platform"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Add to Queue",
        "type": "n8n-nodes-base.airtable",
        "position": [3360, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Store as Draft (fail branch) --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT},
            "columns": {
                "value": {
                    "Title": "={{ $json.parsedContent.hook || $json.topic }}",
                    "Calendar Entry ID": "={{ $json.calendarId }}",
                    "Content Type": "social_post",
                    "Body": "={{ $json.parsedContent.body || '' }}",
                    "Status": "Draft",
                    "Quality Score": "={{ $json.qualityScore }}",
                    "Platform": "={{ Array.isArray($json.platform) ? $json.platform.join(', ') : $json.platform || 'all' }}",
                    "Created At": "={{ $now.format('yyyy-MM-dd') }}",
                },
                "schema": [
                    {"id": "Title", "type": "string", "display": True, "displayName": "Title"},
                    {"id": "Calendar Entry ID", "type": "string", "display": True, "displayName": "Calendar Entry ID"},
                    {"id": "Content Type", "type": "string", "display": True, "displayName": "Content Type"},
                    {"id": "Body", "type": "string", "display": True, "displayName": "Body"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Quality Score", "type": "number", "display": True, "displayName": "Quality Score"},
                    {"id": "Platform", "type": "string", "display": True, "displayName": "Platform"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Store as Draft",
        "type": "n8n-nodes-base.airtable",
        "position": [2400, 700],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Error Handling --
    nodes.append({"parameters": {}, "id": uid(), "name": "Error Trigger", "type": "n8n-nodes-base.errorTrigger", "position": [200, 960], "typeVersion": 1})
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com", "subject": "SEO/SOCIAL ERROR - {{ $json.workflow.name }}",
            "emailType": "html",
            "message": "=<h2>SEO + Social Engine Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
            "options": {},
        },
        "id": uid(), "name": "Error Notification", "type": "n8n-nodes-base.gmail", "position": [440, 960], "typeVersion": 2.1, "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    nodes.append({"parameters": {"content": "## WF-06: SEO Content Production\n\n**Schedule:** Daily 9:30AM SAST\n**Purpose:** Read calendar + keywords, AI content generation with quality gate.\n**Quality Gate:** Score >= 6 -> Approved + Queue | < 6 -> Draft for review.", "height": 160, "width": 420}, "id": "wf06-note-1", "type": "n8n-nodes-base.stickyNote", "position": [140, 220], "typeVersion": 1, "name": "Note 1"})

    return nodes


def build_wf06_connections():
    """Build connections for the SEO Content Production workflow."""
    return {
        "Daily 9:30AM SAST": {"main": [[{"node": "System Config", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "System Config", "type": "main", "index": 0}]]},
        "System Config": {"main": [[{"node": "Read Content Calendar", "type": "main", "index": 0}, {"node": "Read Keywords", "type": "main", "index": 0}, {"node": "Read Content Topics", "type": "main", "index": 0}]]},
        "Read Content Calendar": {"main": [[{"node": "Has Calendar Items?", "type": "main", "index": 0}]]},
        "Has Calendar Items?": {"main": [[{"node": "Loop Over Content", "type": "main", "index": 0}], []]},
        "Loop Over Content": {"main": [[], [{"node": "Build SEO Brief", "type": "main", "index": 0}]]},
        "Build SEO Brief": {"main": [[{"node": "AI Content Generation", "type": "main", "index": 0}]]},
        "AI Content Generation": {"main": [[{"node": "Parse & Quality Gate", "type": "main", "index": 0}]]},
        "Parse & Quality Gate": {"main": [[{"node": "Quality Pass?", "type": "main", "index": 0}]]},
        "Quality Pass?": {"main": [[{"node": "Hook Optimizer", "type": "main", "index": 0}], [{"node": "Store as Draft", "type": "main", "index": 0}]]},
        "Hook Optimizer": {"main": [[{"node": "Build Final Content", "type": "main", "index": 0}]]},
        "Build Final Content": {"main": [[{"node": "Store Content", "type": "main", "index": 0}]]},
        "Store Content": {"main": [[{"node": "Update Calendar Ready", "type": "main", "index": 0}]]},
        "Update Calendar Ready": {"main": [[{"node": "Add to Queue", "type": "main", "index": 0}]]},
        "Add to Queue": {"main": [[{"node": "Loop Over Content", "type": "main", "index": 0}]]},
        "Store as Draft": {"main": [[{"node": "Loop Over Content", "type": "main", "index": 0}]]},
        "Error Trigger": {"main": [[{"node": "Error Notification", "type": "main", "index": 0}]]},
    }



# ==================================================================
# WF-07: PUBLISHING & SCHEDULING
# ==================================================================

def build_wf07_nodes():
    """Build all nodes for the Publishing & Scheduling workflow."""
    nodes = []

    # -- Triggers --
    nodes.append({
        "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "30 8 * * *"}]}},
        "id": uid(), "name": "Daily 10:30AM SAST",
        "type": "n8n-nodes-base.scheduleTrigger", "position": [200, 400], "typeVersion": 1.2,
    })
    nodes.append({"parameters": {}, "id": uid(), "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "position": [200, 600], "typeVersion": 1})

    # -- Read Publish Queue --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_PUBLISH_QUEUE},
            "filterByFormula": '=({Status} = "Queued")',
        },
        "id": uid(), "name": "Read Publish Queue",
        "type": "n8n-nodes-base.airtable", "position": [440, 500], "typeVersion": 2.1,
        "alwaysOutputData": True, "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Has Items --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "strict"},
                "combinator": "and",
                "conditions": [{"id": uid(), "operator": {"type": "object", "operation": "notEmpty", "singleValue": True}, "leftValue": "={{ $json.id }}", "rightValue": ""}],
            },
            "options": {},
        },
        "id": uid(), "name": "Has Queue Items?",
        "type": "n8n-nodes-base.if", "position": [680, 500], "typeVersion": 2.2,
    })

    # -- Loop --
    nodes.append({
        "parameters": {"options": {"batchSize": 1}},
        "id": uid(), "name": "Loop Over Queue",
        "type": "n8n-nodes-base.splitInBatches", "position": [920, 400], "typeVersion": 3,
    })

    # -- Read Content --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT},
            "filterByFormula": '=({Title} = "{{ $json[\'Content ID\'] }}")',
        },
        "id": uid(), "name": "Read Content",
        "type": "n8n-nodes-base.airtable", "position": [1160, 600], "typeVersion": 2.1,
        "alwaysOutputData": True, "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Format for Blotato --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const content = $input.first().json;\n"
                "const queueItem = $('Loop Over Queue').item.json;\n"
                "const postText = content.Body || content.Title || 'Check out our latest update!';\n"
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
        "id": uid(), "name": "Format for Blotato",
        "type": "n8n-nodes-base.code", "position": [1400, 600], "typeVersion": 2, "alwaysOutputData": True,
    })

    # -- 3 Blotato platform nodes (active accounts: TikTok, Instagram, Facebook) --
    platforms = [
        ("TikTok", "tiktok", [1700, 400]),
        ("Instagram", "instagram", [1700, 600]),
        ("Facebook", "facebook", [1700, 800]),
    ]
    for platform_name, platform_key, position in platforms:
        account = BLOTATO_ACCOUNTS[platform_key]
        params = {
            "platform": platform_key,
            "accountId": {"__rl": True, "mode": "list", "value": account["accountId"]},
            "postContentText": "={{ $json.postText }}",
            "options": {},
        }
        if platform_key == "facebook" and "subAccountId" in account:
            params["facebookPageId"] = {"__rl": True, "mode": "list", "value": account["subAccountId"]}
        nodes.append({
            "parameters": params, "id": uid(), "name": f"{platform_name} [BLOTATO]",
            "type": "@blotato/n8n-nodes-blotato.blotato", "position": position,
            "typeVersion": 2, "credentials": {"blotatoApi": CRED_BLOTATO}, "onError": "continueRegularOutput",
        })

    # -- Merge --
    nodes.append({"parameters": {"mode": "append"}, "id": uid(), "name": "Merge Platform Results", "type": "n8n-nodes-base.merge", "position": [2000, 600], "typeVersion": 3})

    # -- Process Results --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const items = $input.all();\n"
                "const platforms = ['TikTok', 'Instagram', 'Facebook'];\n"
                "const formatData = $('Format for Blotato').first().json;\n"
                "const now = new Date().toISOString().split('T')[0];\n"
                "let successCount = 0, failCount = 0;\n"
                "const logEntries = items.map((item, i) => {\n"
                "  const platform = platforms[i] || 'Unknown';\n"
                "  const hasError = !!(item.json.error || item.json.statusCode >= 400);\n"
                "  if (hasError) { failCount++; } else { successCount++; }\n"
                "  return { json: {\n"
                "    'Log ID': `LOG-${Date.now()}-${platform}`,\n"
                "    'Content ID': formatData.contentId || '',\n"
                "    'Platform': platform, 'Published At': now,\n"
                "    'Status': hasError ? 'Failed' : 'Success',\n"
                "    'Response': JSON.stringify(item.json).substring(0, 200),\n"
                "    _queueId: formatData.queueId || '', _contentId: formatData.contentId || '',\n"
                "    _successCount: successCount, _failCount: failCount,\n"
                "  }};\n"
                "});\n"
                "return logEntries;"
            ),
        },
        "id": uid(), "name": "Process Results",
        "type": "n8n-nodes-base.code", "position": [2240, 600], "typeVersion": 2, "alwaysOutputData": True,
    })

    # -- Store Distribution Log --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
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
                "mappingMode": "defineBelow", "matchingColumns": ["Log ID"],
            },
            "options": {},
        },
        "id": uid(), "name": "Store Distribution Log",
        "type": "n8n-nodes-base.airtable", "position": [2480, 600], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Update Queue Status --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_PUBLISH_QUEUE},
            "columns": {
                "value": {"Status": "Published", "Published At": "={{ $now.format('yyyy-MM-dd') }}", "Platform Results": "={{ $json._successCount + '/' + ($json._successCount + $json._failCount) + ' platforms succeeded' }}"},
                "schema": [{"id": "Status", "type": "string", "display": True, "displayName": "Status"}, {"id": "Published At", "type": "string", "display": True, "displayName": "Published At"}, {"id": "Platform Results", "type": "string", "display": True, "displayName": "Platform Results"}],
                "mappingMode": "defineBelow", "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(), "name": "Update Queue Status",
        "type": "n8n-nodes-base.airtable", "position": [2720, 600], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Update Content Status --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT},
            "columns": {
                "value": {"Status": "Published"},
                "schema": [{"id": "Status", "type": "string", "display": True, "displayName": "Status"}],
                "mappingMode": "defineBelow", "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(), "name": "Content -> Published",
        "type": "n8n-nodes-base.airtable", "position": [2960, 600], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Aggregate & Email --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const now = new Date().toLocaleString('en-ZA', { timeZone: 'Africa/Johannesburg' });\n"
                "let totalPublished = 0, totalFailed = 0;\n"
                "try { const items = $('Process Results').all(); for (const item of items) { totalPublished += item.json._successCount || 0; totalFailed += item.json._failCount || 0; } } catch(e) {}\n"
                "return { json: {\n"
                "  subject: `SEO Social Distribution: ${totalPublished} posts published`,\n"
                "  body: ['<h2 style=\"color:#FF6D5A\">Daily Publishing Report</h2>', `<p><strong>Date:</strong> ${now}</p>`, '<hr>', `<p><strong>Successful:</strong> ${totalPublished}</p>`, `<p><strong>Failed:</strong> ${totalFailed}</p>`, '<p>Check Distribution Log for details.</p>'].join('\\n')\n"
                "}};"
            ),
        },
        "id": uid(), "name": "Aggregate Distribution",
        "type": "n8n-nodes-base.code", "position": [3440, 400], "typeVersion": 2, "alwaysOutputData": True,
    })
    nodes.append({
        "parameters": {"sendTo": "ian@anyvisionmedia.com", "subject": "={{ $json.subject }}", "emailType": "html", "message": "={{ $json.body }}", "options": {}},
        "id": uid(), "name": "Send Distribution Summary",
        "type": "n8n-nodes-base.gmail", "position": [3680, 400], "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL}, "onError": "continueRegularOutput",
    })

    # -- Error Handling --
    nodes.append({"parameters": {}, "id": uid(), "name": "Error Trigger", "type": "n8n-nodes-base.errorTrigger", "position": [200, 880], "typeVersion": 1})
    nodes.append({
        "parameters": {"sendTo": "ian@anyvisionmedia.com", "subject": "SEO/SOCIAL ERROR - {{ $json.workflow.name }}", "emailType": "html",
            "message": "=<h2>SEO + Social Engine Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>", "options": {}},
        "id": uid(), "name": "Error Notification", "type": "n8n-nodes-base.gmail", "position": [440, 880], "typeVersion": 2.1, "credentials": {"gmailOAuth2": CRED_GMAIL},
    })
    nodes.append({"parameters": {"content": "## WF-07: Publishing & Scheduling\n\n**Schedule:** Daily 10:30AM SAST\n**Purpose:** Read publish queue, post to TikTok, Instagram, Facebook via Blotato, log results.\n**No AI tokens used** - pure distribution.", "height": 140, "width": 420}, "id": "wf07-note-1", "type": "n8n-nodes-base.stickyNote", "position": [140, 220], "typeVersion": 1, "name": "Note 1"})
    return nodes


def build_wf07_connections():
    """Build connections for Publishing & Scheduling (scatter-gather pattern)."""
    connections = {
        "Daily 10:30AM SAST": {"main": [[{"node": "Read Publish Queue", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Read Publish Queue", "type": "main", "index": 0}]]},
        "Read Publish Queue": {"main": [[{"node": "Has Queue Items?", "type": "main", "index": 0}]]},
        "Has Queue Items?": {"main": [[{"node": "Loop Over Queue", "type": "main", "index": 0}], [{"node": "Aggregate Distribution", "type": "main", "index": 0}]]},
        "Loop Over Queue": {"main": [[{"node": "Aggregate Distribution", "type": "main", "index": 0}], [{"node": "Read Content", "type": "main", "index": 0}]]},
        "Read Content": {"main": [[{"node": "Format for Blotato", "type": "main", "index": 0}]]},
        "Format for Blotato": {"main": [[
            {"node": "TikTok [BLOTATO]", "type": "main", "index": 0},
            {"node": "Instagram [BLOTATO]", "type": "main", "index": 0},
            {"node": "Facebook [BLOTATO]", "type": "main", "index": 0},
        ]]},
        "TikTok [BLOTATO]": {"main": [[{"node": "Merge Platform Results", "type": "main", "index": 0}]]},
        "Instagram [BLOTATO]": {"main": [[{"node": "Merge Platform Results", "type": "main", "index": 1}]]},
        "Facebook [BLOTATO]": {"main": [[{"node": "Merge Platform Results", "type": "main", "index": 2}]]},
        "Merge Platform Results": {"main": [[{"node": "Process Results", "type": "main", "index": 0}]]},
        "Process Results": {"main": [[{"node": "Store Distribution Log", "type": "main", "index": 0}]]},
        "Store Distribution Log": {"main": [[{"node": "Update Queue Status", "type": "main", "index": 0}]]},
        "Update Queue Status": {"main": [[{"node": "Content -> Published", "type": "main", "index": 0}]]},
        "Content -> Published": {"main": [[{"node": "Loop Over Queue", "type": "main", "index": 0}]]},
        "Aggregate Distribution": {"main": [[{"node": "Send Distribution Summary", "type": "main", "index": 0}]]},
        "Error Trigger": {"main": [[{"node": "Error Notification", "type": "main", "index": 0}]]},
    }
    return connections


# ==================================================================
# WF-08: ENGAGEMENT & COMMUNITY
# ==================================================================

def build_wf08_nodes():
    """Build all nodes for the Engagement & Community workflow."""
    nodes = []

    # -- Trigger (every 30 min, 5AM-7PM UTC) --
    nodes.append({
        "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "*/30 5-19 * * *"}]}},
        "id": uid(), "name": "Every 30min Daytime",
        "type": "n8n-nodes-base.scheduleTrigger", "position": [200, 400], "typeVersion": 1.2,
    })
    nodes.append({"parameters": {}, "id": uid(), "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "position": [200, 600], "typeVersion": 1})

    # -- System Config --
    nodes.append({
        "parameters": {
            "mode": "manual", "duplicateItem": False,
            "assignments": {"assignments": [
                {"id": uid(), "name": "todayDate", "value": "={{ $now.format('yyyy-MM-dd') }}", "type": "string"},
                {"id": uid(), "name": "aiModel", "value": "anthropic/claude-sonnet-4-20250514", "type": "string"},
                {"id": uid(), "name": "companyName", "value": "AnyVision Media", "type": "string"},
            ]},
        },
        "id": uid(), "name": "System Config",
        "type": "n8n-nodes-base.set", "position": [440, 500], "typeVersion": 3.4,
    })

    # -- Read Recent Distribution Log (last 48h) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_DISTRIBUTION_LOG},
            "filterByFormula": "=IS_AFTER({Published At}, DATEADD(TODAY(), -2, 'days'))",
        },
        "id": uid(), "name": "Read Recent Posts",
        "type": "n8n-nodes-base.airtable", "position": [680, 500], "typeVersion": 2.1,
        "alwaysOutputData": True, "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Fetch Engagement Metrics (simulated) --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const posts = $input.all();\n"
                "const now = new Date().toISOString();\n"
                "\n"
                "// Simulate fetching engagement metrics for each post\n"
                "const metricsResults = posts.map(post => {\n"
                "  const platform = post.json.Platform || 'Unknown';\n"
                "  // In production, replace with actual Blotato/platform API calls\n"
                "  const simulated = {\n"
                "    likes: Math.floor(Math.random() * 50),\n"
                "    comments: Math.floor(Math.random() * 10),\n"
                "    shares: Math.floor(Math.random() * 5),\n"
                "    impressions: Math.floor(Math.random() * 1000),\n"
                "    clicks: Math.floor(Math.random() * 20),\n"
                "  };\n"
                "  const engagementScore = simulated.likes * 1 + simulated.comments * 3 + simulated.shares * 5;\n"
                "  return {\n"
                "    json: {\n"
                "      contentId: post.json['Content ID'] || '',\n"
                "      platform: platform,\n"
                "      publishedAt: post.json['Published At'] || '',\n"
                "      metrics: simulated,\n"
                "      engagementScore: engagementScore,\n"
                "      isSpike: engagementScore > 80,\n"
                "      checkedAt: now\n"
                "    }\n"
                "  };\n"
                "});\n"
                "return metricsResults.length > 0 ? metricsResults : [{ json: { contentId: 'none', platform: 'none', metrics: {}, engagementScore: 0, isSpike: false, checkedAt: now } }];"
            ),
        },
        "id": uid(), "name": "Fetch Engagement Metrics",
        "type": "n8n-nodes-base.code", "position": [920, 500], "typeVersion": 2, "alwaysOutputData": True, "onError": "continueRegularOutput",
    })

    # -- Has Engagement Spikes? --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "strict"},
                "combinator": "and",
                "conditions": [{"id": uid(), "operator": {"type": "number", "operation": "gt"}, "leftValue": "={{ $json.engagementScore }}", "rightValue": 80}],
            },
            "options": {},
        },
        "id": uid(), "name": "Has Spikes?",
        "type": "n8n-nodes-base.if", "position": [1160, 500], "typeVersion": 2.2,
    })

    # -- Log Engagement (both branches) --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_ENGAGEMENT_LOG},
            "columns": {
                "value": {
                    "Content ID": "={{ $json.contentId }}", "Platform": "={{ $json.platform }}",
                    "Engagement Score": "={{ $json.engagementScore }}", "Likes": "={{ $json.metrics.likes }}",
                    "Comments": "={{ $json.metrics.comments }}", "Shares": "={{ $json.metrics.shares }}",
                    "Impressions": "={{ $json.metrics.impressions }}", "Is Spike": "={{ $json.isSpike }}",
                    "Checked At": "={{ $json.checkedAt }}",
                },
                "schema": [
                    {"id": "Content ID", "type": "string", "display": True, "displayName": "Content ID"},
                    {"id": "Platform", "type": "string", "display": True, "displayName": "Platform"},
                    {"id": "Engagement Score", "type": "number", "display": True, "displayName": "Engagement Score"},
                    {"id": "Likes", "type": "number", "display": True, "displayName": "Likes"},
                    {"id": "Comments", "type": "number", "display": True, "displayName": "Comments"},
                    {"id": "Shares", "type": "number", "display": True, "displayName": "Shares"},
                    {"id": "Impressions", "type": "number", "display": True, "displayName": "Impressions"},
                    {"id": "Is Spike", "type": "boolean", "display": True, "displayName": "Is Spike"},
                    {"id": "Checked At", "type": "string", "display": True, "displayName": "Checked At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(), "name": "Log Engagement",
        "type": "n8n-nodes-base.airtable", "position": [1400, 400], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Log Normal Engagement --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_ENGAGEMENT_LOG},
            "columns": {
                "value": {
                    "Content ID": "={{ $json.contentId }}", "Platform": "={{ $json.platform }}",
                    "Engagement Score": "={{ $json.engagementScore }}", "Likes": "={{ $json.metrics.likes }}",
                    "Comments": "={{ $json.metrics.comments }}", "Shares": "={{ $json.metrics.shares }}",
                    "Impressions": "={{ $json.metrics.impressions }}", "Is Spike": "={{ $json.isSpike }}",
                    "Checked At": "={{ $json.checkedAt }}",
                },
                "schema": [
                    {"id": "Content ID", "type": "string", "display": True, "displayName": "Content ID"},
                    {"id": "Platform", "type": "string", "display": True, "displayName": "Platform"},
                    {"id": "Engagement Score", "type": "number", "display": True, "displayName": "Engagement Score"},
                    {"id": "Likes", "type": "number", "display": True, "displayName": "Likes"},
                    {"id": "Comments", "type": "number", "display": True, "displayName": "Comments"},
                    {"id": "Shares", "type": "number", "display": True, "displayName": "Shares"},
                    {"id": "Impressions", "type": "number", "display": True, "displayName": "Impressions"},
                    {"id": "Is Spike", "type": "boolean", "display": True, "displayName": "Is Spike"},
                    {"id": "Checked At", "type": "string", "display": True, "displayName": "Checked At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(), "name": "Log Normal Engagement",
        "type": "n8n-nodes-base.airtable", "position": [1400, 700], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- AI Comment Suggestions (spike branch) --
    nodes.append({
        "parameters": {
            "method": "POST", "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
            "sendBody": True, "specifyBody": "json",
            "jsonBody": "={\n"
                "  \"model\": \"{{ $('System Config').first().json.aiModel }}\",\n"
                "  \"max_tokens\": 500,\n"
                "  \"temperature\": 0.7,\n"
                "  \"messages\": [\n"
                "    {\n"
                "      \"role\": \"system\",\n"
                f"      \"content\": {json.dumps(ENGAGEMENT_REPLY_PROMPT)}\n"
                "    },\n"
                "    {\n"
                "      \"role\": \"user\",\n"
                "      \"content\": {{ JSON.stringify('High engagement detected on ' + $json.platform + ' for content ' + $json.contentId + '. Engagement score: ' + $json.engagementScore + '. Metrics: ' + JSON.stringify($json.metrics) + '. Generate suggested replies.') }}\n"
                "    }\n"
                "  ]\n"
                "}",
            "options": {"timeout": 30000},
        },
        "id": uid(), "name": "AI Comment Suggestions",
        "type": "n8n-nodes-base.httpRequest", "position": [1640, 400], "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER}, "onError": "continueRegularOutput",
        "retryOnFail": True, "maxTries": 2, "waitBetweenTries": 2000,
    })

    # -- Send Spike Alert --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=ENGAGEMENT SPIKE - {{ $('Has Spikes?').first().json.platform }} (Score: {{ $('Has Spikes?').first().json.engagementScore }})",
            "emailType": "html",
            "message": "=<h2 style=\"color:#FF6D5A\">Engagement Spike Detected!</h2>\n<p><strong>Platform:</strong> {{ $('Has Spikes?').first().json.platform }}</p>\n<p><strong>Content:</strong> {{ $('Has Spikes?').first().json.contentId }}</p>\n<p><strong>Score:</strong> {{ $('Has Spikes?').first().json.engagementScore }}</p>\n<hr>\n<p><strong>AI Suggestions:</strong></p>\n<pre>{{ $json.choices ? $json.choices[0].message.content : 'No suggestions generated' }}</pre>",
            "options": {},
        },
        "id": uid(), "name": "Send Spike Alert",
        "type": "n8n-nodes-base.gmail", "position": [1880, 400], "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL}, "onError": "continueRegularOutput",
    })

    # -- Error Handling --
    nodes.append({"parameters": {}, "id": uid(), "name": "Error Trigger", "type": "n8n-nodes-base.errorTrigger", "position": [200, 880], "typeVersion": 1})
    nodes.append({
        "parameters": {"sendTo": "ian@anyvisionmedia.com", "subject": "SEO/SOCIAL ERROR - {{ $json.workflow.name }}", "emailType": "html",
            "message": "=<h2>SEO + Social Engine Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>", "options": {}},
        "id": uid(), "name": "Error Notification", "type": "n8n-nodes-base.gmail", "position": [440, 880], "typeVersion": 2.1, "credentials": {"gmailOAuth2": CRED_GMAIL},
    })
    nodes.append({"parameters": {"content": "## WF-08: Engagement & Community\n\n**Schedule:** Every 30min 5AM-7PM UTC\n**Purpose:** Monitor engagement metrics, detect spikes, AI comment suggestions.\n**Spike Threshold:** Engagement score > 80 -> Gmail alert + AI suggestions.", "height": 160, "width": 420}, "id": "wf08-note-1", "type": "n8n-nodes-base.stickyNote", "position": [140, 220], "typeVersion": 1, "name": "Note 1"})
    return nodes


def build_wf08_connections():
    """Build connections for Engagement & Community."""
    return {
        "Every 30min Daytime": {"main": [[{"node": "System Config", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "System Config", "type": "main", "index": 0}]]},
        "System Config": {"main": [[{"node": "Read Recent Posts", "type": "main", "index": 0}]]},
        "Read Recent Posts": {"main": [[{"node": "Fetch Engagement Metrics", "type": "main", "index": 0}]]},
        "Fetch Engagement Metrics": {"main": [[{"node": "Has Spikes?", "type": "main", "index": 0}]]},
        "Has Spikes?": {"main": [[{"node": "Log Engagement", "type": "main", "index": 0}], [{"node": "Log Normal Engagement", "type": "main", "index": 0}]]},
        "Log Engagement": {"main": [[{"node": "AI Comment Suggestions", "type": "main", "index": 0}]]},
        "AI Comment Suggestions": {"main": [[{"node": "Send Spike Alert", "type": "main", "index": 0}]]},
        "Error Trigger": {"main": [[{"node": "Error Notification", "type": "main", "index": 0}]]},
    }



# ==================================================================
# WF-09: LEAD CAPTURE & ATTRIBUTION
# ==================================================================

def build_wf09_nodes():
    """Build all nodes for the Lead Capture & Attribution workflow."""
    nodes = []

    # -- Webhook Trigger --
    nodes.append({
        "parameters": {
            "path": "seo-social/lead-capture",
            "httpMethod": "POST",
            "responseMode": "responseNode",
            "options": {},
        },
        "id": uid(), "name": "Lead Capture Webhook",
        "type": "n8n-nodes-base.webhook", "position": [200, 400], "typeVersion": 2,
        "webhookId": uid(),
    })

    # -- Daily Batch Trigger --
    nodes.append({
        "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 6 * * *"}]}},
        "id": uid(), "name": "Daily Batch 8AM SAST",
        "type": "n8n-nodes-base.scheduleTrigger", "position": [200, 700], "typeVersion": 1.2,
    })
    nodes.append({"parameters": {}, "id": uid(), "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "position": [200, 900], "typeVersion": 1})

    # -- System Config --
    nodes.append({
        "parameters": {
            "mode": "manual", "duplicateItem": False,
            "assignments": {"assignments": [
                {"id": uid(), "name": "todayDate", "value": "={{ $now.format('yyyy-MM-dd') }}", "type": "string"},
                {"id": uid(), "name": "aiModel", "value": "anthropic/claude-sonnet-4-20250514", "type": "string"},
                {"id": uid(), "name": "companyName", "value": "AnyVision Media", "type": "string"},
            ]},
        },
        "id": uid(), "name": "System Config",
        "type": "n8n-nodes-base.set", "position": [440, 500], "typeVersion": 3.4,
    })

    # -- Parse UTM Params (webhook branch) --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const body = $json.body || $json;\n"
                "const headers = $json.headers || {};\n"
                "\n"
                "// Extract UTM parameters\n"
                "const utm = {\n"
                "  source: body.utm_source || body.source || 'direct',\n"
                "  medium: body.utm_medium || body.medium || 'unknown',\n"
                "  campaign: body.utm_campaign || body.campaign || '',\n"
                "  term: body.utm_term || body.term || '',\n"
                "  content: body.utm_content || body.content || '',\n"
                "};\n"
                "\n"
                "// Extract lead data\n"
                "const lead = {\n"
                "  email: (body.email || '').toLowerCase().trim(),\n"
                "  name: body.name || body.full_name || '',\n"
                "  company: body.company || body.organization || '',\n"
                "  phone: body.phone || '',\n"
                "  message: body.message || body.inquiry || '',\n"
                "  page_url: body.page_url || headers.referer || '',\n"
                "  ip: headers['x-forwarded-for'] || headers['x-real-ip'] || '',\n"
                "};\n"
                "\n"
                "// Basic lead score\n"
                "let score = 20; // base\n"
                "if (lead.email) score += 20;\n"
                "if (lead.name) score += 10;\n"
                "if (lead.company) score += 15;\n"
                "if (lead.phone) score += 15;\n"
                "if (lead.message && lead.message.length > 20) score += 10;\n"
                "if (utm.source === 'organic') score += 10;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    lead: lead,\n"
                "    utm: utm,\n"
                "    lead_score: Math.min(100, score),\n"
                "    source_type: 'webhook',\n"
                "    received_at: new Date().toISOString()\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(), "name": "Parse UTM & Lead Data",
        "type": "n8n-nodes-base.code", "position": [680, 400], "typeVersion": 2, "alwaysOutputData": True,
    })

    # -- Check Duplicate --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_LEADS},
            "filterByFormula": '=({Email} = "{{ $json.lead.email }}")',
        },
        "id": uid(), "name": "Check Duplicate",
        "type": "n8n-nodes-base.airtable", "position": [920, 400], "typeVersion": 2.1,
        "alwaysOutputData": True, "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Is New Lead? --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "strict"},
                "combinator": "and",
                "conditions": [{"id": uid(), "operator": {"type": "object", "operation": "empty", "singleValue": True}, "leftValue": "={{ $json.id }}", "rightValue": ""}],
            },
            "options": {},
        },
        "id": uid(), "name": "Is New?",
        "type": "n8n-nodes-base.if", "position": [1160, 400], "typeVersion": 2.2,
    })

    # -- Create Lead (NO matchingColumns) --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_LEADS},
            "columns": {
                "value": {
                    "Email": "={{ $('Parse UTM & Lead Data').first().json.lead.email }}",
                    "Name": "={{ $('Parse UTM & Lead Data').first().json.lead.name }}",
                    "Company": "={{ $('Parse UTM & Lead Data').first().json.lead.company }}",
                    "Phone": "={{ $('Parse UTM & Lead Data').first().json.lead.phone }}",
                    "Message": "={{ $('Parse UTM & Lead Data').first().json.lead.message }}",
                    "Source": "={{ $('Parse UTM & Lead Data').first().json.utm.source }}",
                    "Medium": "={{ $('Parse UTM & Lead Data').first().json.utm.medium }}",
                    "Campaign": "={{ $('Parse UTM & Lead Data').first().json.utm.campaign }}",
                    "Lead Score": "={{ $('Parse UTM & Lead Data').first().json.lead_score }}",
                    "Status": "New",
                    "Page URL": "={{ $('Parse UTM & Lead Data').first().json.lead.page_url }}",
                    "Created At": "={{ $('Parse UTM & Lead Data').first().json.received_at }}",
                },
                "schema": [
                    {"id": "Email", "type": "string", "display": True, "displayName": "Email"},
                    {"id": "Name", "type": "string", "display": True, "displayName": "Name"},
                    {"id": "Company", "type": "string", "display": True, "displayName": "Company"},
                    {"id": "Phone", "type": "string", "display": True, "displayName": "Phone"},
                    {"id": "Message", "type": "string", "display": True, "displayName": "Message"},
                    {"id": "Source", "type": "string", "display": True, "displayName": "Source"},
                    {"id": "Medium", "type": "string", "display": True, "displayName": "Medium"},
                    {"id": "Campaign", "type": "string", "display": True, "displayName": "Campaign"},
                    {"id": "Lead Score", "type": "number", "display": True, "displayName": "Lead Score"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Page URL", "type": "string", "display": True, "displayName": "Page URL"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(), "name": "Create Lead",
        "type": "n8n-nodes-base.airtable", "position": [1400, 300], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Update Existing Lead --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_LEADS},
            "columns": {
                "value": {
                    "Lead Score": "={{ $('Parse UTM & Lead Data').first().json.lead_score }}",
                    "Last Activity": "={{ $('Parse UTM & Lead Data').first().json.received_at }}",
                    "Touch Count": "={{ ($json['Touch Count'] || 0) + 1 }}",
                },
                "schema": [
                    {"id": "Lead Score", "type": "number", "display": True, "displayName": "Lead Score"},
                    {"id": "Last Activity", "type": "string", "display": True, "displayName": "Last Activity"},
                    {"id": "Touch Count", "type": "number", "display": True, "displayName": "Touch Count"},
                ],
                "mappingMode": "defineBelow", "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(), "name": "Update Lead",
        "type": "n8n-nodes-base.airtable", "position": [1400, 550], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Route by Score --
    nodes.append({
        "parameters": {
            "rules": {
                "values": [
                    {"conditions": {"conditions": [{"leftValue": "={{ $('Parse UTM & Lead Data').first().json.lead_score }}", "rightValue": 80, "operator": {"type": "number", "operation": "gte"}}]}, "renameOutput": True, "outputKey": "Hot"},
                    {"conditions": {"conditions": [{"leftValue": "={{ $('Parse UTM & Lead Data').first().json.lead_score }}", "rightValue": 50, "operator": {"type": "number", "operation": "gte"}}]}, "renameOutput": True, "outputKey": "Warm"},
                    {"conditions": {"conditions": [{"leftValue": "={{ $('Parse UTM & Lead Data').first().json.lead_score }}", "rightValue": 0, "operator": {"type": "number", "operation": "gte"}}]}, "renameOutput": True, "outputKey": "Cold"},
                ]
            }
        },
        "id": uid(), "name": "Route by Score",
        "type": "n8n-nodes-base.switch", "position": [1640, 400], "typeVersion": 3.2,
    })

    # -- Hot Lead Alert --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=HOT LEAD (Score: {{ $('Parse UTM & Lead Data').first().json.lead_score }}) - {{ $('Parse UTM & Lead Data').first().json.lead.name || $('Parse UTM & Lead Data').first().json.lead.email }}",
            "emailType": "html",
            "message": "=<h2 style=\"color:#FF6D5A\">Hot Lead Alert!</h2>\n<p><strong>Name:</strong> {{ $('Parse UTM & Lead Data').first().json.lead.name }}</p>\n<p><strong>Email:</strong> {{ $('Parse UTM & Lead Data').first().json.lead.email }}</p>\n<p><strong>Company:</strong> {{ $('Parse UTM & Lead Data').first().json.lead.company }}</p>\n<p><strong>Score:</strong> {{ $('Parse UTM & Lead Data').first().json.lead_score }}/100</p>\n<p><strong>Source:</strong> {{ $('Parse UTM & Lead Data').first().json.utm.source }} / {{ $('Parse UTM & Lead Data').first().json.utm.medium }}</p>\n<p><strong>Message:</strong> {{ $('Parse UTM & Lead Data').first().json.lead.message }}</p>\n<hr>\n<p>Respond within 1 hour for best conversion rates.</p>",
            "options": {},
        },
        "id": uid(), "name": "Hot Lead Alert",
        "type": "n8n-nodes-base.gmail", "position": [1880, 300], "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL}, "onError": "continueRegularOutput",
    })

    # -- Respond to Webhook --
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({success: true, lead_id: $('Parse UTM & Lead Data').first().json.lead.email, score: $('Parse UTM & Lead Data').first().json.lead_score, status: 'received'}) }}",
            "options": {},
        },
        "id": uid(), "name": "Respond Success",
        "type": "n8n-nodes-base.respondToWebhook", "position": [2120, 400], "typeVersion": 1.1,
    })

    # -- Batch Reconciliation (daily branch) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_LEADS},
            "filterByFormula": "=AND({Status} = 'New', IS_BEFORE({Created At}, DATEADD(TODAY(), -1, 'days')))",
        },
        "id": uid(), "name": "Read Stale Leads",
        "type": "n8n-nodes-base.airtable", "position": [680, 800], "typeVersion": 2.1,
        "alwaysOutputData": True, "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Batch Summary --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const leads = $input.all();\n"
                "const validLeads = leads.filter(l => l.json.id);\n"
                "const count = validLeads.length;\n"
                "if (count === 0) return [{ json: { message: 'No stale leads to reconcile', count: 0 } }];\n"
                "// Return each stale lead for downstream processing\n"
                "return validLeads.map(l => ({ json: { ...l.json, staleCount: count } }));"
            ),
        },
        "id": uid(), "name": "Batch Summary",
        "type": "n8n-nodes-base.code", "position": [920, 800], "typeVersion": 2, "alwaysOutputData": True,
    })

    # -- Has Stale Leads? (routes stale leads to scoring by clearing Grade) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.id }}",
                        "rightValue": "",
                        "operator": {"type": "string", "operation": "notEmpty"},
                    }
                ],
            },
        },
        "id": uid(), "name": "Has Stale?",
        "type": "n8n-nodes-base.if", "position": [1140, 800], "typeVersion": 2.2,
    })

    # -- Clear Grade for Scoring (so BRIDGE-03 picks them up) --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_LEADS},
            "id": "={{ $json.id }}",
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Grade": "",
                    "Last Activity": "={{ $now.format('yyyy-MM-dd') }}",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "Grade", "displayName": "Grade", "required": False, "defaultMatch": False, "display": True, "type": "string", "canBeUsedToMatch": False},
                ],
            },
            "options": {},
        },
        "id": uid(), "name": "Clear Grade for Scoring",
        "type": "n8n-nodes-base.airtable", "position": [1360, 700], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Error Handling --
    nodes.append({"parameters": {}, "id": uid(), "name": "Error Trigger", "type": "n8n-nodes-base.errorTrigger", "position": [200, 1100], "typeVersion": 1})
    nodes.append({
        "parameters": {"sendTo": "ian@anyvisionmedia.com", "subject": "SEO/SOCIAL ERROR - {{ $json.workflow.name }}", "emailType": "html",
            "message": "=<h2>SEO + Social Engine Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>", "options": {}},
        "id": uid(), "name": "Error Notification", "type": "n8n-nodes-base.gmail", "position": [440, 1100], "typeVersion": 2.1, "credentials": {"gmailOAuth2": CRED_GMAIL},
    })
    nodes.append({"parameters": {"content": "## WF-09: Lead Capture & Attribution\n\n**Triggers:** Webhook (POST /seo-social/lead-capture) + Daily batch\n**Purpose:** Parse UTM params, deduplicate, score leads, route by quality.\n**Hot leads (>=80):** Immediate Gmail alert to Ian.", "height": 160, "width": 420}, "id": "wf09-note-1", "type": "n8n-nodes-base.stickyNote", "position": [140, 220], "typeVersion": 1, "name": "Note 1"})
    return nodes


def build_wf09_connections():
    """Build connections for Lead Capture & Attribution."""
    return {
        "Lead Capture Webhook": {"main": [[{"node": "System Config", "type": "main", "index": 0}]]},
        "Daily Batch 8AM SAST": {"main": [[{"node": "Read Stale Leads", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Read Stale Leads", "type": "main", "index": 0}]]},
        "System Config": {"main": [[{"node": "Parse UTM & Lead Data", "type": "main", "index": 0}]]},
        "Parse UTM & Lead Data": {"main": [[{"node": "Check Duplicate", "type": "main", "index": 0}]]},
        "Check Duplicate": {"main": [[{"node": "Is New?", "type": "main", "index": 0}]]},
        "Is New?": {"main": [[{"node": "Create Lead", "type": "main", "index": 0}], [{"node": "Update Lead", "type": "main", "index": 0}]]},
        "Create Lead": {"main": [[{"node": "Route by Score", "type": "main", "index": 0}]]},
        "Update Lead": {"main": [[{"node": "Route by Score", "type": "main", "index": 0}]]},
        "Route by Score": {"main": [[{"node": "Hot Lead Alert", "type": "main", "index": 0}], [{"node": "Respond Success", "type": "main", "index": 0}], [{"node": "Respond Success", "type": "main", "index": 0}]]},
        "Hot Lead Alert": {"main": [[{"node": "Respond Success", "type": "main", "index": 0}]]},
        "Read Stale Leads": {"main": [[{"node": "Batch Summary", "type": "main", "index": 0}]]},
        "Batch Summary": {"main": [[{"node": "Has Stale?", "type": "main", "index": 0}]]},
        "Has Stale?": {"main": [[{"node": "Clear Grade for Scoring", "type": "main", "index": 0}], []]},
        "Error Trigger": {"main": [[{"node": "Error Notification", "type": "main", "index": 0}]]},
    }


# ==================================================================
# WF-10: SEO MAINTENANCE
# ==================================================================

def build_wf10_nodes():
    """Build all nodes for the SEO Maintenance workflow."""
    nodes = []

    # -- Trigger --
    nodes.append({
        "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 0 * * 0"}]}},
        "id": uid(), "name": "Weekly Sun 2AM SAST",
        "type": "n8n-nodes-base.scheduleTrigger", "position": [200, 400], "typeVersion": 1.2,
    })
    nodes.append({"parameters": {}, "id": uid(), "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "position": [200, 600], "typeVersion": 1})

    # -- System Config --
    nodes.append({
        "parameters": {
            "mode": "manual", "duplicateItem": False,
            "assignments": {"assignments": [
                {"id": uid(), "name": "todayDate", "value": "={{ $now.format('yyyy-MM-dd') }}", "type": "string"},
                {"id": uid(), "name": "aiModel", "value": "anthropic/claude-sonnet-4-20250514", "type": "string"},
                {"id": uid(), "name": "companyName", "value": "AnyVision Media", "type": "string"},
            ]},
        },
        "id": uid(), "name": "System Config",
        "type": "n8n-nodes-base.set", "position": [440, 500], "typeVersion": 3.4,
    })

    # -- Read Content Topics (pillar pages) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT_TOPICS},
            "filterByFormula": "=({Status} = 'Active')",
        },
        "id": uid(), "name": "Read Content Topics",
        "type": "n8n-nodes-base.airtable", "position": [680, 500], "typeVersion": 2.1,
        "alwaysOutputData": True, "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Loop Over Pages --
    nodes.append({
        "parameters": {"options": {"batchSize": 1}},
        "id": uid(), "name": "Loop Over Pages",
        "type": "n8n-nodes-base.splitInBatches", "position": [920, 500], "typeVersion": 3,
    })

    # -- Crawl Page & Check Links --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const topic = $json;\n"
                "const url = topic.URL || topic.Page_URL || 'https://www.anyvisionmedia.com';\n"
                "\n"
                "let crawlResult = { url: url, title: '', wordCount: 0, hasH1: false, hasMeta: false, brokenLinks: 0, internalLinks: 0, success: false };\n"
                "\n"
                "try {\n"
                "  const html = await this.helpers.httpRequest({\n"
                "    method: 'GET', url: url, timeout: 15000,\n"
                "    headers: { 'User-Agent': 'Mozilla/5.0 (compatible; AnyVisionSEOBot/1.0)' }\n"
                "  });\n"
                "  const text = html.replace(/<script[^>]*>[\\s\\S]*?<\\/script>/gi, '').replace(/<style[^>]*>[\\s\\S]*?<\\/style>/gi, '').replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim();\n"
                "  crawlResult.wordCount = text.split(' ').length;\n"
                "  crawlResult.title = (html.match(/<title[^>]*>(.*?)<\\/title>/i) || [])[1] || '';\n"
                "  crawlResult.hasH1 = /<h1[^>]*>/i.test(html);\n"
                "  crawlResult.hasMeta = /<meta[^>]*name=[\"']description[\"'][^>]*>/i.test(html);\n"
                "  crawlResult.success = true;\n"
                "\n"
                "  // Extract and check links\n"
                "  const linkRegex = /href=[\"'](https?:\\/\\/[^\"']+)[\"']/gi;\n"
                "  let linkMatch;\n"
                "  const links = [];\n"
                "  while ((linkMatch = linkRegex.exec(html)) !== null && links.length < 10) {\n"
                "    links.push(linkMatch[1]);\n"
                "  }\n"
                "  crawlResult.internalLinks = links.filter(l => l.includes('anyvisionmedia.com')).length;\n"
                "\n"
                "  // Check first 5 links for broken\n"
                "  for (const link of links.slice(0, 5)) {\n"
                "    try {\n"
                "      await this.helpers.httpRequest({ method: 'HEAD', url: link, timeout: 5000 });\n"
                "    } catch(e) {\n"
                "      crawlResult.brokenLinks++;\n"
                "    }\n"
                "  }\n"
                "} catch(e) {\n"
                "  crawlResult.error = e.message;\n"
                "}\n"
                "\n"
                "return { json: { ...crawlResult, topicId: topic.id, topicName: topic.Topic || topic.Name || '' } };"
            ),
        },
        "id": uid(), "name": "Crawl Page & Check Links",
        "type": "n8n-nodes-base.code", "position": [1160, 600], "typeVersion": 2,
        "alwaysOutputData": True, "onError": "continueRegularOutput",
    })

    # -- PageSpeed API --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "=https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={{ encodeURIComponent($json.url) }}&strategy=mobile",
            "options": {"timeout": 30000},
        },
        "id": uid(), "name": "PageSpeed API",
        "type": "n8n-nodes-base.httpRequest", "position": [1400, 600], "typeVersion": 4.2,
        "onError": "continueRegularOutput", "retryOnFail": True, "maxTries": 2, "waitBetweenTries": 3000,
    })

    # -- Compute SEO Score --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const crawl = $('Crawl Page & Check Links').first().json;\n"
                "const pagespeed = $input.first().json;\n"
                "\n"
                "// Extract PageSpeed score\n"
                "let psScore = 50;\n"
                "try { psScore = Math.round((pagespeed.lighthouseResult.categories.performance.score || 0.5) * 100); } catch(e) {}\n"
                "\n"
                "// Deterministic SEO scoring formula\n"
                "const speedScore = psScore;\n"
                "const contentScore = Math.min(100, (crawl.wordCount || 0) / 20 + (crawl.hasH1 ? 20 : 0) + (crawl.hasMeta ? 20 : 0));\n"
                "const linkScore = Math.max(0, 100 - (crawl.brokenLinks || 0) * 25 + (crawl.internalLinks || 0) * 10);\n"
                "const techScore = (crawl.success ? 50 : 0) + (crawl.title ? 25 : 0) + (crawl.hasMeta ? 25 : 0);\n"
                "\n"
                "const composite = Math.round(speedScore * 0.30 + contentScore * 0.25 + linkScore * 0.25 + techScore * 0.20);\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    url: crawl.url,\n"
                "    topicId: crawl.topicId,\n"
                "    topicName: crawl.topicName,\n"
                "    scores: { speed: speedScore, content: contentScore, links: linkScore, technical: techScore },\n"
                "    composite_score: Math.min(100, composite),\n"
                "    grade: composite >= 80 ? 'Healthy' : composite >= 60 ? 'Needs Work' : composite >= 40 ? 'Poor' : 'Critical',\n"
                "    crawlData: { wordCount: crawl.wordCount, hasH1: crawl.hasH1, hasMeta: crawl.hasMeta, brokenLinks: crawl.brokenLinks, internalLinks: crawl.internalLinks },\n"
                "    pagespeedScore: psScore,\n"
                "    auditDate: $('System Config').first().json.todayDate\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(), "name": "Compute SEO Score",
        "type": "n8n-nodes-base.code", "position": [1640, 600], "typeVersion": 2, "alwaysOutputData": True,
    })

    # -- AI SEO Analysis --
    nodes.append({
        "parameters": {
            "method": "POST", "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
            "sendBody": True, "specifyBody": "json",
            "jsonBody": "={\n"
                "  \"model\": \"{{ $('System Config').first().json.aiModel }}\",\n"
                "  \"max_tokens\": 1000,\n"
                "  \"temperature\": 0.5,\n"
                "  \"messages\": [\n"
                "    {\n"
                "      \"role\": \"system\",\n"
                f"      \"content\": {json.dumps(SEO_AUDIT_ANALYSIS_PROMPT)}\n"
                "    },\n"
                "    {\n"
                "      \"role\": \"user\",\n"
                "      \"content\": {{ JSON.stringify('Page: ' + $json.url + '\\nSEO Score: ' + $json.composite_score + '/100 (' + $json.grade + ')\\nPageSpeed: ' + $json.pagespeedScore + '/100\\nCrawl Data: ' + JSON.stringify($json.crawlData) + '\\nScore Breakdown: ' + JSON.stringify($json.scores)) }}\n"
                "    }\n"
                "  ]\n"
                "}",
            "options": {"timeout": 60000},
        },
        "id": uid(), "name": "AI SEO Analysis",
        "type": "n8n-nodes-base.httpRequest", "position": [1880, 600], "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER}, "onError": "continueRegularOutput",
        "retryOnFail": True, "maxTries": 2, "waitBetweenTries": 3000,
    })

    # -- Store SEO Audit --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SEO_AUDITS},
            "columns": {
                "value": {
                    "URL": "={{ $('Compute SEO Score').first().json.url }}",
                    "Topic": "={{ $('Compute SEO Score').first().json.topicName }}",
                    "Composite Score": "={{ $('Compute SEO Score').first().json.composite_score }}",
                    "Grade": "={{ $('Compute SEO Score').first().json.grade }}",
                    "PageSpeed Score": "={{ $('Compute SEO Score').first().json.pagespeedScore }}",
                    "Score Details": "={{ JSON.stringify($('Compute SEO Score').first().json.scores) }}",
                    "Crawl Data": "={{ JSON.stringify($('Compute SEO Score').first().json.crawlData) }}",
                    "AI Analysis": "={{ $json.choices ? $json.choices[0].message.content : '' }}",
                    "Audit Date": "={{ $('Compute SEO Score').first().json.auditDate }}",
                },
                "schema": [
                    {"id": "URL", "type": "string", "display": True, "displayName": "URL"},
                    {"id": "Topic", "type": "string", "display": True, "displayName": "Topic"},
                    {"id": "Composite Score", "type": "number", "display": True, "displayName": "Composite Score"},
                    {"id": "Grade", "type": "string", "display": True, "displayName": "Grade"},
                    {"id": "PageSpeed Score", "type": "number", "display": True, "displayName": "PageSpeed Score"},
                    {"id": "Score Details", "type": "string", "display": True, "displayName": "Score Details"},
                    {"id": "Crawl Data", "type": "string", "display": True, "displayName": "Crawl Data"},
                    {"id": "AI Analysis", "type": "string", "display": True, "displayName": "AI Analysis"},
                    {"id": "Audit Date", "type": "string", "display": True, "displayName": "Audit Date"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(), "name": "Store SEO Audit",
        "type": "n8n-nodes-base.airtable", "position": [2120, 600], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Update Content Topics Score --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CONTENT_TOPICS},
            "columns": {
                "value": {
                    "SEO Score": "={{ $('Compute SEO Score').first().json.composite_score }}",
                    "Last Audit": "={{ $('Compute SEO Score').first().json.auditDate }}",
                },
                "schema": [
                    {"id": "SEO Score", "type": "number", "display": True, "displayName": "SEO Score"},
                    {"id": "Last Audit", "type": "string", "display": True, "displayName": "Last Audit"},
                ],
                "mappingMode": "defineBelow", "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(), "name": "Update Topic Score",
        "type": "n8n-nodes-base.airtable", "position": [2360, 600], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Build & Send Report --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const now = new Date().toLocaleString('en-ZA', { timeZone: 'Africa/Johannesburg' });\n"
                "let audits = [];\n"
                "try { audits = $('Compute SEO Score').all().map(i => i.json); } catch(e) {}\n"
                "const avgScore = audits.length > 0 ? Math.round(audits.reduce((s, a) => s + a.composite_score, 0) / audits.length) : 0;\n"
                "const rowsHtml = audits.map(a => `<tr><td>${a.url}</td><td>${a.composite_score}</td><td>${a.grade}</td><td>${a.pagespeedScore}</td></tr>`).join('\\n');\n"
                "return { json: {\n"
                "  subject: `SEO Maintenance Report: Avg Score ${avgScore}/100 (${audits.length} pages)`,\n"
                "  body: ['<h2 style=\"color:#FF6D5A\">Weekly SEO Maintenance Report</h2>', `<p><strong>Date:</strong> ${now}</p>`, `<p><strong>Pages audited:</strong> ${audits.length}</p>`, `<p><strong>Average SEO score:</strong> ${avgScore}/100</p>`, '<hr>', '<table border=\"1\" cellpadding=\"6\" style=\"border-collapse:collapse\"><tr><th>URL</th><th>SEO Score</th><th>Grade</th><th>PageSpeed</th></tr>', rowsHtml, '</table>', '<hr>', '<p>Full audit details in SEO Audits table.</p>'].join('\\n')\n"
                "}};"
            ),
        },
        "id": uid(), "name": "Build SEO Report",
        "type": "n8n-nodes-base.code", "position": [2600, 400], "typeVersion": 2, "alwaysOutputData": True,
    })
    nodes.append({
        "parameters": {"sendTo": "ian@anyvisionmedia.com", "subject": "={{ $json.subject }}", "emailType": "html", "message": "={{ $json.body }}", "options": {}},
        "id": uid(), "name": "Send SEO Report",
        "type": "n8n-nodes-base.gmail", "position": [2840, 400], "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL}, "onError": "continueRegularOutput",
    })

    # -- Error Handling --
    nodes.append({"parameters": {}, "id": uid(), "name": "Error Trigger", "type": "n8n-nodes-base.errorTrigger", "position": [200, 880], "typeVersion": 1})
    nodes.append({
        "parameters": {"sendTo": "ian@anyvisionmedia.com", "subject": "SEO/SOCIAL ERROR - {{ $json.workflow.name }}", "emailType": "html",
            "message": "=<h2>SEO + Social Engine Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>", "options": {}},
        "id": uid(), "name": "Error Notification", "type": "n8n-nodes-base.gmail", "position": [440, 880], "typeVersion": 2.1, "credentials": {"gmailOAuth2": CRED_GMAIL},
    })
    nodes.append({"parameters": {"content": "## WF-10: SEO Maintenance\n\n**Schedule:** Weekly Sunday 2AM SAST\n**Purpose:** Crawl pages, check broken links, PageSpeed API, AI SEO analysis.\n**Output:** SEO Audits table + Content Topics score update + report email.", "height": 160, "width": 420}, "id": "wf10-note-1", "type": "n8n-nodes-base.stickyNote", "position": [140, 220], "typeVersion": 1, "name": "Note 1"})
    return nodes


def build_wf10_connections():
    """Build connections for SEO Maintenance."""
    return {
        "Weekly Sun 2AM SAST": {"main": [[{"node": "System Config", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "System Config", "type": "main", "index": 0}]]},
        "System Config": {"main": [[{"node": "Read Content Topics", "type": "main", "index": 0}]]},
        "Read Content Topics": {"main": [[{"node": "Loop Over Pages", "type": "main", "index": 0}]]},
        "Loop Over Pages": {"main": [[{"node": "Build SEO Report", "type": "main", "index": 0}], [{"node": "Crawl Page & Check Links", "type": "main", "index": 0}]]},
        "Crawl Page & Check Links": {"main": [[{"node": "PageSpeed API", "type": "main", "index": 0}]]},
        "PageSpeed API": {"main": [[{"node": "Compute SEO Score", "type": "main", "index": 0}]]},
        "Compute SEO Score": {"main": [[{"node": "AI SEO Analysis", "type": "main", "index": 0}]]},
        "AI SEO Analysis": {"main": [[{"node": "Store SEO Audit", "type": "main", "index": 0}]]},
        "Store SEO Audit": {"main": [[{"node": "Update Topic Score", "type": "main", "index": 0}]]},
        "Update Topic Score": {"main": [[{"node": "Loop Over Pages", "type": "main", "index": 0}]]},
        "Build SEO Report": {"main": [[{"node": "Send SEO Report", "type": "main", "index": 0}]]},
        "Error Trigger": {"main": [[{"node": "Error Notification", "type": "main", "index": 0}]]},
    }



# ==================================================================
# WF-11: ANALYTICS & REPORTING
# ==================================================================

def build_wf11_nodes():
    """Build all nodes for the Analytics & Reporting workflow."""
    nodes = []

    # -- Trigger --
    nodes.append({
        "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 4 * * 1"}]}},
        "id": uid(), "name": "Weekly Mon 6AM SAST",
        "type": "n8n-nodes-base.scheduleTrigger", "position": [200, 400], "typeVersion": 1.2,
    })
    nodes.append({"parameters": {}, "id": uid(), "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "position": [200, 600], "typeVersion": 1})

    # -- System Config --
    nodes.append({
        "parameters": {
            "mode": "manual", "duplicateItem": False,
            "assignments": {"assignments": [
                {"id": uid(), "name": "todayDate", "value": "={{ $now.format('yyyy-MM-dd') }}", "type": "string"},
                {"id": uid(), "name": "weekNumber", "value": "={{ $now.format('yyyy') + '-W' + $now.format('WW') }}", "type": "string"},
                {"id": uid(), "name": "monthNumber", "value": "={{ $now.format('yyyy-MM') }}", "type": "string"},
                {"id": uid(), "name": "dayOfMonth", "value": "={{ $now.format('d') }}", "type": "string"},
                {"id": uid(), "name": "aiModel", "value": "anthropic/claude-sonnet-4-20250514", "type": "string"},
                {"id": uid(), "name": "companyName", "value": "AnyVision Media", "type": "string"},
            ]},
        },
        "id": uid(), "name": "System Config",
        "type": "n8n-nodes-base.set", "position": [440, 500], "typeVersion": 3.4,
    })

    # -- Read Engagement Log --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_ENGAGEMENT_LOG},
            "filterByFormula": "=IS_AFTER({Checked At}, DATEADD(TODAY(), -7, 'days'))",
        },
        "id": uid(), "name": "Read Engagement Log",
        "type": "n8n-nodes-base.airtable", "position": [680, 300], "typeVersion": 2.1,
        "alwaysOutputData": True, "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Read Distribution Log --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_DISTRIBUTION_LOG},
            "filterByFormula": "=IS_AFTER({Published At}, DATEADD(TODAY(), -7, 'days'))",
        },
        "id": uid(), "name": "Read Distribution Log",
        "type": "n8n-nodes-base.airtable", "position": [680, 440], "typeVersion": 2.1,
        "alwaysOutputData": True, "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Read Leads --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_LEADS},
            "filterByFormula": "=IS_AFTER({Created At}, DATEADD(TODAY(), -7, 'days'))",
        },
        "id": uid(), "name": "Read Leads",
        "type": "n8n-nodes-base.airtable", "position": [680, 580], "typeVersion": 2.1,
        "alwaysOutputData": True, "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Read SEO Audits --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SEO_AUDITS},
            "filterByFormula": "=IS_AFTER({Audit Date}, DATEADD(TODAY(), -7, 'days'))",
        },
        "id": uid(), "name": "Read SEO Audits",
        "type": "n8n-nodes-base.airtable", "position": [680, 720], "typeVersion": 2.1,
        "alwaysOutputData": True, "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Read Keywords --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_KEYWORDS},
            "filterByFormula": "=({Status} = 'Active')",
        },
        "id": uid(), "name": "Read Keywords",
        "type": "n8n-nodes-base.airtable", "position": [680, 860], "typeVersion": 2.1,
        "alwaysOutputData": True, "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Compute KPIs --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const config = $('System Config').first().json;\n"
                "\n"
                "// Gather data\n"
                "let engagement = [], distribution = [], leads = [], audits = [], keywords = [];\n"
                "try { engagement = $('Read Engagement Log').all().map(i => i.json); } catch(e) {}\n"
                "try { distribution = $('Read Distribution Log').all().map(i => i.json); } catch(e) {}\n"
                "try { leads = $('Read Leads').all().map(i => i.json).filter(l => l.Email); } catch(e) {}\n"
                "try { audits = $('Read SEO Audits').all().map(i => i.json).filter(a => a.URL); } catch(e) {}\n"
                "try { keywords = $('Read Keywords').all().map(i => i.json).filter(k => k.Keyword); } catch(e) {}\n"
                "\n"
                "// Engagement KPIs\n"
                "const totalLikes = engagement.reduce((s, e) => s + (e.Likes || 0), 0);\n"
                "const totalComments = engagement.reduce((s, e) => s + (e.Comments || 0), 0);\n"
                "const totalShares = engagement.reduce((s, e) => s + (e.Shares || 0), 0);\n"
                "const totalImpressions = engagement.reduce((s, e) => s + (e.Impressions || 0), 0);\n"
                "const avgEngagement = engagement.length > 0 ? Math.round(engagement.reduce((s, e) => s + (e['Engagement Score'] || 0), 0) / engagement.length) : 0;\n"
                "\n"
                "// Distribution KPIs\n"
                "const totalPosts = distribution.filter(d => d['Log ID']).length;\n"
                "const successPosts = distribution.filter(d => d.Status === 'Success').length;\n"
                "const publishRate = totalPosts > 0 ? Math.round(successPosts / totalPosts * 100) : 0;\n"
                "\n"
                "// Lead KPIs\n"
                "const newLeads = leads.length;\n"
                "const hotLeads = leads.filter(l => (l['Lead Score'] || 0) >= 80).length;\n"
                "const avgLeadScore = leads.length > 0 ? Math.round(leads.reduce((s, l) => s + (l['Lead Score'] || 0), 0) / leads.length) : 0;\n"
                "\n"
                "// SEO KPIs\n"
                "const avgSeoScore = audits.length > 0 ? Math.round(audits.reduce((s, a) => s + (a['Composite Score'] || 0), 0) / audits.length) : 0;\n"
                "const activeKeywords = keywords.length;\n"
                "\n"
                "const isMonthly = parseInt(config.dayOfMonth) <= 7;\n"
                "\n"
                "const kpis = {\n"
                "  engagement: { likes: totalLikes, comments: totalComments, shares: totalShares, impressions: totalImpressions, avgScore: avgEngagement },\n"
                "  distribution: { totalPosts, successPosts, publishRate },\n"
                "  leads: { newLeads, hotLeads, avgLeadScore },\n"
                "  seo: { avgSeoScore, activeKeywords, pagesAudited: audits.length },\n"
                "  isMonthly: isMonthly,\n"
                "  week: config.weekNumber,\n"
                "  month: config.monthNumber,\n"
                "  date: config.todayDate\n"
                "};\n"
                "\n"
                "return { json: kpis };"
            ),
        },
        "id": uid(), "name": "Compute KPIs",
        "type": "n8n-nodes-base.code", "position": [1000, 500], "typeVersion": 2, "alwaysOutputData": True,
    })

    # -- AI Insights --
    nodes.append({
        "parameters": {
            "method": "POST", "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
            "sendBody": True, "specifyBody": "json",
            "jsonBody": "={\n"
                "  \"model\": \"{{ $('System Config').first().json.aiModel }}\",\n"
                "  \"max_tokens\": 1500,\n"
                "  \"temperature\": 0.6,\n"
                "  \"messages\": [\n"
                "    {\n"
                "      \"role\": \"system\",\n"
                f"      \"content\": {json.dumps(ANALYTICS_INSIGHTS_PROMPT)}\n"
                "    },\n"
                "    {\n"
                "      \"role\": \"user\",\n"
                "      \"content\": {{ JSON.stringify('Weekly KPI Report for AnyVision Media:\\n' + JSON.stringify($json, null, 2)) }}\n"
                "    }\n"
                "  ]\n"
                "}",
            "options": {"timeout": 60000},
        },
        "id": uid(), "name": "AI Weekly Insights",
        "type": "n8n-nodes-base.httpRequest", "position": [1280, 500], "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER}, "onError": "continueRegularOutput",
        "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 3000,
    })

    # -- Build HTML Report --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const kpis = $('Compute KPIs').first().json;\n"
                "const aiResponse = $input.first().json;\n"
                "const now = new Date().toLocaleString('en-ZA', { timeZone: 'Africa/Johannesburg' });\n"
                "\n"
                "let aiInsights = '';\n"
                "try { aiInsights = aiResponse.choices[0].message.content; } catch(e) { aiInsights = 'AI analysis unavailable.'; }\n"
                "\n"
                "const report = [\n"
                "  '<div style=\"font-family:Arial,sans-serif;max-width:700px\">',\n"
                "  '<h2 style=\"color:#FF6D5A\">Weekly Analytics Report</h2>',\n"
                "  `<p><strong>Week:</strong> ${kpis.week} | <strong>Date:</strong> ${now}</p>`,\n"
                "  '<hr>',\n"
                "  '<h3>Engagement</h3>',\n"
                "  `<table border=\"1\" cellpadding=\"6\" style=\"border-collapse:collapse\">`,\n"
                "  `<tr><td>Likes</td><td><strong>${kpis.engagement.likes}</strong></td></tr>`,\n"
                "  `<tr><td>Comments</td><td><strong>${kpis.engagement.comments}</strong></td></tr>`,\n"
                "  `<tr><td>Shares</td><td><strong>${kpis.engagement.shares}</strong></td></tr>`,\n"
                "  `<tr><td>Impressions</td><td><strong>${kpis.engagement.impressions}</strong></td></tr>`,\n"
                "  `<tr><td>Avg Engagement Score</td><td><strong>${kpis.engagement.avgScore}</strong></td></tr>`,\n"
                "  '</table>',\n"
                "  '<h3>Distribution</h3>',\n"
                "  `<p>Posts: ${kpis.distribution.totalPosts} | Success Rate: ${kpis.distribution.publishRate}%</p>`,\n"
                "  '<h3>Leads</h3>',\n"
                "  `<p>New: ${kpis.leads.newLeads} | Hot: ${kpis.leads.hotLeads} | Avg Score: ${kpis.leads.avgLeadScore}</p>`,\n"
                "  '<h3>SEO Health</h3>',\n"
                "  `<p>Avg SEO Score: ${kpis.seo.avgSeoScore}/100 | Active Keywords: ${kpis.seo.activeKeywords} | Pages Audited: ${kpis.seo.pagesAudited}</p>`,\n"
                "  '<hr>',\n"
                "  '<h3>AI Insights</h3>',\n"
                "  `<pre style=\"white-space:pre-wrap;font-size:13px\">${aiInsights}</pre>`,\n"
                "  '</div>',\n"
                "].join('\\n');\n"
                "\n"
                "const tokensUsed = aiResponse.usage ? aiResponse.usage.total_tokens : 0;\n"
                "\n"
                "return { json: {\n"
                "  subject: `Weekly Analytics: ${kpis.leads.newLeads} leads, ${kpis.distribution.totalPosts} posts, SEO ${kpis.seo.avgSeoScore}/100`,\n"
                "  body: report,\n"
                "  kpis: kpis,\n"
                "  tokensUsed: tokensUsed,\n"
                "  isMonthly: kpis.isMonthly\n"
                "}};"
            ),
        },
        "id": uid(), "name": "Build HTML Report",
        "type": "n8n-nodes-base.code", "position": [1560, 500], "typeVersion": 2, "alwaysOutputData": True,
    })

    # -- Store Analytics Snapshot --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_ANALYTICS_SNAPSHOTS},
            "columns": {
                "value": {
                    "Week": "={{ $json.kpis.week }}",
                    "Date": "={{ $json.kpis.date }}",
                    "Total Posts": "={{ $json.kpis.distribution.totalPosts }}",
                    "Success Rate": "={{ $json.kpis.distribution.publishRate }}",
                    "New Leads": "={{ $json.kpis.leads.newLeads }}",
                    "Hot Leads": "={{ $json.kpis.leads.hotLeads }}",
                    "Avg Engagement": "={{ $json.kpis.engagement.avgScore }}",
                    "Avg SEO Score": "={{ $json.kpis.seo.avgSeoScore }}",
                    "Tokens Used": "={{ $json.tokensUsed }}",
                },
                "schema": [
                    {"id": "Week", "type": "string", "display": True, "displayName": "Week"},
                    {"id": "Date", "type": "string", "display": True, "displayName": "Date"},
                    {"id": "Total Posts", "type": "number", "display": True, "displayName": "Total Posts"},
                    {"id": "Success Rate", "type": "number", "display": True, "displayName": "Success Rate"},
                    {"id": "New Leads", "type": "number", "display": True, "displayName": "New Leads"},
                    {"id": "Hot Leads", "type": "number", "display": True, "displayName": "Hot Leads"},
                    {"id": "Avg Engagement", "type": "number", "display": True, "displayName": "Avg Engagement"},
                    {"id": "Avg SEO Score", "type": "number", "display": True, "displayName": "Avg SEO Score"},
                    {"id": "Tokens Used", "type": "number", "display": True, "displayName": "Tokens Used"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(), "name": "Store Analytics Snapshot",
        "type": "n8n-nodes-base.airtable", "position": [1800, 500], "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}, "onError": "continueRegularOutput",
    })

    # -- Send Weekly Report --
    nodes.append({
        "parameters": {"sendTo": "ian@anyvisionmedia.com", "subject": "={{ $('Build HTML Report').first().json.subject }}", "emailType": "html", "message": "={{ $('Build HTML Report').first().json.body }}", "options": {}},
        "id": uid(), "name": "Send Weekly Report",
        "type": "n8n-nodes-base.gmail", "position": [2040, 500], "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL}, "onError": "continueRegularOutput",
    })

    # -- Is Monthly? --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "strict"},
                "combinator": "and",
                "conditions": [{"id": uid(), "operator": {"type": "number", "operation": "lte"}, "leftValue": "={{ parseInt($('System Config').first().json.dayOfMonth) }}", "rightValue": 7}],
            },
            "options": {},
        },
        "id": uid(), "name": "Is Monthly?",
        "type": "n8n-nodes-base.if", "position": [2280, 500], "typeVersion": 2.2,
    })

    # -- AI Monthly Strategy Review --
    nodes.append({
        "parameters": {
            "method": "POST", "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
            "sendBody": True, "specifyBody": "json",
            "jsonBody": "={\n"
                "  \"model\": \"{{ $('System Config').first().json.aiModel }}\",\n"
                "  \"max_tokens\": 2500,\n"
                "  \"temperature\": 0.6,\n"
                "  \"messages\": [\n"
                "    {\n"
                "      \"role\": \"system\",\n"
                f"      \"content\": {json.dumps(MONTHLY_STRATEGY_PROMPT)}\n"
                "    },\n"
                "    {\n"
                "      \"role\": \"user\",\n"
                "      \"content\": {{ JSON.stringify('Monthly Strategy Review for AnyVision Media\\nMonth: ' + $('System Config').first().json.monthNumber + '\\nKPIs: ' + JSON.stringify($('Compute KPIs').first().json, null, 2)) }}\n"
                "    }\n"
                "  ]\n"
                "}",
            "options": {"timeout": 90000},
        },
        "id": uid(), "name": "AI Monthly Strategy",
        "type": "n8n-nodes-base.httpRequest", "position": [2520, 400], "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER}, "onError": "continueRegularOutput",
        "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 5000,
    })

    # -- Send Monthly Report --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=Monthly Strategy Review - {{ $('System Config').first().json.monthNumber }}",
            "emailType": "html",
            "message": "=<h2 style=\"color:#FF6D5A\">Monthly Strategy Review</h2>\n<p><strong>Month:</strong> {{ $('System Config').first().json.monthNumber }}</p>\n<hr>\n<pre style=\"white-space:pre-wrap;font-size:13px\">{{ $json.choices ? $json.choices[0].message.content : 'Strategy review unavailable.' }}</pre>",
            "options": {},
        },
        "id": uid(), "name": "Send Monthly Report",
        "type": "n8n-nodes-base.gmail", "position": [2760, 400], "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL}, "onError": "continueRegularOutput",
    })

    # -- Error Handling --
    nodes.append({"parameters": {}, "id": uid(), "name": "Error Trigger", "type": "n8n-nodes-base.errorTrigger", "position": [200, 1000], "typeVersion": 1})
    nodes.append({
        "parameters": {"sendTo": "ian@anyvisionmedia.com", "subject": "SEO/SOCIAL ERROR - {{ $json.workflow.name }}", "emailType": "html",
            "message": "=<h2>SEO + Social Engine Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>", "options": {}},
        "id": uid(), "name": "Error Notification", "type": "n8n-nodes-base.gmail", "position": [440, 1000], "typeVersion": 2.1, "credentials": {"gmailOAuth2": CRED_GMAIL},
    })
    nodes.append({"parameters": {"content": "## WF-11: Analytics & Reporting\n\n**Schedule:** Weekly Mon 6AM SAST\n**Purpose:** Compute KPIs across all tables, AI insights, HTML report.\n**Monthly:** If day <= 7, triggers extended AI strategy review.", "height": 160, "width": 420}, "id": "wf11-note-1", "type": "n8n-nodes-base.stickyNote", "position": [140, 220], "typeVersion": 1, "name": "Note 1"})
    return nodes


def build_wf11_connections():
    """Build connections for Analytics & Reporting."""
    return {
        "Weekly Mon 6AM SAST": {"main": [[{"node": "System Config", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "System Config", "type": "main", "index": 0}]]},
        "System Config": {"main": [[
            {"node": "Read Engagement Log", "type": "main", "index": 0},
            {"node": "Read Distribution Log", "type": "main", "index": 0},
            {"node": "Read Leads", "type": "main", "index": 0},
            {"node": "Read SEO Audits", "type": "main", "index": 0},
            {"node": "Read Keywords", "type": "main", "index": 0},
        ]]},
        "Read Engagement Log": {"main": [[{"node": "Compute KPIs", "type": "main", "index": 0}]]},
        "Read Distribution Log": {"main": [[{"node": "Compute KPIs", "type": "main", "index": 0}]]},
        "Read Leads": {"main": [[{"node": "Compute KPIs", "type": "main", "index": 0}]]},
        "Read SEO Audits": {"main": [[{"node": "Compute KPIs", "type": "main", "index": 0}]]},
        "Read Keywords": {"main": [[{"node": "Compute KPIs", "type": "main", "index": 0}]]},
        "Compute KPIs": {"main": [[{"node": "AI Weekly Insights", "type": "main", "index": 0}]]},
        "AI Weekly Insights": {"main": [[{"node": "Build HTML Report", "type": "main", "index": 0}]]},
        "Build HTML Report": {"main": [[{"node": "Store Analytics Snapshot", "type": "main", "index": 0}]]},
        "Store Analytics Snapshot": {"main": [[{"node": "Send Weekly Report", "type": "main", "index": 0}]]},
        "Send Weekly Report": {"main": [[{"node": "Is Monthly?", "type": "main", "index": 0}]]},
        "Is Monthly?": {"main": [[{"node": "AI Monthly Strategy", "type": "main", "index": 0}], []]},
        "AI Monthly Strategy": {"main": [[{"node": "Send Monthly Report", "type": "main", "index": 0}]]},
        "Error Trigger": {"main": [[{"node": "Error Notification", "type": "main", "index": 0}]]},
    }


# ==================================================================
# WORKFLOW ASSEMBLY
# ==================================================================

WORKFLOW_DEFS = {
    "wf_score": {
        "name": "SEO Social - Scoring Engine",
        "build_nodes": lambda: build_wf_score_nodes(),
        "build_connections": lambda: build_wf_score_connections(),
    },
    "wf05": {
        "name": "SEO Social - Trend & Keyword Discovery (WF-05)",
        "build_nodes": lambda: build_wf05_nodes(),
        "build_connections": lambda: build_wf05_connections(),
    },
    "wf06": {
        "name": "SEO Social - Content Production (WF-06)",
        "build_nodes": lambda: build_wf06_nodes(),
        "build_connections": lambda: build_wf06_connections(),
    },
    "wf07": {
        "name": "SEO Social - Publishing & Scheduling (WF-07)",
        "build_nodes": lambda: build_wf07_nodes(),
        "build_connections": lambda: build_wf07_connections(),
    },
    "wf08": {
        "name": "SEO Social - Engagement & Community (WF-08)",
        "build_nodes": lambda: build_wf08_nodes(),
        "build_connections": lambda: build_wf08_connections(),
    },
    "wf09": {
        "name": "SEO Social - Lead Capture & Attribution (WF-09)",
        "build_nodes": lambda: build_wf09_nodes(),
        "build_connections": lambda: build_wf09_connections(),
    },
    "wf10": {
        "name": "SEO Social - SEO Maintenance (WF-10)",
        "build_nodes": lambda: build_wf10_nodes(),
        "build_connections": lambda: build_wf10_connections(),
    },
    "wf11": {
        "name": "SEO Social - Analytics & Reporting (WF-11)",
        "build_nodes": lambda: build_wf11_nodes(),
        "build_connections": lambda: build_wf11_connections(),
    },
}


def build_workflow(wf_id):
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


def save_workflow(wf_id, workflow):
    """Save workflow JSON to file."""
    filenames = {
        "wf_score": "wf_score_scoring_engine.json",
        "wf05": "wf05_trend_keyword_discovery.json",
        "wf06": "wf06_content_production.json",
        "wf07": "wf07_publishing_scheduling.json",
        "wf08": "wf08_engagement_community.json",
        "wf09": "wf09_lead_capture_attribution.json",
        "wf10": "wf10_seo_maintenance.json",
        "wf11": "wf11_analytics_reporting.json",
    }

    output_dir = Path(__file__).parent.parent / "workflows" / "seo-social-dept"
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


# ==================================================================
# CLI
# ==================================================================

def main():
    args = sys.argv[1:]
    action = args[0] if args else "build"
    target = args[1] if len(args) > 1 else "all"

    # Add tools dir to path
    sys.path.insert(0, str(Path(__file__).parent))

    print("=" * 60)
    print("SEO + SOCIAL GROWTH ENGINE - WORKFLOW BUILDER")
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
        print("  Set these env vars in .env:")
        print("  - MARKETING_AIRTABLE_BASE_ID")
        print("  - SEO_TABLE_KEYWORDS, SEO_TABLE_SERP_SNAPSHOTS, etc.")
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
    print("  3. Create Airtable tables: Keywords, SERP Snapshots, Engagement Log, Leads,")
    print("     SEO Audits, Analytics Snapshots, Scoring Log, Content Topics")
    print("  4. Set table IDs in .env (SEO_TABLE_KEYWORDS, etc.)")
    print("  5. Test WF-SCORE with Manual Trigger")
    print("  6. Test WF-05 with Manual Trigger -> check Keywords table")
    print("  7. Test WF-09 webhook with curl POST")
    print("  8. Once verified, activate schedule triggers")


if __name__ == "__main__":
    main()
