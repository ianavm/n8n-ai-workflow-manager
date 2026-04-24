"use client";

import Link from "next/link";
import { Bell } from "lucide-react";

import { Button } from "@/components/ui-shadcn/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui-shadcn/popover";
import { Badge } from "@/components/ui-shadcn/badge";

export function NotificationsMenu() {
  // Notifications are fetched on the /portal/notifications page itself —
  // the top-bar popover is a light preview. Empty state for now; real
  // data wires in during Phase F without touching the shell.
  const unreadCount = 0;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          className="relative"
          aria-label={`Notifications${unreadCount ? ` (${unreadCount} unread)` : ""}`}
        >
          <Bell className="size-4" />
          {unreadCount > 0 ? (
            <span
              aria-hidden
              className="absolute top-1 right-1 size-2 rounded-full bg-[var(--accent-coral)] ring-2 ring-[var(--bg-elevated)] pulse-dot"
            />
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-4 py-3">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-foreground">Notifications</h3>
            {unreadCount > 0 ? (
              <Badge tone="brand" appearance="soft" size="sm">
                {unreadCount}
              </Badge>
            ) : null}
          </div>
        </div>
        <div className="flex flex-col items-center justify-center px-6 py-8 text-center">
          <div className="grid size-10 place-items-center rounded-full bg-[var(--bg-card-hover)] text-[var(--text-muted)] mb-3">
            <Bell className="size-4" aria-hidden />
          </div>
          <p className="text-sm font-semibold text-foreground">You&rsquo;re all caught up</p>
          <p className="text-xs text-[var(--text-dim)] mt-1">
            New alerts will appear here as they happen.
          </p>
        </div>
        <div className="border-t border-[var(--border-subtle)] px-2 py-2">
          <Button variant="ghost" size="sm" asChild className="w-full justify-center">
            <Link href="/portal/notifications">View all</Link>
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
