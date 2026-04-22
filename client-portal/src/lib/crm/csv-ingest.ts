import type { SupabaseClient } from "@supabase/supabase-js";
import type { CrmTargetField } from "./csv-mapping";

export interface IngestInput {
  supabase: SupabaseClient;
  clientId: string;
  importId: string;
  rows: Record<string, string>[];
  mapping: Record<string, CrmTargetField | null>;
  defaultStageKey: string;
}

export interface IngestResult {
  ingested: number;
  failed: number;
  errors: Array<{ row: number; reason: string }>;
}

interface ParsedRow {
  company: {
    name: string;
    domain: string | null;
    industry: string | null;
    country: string | null;
    size_band: string | null;
    revenue_band: string | null;
    website: string | null;
    linkedin_url: string | null;
    hq_city: string | null;
  } | null;
  contact: {
    first_name: string | null;
    last_name: string | null;
    title: string | null;
    email: string | null;
    phone: string | null;
    linkedin_url: string | null;
  } | null;
  lead: {
    stage_key: string | null;
    score: number | null;
    source: string | null;
    tags: string[];
    deal_value_zar: number | null;
    deal_probability: number | null;
    next_action: string | null;
    next_action_at: string | null;
  };
}

/**
 * Apply a user-confirmed mapping to CSV rows and insert companies / contacts / leads.
 *
 * De-duplication:
 *   - Companies unique on (client_id, lower(domain)) → upsert by domain when present.
 *   - Contacts unique on (client_id, lower(email))  → upsert by email when present.
 *   - Leads always inserted fresh (one lead per CSV row; dedup is owner policy).
 */
export async function ingestCsvBatch(input: IngestInput): Promise<IngestResult> {
  const errors: Array<{ row: number; reason: string }> = [];
  let ingested = 0;

  const invMap = invertMapping(input.mapping);

  for (let i = 0; i < input.rows.length; i++) {
    const raw = input.rows[i];
    try {
      const parsed = parseRow(raw, invMap);

      const companyId = parsed.company
        ? await upsertCompany(input.supabase, input.clientId, input.importId, parsed.company)
        : null;

      const contactId = parsed.contact
        ? await upsertContact(
            input.supabase,
            input.clientId,
            input.importId,
            parsed.contact,
            companyId,
          )
        : null;

      await insertLead(input.supabase, input.clientId, input.importId, parsed.lead, {
        companyId,
        contactId,
        defaultStageKey: input.defaultStageKey,
      });
      ingested += 1;
    } catch (err) {
      errors.push({
        row: i + 2, // +2 because row 1 is headers and humans 1-index
        reason: err instanceof Error ? err.message : "Unknown error",
      });
    }
  }

  return { ingested, failed: errors.length, errors };
}

function invertMapping(
  mapping: Record<string, CrmTargetField | null>,
): Partial<Record<CrmTargetField, string>> {
  const inv: Partial<Record<CrmTargetField, string>> = {};
  for (const [col, field] of Object.entries(mapping)) {
    if (field && !inv[field]) inv[field] = col;
  }
  return inv;
}

function pick(
  raw: Record<string, string>,
  invMap: Partial<Record<CrmTargetField, string>>,
  field: CrmTargetField,
): string | null {
  const col = invMap[field];
  if (!col) return null;
  const v = raw[col];
  if (v === undefined || v === null) return null;
  const trimmed = String(v).trim();
  return trimmed === "" ? null : trimmed;
}

function parseRow(
  raw: Record<string, string>,
  invMap: Partial<Record<CrmTargetField, string>>,
): ParsedRow {
  // Company
  let companyName = pick(raw, invMap, "company_name");
  const companyDomain = pick(raw, invMap, "company_domain");
  const companyWebsite = pick(raw, invMap, "company_website");
  // If no explicit name but we have a website, derive name from domain as a last resort.
  if (!companyName && companyWebsite) {
    companyName = deriveNameFromDomain(companyWebsite);
  } else if (!companyName && companyDomain) {
    companyName = deriveNameFromDomain(companyDomain);
  }

  const company = companyName
    ? {
        name: companyName,
        domain: canonicalizeDomain(companyDomain ?? companyWebsite),
        industry: pick(raw, invMap, "company_industry"),
        country: pick(raw, invMap, "company_country"),
        size_band: pick(raw, invMap, "company_size_band"),
        revenue_band: pick(raw, invMap, "company_revenue_band"),
        website: canonicalizeWebsite(companyWebsite),
        linkedin_url: pick(raw, invMap, "company_linkedin_url"),
        hq_city: pick(raw, invMap, "company_hq_city"),
      }
    : null;

  // Contact
  let firstName = pick(raw, invMap, "contact_first_name");
  let lastName = pick(raw, invMap, "contact_last_name");
  const fullName = pick(raw, invMap, "contact_full_name");
  if (!firstName && !lastName && fullName) {
    const parts = fullName.split(/\s+/);
    firstName = parts[0] ?? null;
    lastName = parts.slice(1).join(" ") || null;
  }
  const email = pick(raw, invMap, "contact_email");
  const phone = pick(raw, invMap, "contact_phone");
  const title = pick(raw, invMap, "contact_title");
  const contactLinkedIn = pick(raw, invMap, "contact_linkedin_url");

  const contact =
    firstName || lastName || email || phone
      ? {
          first_name: firstName,
          last_name: lastName,
          title,
          email: email?.toLowerCase() ?? null,
          phone,
          linkedin_url: contactLinkedIn,
        }
      : null;

  // Lead
  const scoreRaw = pick(raw, invMap, "lead_score");
  const dealValueRaw = pick(raw, invMap, "lead_deal_value");
  const probRaw = pick(raw, invMap, "lead_deal_probability");
  const tagsRaw = pick(raw, invMap, "lead_tags");

  const lead = {
    stage_key: pick(raw, invMap, "lead_stage_key"),
    score: clampInt(parseMaybeInt(scoreRaw), 0, 100),
    source: pick(raw, invMap, "lead_source"),
    tags: tagsRaw ? tagsRaw.split(/[,;|]/).map((t) => t.trim()).filter(Boolean) : [],
    deal_value_zar: parseMaybeFloat(dealValueRaw),
    deal_probability: clampInt(parseMaybeInt(probRaw), 0, 100),
    next_action: pick(raw, invMap, "lead_next_action"),
    next_action_at: parseMaybeDate(pick(raw, invMap, "lead_next_action_at")),
  };

  return { company, contact, lead };
}

async function upsertCompany(
  supabase: SupabaseClient,
  clientId: string,
  importId: string,
  company: NonNullable<ParsedRow["company"]>,
): Promise<string> {
  if (company.domain) {
    const { data: existing } = await supabase
      .from("crm_companies")
      .select("id")
      .eq("client_id", clientId)
      .ilike("domain", company.domain)
      .maybeSingle();
    if (existing?.id) return existing.id;
  }

  const { data, error } = await supabase
    .from("crm_companies")
    .insert({ ...company, client_id: clientId, meta: { import_id: importId } })
    .select("id")
    .single();

  if (error) throw new Error(`company insert: ${error.message}`);
  return data.id;
}

async function upsertContact(
  supabase: SupabaseClient,
  clientId: string,
  importId: string,
  contact: NonNullable<ParsedRow["contact"]>,
  companyId: string | null,
): Promise<string> {
  if (contact.email) {
    const { data: existing } = await supabase
      .from("crm_contacts")
      .select("id")
      .eq("client_id", clientId)
      .ilike("email", contact.email)
      .maybeSingle();
    if (existing?.id) return existing.id;
  }

  const { data, error } = await supabase
    .from("crm_contacts")
    .insert({ ...contact, client_id: clientId, company_id: companyId, meta: { import_id: importId } })
    .select("id")
    .single();

  if (error) throw new Error(`contact insert: ${error.message}`);
  return data.id;
}

async function insertLead(
  supabase: SupabaseClient,
  clientId: string,
  importId: string,
  lead: ParsedRow["lead"],
  refs: { companyId: string | null; contactId: string | null; defaultStageKey: string },
): Promise<void> {
  const { error } = await supabase.from("crm_leads").insert({
    client_id: clientId,
    company_id: refs.companyId,
    contact_id: refs.contactId,
    stage_key: lead.stage_key ?? refs.defaultStageKey,
    score: lead.score,
    source: lead.source ?? "csv_import",
    tags: lead.tags,
    deal_value_zar: lead.deal_value_zar,
    deal_probability: lead.deal_probability,
    next_action: lead.next_action,
    next_action_at: lead.next_action_at,
    meta: { import_id: importId },
  });

  if (error) throw new Error(`lead insert: ${error.message}`);
}

// ------------------------------------------------------------------
// parsing helpers
// ------------------------------------------------------------------

function canonicalizeDomain(input: string | null): string | null {
  if (!input) return null;
  return input
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/^www\./, "")
    .replace(/\/.*$/, "")
    .trim() || null;
}

function canonicalizeWebsite(input: string | null): string | null {
  if (!input) return null;
  const t = input.trim();
  if (!t) return null;
  if (/^https?:\/\//i.test(t)) return t;
  return `https://${t}`;
}

function deriveNameFromDomain(input: string): string | null {
  const dom = canonicalizeDomain(input);
  if (!dom) return null;
  const base = dom.split(".")[0];
  if (!base) return null;
  return base.charAt(0).toUpperCase() + base.slice(1);
}

function parseMaybeInt(s: string | null): number | null {
  if (s === null) return null;
  const n = Number(s.replace(/[, ]+/g, ""));
  return Number.isFinite(n) ? Math.round(n) : null;
}

function parseMaybeFloat(s: string | null): number | null {
  if (s === null) return null;
  const n = Number(s.replace(/[^\d.\-]/g, ""));
  return Number.isFinite(n) ? n : null;
}

function clampInt(v: number | null, min: number, max: number): number | null {
  if (v === null) return null;
  return Math.max(min, Math.min(max, v));
}

function parseMaybeDate(s: string | null): string | null {
  if (!s) return null;
  const t = Date.parse(s);
  if (Number.isNaN(t)) return null;
  return new Date(t).toISOString();
}
