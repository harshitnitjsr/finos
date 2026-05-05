"use client";
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Building2, Shield, Search, Plus, X, AlertTriangle,
  CheckCircle2, TrendingUp, InboxIcon, ChevronRight, Loader2, Heart, CreditCard,
} from "lucide-react";
import PageContextHelp from "@/components/global/PageContextHelp";
import { apiFetch } from "@/lib/api";

const cv = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const iv = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };

interface Vendor {
  id: string; name: string; email?: string; category?: string; website?: string;
  risk_level: string; risk_score: number; is_verified: boolean; is_active: boolean;
  total_paid: number; total_paid_display?: number; total_paid_currency?: string;
  payment_currency: string; created_at: string;
}
interface VendorDetail extends Vendor {
  invoice_stats: { currency: string; count: number; total: number }[];
  vendor_health?: Record<string, unknown>;
  health_analysis?: Record<string, unknown>;
  bank_details?: { account_name?: string; account_number?: string; ifsc_code?: string } | null;
}
interface VendorsResp { vendors: Vendor[]; total: number; base_currency?: string; }
interface SemanticMatch { id: string; score: number; name?: string; category?: string; risk_level?: string; }

const RISK_STYLES: Record<string, { color: string; bg: string; icon: React.ReactNode }> = {
  low:    { color: "#10b981", bg: "rgba(16,185,129,0.1)",  icon: <CheckCircle2 size={12} /> },
  medium: { color: "#f59e0b", bg: "rgba(245,158,11,0.1)",  icon: <AlertTriangle size={12} /> },
  high:   { color: "#f43f5e", bg: "rgba(244,63,94,0.1)",   icon: <AlertTriangle size={12} /> },
};
const CURRENCY_SYMBOLS: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£", JPY: "¥" };

function useVendors(params: { category?: string; risk_level?: string }) {
  const sp = new URLSearchParams();
  if (params.category) sp.set("category", params.category);
  if (params.risk_level) sp.set("risk_level", params.risk_level);
  return useQuery<VendorsResp>({
    queryKey: ["vendors", params],
    queryFn: () => apiFetch<VendorsResp>(`/vendors/?${sp}`),
    refetchInterval: 8000,   // Poll every 8s — new vendors from invoice uploads appear quickly
  });
}
function useVendorDetail(id: string | null, healthCheck: boolean) {
  return useQuery<VendorDetail>({
    queryKey: ["vendor-detail", id, healthCheck],
    queryFn: () => apiFetch<VendorDetail>(`/vendors/${id}?health_check=${healthCheck}`),
    enabled: !!id,
  });
}

export default function VendorsPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [healthCheck, setHealthCheck] = useState(false);
  const [riskFilter, setRiskFilter] = useState<string>("");
  const [showCreate, setShowCreate] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [semanticResults, setSemanticResults] = useState<SemanticMatch[]>([]);
  const [searching, setSearching] = useState(false);
  const { data, isLoading } = useVendors({ risk_level: riskFilter || undefined });
  const { data: detail, isLoading: detailLoading } = useVendorDetail(selectedId, healthCheck);
  const vendors: Vendor[] = data?.vendors || [];
  const baseCurrency = data?.base_currency || "USD";
  const currencySymbol = CURRENCY_SYMBOLS[baseCurrency] || "$";

  const [createForm, setCreateForm] = useState({ name: "", email: "", category: "", payment_currency: baseCurrency });
  
  // Sync default currency
  useEffect(() => {
    if (baseCurrency) setCreateForm(prev => ({ ...prev, payment_currency: baseCurrency }));
  }, [baseCurrency]);

  const [createMsg, setCreateMsg] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: (body: typeof createForm) => apiFetch<Record<string, unknown>>("/vendors/", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["vendors"] });
      setShowCreate(false);
      setCreateForm({ name: "", email: "", category: "", payment_currency: "USD" });
      if (data._existing) {
        setCreateMsg(data._message as string || "Vendor already exists — existing record shown.");
        setTimeout(() => setCreateMsg(null), 5000);
      }
    },
  });

  const handleSemanticSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const res = await apiFetch<{ matches: SemanticMatch[] }>(`/vendors/search/semantic?q=${encodeURIComponent(searchQuery)}`);
      setSemanticResults(res.matches || []);
    } catch { setSemanticResults([]); }
    finally { setSearching(false); }
  };

  const riskOptions = ["", "low", "medium", "high"];

  return (
    <motion.div variants={cv} initial="hidden" animate="show" className="space-y-6">
      {/* Duplicate vendor toast */}
      {createMsg && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-amber-300"
          style={{ background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.3)" }}>
          <AlertTriangle size={14} className="shrink-0" />
          {createMsg}
        </div>
      )}
      {/* Header */}
      <motion.div variants={iv} className="flex items-center justify-between">
        <div>
          <div className="flex items-center">
            <h1 className="text-2xl font-bold text-white">Vendor Intelligence</h1>
            <PageContextHelp
              pageName="Vendor Intelligence"
              why="Managing third-party vendors is critical for preventing fraud and tracking holistic spend across disparate invoices and expenses."
              what="This page maintains a unified view of all active vendors. It leverages intelligent search to let you search vendors by intent (e.g. 'cloud infrastructure') rather than exact name."
              how="Use the search bar to find overlapping tools or redundant vendors. Review the risk score for each vendor—high-risk vendors should have their invoices scrutinized in the Approval Center."
            />
          </div>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
            {data?.total ?? "—"} vendors · intelligent risk scoring · smart search
          </p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90"
          style={{ background: "linear-gradient(135deg,#3b82f6,#8b5cf6)" }}>
          <Plus size={14} /> Add Vendor
        </button>
      </motion.div>

      {/* Semantic Search */}
      <motion.div variants={iv} className="card p-4">
        <p className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-1"><Search size={12} /> Intelligent Vendor Search</p>
        <div className="flex gap-2">
          <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSemanticSearch()}
            placeholder='e.g. "cloud infrastructure AWS-like"'
            className="flex-1 px-3 py-2 rounded-xl text-sm text-white bg-transparent border"
            style={{ background: "var(--color-bg-elevated)", borderColor: "var(--color-border)" }} />
          <button onClick={handleSemanticSearch} disabled={searching}
            className="px-4 py-2 rounded-xl text-sm font-semibold text-white flex items-center gap-2"
            style={{ background: "rgba(59,130,246,0.2)", border: "1px solid rgba(59,130,246,0.3)" }}>
            {searching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />} Search
          </button>
        </div>
        {semanticResults.length > 0 && (
          <div className="mt-3 space-y-1">
            {semanticResults.map(m => {
              const vid = m.id || (m as any).vendor_id;
              return (
                <div key={vid} onClick={() => setSelectedId(vid)}
                  className="flex items-center justify-between p-2 rounded-lg cursor-pointer hover:border-blue-500/30 transition-colors"
                  style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
                  <div className="flex items-center gap-2">
                    <Building2 size={12} className="text-blue-400" />
                    <span className="text-sm text-white">{m.name || vid.slice(0, 8)}</span>
                    {m.category && <span className="text-xs text-slate-500">· {m.category}</span>}
                  </div>
                  <span className="text-xs text-emerald-400">{((m.score || 0) * 100).toFixed(0)}% match</span>
                </div>
              );
            })}
          </div>
        )}
      </motion.div>

      {/* Filters */}
      <motion.div variants={iv} className="flex gap-2">
        {riskOptions.map(r => (
          <button key={r || "all"} onClick={() => setRiskFilter(r)}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${riskFilter === r ? "bg-blue-500 text-white" : "text-slate-400 hover:text-white"}`}
            style={riskFilter !== r ? { background: "var(--color-bg-card)", border: "1px solid var(--color-border)" } : {}}>
            {r ? `${r.charAt(0).toUpperCase() + r.slice(1)} Risk` : "All Vendors"}
          </button>
        ))}
      </motion.div>

      {/* Vendor List */}
      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {Array.from({ length: 6 }).map((_, i) => <div key={i} className="card p-5 shimmer h-28" />)}
        </div>
      ) : vendors.length === 0 ? (
        <div className="card p-16 flex flex-col items-center gap-3">
          <InboxIcon size={36} style={{ color: "var(--color-text-muted)" }} />
          <p className="text-white font-semibold">No vendors found</p>
        </div>
      ) : (
        <motion.div variants={iv} className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {vendors.map(vendor => {
            const rs = RISK_STYLES[vendor.risk_level] || RISK_STYLES.low;
            return (
              <div key={vendor.id} onClick={() => setSelectedId(vendor.id)}
                className="card p-5 cursor-pointer hover:border-blue-500/20 transition-all"
                style={{ borderColor: selectedId === vendor.id ? "rgba(59,130,246,0.4)" : undefined }}>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                      style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
                      <Building2 size={18} className="text-blue-400" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-white">{vendor.name}</p>
                      <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>
                        {vendor.category || "Uncategorized"} · {vendor.payment_currency}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-semibold"
                    style={{ background: rs.bg, color: rs.color }}>
                    {rs.icon} {vendor.risk_level}
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div className="p-2 rounded-lg text-center" style={{ background: "var(--color-bg-elevated)" }}>
                    <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Total Paid</p>
                    <p className="text-sm font-bold text-white">
                      {(() => {
                        const amt = vendor.total_paid;
                        if (amt >= 1_000_000) return `${currencySymbol}${(amt / 1_000_000).toFixed(1)}M`;
                        if (amt >= 1000) return `${currencySymbol}${(amt / 1000).toFixed(1)}K`;
                        return `${currencySymbol}${amt.toFixed(0)}`;
                      })()}
                    </p>
                  </div>
                  <div className="p-2 rounded-lg text-center" style={{ background: "var(--color-bg-elevated)" }}>
                    <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Risk Score</p>
                    <p className="text-sm font-bold" style={{ color: rs.color }}>{vendor.risk_score.toFixed(0)}</p>
                  </div>
                  <div className="p-2 rounded-lg text-center" style={{ background: "var(--color-bg-elevated)" }}>
                    <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Verified</p>
                    <p className="text-sm font-bold" style={{ color: vendor.is_verified ? "#10b981" : "#f43f5e" }}>
                      {vendor.is_verified ? "Yes" : "No"}
                    </p>
                  </div>
                </div>
                <div className="flex items-center justify-end mt-2">
                  <ChevronRight size={14} style={{ color: "var(--color-text-muted)" }} />
                </div>
              </div>
            );
          })}
        </motion.div>
      )}

      {/* Vendor Detail Drawer */}
      <AnimatePresence>
        {selectedId && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex justify-end"
            style={{ background: "rgba(0,0,0,0.6)" }}
            onClick={e => { if (e.target === e.currentTarget) setSelectedId(null); }}>
            <motion.div initial={{ x: 400 }} animate={{ x: 0 }} exit={{ x: 400 }}
              className="w-full max-w-lg h-full overflow-y-auto"
              style={{ background: "var(--color-bg-card)", borderLeft: "1px solid var(--color-border)" }}>
              <div className="p-6 space-y-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-bold text-white">Vendor Details</h2>
                  <button onClick={() => setSelectedId(null)}
                    className="p-2 rounded-xl transition-colors hover:bg-white/5">
                    <X size={16} className="text-slate-400" />
                  </button>
                </div>

                {detailLoading ? (
                  <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="shimmer h-16 rounded-xl" />)}</div>
                ) : detail ? (
                  <>
                    <div className="p-4 rounded-xl" style={{ background: "var(--color-bg-elevated)" }}>
                      <h3 className="text-xl font-bold text-white">{detail.name}</h3>
                      <p className="text-sm mt-1" style={{ color: "var(--color-text-muted)" }}>{detail.email || "No email"}</p>
                      {detail.website && <a href={detail.website} target="_blank" rel="noreferrer" className="text-xs text-blue-400 hover:underline">{detail.website}</a>}
                    </div>

                    {/* Invoice Stats */}
                    {detail.invoice_stats?.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-1"><TrendingUp size={12} /> Invoice History</p>
                        <div className="space-y-2">
                          {detail.invoice_stats.map(s => (
                            <div key={s.currency} className="flex items-center justify-between p-3 rounded-xl"
                              style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
                              <span className="text-sm text-white">{s.currency} — {s.count} invoices</span>
                              <span className="text-sm font-bold text-emerald-400">
                                {CURRENCY_SYMBOLS[s.currency] || "$"}{s.total.toLocaleString()}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* AI Health Check Toggle */}
                    <div className="flex items-center justify-between p-3 rounded-xl"
                      style={{ background: "rgba(139,92,246,0.08)", border: "1px solid rgba(139,92,246,0.2)" }}>
                      <div className="flex items-center gap-2">
                        <Heart size={14} className="text-violet-400" />
                        <span className="text-sm font-semibold text-white">System Health Analysis</span>
                      </div>
                      <button onClick={() => setHealthCheck(!healthCheck)}
                        className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${healthCheck ? "bg-violet-500 text-white" : "text-slate-400"}`}
                        style={!healthCheck ? { background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" } : {}}>
                        {healthCheck ? "Loaded" : "Run Analysis"}
                      </button>
                    </div>

                    {/* Bank Details — saved from approval modal */}
                    <div>
                      <p className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-1">
                        <CreditCard size={12} /> Bank Account
                      </p>
                      {detail.bank_details ? (
                        <div className="p-3 rounded-xl space-y-2" style={{ background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.2)" }}>
                          {[
                            { label: "Account Name", value: detail.bank_details.account_name },
                            { label: "Account Number", value: detail.bank_details.account_number ? `••••${detail.bank_details.account_number.slice(-4)}` : null },
                            { label: "IFSC Code", value: detail.bank_details.ifsc_code },
                          ].map(({ label, value }) => value ? (
                            <div key={label} className="flex justify-between text-xs">
                              <span style={{ color: "var(--color-text-muted)" }}>{label}</span>
                              <span className="text-white font-medium">{value}</span>
                            </div>
                          ) : null)}
                        </div>
                      ) : (
                        <div className="p-3 rounded-xl text-xs" style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}>
                          No bank details saved. Approve an invoice for this vendor to add them.
                        </div>
                      )}
                    </div>

                    {/* Payment Routing */}
                    <VendorPaymentRouting vendorId={detail.id} />


                    {/* Vendor Health */}
                    {healthCheck && detail.vendor_health && (
                      <div className="p-4 rounded-xl space-y-2"
                        style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
                        <p className="text-xs font-semibold text-slate-400 flex items-center gap-1"><Shield size={12} /> System Health Score</p>
                        {Object.entries(detail.vendor_health as Record<string, unknown>).slice(0, 6).map(([k, v]) => (
                          <div key={k} className="flex items-center justify-between text-sm">
                            <span style={{ color: "var(--color-text-muted)" }}>{k.replace(/_/g, " ")}</span>
                            <span className="text-white font-medium">{String(v)}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Deep Insight Analysis */}
                    {healthCheck && detail.health_analysis && (
                      <div className="p-4 rounded-xl"
                        style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.15)" }}>
                        <p className="text-xs font-semibold text-emerald-400 mb-2">System Insight Analysis</p>
                        {typeof detail.health_analysis === "string" ? (
                          <p className="text-sm text-white">{detail.health_analysis as string}</p>
                        ) : (
                          <div className="space-y-1">
                            {Object.entries(detail.health_analysis as Record<string, unknown>).slice(0, 5).map(([k, v]) => (
                              <div key={k} className="text-sm">
                                <span className="text-slate-400">{k.replace(/_/g, " ")}: </span>
                                <span className="text-white">{String(v)}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </>
                ) : null}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Create Vendor Modal */}
      <AnimatePresence>
        {showCreate && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: "rgba(0,0,0,0.7)" }}
            onClick={e => { if (e.target === e.currentTarget) setShowCreate(false); }}>
            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }}
              className="w-full max-w-md p-6 rounded-2xl space-y-4"
              style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border)" }}>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-white">Add Vendor</h2>
                <button onClick={() => setShowCreate(false)} className="p-2 rounded-xl hover:bg-white/5">
                  <X size={16} className="text-slate-400" />
                </button>
              </div>
              {(["name", "email", "category"] as const).map(field => (
                <div key={field}>
                  <label className="text-xs font-semibold text-slate-400 block mb-1">{field.charAt(0).toUpperCase() + field.slice(1)}{field === "name" ? " *" : ""}</label>
                  <input value={createForm[field]} onChange={e => setCreateForm(f => ({ ...f, [field]: e.target.value }))}
                    placeholder={field === "name" ? "Acme Corp" : field === "email" ? "billing@acme.com" : "Software"}
                    className="w-full px-3 py-2 rounded-xl text-sm text-white"
                    style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }} />
                </div>
              ))}
              <div>
                <label className="text-xs font-semibold text-slate-400 block mb-1">Currency</label>
                <select value={createForm.payment_currency} onChange={e => setCreateForm(f => ({ ...f, payment_currency: e.target.value }))}
                  className="w-full px-3 py-2 rounded-xl text-sm text-white"
                  style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
                  {["USD", "INR", "EUR", "GBP"].map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <button onClick={() => createMutation.mutate(createForm)} disabled={!createForm.name || createMutation.isPending}
                className="w-full py-3 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90 disabled:opacity-50"
                style={{ background: "linear-gradient(135deg,#3b82f6,#8b5cf6)" }}>
                {createMutation.isPending ? "Creating…" : "Create Vendor"}
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Vendor Payment Routing Component
// ─────────────────────────────────────────────────────────────────────────────
function VendorPaymentRouting({ vendorId }: { vendorId: string }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<{ details: any[] }>({
    queryKey: ["vendor_payment_details", vendorId],
    queryFn: () => apiFetch(`/payments/vendors/${vendorId}/details`)
  });

  const [adding, setAdding] = useState(false);
  const [method, setMethod] = useState("upi");
  const [details, setDetails] = useState<Record<string, string>>({});

  const mut = useMutation({
    mutationFn: () => apiFetch(`/payments/vendors/${vendorId}/details`, {
      method: "POST",
      body: JSON.stringify({ method, details, is_primary: true })
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["vendor_payment_details", vendorId] });
      setAdding(false);
      setDetails({});
    }
  });

  const del = useMutation({
    mutationFn: (id: string) => apiFetch(`/payments/vendors/${vendorId}/details/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["vendor_payment_details", vendorId] })
  });

  const routing = data?.details || [];

  return (
    <div className="p-4 rounded-xl border border-white/10" style={{ background: "var(--color-bg-elevated)" }}>
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-bold text-white flex items-center gap-2"><Building2 size={14} className="text-blue-400"/> Payment Routing</h4>
        <button onClick={() => setAdding(!adding)} className="text-xs font-semibold text-blue-400 hover:text-blue-300">
          {adding ? "Cancel" : "+ Add Detail"}
        </button>
      </div>

      {adding && (
        <div className="mb-4 p-3 rounded-lg bg-black/20 border border-white/5 space-y-3">
          <select value={method} onChange={e => { setMethod(e.target.value); setDetails({}); }} className="w-full text-xs p-2 rounded-lg bg-black/40 text-white border border-white/10">
            <option value="upi">UPI ID</option>
            <option value="bank">Bank Account</option>
            <option value="stripe_account">Stripe Connect Account</option>
          </select>
          
          {method === "upi" && <input placeholder="vendor@upi" onChange={e => setDetails({ upi_id: e.target.value })} className="w-full text-xs p-2 rounded-lg bg-black/40 text-white border border-white/10" />}
          {method === "bank" && (
            <>
              <input placeholder="Account Name" onChange={e => setDetails({ ...details, account_name: e.target.value })} className="w-full text-xs p-2 rounded-lg bg-black/40 text-white border border-white/10" />
              <input placeholder="Account Number" onChange={e => setDetails({ ...details, account_number: e.target.value })} className="w-full text-xs p-2 rounded-lg bg-black/40 text-white border border-white/10" />
              <input placeholder="IFSC Code" onChange={e => setDetails({ ...details, ifsc: e.target.value })} className="w-full text-xs p-2 rounded-lg bg-black/40 text-white border border-white/10" />
            </>
          )}
          {method === "stripe_account" && <input placeholder="acct_123..." onChange={e => setDetails({ stripe_account_id: e.target.value })} className="w-full text-xs p-2 rounded-lg bg-black/40 text-white border border-white/10" />}
          
          <button onClick={() => mut.mutate()} disabled={mut.isPending} className="w-full py-2 bg-blue-500/20 text-blue-400 text-xs font-bold rounded-lg border border-blue-500/30 hover:bg-blue-500/30">
            Save Routing Detail
          </button>
        </div>
      )}

      <div className="space-y-2">
        {isLoading ? <div className="shimmer h-12 rounded-lg" /> : routing.length === 0 ? (
          <p className="text-xs text-slate-500">No payment details set. Vendor cannot be paid via Orchestrator.</p>
        ) : routing.map(r => (
          <div key={r.id} className="flex items-center justify-between p-2.5 rounded-lg bg-black/20 border border-white/5">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-300 uppercase">{r.method.replace("_", " ")}</span>
                {r.is_primary && <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-blue-500/20 text-blue-400">PRIMARY</span>}
              </div>
              <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                {r.method === "upi" ? r.details.upi_id : 
                 r.method === "bank" ? `${r.details.account_number} (${r.details.ifsc})` : 
                 r.details.stripe_account_id}
              </div>
            </div>
            <button onClick={() => del.mutate(r.id)} className="text-slate-500 hover:text-rose-400"><X size={14}/></button>
          </div>
        ))}
      </div>
    </div>
  );
}
