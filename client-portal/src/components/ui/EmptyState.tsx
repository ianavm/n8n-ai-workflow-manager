"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowRight } from "lucide-react";

import { EmptyState as PortalEmptyState } from "@/components/portal/EmptyState";
import { Button } from "@/components/ui-shadcn/button";

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    href: string;
  };
}

/**
 * Legacy EmptyState API preserved for admin. Forwards to the portal
 * EmptyState which uses the new token system + Card primitive.
 */
export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <PortalEmptyState
      icon={icon}
      title={title}
      description={description}
      action={
        action ? (
          <Button asChild variant="default" size="sm">
            <Link href={action.href}>
              {action.label}
              <ArrowRight className="size-3.5" />
            </Link>
          </Button>
        ) : undefined
      }
    />
  );
}
