import { NextRequest, NextResponse } from "next/server";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import type { AutomationTemplate } from "@/components/onboarding/types";

// Static automation templates — these are filtered by industry/need at runtime
const ALL_TEMPLATES: AutomationTemplate[] = [
  // Marketing templates
  {
    id: "lead_auto_respond",
    name: "Auto-Respond to New Leads",
    description: "Instantly reply to new inquiries with a personalised AI message and log them to your CRM.",
    time_saved: "5 hours/week",
    tools_needed: ["google_workspace"],
    category: "marketing",
    icon: "⚡",
  },
  {
    id: "social_content",
    name: "AI Social Media Content",
    description: "Generate and publish weekly social media posts across all your platforms automatically.",
    time_saved: "8 hours/week",
    tools_needed: [],
    category: "marketing",
    icon: "📱",
  },
  {
    id: "weekly_performance",
    name: "Weekly Performance Report",
    description: "Get an AI-generated summary of your marketing, leads, and revenue every Monday morning.",
    time_saved: "3 hours/week",
    tools_needed: ["google_workspace"],
    category: "marketing",
    icon: "📊",
  },
  {
    id: "ad_campaign_monitor",
    name: "Ad Campaign Monitor",
    description: "Track your Google and Meta ad spend, flag underperformers, and suggest optimisations.",
    time_saved: "4 hours/week",
    tools_needed: ["google_ads", "meta_ads"],
    category: "marketing",
    icon: "📈",
  },
  // Accounting templates
  {
    id: "invoice_followup",
    name: "Invoice Follow-Up Automation",
    description: "Send friendly payment reminders on schedule — 7 days, 14 days, 30 days overdue.",
    time_saved: "6 hours/week",
    tools_needed: ["quickbooks", "google_workspace"],
    category: "accounting",
    icon: "💰",
  },
  {
    id: "expense_tracker",
    name: "Smart Expense Tracking",
    description: "Automatically categorise and log business expenses from email receipts.",
    time_saved: "4 hours/week",
    tools_needed: ["quickbooks", "google_workspace"],
    category: "accounting",
    icon: "🧾",
  },
  {
    id: "month_end_prep",
    name: "Month-End Prep Assistant",
    description: "AI generates your month-end reconciliation checklist and flags discrepancies.",
    time_saved: "10 hours/month",
    tools_needed: ["quickbooks"],
    category: "accounting",
    icon: "📋",
  },
  // Advisory templates
  {
    id: "client_onboarding",
    name: "Client Onboarding Workflow",
    description: "Automate new client intake — forms, document collection, welcome emails, and scheduling.",
    time_saved: "3 hours/client",
    tools_needed: ["google_workspace"],
    category: "advisory",
    icon: "🤝",
  },
  {
    id: "meeting_prep",
    name: "AI Meeting Prep",
    description: "Before every client meeting, get an AI briefing with key metrics and talking points.",
    time_saved: "2 hours/meeting",
    tools_needed: ["google_workspace"],
    category: "advisory",
    icon: "📝",
  },
  // General / All-purpose
  {
    id: "email_triage",
    name: "Smart Email Triage",
    description: "AI classifies incoming emails by urgency and department, then routes them automatically.",
    time_saved: "5 hours/week",
    tools_needed: ["google_workspace"],
    category: "all",
    icon: "📧",
  },
];

export async function GET(request: NextRequest) {
  // Auth check (HIGH-3 fix)
  const supabase = await createServerSupabaseClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const primaryNeed = searchParams.get("primary_need") || "";

  // Filter templates based on primary need
  let filtered = ALL_TEMPLATES;
  if (primaryNeed && primaryNeed !== "all") {
    // Show category-specific templates + general templates
    filtered = ALL_TEMPLATES.filter(
      (t) => t.category === primaryNeed || t.category === "all"
    );
  }

  // If no filters or very few results, show all
  if (filtered.length < 3) {
    filtered = ALL_TEMPLATES;
  }

  // Limit to 6 templates max for the onboarding wizard
  const templates = filtered.slice(0, 6);

  return NextResponse.json({ templates });
}
