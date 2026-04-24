"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronsUpDown, CreditCard, LogOut, Settings, User } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { useBrand } from "@/lib/providers/BrandProvider";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui-shadcn/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui-shadcn/dropdown-menu";
import { cn } from "@/lib/utils";

interface UserMenuProps {
  variant?: "sidebar" | "topbar";
}

function initialsFrom(name: string | null | undefined): string {
  if (!name) return "AV";
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "AV";
}

export function UserMenu({ variant = "sidebar" }: UserMenuProps) {
  const router = useRouter();
  const { companyName, logoUrl } = useBrand();
  const [email, setEmail] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const supabase = createClient();
      const { data } = await supabase.auth.getUser();
      if (cancelled || !data.user) return;
      setEmail(data.user.email ?? null);
      const meta = data.user.user_metadata as { full_name?: string; name?: string } | undefined;
      setDisplayName(meta?.full_name ?? meta?.name ?? null);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/portal/login");
  }

  const label = displayName ?? email ?? companyName;
  const initials = initialsFrom(displayName ?? companyName);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className={cn(
            "flex items-center gap-3 rounded-[var(--radius-md)] text-left transition-colors duration-[var(--dur-fast)]",
            "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-[var(--ring)]/40",
            variant === "sidebar"
              ? "w-full p-2 hover:bg-[var(--sidebar-accent)]"
              : "p-1 pr-2 hover:bg-[var(--bg-card-hover)]",
          )}
          aria-label="Account menu"
        >
          <Avatar className="size-8 ring-1 ring-[var(--border-subtle)]">
            {logoUrl ? <AvatarImage src={logoUrl} alt={companyName} /> : null}
            <AvatarFallback className="bg-[image:var(--brand-gradient)] text-white text-xs font-bold">
              {initials}
            </AvatarFallback>
          </Avatar>
          {variant === "sidebar" ? (
            <>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-foreground truncate">{label}</p>
                <p className="text-xs text-[var(--text-dim)] truncate">{email ?? companyName}</p>
              </div>
              <ChevronsUpDown className="size-3.5 text-[var(--text-dim)] shrink-0" aria-hidden />
            </>
          ) : (
            <span className="hidden md:inline text-sm font-medium text-foreground max-w-[160px] truncate">
              {label}
            </span>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align={variant === "sidebar" ? "start" : "end"} className="w-60">
        <DropdownMenuLabel>
          <div className="flex flex-col gap-0.5">
            <span className="text-sm font-semibold text-foreground">{label}</span>
            {email ? (
              <span className="text-xs font-normal text-[var(--text-dim)]">{email}</span>
            ) : null}
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/portal/settings" className="gap-2">
            <User className="size-4" /> Profile
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/portal/settings" className="gap-2">
            <Settings className="size-4" /> Settings
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/portal/billing" className="gap-2">
            <CreditCard className="size-4" /> Billing
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={handleSignOut}
          className="gap-2 text-[var(--danger)] focus:text-[var(--danger)] focus:bg-[color-mix(in_srgb,var(--danger)_10%,transparent)]"
        >
          <LogOut className="size-4" /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
