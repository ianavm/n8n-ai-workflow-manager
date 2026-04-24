"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { toast } from "sonner";
import { UserPlus, Lock, Ban } from "lucide-react";

export default function ManagementPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [creating, setCreating] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Create client form
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [company, setCompany] = useState("");
  const [password, setPassword] = useState("");

  // Reset password form
  const [resetClientId, setResetClientId] = useState("");
  const [newPassword, setNewPassword] = useState("");

  // Status update
  const [statusClientId, setStatusClientId] = useState("");
  const [newStatus, setNewStatus] = useState("active");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setMessage(null);

    const res = await fetch("/api/admin/clients", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        full_name: fullName,
        company_name: company || undefined,
        password,
      }),
    });

    const data = await res.json();
    if (res.ok) {
      setMessage({
        type: "success",
        text: `Client created! API Key: ${data.api_key}`,
      });
      toast.success("Client created successfully");
      setEmail("");
      setFullName("");
      setCompany("");
      setPassword("");
      setShowCreate(false);
    } else {
      setMessage({ type: "error", text: data.error });
      toast.error(data.error);
    }
    setCreating(false);
  }

  async function handleReset(e: React.FormEvent) {
    e.preventDefault();
    setResetting(true);
    setMessage(null);

    const res = await fetch("/api/auth/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: resetClientId, new_password: newPassword }),
    });

    const data = await res.json();
    if (res.ok) {
      setMessage({ type: "success", text: "Password reset successfully!" });
      toast.success("Password reset successfully");
      setResetClientId("");
      setNewPassword("");
      setShowReset(false);
    } else {
      setMessage({ type: "error", text: data.error });
      toast.error(data.error);
    }
    setResetting(false);
  }

  async function handleStatusUpdate() {
    if (!statusClientId || !newStatus) return;
    setMessage(null);

    const res = await fetch("/api/admin/clients", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: statusClientId, status: newStatus }),
    });

    const data = await res.json();
    if (res.ok) {
      setMessage({ type: "success", text: `Client status updated to ${newStatus}` });
      toast.success(`Client status updated to ${newStatus}`);
      setStatusClientId("");
    } else {
      setMessage({ type: "error", text: data.error });
      toast.error(data.error);
    }
  }

  return (
    <div className="space-y-8 max-w-3xl">
      <div className="relative">
        <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
        <div className="relative">
          <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
            Client <span className="gradient-text">Management</span>
          </h1>
          <p className="text-base text-[var(--text-muted)] mt-2">
            Create, manage, and configure client accounts
          </p>
        </div>
      </div>

      {/* Status Messages */}
      {message && (
        <div
          className={`px-4 py-3 rounded-lg text-sm ${
            message.type === "success"
              ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
              : "bg-red-500/10 border border-red-500/20 text-red-400"
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Actions */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="cursor-pointer" hover>
          <button onClick={() => setShowCreate(true)} className="w-full text-left">
            <div className="w-10 h-10 rounded-lg bg-[rgba(0,212,170,0.1)] border border-[rgba(0,212,170,0.2)] flex items-center justify-center mb-3 text-[#00D4AA]">
              <UserPlus size={20} />
            </div>
            <h3 className="text-sm font-medium text-white">Create Client</h3>
            <p className="text-xs text-[var(--text-dim)] mt-1">Set up a new client account</p>
          </button>
        </Card>
        <Card className="cursor-pointer" hover>
          <button onClick={() => setShowReset(true)} className="w-full text-left">
            <div className="w-10 h-10 rounded-lg bg-[rgba(108,99,255,0.1)] border border-[rgba(108,99,255,0.2)] flex items-center justify-center mb-3 text-[#6C63FF]">
              <Lock size={20} />
            </div>
            <h3 className="text-sm font-medium text-white">Reset Password</h3>
            <p className="text-xs text-[var(--text-dim)] mt-1">Reset a client&apos;s password</p>
          </button>
        </Card>
        <Card>
          <div className="w-10 h-10 rounded-lg bg-[rgba(245,158,11,0.1)] border border-[rgba(245,158,11,0.2)] flex items-center justify-center mb-3 text-[#F59E0B]">
            <Ban size={20} />
          </div>
          <h3 className="text-sm font-medium text-white mb-3">Update Status</h3>
          <div className="space-y-2">
            <Input
              placeholder="Client ID"
              value={statusClientId}
              onChange={(e) => setStatusClientId(e.target.value)}
            />
            <select
              value={newStatus}
              onChange={(e) => setNewStatus(e.target.value)}
              className="w-full"
            >
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
              <option value="inactive">Inactive</option>
            </select>
            <Button size="sm" variant="secondary" onClick={handleStatusUpdate}>
              Update
            </Button>
          </div>
        </Card>
      </div>

      {/* Create Client Modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Create New Client">
        <form onSubmit={handleCreate} className="space-y-4">
          <Input label="Full Name" value={fullName} onChange={(e) => setFullName(e.target.value)} required placeholder="John Doe" />
          <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="client@company.com" />
          <Input label="Company Name" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Optional" />
          <Input label="Temporary Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required placeholder="Min 8 characters" />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" type="button" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button type="submit" loading={creating}>Create Client</Button>
          </div>
        </form>
      </Modal>

      {/* Reset Password Modal */}
      <Modal open={showReset} onClose={() => setShowReset(false)} title="Reset Client Password">
        <form onSubmit={handleReset} className="space-y-4">
          <Input label="Client ID" value={resetClientId} onChange={(e) => setResetClientId(e.target.value)} required placeholder="Client UUID" />
          <Input label="New Password" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required placeholder="Min 8 characters" />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" type="button" onClick={() => setShowReset(false)}>Cancel</Button>
            <Button type="submit" loading={resetting}>Reset Password</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
