export interface MergeTagContact {
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  title: string | null;
}

export interface MergeTagCompany {
  name: string | null;
  industry: string | null;
  website: string | null;
}

export interface MergeTagLead {
  id: string;
  next_action: string | null;
  tags: string[];
}

export interface MergeTagContext {
  lead: MergeTagLead;
  contact: MergeTagContact | null;
  company: MergeTagCompany | null;
  sender: {
    name: string | null;
    email: string | null;
    signature: string | null;
  };
  custom?: Record<string, string | number | null | undefined>;
}

/**
 * Resolve {{tag}} merge tags in a string. Unknown tags are left intact so the
 * user sees them and can fill them in manually.
 */
export function renderMergeTags(input: string, ctx: MergeTagContext): string {
  if (!input) return "";
  return input.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (match, tag: string) => {
    const value = resolveTag(tag, ctx);
    return value ?? match;
  });
}

function resolveTag(tag: string, ctx: MergeTagContext): string | null {
  switch (tag) {
    case "first_name":
      return ctx.contact?.first_name ?? null;
    case "last_name":
      return ctx.contact?.last_name ?? null;
    case "contact_name":
      return joinName(ctx.contact?.first_name, ctx.contact?.last_name);
    case "contact_email":
      return ctx.contact?.email ?? null;
    case "title":
      return ctx.contact?.title ?? null;
    case "company":
      return ctx.company?.name ?? null;
    case "industry":
      return ctx.company?.industry ?? null;
    case "website":
      return ctx.company?.website ?? null;
    case "sender_name":
      return ctx.sender.name ?? null;
    case "sender_email":
      return ctx.sender.email ?? null;
    case "signature":
      return ctx.sender.signature ?? null;
    case "pain_point":
    case "custom_note":
    case "meeting_link":
      return coerce(ctx.custom?.[tag]);
    default:
      return coerce(ctx.custom?.[tag]);
  }
}

function joinName(first?: string | null, last?: string | null): string | null {
  const parts = [first, last].filter(Boolean);
  return parts.length ? parts.join(" ") : null;
}

function coerce(value: string | number | null | undefined): string | null {
  if (value === null || value === undefined || value === "") return null;
  return String(value);
}

/**
 * Extract the tag names present in a template string (without braces).
 */
export function extractMergeTags(input: string): string[] {
  const tags = new Set<string>();
  const re = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(input)) !== null) {
    tags.add(m[1]);
  }
  return Array.from(tags);
}
