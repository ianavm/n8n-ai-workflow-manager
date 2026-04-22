/**
 * Auto-detect which CSV columns map to which CRM fields.
 *
 * We match on normalized column names (lowercase, alphanumeric only), trying
 * canonical names first, then a list of common aliases exported by HubSpot,
 * Pipedrive, Salesforce, Zoho, Apollo, etc.
 */

export type CrmTargetField =
  // Company
  | "company_name"
  | "company_domain"
  | "company_industry"
  | "company_country"
  | "company_size_band"
  | "company_revenue_band"
  | "company_website"
  | "company_linkedin_url"
  | "company_hq_city"
  // Contact
  | "contact_first_name"
  | "contact_last_name"
  | "contact_full_name"
  | "contact_title"
  | "contact_email"
  | "contact_phone"
  | "contact_linkedin_url"
  // Lead
  | "lead_stage_key"
  | "lead_score"
  | "lead_source"
  | "lead_tags"
  | "lead_deal_value"
  | "lead_deal_probability"
  | "lead_next_action"
  | "lead_next_action_at";

export interface FieldDefinition {
  key: CrmTargetField;
  label: string;
  group: "company" | "contact" | "lead";
  required?: boolean;
  aliases: string[];
}

export const FIELD_DEFINITIONS: readonly FieldDefinition[] = [
  {
    key: "company_name",
    label: "Company name",
    group: "company",
    required: true,
    aliases: ["company", "companyname", "accountname", "account", "organization", "organisation", "businessname"],
  },
  {
    key: "company_domain",
    label: "Company domain",
    group: "company",
    aliases: ["domain", "companydomain", "website", "websiteurl", "url"],
  },
  {
    key: "company_industry",
    label: "Industry",
    group: "company",
    aliases: ["industry", "sector", "vertical"],
  },
  {
    key: "company_country",
    label: "Country",
    group: "company",
    aliases: ["country", "companycountry", "billingcountry"],
  },
  {
    key: "company_size_band",
    label: "Company size",
    group: "company",
    aliases: ["companysize", "employees", "numberofemployees", "headcount", "sizeband"],
  },
  {
    key: "company_revenue_band",
    label: "Revenue",
    group: "company",
    aliases: ["revenue", "annualrevenue", "revenueband"],
  },
  {
    key: "company_website",
    label: "Website",
    group: "company",
    aliases: ["website", "websiteurl", "url", "companywebsite"],
  },
  {
    key: "company_linkedin_url",
    label: "Company LinkedIn",
    group: "company",
    aliases: ["linkedin", "companylinkedin", "linkedincompany", "linkedinurl"],
  },
  {
    key: "company_hq_city",
    label: "HQ city",
    group: "company",
    aliases: ["city", "hqcity", "headquarters", "billingcity"],
  },
  {
    key: "contact_first_name",
    label: "First name",
    group: "contact",
    aliases: ["firstname", "givenname", "first"],
  },
  {
    key: "contact_last_name",
    label: "Last name",
    group: "contact",
    aliases: ["lastname", "surname", "familyname", "last"],
  },
  {
    key: "contact_full_name",
    label: "Full name",
    group: "contact",
    aliases: ["name", "fullname", "contactname", "leadname"],
  },
  {
    key: "contact_title",
    label: "Title / role",
    group: "contact",
    aliases: ["title", "jobtitle", "role", "position"],
  },
  {
    key: "contact_email",
    label: "Email",
    group: "contact",
    aliases: ["email", "emailaddress", "workemail", "contactemail"],
  },
  {
    key: "contact_phone",
    label: "Phone",
    group: "contact",
    aliases: ["phone", "phonenumber", "mobile", "mobilephone", "workphone", "telephone"],
  },
  {
    key: "contact_linkedin_url",
    label: "Contact LinkedIn",
    group: "contact",
    aliases: ["linkedin", "personlinkedin", "contactlinkedin", "linkedinprofile"],
  },
  {
    key: "lead_stage_key",
    label: "Stage",
    group: "lead",
    aliases: ["stage", "dealstage", "status", "pipelinestage", "leadstatus"],
  },
  {
    key: "lead_score",
    label: "Score (0-100)",
    group: "lead",
    aliases: ["score", "leadscore", "rating"],
  },
  {
    key: "lead_source",
    label: "Source",
    group: "lead",
    aliases: ["source", "leadsource", "utm", "originalsource", "channel"],
  },
  {
    key: "lead_tags",
    label: "Tags (comma-separated)",
    group: "lead",
    aliases: ["tags", "labels", "segment"],
  },
  {
    key: "lead_deal_value",
    label: "Deal value",
    group: "lead",
    aliases: ["dealvalue", "amount", "dealamount", "value", "opportunityamount"],
  },
  {
    key: "lead_deal_probability",
    label: "Probability (0-100)",
    group: "lead",
    aliases: ["probability", "dealprobability", "winprobability"],
  },
  {
    key: "lead_next_action",
    label: "Next action",
    group: "lead",
    aliases: ["nextaction", "nextstep", "action", "task"],
  },
  {
    key: "lead_next_action_at",
    label: "Next action date",
    group: "lead",
    aliases: ["nextactionat", "nextactiondate", "duedate", "nextstepdate", "followupdate"],
  },
];

export function normalizeHeader(header: string): string {
  return header.toLowerCase().replace(/[^a-z0-9]+/g, "");
}

/**
 * For each CSV column, return the best-guess target field (or null).
 * First match wins — FIELD_DEFINITIONS order is authoritative for ties.
 */
export function autoDetectMapping(
  headers: string[],
): Record<string, CrmTargetField | null> {
  const used = new Set<CrmTargetField>();
  const result: Record<string, CrmTargetField | null> = {};

  for (const header of headers) {
    const norm = normalizeHeader(header);
    let best: CrmTargetField | null = null;

    for (const def of FIELD_DEFINITIONS) {
      if (used.has(def.key)) continue;
      if (normalizeHeader(def.key.replace(/^(company|contact|lead)_/, "")) === norm) {
        best = def.key;
        break;
      }
      if (def.aliases.some((a) => a === norm)) {
        best = def.key;
        break;
      }
    }

    result[header] = best;
    if (best) used.add(best);
  }

  return result;
}

export function getFieldDefinition(key: CrmTargetField): FieldDefinition {
  const def = FIELD_DEFINITIONS.find((d) => d.key === key);
  if (!def) throw new Error(`Unknown CRM target field: ${key}`);
  return def;
}
