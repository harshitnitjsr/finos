"use client";
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  CreditCard, Landmark, Plus, ArrowRightLeft,
  CheckCircle2, AlertTriangle, Loader2, DollarSign, Clock, Search, ExternalLink, X
} from "lucide-react";
import { apiFetch } from "@/lib/api";

const cv = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const iv = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };

type Tab = "sources" | "execute" | "history";

// Types
interface Source {
  id: string; type: string; provider: string; display_name: string;
  tokenized_data: any; is_active: boolean; is_default: boolean; created_at: string;
}
interface Payment {
  id: string; amount: number; currency: string; status: string;
  provider: string; provider_ref: string; failure_reason?: string;
  vendor_id?: string; invoice_id?: string; created_at: string;
}
interface Vendor { id: string; name: string; payment_currency: string; }
interface Invoice { id: string; invoice_number: string; total_amount: number; currency: string; vendor_id: string; status: string; }

// Hooks
function useSources() {
  return useQuery<{ sources: Source[] }>({ queryKey: ["payment_sources"], queryFn: () => apiFetch("/payments/sources") });
}
function usePayments() {
  return useQuery<{ payments: Payment[], total: number }>({ queryKey: ["payments"], queryFn: () => apiFetch("/payments/") });
}
function useVendors() {
  return useQuery<{ vendors: Vendor[] }>({ queryKey: ["vendors_min"], queryFn: () => apiFetch("/vendors/?limit=100") });
}
function useInvoices() {
  return useQuery<{ invoices: Invoice[] }>({ queryKey: ["invoices_appr"], queryFn: () => apiFetch("/invoices/?status=approved") });
}

export default function PaymentsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("execute");
  const qc = useQueryClient();
  const oauthMut = useMutation({
    mutationFn: ({ provider, code }: { provider: string, code: string }) => 
      apiFetch(`/payments/sources/${provider}/oauth`, { method: "POST", body: JSON.stringify({ code }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payment_sources"] });
      setActiveTab("sources");
      // remove ?code= and ?state= from URL without reloading
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    if (code && state && !oauthMut.isPending) {
      oauthMut.mutate({ provider: state, code });
    }
  }, []);

  return (
    <motion.div variants={cv} initial="hidden" animate="show" className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <motion.div variants={iv} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <ArrowRightLeft className="text-blue-400" /> Payment Orchestration
          </h1>
          <p className="text-sm mt-1 text-slate-400">
            Unified payment execution engine across all banking and gateway providers.
          </p>
        </div>
      </motion.div>

      {/* Tabs */}
      <motion.div variants={iv} className="flex gap-2 border-b border-white/10 pb-4">
        {[
          { id: "execute", label: "Execute Payment", icon: DollarSign },
          { id: "sources", label: "Payment Sources", icon: Landmark },
          { id: "history", label: "Payment History", icon: Clock },
        ].map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id as Tab)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
              activeTab === t.id ? "bg-white/10 text-white" : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
            }`}>
            <t.icon size={16} className={activeTab === t.id ? "text-blue-400" : ""} /> {t.label}
          </button>
        ))}
      </motion.div>

      {/* Content */}
      <motion.div variants={cv} initial="hidden" animate="show" key={activeTab}>
        {activeTab === "sources" && <SourcesTab />}
        {activeTab === "execute" && <ExecuteTab />}
        {activeTab === "history" && <HistoryTab />}
      </motion.div>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sources Tab
// ─────────────────────────────────────────────────────────────────────────────
function SourcesTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useSources();
  const [showConnect, setShowConnect] = useState(false);
  
  const sources = data?.sources || [];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-bold text-white">Connected Sources</h2>
        <button onClick={() => setShowConnect(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded-xl text-sm font-semibold hover:bg-blue-500/30 transition-colors">
          <Plus size={16} /> Connect Source
        </button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 gap-4">{Array(4).fill(0).map((_, i) => <div key={i} className="shimmer h-32 rounded-2xl" />)}</div>
      ) : sources.length === 0 ? (
        <div className="card p-12 text-center flex flex-col items-center">
          <Landmark size={48} className="text-slate-500 mb-4" />
          <h3 className="text-white font-bold mb-2">No payment sources connected</h3>
          <p className="text-sm text-slate-400 max-w-sm mb-6">Connect your existing Stripe or Razorpay account, or add a bank account to route via RazorpayX.</p>
          <button onClick={() => setShowConnect(true)} className="px-6 py-2.5 bg-white text-black font-semibold rounded-xl text-sm hover:opacity-90 transition-opacity">Add Source</button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sources.map(s => (
            <SourceCard key={s.id} source={s} />
          ))}
        </div>
      )}

      {/* Connect Modal */}
      <AnimatePresence>
        {showConnect && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
            onClick={e => { if (e.target === e.currentTarget) setShowConnect(false); }}>
            <motion.div initial={{ scale: 0.95 }} animate={{ scale: 1 }} exit={{ scale: 0.95 }}
              className="w-full max-w-2xl bg-[#0a0f1c] border border-white/10 p-0 rounded-2xl overflow-hidden shadow-2xl">
              <div className="p-6 border-b border-white/10 flex justify-between items-center">
                <h2 className="text-lg font-bold text-white">Connect Payment Source</h2>
                <button onClick={() => setShowConnect(false)} className="text-slate-400 hover:text-white"><X size={20} /></button>
              </div>
              <div className="grid grid-cols-2">
                {/* Tech path */}
                <div className="p-6 border-r border-white/10">
                  <h3 className="text-sm font-bold text-slate-300 mb-2 uppercase tracking-wider">Tech Path</h3>
                  <p className="text-xs text-slate-500 mb-6">Connect existing payment gateways directly.</p>
                  
                  <div className="p-4 rounded-xl border border-slate-700/50 bg-slate-800/30 text-center relative overflow-hidden">
                    <div className="absolute inset-0 bg-[linear-gradient(45deg,transparent_25%,rgba(255,255,255,0.05)_50%,transparent_75%,transparent_100%)] bg-[length:250%_250%,100%_100%] animate-[shimmer_2s_infinite]" />
                    <Clock size={24} className="text-slate-500 mx-auto mb-2" />
                    <h4 className="text-sm font-bold text-slate-300 mb-1">Coming Soon</h4>
                    <p className="text-xs text-slate-500">
                      Fully autonomous Stripe & Razorpay OAuth integrations are being polished.
                    </p>
                  </div>
                  
                  {/* Disabled buttons for visual effect */}
                  <div className="space-y-3 mt-4 opacity-30 pointer-events-none grayscale">
                    <button onClick={async () => {
                      try {
                        const res = await apiFetch<{url: string}>("/payments/sources/stripe/oauth/link");
                        window.location.href = res.url;
                      } catch (e) { alert("Failed to generate Stripe link"); }
                    }} className="w-full p-3 rounded-xl border border-indigo-500/30 bg-indigo-500/10 hover:bg-indigo-500/20 text-left transition-colors flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <DollarSign size={16} className="text-indigo-400" />
                        <span className="text-sm font-medium text-white">Connect Stripe Account</span>
                      </div>
                      <ExternalLink size={14} className="text-indigo-400/50" />
                    </button>
                    
                    {/* Razorpay Connect Button */}
                    <button onClick={async () => {
                      try {
                        const res = await apiFetch<{url: string}>("/payments/sources/razorpay/oauth/link");
                        window.location.href = res.url;
                      } catch (e) { alert("Failed to generate Razorpay link"); }
                    }} className="w-full p-3 rounded-xl border border-blue-500/30 bg-blue-500/10 hover:bg-blue-500/20 text-left transition-colors flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <DollarSign size={16} className="text-blue-400" />
                        <span className="text-sm font-medium text-white">Connect Razorpay Account</span>
                      </div>
                      <ExternalLink size={14} className="text-blue-400/50" />
                    </button>
                    
                    {/* Optional fallback for RazorpayX Virtual Account Number if needed later, but standard OAuth connects the account. */}
                  </div>
                </div>
                {/* Non-tech path */}
                <div className="p-6">
                  <h3 className="text-sm font-bold text-emerald-400 mb-2 uppercase tracking-wider">Business Path</h3>
                  <p className="text-xs text-slate-500 mb-6">No gateway? Just add your bank details. (Routed via RazorpayX automatically).</p>
                  <div className="space-y-3">
                    <ConnectForm type="upi" title="Business UPI" fields={["upi_id"]} onSuccess={() => setShowConnect(false)} />
                    <ConnectForm type="bank" title="Bank Account" fields={["account_number", "ifsc"]} onSuccess={() => setShowConnect(false)} />
                    <ConnectForm type="card" title="Credit Card" fields={["payment_method_id"]} onSuccess={() => setShowConnect(false)} />
                  </div>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function SourceCard({ source: s }: { source: Source }) {
  const qc = useQueryClient();
  const [razorpayXAcct, setRazorpayXAcct] = useState("");
  const mut = useMutation({
    mutationFn: async () => {
      await apiFetch(`/payments/sources/${s.id}`, {
        method: "PATCH",
        body: JSON.stringify({ tokenized_data: { razorpayx_account_number: razorpayXAcct } })
      });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["payment_sources"] }); setRazorpayXAcct(""); }
  });

  const needsAccountNum = s.provider === "razorpayx" && s.type === "razorpay" && !s.tokenized_data.razorpayx_account_number;

  return (
    <div className="card p-5 border border-white/5 relative overflow-hidden group">
      <div className="absolute top-0 right-0 p-3">
        {s.is_default && <span className="bg-emerald-500/20 text-emerald-400 text-[10px] px-2 py-1 rounded-md font-bold uppercase tracking-wider">Default</span>}
      </div>
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center">
          {s.type === 'card' ? <CreditCard size={18} className="text-slate-300" /> : <Landmark size={18} className="text-slate-300" />}
        </div>
        <div>
          <h3 className="font-bold text-white">{s.display_name}</h3>
          <p className="text-xs text-slate-400 uppercase tracking-wide">{s.type} via {s.provider}</p>
        </div>
      </div>
      
      {needsAccountNum ? (
        <div className="mt-3 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
          <p className="text-xs text-amber-400 mb-2 font-medium flex items-center gap-1.5"><AlertTriangle size={14}/> Missing Virtual Account No.</p>
          <div className="flex gap-2">
            <input 
              placeholder="e.g. 23232300..." 
              value={razorpayXAcct} 
              onChange={e => setRazorpayXAcct(e.target.value)} 
              className="flex-1 px-3 py-1.5 text-xs bg-black/40 border border-white/10 rounded-lg text-white" 
            />
            <button onClick={() => mut.mutate()} disabled={!razorpayXAcct || mut.isPending} className="px-3 py-1.5 bg-amber-500 text-black text-xs font-bold rounded-lg hover:bg-amber-400 disabled:opacity-50 transition-colors">
              Save
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-2 bg-black/20 p-3 rounded-lg border border-white/5">
          {Object.entries(s.tokenized_data || {}).map(([k, v]) => (
            <div key={k} className="flex justify-between text-xs">
              <span className="text-slate-500">{k.replace(/_/g, " ")}</span>
              <span className="text-slate-300 font-mono truncate max-w-[150px] text-right" title={String(v)}>{String(v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ConnectForm({ type, title, fields, onSuccess }: { type: string, title: string, fields: string[], onSuccess: () => void }) {
  const qc = useQueryClient();
  const [data, setData] = useState<Record<string, string>>({});
  const [name, setName] = useState(`${title} 1`);
  const [open, setOpen] = useState(false);
  
  const mut = useMutation({
    mutationFn: async () => {
      await apiFetch("/payments/sources", {
        method: "POST",
        body: JSON.stringify({ type, display_name: name, tokenized_data: data, is_default: false })
      });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["payment_sources"] }); setOpen(false); onSuccess(); }
  });

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="w-full p-3 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-left transition-colors flex items-center gap-3">
        {type === "stripe" ? <DollarSign size={16} className="text-indigo-400" /> : <Landmark size={16} className="text-emerald-400" />}
        <span className="text-sm font-medium text-white">{title}</span>
      </button>
    );
  }

  return (
    <div className="p-4 rounded-xl border border-blue-500/30 bg-blue-500/5 space-y-3">
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm font-bold text-white">{title}</span>
        <button onClick={() => setOpen(false)} className="text-slate-400"><X size={14}/></button>
      </div>
      <input placeholder="Display Name" value={name} onChange={e => setName(e.target.value)} className="w-full px-3 py-1.5 text-xs bg-black/30 border border-white/10 rounded-lg text-white" />
      {fields.map(f => (
        <input key={f} placeholder={f.replace(/_/g, " ")} value={data[f] || ""} onChange={e => setData({...data, [f]: e.target.value})} className="w-full px-3 py-1.5 text-xs bg-black/30 border border-white/10 rounded-lg text-white" />
      ))}
      <button onClick={() => mut.mutate()} disabled={mut.isPending} className="w-full py-2 bg-blue-500 text-white text-xs font-bold rounded-lg hover:bg-blue-600 transition-colors">
        {mut.isPending ? "Connecting..." : "Connect"}
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Execute Tab
// ─────────────────────────────────────────────────────────────────────────────
function ExecuteTab() {
  const qc = useQueryClient();
  const { data: vData } = useVendors();
  const { data: iData } = useInvoices();
  const { data: sData } = useSources();
  
  const [vendorId, setVendorId] = useState("");
  const [invoiceId, setInvoiceId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [amount, setAmount] = useState("");
  
  const vendors = vData?.vendors || [];
  const invoices = (iData?.invoices || []).filter(i => vendorId ? i.vendor_id === vendorId : true);
  const sources = (sData?.sources || []).filter(s => s.is_active);

  useEffect(() => {
    if (invoiceId) {
      const inv = invoices.find(i => i.id === invoiceId);
      if (inv) {
        if (!vendorId) setVendorId(inv.vendor_id);
        setAmount(inv.total_amount.toString());
      }
    }
  }, [invoiceId]);

  const mut = useMutation({
    mutationFn: async () => {
      if (invoiceId) {
        return apiFetch(`/payments/execute/invoice/${invoiceId}?source_id=${sourceId}`, { method: "POST" });
      } else {
        return apiFetch(`/payments/execute`, {
          method: "POST",
          body: JSON.stringify({ vendor_id: vendorId, source_id: sourceId, amount: parseFloat(amount), currency: "INR" })
        });
      }
    },
    onSuccess: async (res: any) => {
      if (res.action_required && res.action_data?.type === "razorpay_checkout") {
        const script = document.createElement("script");
        script.src = "https://checkout.razorpay.com/v1/checkout.js";
        script.onload = () => {
          const options = {
            key: res.action_data.key_id,
            amount: res.action_data.amount,
            currency: res.action_data.currency,
            order_id: res.action_data.order_id,
            name: "AFOS Orchestration",
            description: "Invoice / Vendor Payment",
            handler: async function (response: any) {
              try {
                await apiFetch("/payments/execute/verify", {
                  method: "POST",
                  body: JSON.stringify({
                    payment_id: res.id,
                    razorpay_payment_id: response.razorpay_payment_id,
                    razorpay_order_id: response.razorpay_order_id,
                    razorpay_signature: response.razorpay_signature
                  })
                });
                qc.invalidateQueries({ queryKey: ["payments"] });
                qc.invalidateQueries({ queryKey: ["invoices_appr"] });
                setInvoiceId(""); setAmount("");
                alert("Payment Completed and Verified Successfully!");
              } catch (e: any) {
                alert("Payment verification failed: " + e.message);
              }
            },
            theme: { color: "#2563eb" }
          };
          const rzp = new (window as any).Razorpay(options);
          rzp.open();
        };
        document.body.appendChild(script);
        return;
      }

      qc.invalidateQueries({ queryKey: ["payments"] });
      qc.invalidateQueries({ queryKey: ["invoices_appr"] });
      setInvoiceId(""); setAmount("");
      alert("Payment Execution Triggered Successfully!");
    },
    onError: (e: any) => alert(`Failed: ${e.message}`)
  });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <div className="lg:col-span-3 card p-6 space-y-5">
        <h2 className="text-lg font-bold text-white mb-2">Execute Payment</h2>
        
        <div>
          <label className="text-xs font-semibold text-slate-400 block mb-1.5">1. Select Vendor</label>
          <select value={vendorId} onChange={e => {setVendorId(e.target.value); setInvoiceId(""); setAmount("");}} className="w-full px-3 py-2.5 bg-black/20 border border-white/10 rounded-xl text-sm text-white focus:border-blue-500/50 outline-none">
            <option value="">-- Select Vendor --</option>
            {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
          </select>
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-400 block mb-1.5">2. Select Approved Invoice (Optional)</label>
          <select value={invoiceId} onChange={e => setInvoiceId(e.target.value)} disabled={invoices.length === 0} className="w-full px-3 py-2.5 bg-black/20 border border-white/10 rounded-xl text-sm text-white focus:border-blue-500/50 outline-none disabled:opacity-50">
            <option value="">-- Direct Payment (No Invoice) --</option>
            {invoices.map(i => <option key={i.id} value={i.id}>{i.invoice_number || i.id.slice(0,8)} — {i.currency} {i.total_amount}</option>)}
          </select>
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-400 block mb-1.5">3. Amount</label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">INR</span>
            <input type="number" value={amount} onChange={e => setAmount(e.target.value)} disabled={!!invoiceId} placeholder="0.00" className="w-full pl-12 pr-3 py-2.5 bg-black/20 border border-white/10 rounded-xl text-sm text-white focus:border-blue-500/50 outline-none disabled:opacity-50" />
          </div>
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-400 block mb-1.5">4. Payment Source</label>
          <select value={sourceId} onChange={e => setSourceId(e.target.value)} className="w-full px-3 py-2.5 bg-black/20 border border-white/10 rounded-xl text-sm text-white focus:border-blue-500/50 outline-none">
            <option value="">-- Select Source --</option>
            {sources.map(s => <option key={s.id} value={s.id}>{s.display_name} ({s.type})</option>)}
          </select>
        </div>

        <button onClick={() => mut.mutate()} disabled={!vendorId || !sourceId || !amount || mut.isPending}
          className="w-full py-3.5 rounded-xl font-bold text-white shadow-lg transition-all disabled:opacity-50 hover:opacity-90"
          style={{ background: "linear-gradient(135deg, #2563eb, #7c3aed)" }}>
          {mut.isPending ? <span className="flex items-center justify-center gap-2"><Loader2 size={16} className="animate-spin"/> Executing via Orchestrator...</span> : `Pay INR ${amount || '0.00'}`}
        </button>
      </div>

      <div className="lg:col-span-2 space-y-4">
        <div className="card p-5 border border-indigo-500/20 bg-indigo-500/5">
          <h3 className="text-sm font-bold text-indigo-400 flex items-center gap-2 mb-2"><CheckCircle2 size={16}/> Non-Tech Checkout Mode</h3>
          <p className="text-xs text-slate-400 leading-relaxed mb-3">
            Because this uses a manual Bank/UPI/Card source, true autonomous backend execution is prohibited by the RBI.
          </p>
          <p className="text-xs text-slate-400 leading-relaxed">
            The Orchestrator will pause and open a secure **Razorpay Checkout** modal. You will scan a QR code to pay, and the money will be automatically split to the vendor via Razorpay Route!
          </p>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// History Tab
// ─────────────────────────────────────────────────────────────────────────────
function HistoryTab() {
  const { data, isLoading } = usePayments();
  const payments = data?.payments || [];

  return (
    <div className="card p-0 overflow-hidden border border-white/10">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-white/10 text-xs font-semibold text-slate-400 uppercase tracking-wider bg-black/20">
              <th className="px-5 py-4">ID / Time</th>
              <th className="px-5 py-4">Amount</th>
              <th className="px-5 py-4">Target</th>
              <th className="px-5 py-4">Provider / Ref</th>
              <th className="px-5 py-4">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-sm">
            {isLoading ? (
              <tr><td colSpan={5} className="p-8 text-center text-slate-500"><Loader2 className="animate-spin mx-auto"/></td></tr>
            ) : payments.length === 0 ? (
              <tr><td colSpan={5} className="p-8 text-center text-slate-500">No payment history found.</td></tr>
            ) : payments.map(p => {
              const date = new Date(p.created_at).toLocaleString();
              return (
                <tr key={p.id} className="hover:bg-white/5 transition-colors group">
                  <td className="px-5 py-4">
                    <div className="text-white font-mono text-xs mb-1">{p.id.slice(0,8)}</div>
                    <div className="text-slate-500 text-[10px]">{date}</div>
                  </td>
                  <td className="px-5 py-4">
                    <div className="text-white font-bold">{p.currency} {p.amount.toLocaleString()}</div>
                  </td>
                  <td className="px-5 py-4">
                    {p.vendor_id ? (
                      <div className="flex items-center gap-1.5 text-blue-400 hover:underline cursor-pointer"><Landmark size={12}/> Vendor</div>
                    ) : "-"}
                    {p.invoice_id && <div className="text-xs text-slate-400 mt-1">Inv: {p.invoice_id.slice(0,8)}</div>}
                  </td>
                  <td className="px-5 py-4">
                    <div className="text-slate-300 font-medium capitalize">{p.provider || "-"}</div>
                    {p.provider_ref && <div className="text-slate-500 text-[10px] font-mono mt-1">{p.provider_ref}</div>}
                  </td>
                  <td className="px-5 py-4">
                    <StatusBadge status={p.status} error={p.failure_reason} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatusBadge({ status, error }: { status: string, error?: string }) {
  const colors: Record<string, string> = {
    completed: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    processing: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    failed: "bg-rose-500/10 text-rose-400 border-rose-500/20",
    pending: "bg-slate-500/10 text-slate-300 border-slate-500/20",
    refunded: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  };
  const cls = colors[status] || colors.pending;
  return (
    <div className="flex flex-col items-start gap-1">
      <span className={`px-2.5 py-1 border rounded-md text-[10px] font-bold uppercase tracking-wider ${cls}`}>
        {status}
      </span>
      {error && status === "failed" && <span className="text-[10px] text-rose-500 truncate max-w-[150px]" title={error}>{error}</span>}
    </div>
  );
}
