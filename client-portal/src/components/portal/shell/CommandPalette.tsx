"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui-shadcn/command";
import { NAV_GROUPS } from "@/components/portal/shell/nav-config";
import { useMember } from "@/lib/providers/MemberProvider";
import { cn } from "@/lib/utils";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();
  const { memberRole } = useMember();
  const isManager = memberRole === "manager";

  // Global ⌘K / Ctrl+K shortcut is registered by PortalShell so a single
  // instance can be toggled from anywhere in the shell.
  const run = (href: string) => {
    onOpenChange(false);
    router.push(href);
  };

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Command palette"
      description="Jump to a page or action."
      className="max-w-xl"
    >
      <CommandInput placeholder="Search pages, clients, invoices..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        {NAV_GROUPS.map((group, i) => {
          const visibleItems = group.items.filter(
            (item) => !item.managerOnly || isManager,
          );
          if (visibleItems.length === 0) return null;
          return (
            <div key={group.label}>
              {i > 0 ? <CommandSeparator /> : null}
              <CommandGroup heading={group.label}>
                {visibleItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <CommandItem
                      key={item.href}
                      value={`${item.label} ${(item.keywords ?? []).join(" ")} ${group.label}`}
                      onSelect={() => run(item.href)}
                    >
                      <Icon className="size-4 text-[var(--text-muted)]" aria-hidden />
                      <span>{item.label}</span>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </div>
          );
        })}
      </CommandList>
    </CommandDialog>
  );
}

/**
 * Top-bar trigger button styled as a search pill. Parent controls the
 * `open` prop but this renders the visual affordance + Cmd-K label.
 */
export function CommandPaletteTrigger({
  onOpen,
  className,
}: {
  onOpen: () => void;
  className?: string;
}) {
  const [shortcutLabel, setShortcutLabel] = useState<string>("Ctrl K");

  useEffect(() => {
    const isMac = /Mac|iPhone|iPad/.test(navigator.platform);
    setShortcutLabel(isMac ? "⌘K" : "Ctrl K");
  }, []);

  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label="Open command palette"
      className={cn(
        "group hidden md:inline-flex items-center gap-3 h-9 pl-3 pr-2 min-w-[260px] max-w-[360px]",
        "rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-card)]",
        "text-[var(--text-dim)] text-sm transition-colors duration-[var(--dur-fast)]",
        "hover:bg-[var(--bg-card-hover)] hover:border-[var(--border-accent)] hover:text-[var(--text-muted)]",
        "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-[var(--ring)]/40",
        className,
      )}
    >
      <Search className="size-3.5 shrink-0" />
      <span className="flex-1 text-left">Search or jump to...</span>
      <kbd className="ml-auto inline-flex items-center gap-1 rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-inset)] px-2 py-0.5 text-[10px] font-mono font-semibold text-[var(--text-muted)]">
        {shortcutLabel}
      </kbd>
    </button>
  );
}

export { CommandShortcut };
