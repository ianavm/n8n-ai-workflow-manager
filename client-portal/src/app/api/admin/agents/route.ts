import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

// Tier mapping for agent grouping
const AGENT_TIERS: Record<string, number> = {
  agent_orchestrator: 1, agent_chief: 1,
  agent_finance: 2, agent_marketing: 2, agent_growth_organic: 2, agent_growth_paid: 2, agent_pipeline: 2,
  agent_client_success: 3, agent_support: 3, agent_whatsapp: 3,
  agent_sentinel: 4, agent_engineer: 4, agent_devops: 4,
  agent_content: 5, agent_intelligence: 5, agent_market_intel: 5, agent_knowledge_mgr: 5, agent_data_analyst: 5,
  agent_qa: 6, agent_brand_guardian: 6, agent_compliance: 6,
  agent_financial_intel: 7, agent_crm_sync: 7, agent_booking: 7, agent_data_curator: 7,
};

async function checkAdminOrApiKey(req: NextRequest): Promise<boolean> {
  // Admin session auth
  const session = await getSession();
  if (session && (session.role === "owner" || session.role === "employee")) return true;
  // Internal API key auth (for n8n workflows)
  const apiKey = req.headers.get("x-api-key");
  if (apiKey && apiKey === process.env.INTERNAL_API_KEY) return true;
  return false;
}

export async function GET(req: NextRequest) {
  if (!(await checkAdminOrApiKey(req))) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServiceRoleClient();
  const { data, error } = await supabase
    .from("agent_status")
    .select("*")
    .order("department")
    .order("agent_id");

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  // Map DB columns to frontend-expected shape
  const mapped = (data || []).map((agent) => ({
    id: agent.id,
    agent_id: agent.agent_id,
    agent_name: agent.agent_name,
    department: agent.department,
    status: agent.status,
    health_score: agent.health_score,
    workflows_monitored: Array.isArray(agent.workflow_ids) ? agent.workflow_ids.length : 0,
    workflow_ids: agent.workflow_ids || [],
    last_heartbeat: agent.last_heartbeat,
    kpi_summary: agent.kpis || {},
    error_summary: agent.error_count > 0 ? [{ workflow_id: "unknown", errors: agent.error_count }] : [],
    error_count: agent.error_count || 0,
    tier: AGENT_TIERS[agent.agent_id] || 7,
    updated_at: agent.updated_at,
  }));

  return NextResponse.json(mapped);
}

export async function POST(req: NextRequest) {
  if (!(await checkAdminOrApiKey(req))) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServiceRoleClient();
  const body = await req.json();

  const { data, error } = await supabase
    .from("agent_status")
    .upsert(
      {
        agent_id: body.agent_id,
        agent_name: body.agent_name,
        department: body.department,
        status: body.status,
        health_score: body.health_score,
        workflow_ids: body.workflow_ids || [],
        last_heartbeat: new Date().toISOString(),
        kpis: body.kpi_summary || body.kpis || {},
        error_count: body.error_count || 0,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "agent_id" }
    )
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}
