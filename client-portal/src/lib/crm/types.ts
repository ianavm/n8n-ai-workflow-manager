export type CrmStageKey =
  | "new"
  | "enriched"
  | "researched"
  | "outreach_sent"
  | "replied"
  | "meeting_booked"
  | "closed_won"
  | "closed_lost"
  | (string & {});

export interface CrmStage {
  id: string;
  client_id: string;
  key: CrmStageKey;
  label: string;
  order_index: number;
  is_won: boolean;
  is_lost: boolean;
  color: string | null;
}

export interface CrmCompany {
  id: string;
  client_id: string;
  name: string;
  domain: string | null;
  industry: string | null;
  country: string | null;
  size_band: string | null;
  revenue_band: string | null;
  linkedin_url: string | null;
  website: string | null;
  logo_url: string | null;
  hq_city: string | null;
  meta: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CrmContact {
  id: string;
  client_id: string;
  company_id: string | null;
  first_name: string | null;
  last_name: string | null;
  title: string | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  avatar_url: string | null;
  meta: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CrmLead {
  id: string;
  client_id: string;
  company_id: string | null;
  contact_id: string | null;
  stage_key: CrmStageKey;
  score: number | null;
  status_tags: string[];
  tags: string[];
  owner_admin_id: string | null;
  source: string | null;
  source_campaign: string | null;
  next_action: string | null;
  next_action_at: string | null;
  last_touch_at: string | null;
  deal_value_zar: number | null;
  deal_probability: number | null;
  closed_at: string | null;
  meta: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CrmLeadWithRelations extends CrmLead {
  company: CrmCompany | null;
  contact: CrmContact | null;
}

export type CrmActivityKind =
  | "created"
  | "enriched"
  | "researched"
  | "scored"
  | "stage_changed"
  | "owner_changed"
  | "emailed"
  | "opened"
  | "clicked"
  | "replied"
  | "call_scheduled"
  | "call_completed"
  | "note_added"
  | "tag_added"
  | "tag_removed"
  | "won"
  | "lost";

export interface CrmActivity {
  id: string;
  client_id: string;
  lead_id: string;
  kind: CrmActivityKind;
  meta: Record<string, unknown>;
  actor_admin_id: string | null;
  created_at: string;
}

export type CrmTemplateCategory =
  | "cold_outreach"
  | "follow_up"
  | "post_meeting"
  | "nurture"
  | "other";

export interface CrmEmailTemplate {
  id: string;
  client_id: string;
  name: string;
  category: CrmTemplateCategory;
  subject: string;
  body: string;
  variables: string[];
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface CrmEmailMessage {
  id: string;
  client_id: string;
  lead_id: string;
  template_id: string | null;
  direction: "out" | "in";
  send_mode: "mailto" | "gmail_draft" | "gmail_send" | null;
  provider_message_id: string | null;
  to_email: string | null;
  from_email: string | null;
  subject: string;
  body: string;
  sent_at: string | null;
  opened_at: string | null;
  first_clicked_at: string | null;
  replied_at: string | null;
  created_at: string;
}

export interface CrmResearchReport {
  id: string;
  client_id: string;
  lead_id: string;
  summary: string | null;
  sections: Record<string, unknown>;
  doc_url: string | null;
  pdf_url: string | null;
  model: string | null;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd: number | null;
  version: number;
  is_current: boolean;
  created_at: string;
}

export interface CrmConfig {
  id: string;
  client_id: string;
  sender_name: string | null;
  sender_email: string | null;
  sender_signature: string | null;
  accent_color: string | null;
  score_weight_icp_fit: number;
  score_weight_signals: number;
  score_weight_recency: number;
  score_weight_completeness: number;
  timezone: string;
  airtable_base_id: string | null;
  airtable_companies_table: string | null;
  airtable_leads_table: string | null;
  airtable_sync_enabled: boolean;
  workflow_ids: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface LeadListFilters {
  q?: string;
  stage?: CrmStageKey[];
  industry?: string[];
  country?: string[];
  minScore?: number;
  maxScore?: number;
  source?: string[];
}

export interface Paginated<T> {
  rows: T[];
  total: number;
  page: number;
  pageSize: number;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  meta?: { total: number; page: number; limit: number };
}

export const CRM_ACCENT = "#FF6D5A" as const;
export const CRM_ACCENT_BG = "rgba(255,109,90,0.15)" as const;
export const CRM_ACCENT_BORDER = "rgba(255,109,90,0.3)" as const;
