"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type MemberRole = "manager" | "employee";

export interface MemberContextValue {
  memberId: string | null;
  clientId: string | null;
  memberRole: MemberRole | null;
  seatLimit: number | null;
  totalMembers: number | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

const DEFAULT_VALUE: MemberContextValue = {
  memberId: null,
  clientId: null,
  memberRole: null,
  seatLimit: null,
  totalMembers: null,
  loading: true,
  refresh: async () => {},
};

const MemberCtx = createContext<MemberContextValue>(DEFAULT_VALUE);

interface MeResponse {
  member?: {
    id: string;
    client_id: string;
    role: MemberRole;
  } | null;
  org?: {
    seat_limit: number;
    total_members: number;
  } | null;
}

export function MemberProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<MemberContextValue>(DEFAULT_VALUE);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/portal/me");
      if (!res.ok) {
        setState((prev) => ({ ...prev, loading: false }));
        return;
      }
      const data: MeResponse = await res.json();
      setState({
        memberId: data.member?.id ?? null,
        clientId: data.member?.client_id ?? null,
        memberRole: data.member?.role ?? null,
        seatLimit: data.org?.seat_limit ?? null,
        totalMembers: data.org?.total_members ?? null,
        loading: false,
        refresh,
      });
    } catch {
      setState((prev) => ({ ...prev, loading: false }));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return <MemberCtx.Provider value={{ ...state, refresh }}>{children}</MemberCtx.Provider>;
}

export function useMember(): MemberContextValue {
  return useContext(MemberCtx);
}
