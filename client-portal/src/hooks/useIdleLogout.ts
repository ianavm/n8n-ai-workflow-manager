"use client";

import { useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

import { createClient } from "@/lib/supabase/client";

const DEFAULT_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes
const ACTIVITY_EVENTS = ["mousedown", "keydown", "scroll", "touchstart"] as const;

/**
 * Signs the user out after `timeoutMs` of no user activity and redirects
 * to `/portal/login`. Extracted from the original PortalNav so the shell
 * can own it without coupling to the sidebar.
 */
export function useIdleLogout(timeoutMs: number = DEFAULT_TIMEOUT_MS): void {
  const router = useRouter();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const reset = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      const supabase = createClient();
      await supabase.auth.signOut();
      router.push("/portal/login");
    }, timeoutMs);
  }, [router, timeoutMs]);

  useEffect(() => {
    ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, reset));
    reset();
    return () => {
      ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, reset));
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [reset]);
}
