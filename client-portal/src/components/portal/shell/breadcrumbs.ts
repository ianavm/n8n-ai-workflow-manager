import { NAV_ITEMS_FLAT } from "@/components/portal/shell/nav-config";
import type { BreadcrumbItem } from "@/components/portal/SectionHeader";

/**
 * Build a breadcrumb trail from a pathname.
 *
 * Rules:
 *   - Always start with "Portal" linking to `/portal`.
 *   - Match each path segment against the nav config when possible.
 *   - Overrides take precedence (e.g. for dynamic `[id]` routes where we
 *     want to show the resource name instead of the slug).
 */
export function buildBreadcrumbs(
  pathname: string,
  overrides: Record<string, string> = {},
): BreadcrumbItem[] {
  if (!pathname.startsWith("/portal")) return [];

  const segments = pathname.split("/").filter(Boolean); // ["portal", ...]
  const trail: BreadcrumbItem[] = [{ label: "Portal", href: "/portal" }];

  let accumulated = "";
  for (const seg of segments) {
    accumulated += `/${seg}`;
    if (seg === "portal") continue;

    const navMatch = NAV_ITEMS_FLAT.find((n) => n.href === accumulated);
    const overrideLabel = overrides[accumulated];

    trail.push({
      label: overrideLabel ?? navMatch?.label ?? humanize(seg),
      href: accumulated === pathname ? undefined : accumulated,
    });
  }

  return trail;
}

function humanize(segment: string): string {
  // Skip pure UUIDs / numeric ids — caller is expected to pass an override.
  if (/^[0-9a-f-]{8,}$/i.test(segment)) return "Details";
  return segment
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
