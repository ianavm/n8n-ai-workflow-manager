import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { BlobBackground } from "@/components/portal/BlobBackground";
import { SectionHeader, type BreadcrumbItem } from "@/components/portal/SectionHeader";

interface PageHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  breadcrumb?: BreadcrumbItem[];
  actions?: ReactNode;
  /** Hero ambience — adds blob backgrounds + dot matrix region. */
  hero?: boolean;
  className?: string;
}

/**
 * Page-level hero header. Sits at the top of every portal page, above the
 * main grid. `hero` turns on the ambient blobs for landing-page style
 * impact on Dashboard, Login, Onboarding.
 */
export function PageHeader({
  title,
  description,
  eyebrow,
  breadcrumb,
  actions,
  hero = false,
  className,
}: PageHeaderProps) {
  return (
    <section
      className={cn(
        "relative overflow-hidden",
        hero ? "py-8 md:py-12" : "py-4 md:py-6",
        className,
      )}
    >
      {hero ? <BlobBackground intensity="subtle" /> : null}
      <div className="relative z-[1]">
        <SectionHeader
          title={title}
          description={description}
          eyebrow={eyebrow}
          breadcrumb={breadcrumb}
          actions={actions}
          size="lg"
        />
      </div>
    </section>
  );
}
