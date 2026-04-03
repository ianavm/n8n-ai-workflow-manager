"use client";

import { useEffect, useState, useCallback } from "react";
import { Building2 } from "lucide-react";

interface ClientOption {
  client_id: string;
  company_legal_name: string;
}

interface ClientSelectorProps {
  onClientChange: (clientId: string) => void;
}

export function ClientSelector({ onClientChange }: ClientSelectorProps) {
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [activeClientId, setActiveClientId] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const resp = await fetch("/api/accounting/config");
      const result = await resp.json();
      if (result.clients && result.clients.length > 0) {
        setClients(result.clients);
        const stored = sessionStorage.getItem("acct_active_client_id");
        const initial = stored && result.clients.some((c: ClientOption) => c.client_id === stored)
          ? stored
          : result.active_client_id || result.clients[0].client_id;
        setActiveClientId(initial);
        onClientChange(initial);
      }
      setLoading(false);
    }
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleChange = useCallback((clientId: string) => {
    setActiveClientId(clientId);
    sessionStorage.setItem("acct_active_client_id", clientId);
    onClientChange(clientId);
  }, [onClientChange]);

  if (loading || clients.length <= 1) return null;

  return (
    <div className="flex items-center gap-2">
      <Building2 size={14} className="text-gray-400" />
      <select
        value={activeClientId}
        onChange={(e) => handleChange(e.target.value)}
        className="px-3 py-1.5 rounded-lg bg-[rgba(0,0,0,0.3)] border border-[rgba(255,255,255,0.06)] text-white text-xs appearance-none focus:outline-none focus:border-[rgba(255,109,90,0.3)]"
      >
        {clients.map((c) => (
          <option key={c.client_id} value={c.client_id} className="bg-gray-900">
            {c.company_legal_name}
          </option>
        ))}
      </select>
    </div>
  );
}
