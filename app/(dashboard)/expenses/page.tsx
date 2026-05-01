"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertTriangle, TrendingUp, BarChart2, RefreshCw, InboxIcon } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ScatterChart, Scatter, ZAxis,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const cv = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const iv = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };
const CURRENCY_SYMBOLS: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£", JPY: "¥" };

function useExpenses(params: Record<string, string | boolean | undefined>) {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v != null) searchParams.set(k, String(v)); });
  return useQuery({
    queryKey: ["expenses", params],
    queryFn: async () => {
      const r = await fetch(`${API}/api/v1/expenses/?${searchParams}`);
      if (!r.ok) throw new Error("Failed");
      return r.json();
    },
    refetchInterval: 30000,
  });
}
function useCategories() {
  return useQuery({
    queryKey: ["expense-categories"],
    queryFn: async () => {
      const r = await fetch(`${API}/api/v1/expenses/analytics/by-category`);
      if (!r.ok) throw new Error("Failed");
      return r.json();
    },
  });
}
function useAnomalies() {
  return useQuery({
    queryKey: ["anomalies"],
    queryFn: async () => {
      const r = await fetch(`${API}/api/v1/expenses/analytics/anomalies`);
      if (!r.ok) throw new Error("Failed");
      return r.json();
    },
    refetchInterval: 30000,
  });
}

export default function ExpensesPage() {
  const [activeTab, setActiveTab] = useState<"all" | "anomalies" | "recurring">("all");

  const { data: allData, isLoading: allLoading } = useExpenses({ limit: "100" });
  const { data: categoryData } = useCategories();
  const { data: anomalyData } = useAnomalies();

  const expenses: Record<string, unknown>[] = allData?.expenses || [];
  const anomalies: Record<string, unknown>[] = anomalyData?.anomalies || [];
  const categories: { category: string; currency: string; total: number; count: number }[] = categoryData?.data || [];

  // Filter based on tab
  const displayed = activeTab === "anomalies"
    ? anomalies
    : activeTab === "recurring"
      ? expenses.filter(e => e.is_recurring)
      : expenses;

  // USD categories for chart
  const usdCats = categories.filter(c => c.currency === "USD").slice(0, 8);

  return (
    <motion.div variants={cv} initial="hidden" animate="show" className="space-y-5">
      <motion.div variants={iv} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Expense Intelligence</h1>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
            {allData?.total ?? "—"} total · {anomalies.length} anomalies · {expenses.filter(e => e.is_recurring).length} recurring
          </p>
        </div>
      </motion.div>

      {/* Summary Cards */}
      <motion.div variants={iv} className="grid grid-cols-3 gap-3">
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-2">
            <BarChart2 size={14} className="text-blue-400" />
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Total Expenses</span>
          </div>
          <p className="text-xl font-bold text-white">{allData?.total ?? "—"}</p>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={14} className="text-rose-400" />
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Anomalies</span>
          </div>
          <p className="text-xl font-bold text-rose-400">{anomalies.length}</p>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-2">
            <RefreshCw size={14} className="text-violet-400" />
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Recurring</span>
          </div>
          <p className="text-xl font-bold text-violet-400">{expenses.filter(e => e.is_recurring).length}</p>
        </div>
      </motion.div>

      {/* Category Chart */}
      <motion.div variants={iv} className="card p-5">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp size={16} className="text-emerald-400" />
          <h2 className="text-sm font-semibold text-white">Spend by Category (USD)</h2>
        </div>
        {usdCats.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 rounded-xl" style={{ height: 160, background: "var(--color-bg-elevated)", border: "1px dashed var(--color-border)" }}>
            <InboxIcon size={18} style={{ color: "var(--color-text-muted)" }} />
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>No category data yet</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={usdCats} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
              <XAxis type="number" tick={{ fill: "#475569", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `$${(v / 1000).toFixed(0)}K`} />
              <YAxis type="category" dataKey="category" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} width={140} />
              <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, color: "#f8fafc" }} formatter={(v: number) => [`$${v.toLocaleString()}`, ""]} />
              <Bar dataKey="total" fill="#10b981" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </motion.div>

      {/* Tabs */}
      <motion.div variants={iv} className="flex gap-2">
        {(["all", "anomalies", "recurring"] as const).map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${activeTab === tab ? "bg-blue-500 text-white" : "text-slate-400 hover:text-white"}`}
            style={activeTab !== tab ? { background: "var(--color-bg-card)", border: "1px solid var(--color-border)" } : {}}>
            {tab === "all" ? "All Expenses" : tab === "anomalies" ? `Anomalies (${anomalies.length})` : `Recurring (${expenses.filter(e => e.is_recurring).length})`}
          </button>
        ))}
      </motion.div>

      {/* Expense Table */}
      {allLoading ? (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="card p-4 shimmer h-14" />)}</div>
      ) : displayed.length === 0 ? (
        <div className="card p-12 flex flex-col items-center gap-3">
          <InboxIcon size={32} style={{ color: "var(--color-text-muted)" }} />
          <p className="text-white font-medium">No expenses found</p>
        </div>
      ) : (
        <div className="space-y-2">
          {displayed.map(exp => (
            <motion.div key={exp.id as string} layout
              className="card p-4 hover:border-blue-500/20 transition-colors">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {exp.is_anomaly && <AlertTriangle size={14} className="text-rose-400 flex-shrink-0" />}
                  <div>
                    <p className="text-sm font-medium text-white truncate max-w-xs">{exp.description as string}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(59,130,246,0.1)", color: "#60a5fa" }}>
                        {exp.category as string || "Uncategorized"}
                      </span>
                      {exp.department && <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{exp.department as string}</span>}
                      {exp.vendor_name && <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>· {exp.vendor_name as string}</span>}
                    </div>
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-sm font-bold text-white">
                    {CURRENCY_SYMBOLS[exp.currency as string] || "$"}{(exp.amount as number)?.toLocaleString()}
                  </p>
                  <div className="flex items-center gap-1 mt-0.5 justify-end">
                    {exp.is_anomaly && <span className="badge badge-danger text-xs">anomaly</span>}
                    {exp.is_recurring && <span className="badge badge-neutral text-xs">recurring</span>}
                    <span className={`badge text-xs ${exp.status === "flagged" ? "badge-danger" : exp.status === "categorized" ? "badge-success" : "badge-neutral"}`}>
                      {exp.status as string}
                    </span>
                  </div>
                </div>
              </div>
              {exp.is_anomaly && exp.anomaly_reason && (
                <div className="mt-2 px-3 py-1.5 rounded-lg text-xs" style={{ background: "rgba(244,63,94,0.08)", color: "#fca5a5" }}>
                  ⚠️ {exp.anomaly_reason as string}
                </div>
              )}
            </motion.div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
