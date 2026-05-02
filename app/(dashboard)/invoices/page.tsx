"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, Search, Filter, FileText, X, AlertTriangle, CheckCircle, Clock, InboxIcon } from "lucide-react";
import { useCallback } from "react";

import { apiFetch } from "@/lib/api";
const cv = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } };
const iv = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.3 } } };
const CURRENCY_SYMBOLS: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£", JPY: "¥" };

interface InvoicesResponse {
  invoices: Record<string, unknown>[];
  total: number;
}

function useInvoices(status?: string) {
  return useQuery<InvoicesResponse>({
    queryKey: ["invoices", status],
    queryFn: () => {
      const params = new URLSearchParams({ limit: "50" });
      if (status) params.set("status", status);
      return apiFetch<InvoicesResponse>(`/invoices/?${params}`);
    },
    refetchInterval: 5000,
  });
}

export default function InvoicesPage() {
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const qc = useQueryClient();

  const { data, isLoading } = useInvoices(filterStatus);
  const invoices: Record<string, unknown>[] = data?.invoices || [];

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("currency", "USD");
      const r = await fetch("/api/backend/invoices/upload", { method: "POST", body: fd });
      if (!r.ok) throw new Error("Upload failed");
      return r.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invoices"] }),
  });

  const startTemporalMutation = useMutation({
    mutationFn: (invoiceId: string) =>
      apiFetch("/temporal/invoice/start", {
        method: "POST",
        body: JSON.stringify({ invoice_id: invoiceId }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invoices"] }),
  });

  const approveTemporalMutation = useMutation({
    mutationFn: (invoiceId: string) =>
      apiFetch("/temporal/invoice/signal", {
        method: "POST",
        body: JSON.stringify({ invoice_id: invoiceId, action: "approve" }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invoices"] }),
  });

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) uploadMutation.mutate(file);
  }, [uploadMutation]);

  const filtered = invoices.filter(inv =>
    !search || (inv.invoice_number as string)?.toLowerCase().includes(search.toLowerCase()) ||
    (inv.description as string)?.toLowerCase().includes(search.toLowerCase())
  );

  const selected = filtered.find(inv => inv.id === selectedId);

  const STATUSES = [undefined, "pending", "processing", "awaiting_approval", "approved", "paid", "overdue", "duplicate"];
  const STATUS_LABELS: Record<string, string> = {
    pending: "Pending", processing: "Processing", awaiting_approval: "Awaiting Approval",
    approved: "Approved", paid: "Paid", overdue: "Overdue", duplicate: "Duplicate",
  };

  return (
    <motion.div variants={cv} initial="hidden" animate="show" className="space-y-5">
      <motion.div variants={iv} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Invoice Intelligence</h1>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
            {data?.total ?? "—"} invoices total
          </p>
        </div>
        <label className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold cursor-pointer transition-all hover:opacity-90"
          style={{ background: "rgba(59,130,246,0.15)", color: "#3b82f6", border: "1px solid rgba(59,130,246,0.3)" }}>
          <Upload size={14} />
          Upload Invoice
          <input type="file" accept=".pdf,.png,.jpg,.jpeg" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) uploadMutation.mutate(f); }} />
        </label>
      </motion.div>

      {/* Upload Zone */}
      <motion.div variants={iv}
        onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        className="rounded-xl p-8 text-center transition-all cursor-pointer"
        style={{
          border: `2px dashed ${isDragging ? "#3b82f6" : "var(--color-border)"}`,
          background: isDragging ? "rgba(59,130,246,0.05)" : "var(--color-bg-elevated)",
        }}>
        {uploadMutation.isPending ? (
          <div className="space-y-2">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm text-blue-400 font-medium">Uploading & processing with AI pipeline…</p>
          </div>
        ) : (
          <>
            <Upload size={28} className="mx-auto mb-2 text-slate-500" />
            <p className="text-sm font-medium text-white">Drop invoice PDF or image here</p>
            <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
              AI pipeline: OCR → Field Extraction → Duplicate Check → Risk Scoring → Approval Queue
            </p>
          </>
        )}
        {uploadMutation.isSuccess && (
          <p className="text-xs text-emerald-400 mt-2">✓ Uploaded — AI processing in background</p>
        )}
        {uploadMutation.isError && (
          <p className="text-xs text-rose-400 mt-2">✗ Upload failed — check backend connection</p>
        )}
      </motion.div>

      {/* Filters */}
      <motion.div variants={iv} className="flex gap-2 overflow-x-auto pb-1">
        {STATUSES.map(s => (
          <button key={s ?? "all"} onClick={() => setFilterStatus(s)}
            className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${filterStatus === s ? "bg-blue-500 text-white" : "text-slate-400 hover:text-white"}`}
            style={filterStatus !== s ? { background: "var(--color-bg-card)", border: "1px solid var(--color-border)" } : {}}>
            {s == null ? "All" : STATUS_LABELS[s] || s}
          </button>
        ))}
      </motion.div>

      {/* Search */}
      <motion.div variants={iv} className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--color-text-muted)" }} />
        <input
          value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by invoice # or description…"
          className="w-full pl-9 pr-4 py-2.5 rounded-xl text-sm outline-none transition-all"
          style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)", color: "var(--color-text-primary)" }} />
      </motion.div>

      <div className="flex gap-4">
        {/* Invoice List */}
        <motion.div variants={iv} className="flex-1 space-y-2">
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="card p-4 space-y-2">
                <div className="shimmer h-4 w-32 rounded" /><div className="shimmer h-3 w-48 rounded" />
              </div>
            ))
          ) : filtered.length === 0 ? (
            <div className="card p-12 flex flex-col items-center gap-3">
              <InboxIcon size={32} style={{ color: "var(--color-text-muted)" }} />
              <p className="text-white font-medium">No invoices found</p>
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Upload an invoice or adjust filters</p>
            </div>
          ) : (
            filtered.map(inv => (
              <motion.div key={inv.id as string} layout
                onClick={() => setSelectedId(inv.id === selectedId ? null : inv.id as string)}
                className={`card p-4 cursor-pointer transition-all hover:border-blue-500/30 ${selectedId === inv.id ? "border-blue-500/50" : ""}`}
                whileHover={{ scale: 1.005 }}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${inv.risk_level === "high" || inv.risk_level === "critical" ? "bg-rose-500/10" : inv.risk_level === "medium" ? "bg-amber-500/10" : "bg-emerald-500/10"}`}>
                      {inv.risk_level === "high" || inv.risk_level === "critical" ? <AlertTriangle size={14} className="text-rose-400" /> :
                        inv.status === "paid" ? <CheckCircle size={14} className="text-emerald-400" /> :
                          inv.status === "processing" ? <Clock size={14} className="text-blue-400" /> :
                            <FileText size={14} className="text-slate-400" />}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">{(inv.invoice_number as string) || `INV-${(inv.id as string).slice(0, 8)}`}</p>
                      <p className="text-xs mt-0.5 truncate max-w-[200px]" style={{ color: "var(--color-text-muted)" }}>{inv.description as string || "No description"}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-white">
                      {CURRENCY_SYMBOLS[inv.currency as string] || "$"}{(inv.total_amount as number)?.toLocaleString()}
                    </p>
                    <span className={`badge text-xs ${inv.status === "paid" || inv.status === "approved" ? "badge-success" : inv.status === "overdue" || inv.status === "duplicate" ? "badge-danger" : inv.status === "awaiting_approval" ? "badge-warning" : "badge-neutral"}`}>
                      {STATUS_LABELS[inv.status as string] || inv.status as string}
                    </span>
                  </div>
                </div>
              </motion.div>
            ))
          )}
        </motion.div>

        {/* Detail Panel */}
        <AnimatePresence>
          {selected && (
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}
              className="w-80 flex-shrink-0 card p-5 h-fit sticky top-4 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white">Invoice Detail</h3>
                <button onClick={() => setSelectedId(null)} className="text-slate-400 hover:text-white">
                  <X size={16} />
                </button>
              </div>
              <div className="space-y-3 text-xs">
                {[
                  ["Invoice #", (selected.invoice_number as string) || "Pending extraction"],
                  ["Status", selected.status as string],
                  ["Amount", `${CURRENCY_SYMBOLS[selected.currency as string] || "$"}${(selected.total_amount as number)?.toLocaleString()}`],
                  ["Currency", selected.currency as string],
                  ["Tax", `${CURRENCY_SYMBOLS[selected.currency as string] || "$"}${(selected.tax_amount as number)?.toLocaleString()}`],
                  ["Risk Level", selected.risk_level as string],
                  ["Risk Score", `${(selected.risk_score as number)?.toFixed(1)}/100`],
                  ["AI Confidence", `${((selected.ai_confidence as number) * 100).toFixed(0)}%`],
                  ["Duplicate", (selected.is_duplicate as boolean) ? "⚠️ Yes" : "No"],
                  ["Due Date", selected.due_date ? new Date(selected.due_date as string).toLocaleDateString() : "—"],
                ].map(([label, val]) => (
                  <div key={label} className="flex justify-between items-start gap-2">
                    <span style={{ color: "var(--color-text-muted)" }}>{label}</span>
                    <span className="text-white font-medium text-right">{val}</span>
                  </div>
                ))}
              </div>
              {(selected.policy_violations as unknown[])?.length > 0 && (
                <div className="p-3 rounded-lg" style={{ background: "rgba(244,63,94,0.1)", border: "1px solid rgba(244,63,94,0.2)" }}>
                  <p className="text-xs font-semibold text-rose-400 mb-1">Policy Violations</p>
                  {(selected.policy_violations as { violation: string }[]).map((v, i) => (
                    <p key={i} className="text-xs text-rose-300">{v.violation || JSON.stringify(v)}</p>
                  ))}
                </div>
              )}
              {!!(selected.extracted_fields) && Object.keys(selected.extracted_fields as object).length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-white mb-2">AI Extracted Fields</p>
                  <div className="space-y-1.5">
                    {Object.entries(selected.extracted_fields as Record<string, unknown>)
                      .filter(([k]) => k !== "line_items")
                      .slice(0, 6)
                      .map(([k, v]) => (
                        <div key={k} className="flex justify-between text-xs">
                          <span style={{ color: "var(--color-text-muted)" }}>{k}</span>
                          <span className="text-white truncate max-w-[130px]">{String(v)}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
              
              <div className="flex gap-2 pt-4 mt-4 border-t border-slate-700/50">
                <button 
                  onClick={() => startTemporalMutation.mutate(selected.id as string)}
                  disabled={startTemporalMutation.isPending || selected.status === "processing"}
                  className="flex-1 py-2 bg-blue-500/20 text-blue-400 font-semibold rounded-lg text-xs hover:bg-blue-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed">
                  {startTemporalMutation.isPending || selected.status === "processing" ? "AI Processing..." : "Start AI Workflow"}
                </button>
                {selected.status === "awaiting_approval" && (
                  <button 
                    onClick={() => approveTemporalMutation.mutate(selected.id as string)}
                    disabled={approveTemporalMutation.isPending}
                    className="flex-1 py-2 bg-emerald-500/20 text-emerald-400 font-semibold rounded-lg text-xs hover:bg-emerald-500/30 transition-all">
                    {approveTemporalMutation.isPending ? "Approving..." : "Approve Payment"}
                  </button>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
