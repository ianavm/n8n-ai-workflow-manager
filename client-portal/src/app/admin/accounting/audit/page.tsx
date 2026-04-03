"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { ScrollText, Search } from "lucide-react";

interface AuditEntry {
  id: number;
  event_type: string;
  entity_type: string | null;
  action: string;
  actor: string;
  result: string;
  created_at: string;
}

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-ZA", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

const RESULT_COLORS: Record<string, string> = {
  success: "text-green-400",
  failed: "text-red-400",
  partial: "text-yellow-400",
};

export default function AuditTrailPage() {
  const supabase = createClient();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const limit = 50;

  const fetchEntries = useCallback(async () => {
    setLoading(true);
    let query = supabase
      .from("acct_audit_log")
      .select("id, event_type, entity_type, action, actor, result, created_at")
      .order("created_at", { ascending: false })
      .range((page - 1) * limit, page * limit - 1);

    if (search) {
      query = query.or(`event_type.ilike.%${search}%,actor.ilike.%${search}%,action.ilike.%${search}%`);
    }

    const { data } = await query;
    setEntries((data as AuditEntry[]) ?? []);
    setLoading(false);
  }, [supabase, search, page]);

  useEffect(() => { fetchEntries(); }, [fetchEntries]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Audit Trail</h1>

      <div className="relative max-w-md">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Search events, actors..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="w-full pl-10 pr-4 py-2 rounded-lg bg-[rgba(0,0,0,0.2)] border border-[rgba(255,255,255,0.06)] text-white text-sm placeholder-gray-500 focus:outline-none"
        />
      </div>

      <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[rgba(255,255,255,0.06)]">
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Time</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Event</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Entity</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Action</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Actor</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Result</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <tr key={i} className="border-b border-[rgba(255,255,255,0.03)]">
                  {Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} className="px-4 py-3"><div className="h-4 bg-[rgba(255,255,255,0.05)] rounded animate-pulse" /></td>
                  ))}
                </tr>
              ))
            ) : entries.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-12 text-center text-gray-500">
                <ScrollText className="mx-auto mb-2 text-gray-600" size={32} />
                <p>No audit entries</p>
              </td></tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id} className="border-b border-[rgba(255,255,255,0.03)]">
                  <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">{formatDateTime(entry.created_at)}</td>
                  <td className="px-4 py-3 text-xs text-white font-mono">{entry.event_type}</td>
                  <td className="px-4 py-3 text-xs text-gray-300">{entry.entity_type ?? "-"}</td>
                  <td className="px-4 py-3 text-xs text-gray-300">{entry.action}</td>
                  <td className="px-4 py-3 text-xs text-gray-400">{entry.actor}</td>
                  <td className="px-4 py-3 text-xs">
                    <span className={RESULT_COLORS[entry.result] ?? "text-gray-400"}>{entry.result}</span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex justify-center gap-2">
        <button
          onClick={() => setPage(Math.max(1, page - 1))}
          disabled={page === 1}
          className="px-3 py-1.5 text-xs rounded bg-[rgba(255,255,255,0.05)] text-gray-300 disabled:opacity-30"
        >
          Previous
        </button>
        <span className="px-3 py-1.5 text-xs text-gray-400">Page {page}</span>
        <button
          onClick={() => setPage(page + 1)}
          disabled={entries.length < limit}
          className="px-3 py-1.5 text-xs rounded bg-[rgba(255,255,255,0.05)] text-gray-300 disabled:opacity-30"
        >
          Next
        </button>
      </div>
    </div>
  );
}
