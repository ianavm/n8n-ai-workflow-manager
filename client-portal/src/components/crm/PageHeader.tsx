import type { ReactNode } from "react";

import { PageHeader as PortalPageHeader } from "@/components/portal/PageHeader";

interface PageHeaderProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

/**
 * Thin adapter: CRM pages keep their `<PageHeader title description action>`
 * API while rendering the portal-wide PageHeader (eyebrow, gradient accent,
 * consistent spacing).
 */
export function PageHeader({ title, description, action }: PageHeaderProps) {
  return (
    <PortalPageHeader
      eyebrow="CRM"
      title={title}
      description={description}
      actions={action}
    />
  );
}
