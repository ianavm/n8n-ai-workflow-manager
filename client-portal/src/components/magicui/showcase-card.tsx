/**
 * Showcase card — smoke-test wiring for shadcn + MagicUI.
 * Composes a shadcn <Card> with MagicUI <BorderBeam>.
 * Use when you want an animated accent on a featured card.
 */
"use client";

import * as React from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui-shadcn/card";
import { BorderBeam } from "@/components/magicui/border-beam";
import { cn } from "@/lib/utils";

interface ShowcaseCardProps {
  title: string;
  description?: string;
  children?: React.ReactNode;
  className?: string;
  beamDuration?: number;
}

export function ShowcaseCard({
  title,
  description,
  children,
  className,
  beamDuration = 8,
}: ShowcaseCardProps) {
  return (
    <Card className={cn("relative overflow-hidden", className)}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      {children ? <CardContent>{children}</CardContent> : null}
      <BorderBeam duration={beamDuration} size={100} />
    </Card>
  );
}
