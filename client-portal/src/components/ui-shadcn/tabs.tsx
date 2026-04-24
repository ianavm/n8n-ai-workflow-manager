"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Tabs as TabsPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";

function Tabs({
  className,
  orientation = "horizontal",
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      data-orientation={orientation}
      orientation={orientation}
      className={cn(
        "group/tabs flex gap-4 data-[orientation=horizontal]:flex-col",
        className,
      )}
      {...props}
    />
  );
}

const tabsListVariants = cva(
  "group/tabs-list inline-flex w-fit items-center justify-center rounded-[var(--radius-md)] text-[var(--text-muted)] group-data-[orientation=horizontal]/tabs:h-10 group-data-[orientation=vertical]/tabs:h-fit group-data-[orientation=vertical]/tabs:flex-col",
  {
    variants: {
      variant: {
        // Pill group on a glass surface (mirrors website segmented control)
        default: "bg-[var(--bg-card)] border border-[var(--border-subtle)] p-1 gap-1",
        // Underline row (matches website section nav)
        line: "gap-6 bg-transparent border-b border-[var(--border-subtle)] rounded-none px-0",
        // Ghost — no surrounding surface, hover-only highlight
        ghost: "bg-transparent gap-2 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

function TabsList({
  className,
  variant = "default",
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List> &
  VariantProps<typeof tabsListVariants>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      data-variant={variant}
      className={cn(tabsListVariants({ variant }), className)}
      {...props}
    />
  );
}

function TabsTrigger({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "relative inline-flex items-center justify-center gap-1.5 whitespace-nowrap text-sm font-medium transition-all duration-[var(--dur-med)]",
        "group-data-[orientation=vertical]/tabs:w-full group-data-[orientation=vertical]/tabs:justify-start",
        "hover:text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-[var(--ring)]/40",
        "disabled:pointer-events-none disabled:opacity-50",
        "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        // Default (pill) variant
        "group-data-[variant=default]/tabs-list:px-4 group-data-[variant=default]/tabs-list:py-1.5 group-data-[variant=default]/tabs-list:rounded-[var(--radius-sm)]",
        "group-data-[variant=default]/tabs-list:data-[state=active]:bg-[var(--bg-elevated)] group-data-[variant=default]/tabs-list:data-[state=active]:text-foreground group-data-[variant=default]/tabs-list:data-[state=active]:shadow-[0_1px_2px_rgba(0,0,0,0.3),0_0_0_1px_var(--border-accent)_inset]",
        // Line variant — coral underline on active
        "group-data-[variant=line]/tabs-list:pb-3 group-data-[variant=line]/tabs-list:px-1 group-data-[variant=line]/tabs-list:rounded-none group-data-[variant=line]/tabs-list:bg-transparent",
        "group-data-[variant=line]/tabs-list:after:absolute group-data-[variant=line]/tabs-list:after:-bottom-px group-data-[variant=line]/tabs-list:after:left-0 group-data-[variant=line]/tabs-list:after:right-0 group-data-[variant=line]/tabs-list:after:h-[2px] group-data-[variant=line]/tabs-list:after:bg-[var(--brand-primary)] group-data-[variant=line]/tabs-list:after:opacity-0 group-data-[variant=line]/tabs-list:after:transition-opacity",
        "group-data-[variant=line]/tabs-list:data-[state=active]:text-foreground group-data-[variant=line]/tabs-list:data-[state=active]:after:opacity-100",
        // Ghost variant — subtle pill on active
        "group-data-[variant=ghost]/tabs-list:px-3 group-data-[variant=ghost]/tabs-list:py-1.5 group-data-[variant=ghost]/tabs-list:rounded-[var(--radius-sm)]",
        "group-data-[variant=ghost]/tabs-list:hover:bg-[var(--bg-card)]",
        "group-data-[variant=ghost]/tabs-list:data-[state=active]:bg-[var(--bg-card)] group-data-[variant=ghost]/tabs-list:data-[state=active]:text-foreground",
        className,
      )}
      {...props}
    />
  );
}

function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn("flex-1 outline-none", className)}
      {...props}
    />
  );
}

export { Tabs, TabsList, TabsTrigger, TabsContent, tabsListVariants };
