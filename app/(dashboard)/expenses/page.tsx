"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertTriangle, TrendingUp, BarChart2, RefreshCw, InboxIcon, Sparkles, Loader2, RepeatIcon, Plus } from "lucide-react";
import PageContextHelp from "@/components/global/PageContextHelp";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { apiFetch } from "@/lib/api";
import AddExpenseModal from "@/components/expenses/AddExpenseModal";

const cv = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const iv = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };
const CURRENCY_SYMBOLS: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£", JPY: "¥" };

interface ExpenseItem {
  id: string; description: string; amount: number; currency: string; category: string;
  department?: string; vendor_name?: string; status: string; is_anomaly?: boolean;
  is_recurring?: boolean; anomaly_reason?: string;
  ai_explanation?: string;
  similar_past_anomalies?: { id: string; score: number; description?: string; amount?: number }[];
}
interface ExpensesResp { expenses: ExpenseItem[]; total: number; }
interface CategoryItem { category: string; currency: string; total: number; count: number; }
interface CategoryResp { data: CategoryItem[]; base_currency: string; }
interface AnomalyResp { anomalies: ExpenseItem[]; total: number; }
interface SaasDuplicates {
  total_potential_savings?: number;
  duplicate_groups?: Record<string, unknown>[];
  underutilized?: Record<string, unknown>[];
  consolidation_opportunities?: Record<string, unknown>[];
  summary?: string;
  [key: string]: unknown;
}
interface SubscriptionResp {
  summary?: string;
  subscriptions?: unknown[];
  total_monthly?: number;
  saas_duplicates?: SaasDuplicates;
  recommendations?: string[];
}

function useExpenses(params: Record<string, string | undefined>) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v) sp.set(k, v); });
  return useQuery<ExpensesResp>({
    queryKey: ["expenses", params],
    queryFn: () => apiFetch<ExpensesResp>(`/expenses/?${sp}`),
    refetchInterval: 30000,
  });
}
function useCategories() {
  return useQuery<CategoryResp>({
    queryKey: ["expense-categories"],
    queryFn: () => apiFetch<CategoryResp>("/expenses/analytics/by-category"),
  });
}
function useAnomalies(enrich: boolean) {
  return useQuery<AnomalyResp>({
    queryKey: ["anomalies", enrich],
    queryFn: () => apiFetch<AnomalyResp>(`/expenses/analytics/anomalies?enrich=${enrich}`),
    refetchInterval: enrich ? false : 30000,
    staleTime: enrich ? 5 * 60 * 1000 : 0,
  });
}

export default function ExpensesPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"all" | "anomalies" | "recurring" | "subscriptions">("all");
  const [enrichAnomalies, setEnrichAnomalies] = useState(false);
  const [subscriptionData, setSubscriptionData] = useState<SubscriptionResp | null>(null);
  const [subscriptionLoading, setSubscriptionLoading] = useState(false);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  const { data: allData, isLoading: allLoading } = useExpenses({ limit: "100" });
  const { data: categoryData } = useCategories();
  const { data: anomalyData } = useAnomalies(enrichAnomalies);

  const expenses: ExpenseItem[] = allData?.expenses || [];
  const anomalies: ExpenseItem[] = anomalyData?.anomalies || [];
  const baseCurrency = categoryData?.base_currency || "USD";
  const currencySymbol = CURRENCY_SYMBOLS[baseCurrency] || "$";
  const categories: CategoryItem[] = categoryData?.data || [];
  const baseCats = categories.slice(0, 8);

  const displayed = activeTab === "anomalies" ? anomalies
    : activeTab === "recurring" ? expenses.filter(e => e.is_recurring)
    : expenses;

  const handleAnalyzeSubscriptions = async () => {
    setSubscriptionLoading(true);
    try {
      const res = await apiFetch<SubscriptionResp>("/expenses/analyze/subscriptions", { method: "POST" });
      setSubscriptionData(res);
    } catch { /* non-critical */ }
    finally { setSubscriptionLoading(false); }
  };

  return (
    <motion.div variants={cv} initial="hidden" animate="show" className="space-y-5">
      <motion.div variants={iv} className="flex items-center justify-between">
        <div>
          <div className="flex items-center">
            <h1 className="text-2xl font-bold text-white">Expense Intelligence</h1>
            <PageContextHelp
              pageName="Expense Intelligence"
              why="Tracking corporate expenses across multiple currencies and departments is complex and susceptible to fraud."
              what="This page centralizes all corporate spending. It automatically categorizes expenses, identifies recurring subscriptions, and highlights statistical anomalies using the intelligent platform."
              how="Switch between 'All Expenses', 'Anomalies', and 'Recurring' tabs to triage spend. Look for red anomaly badges which indicate the system has flagged the transaction as highly irregular compared to historical data."
            />
          </div>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
            {allData?.total ?? "—"} total · {anomalies.length} anomalies · {expenses.filter(e => e.is_recurring).length} recurring
          </p>
        </div>
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white font-semibold text-sm transition-colors"
        >
          <Plus size={16} />
          Add Expense
        </button>
      </motion.div>

      {/* Summary Cards */}
      <motion.div variants={iv} className="grid grid-cols-3 gap-3">
        {[
          { label: "Total Expenses", value: allData?.total ?? "—", icon: <BarChart2 size={14} className="text-blue-400" />, color: "text-white" },
          { label: "Anomalies", value: anomalies.length, icon: <AlertTriangle size={14} className="text-rose-400" />, color: "text-rose-400" },
          { label: "Recurring", value: expenses.filter(e => e.is_recurring).length, icon: <RefreshCw size={14} className="text-violet-400" />, color: "text-violet-400" },
        ].map(c => (
          <div key={c.label} className="card p-4">
            <div className="flex items-center gap-2 mb-2">{c.icon}<span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{c.label}</span></div>
            <p className={`text-xl font-bold ${c.color}`}>{String(c.value)}</p>
          </div>
        ))}
      </motion.div>

      {/* Category Chart */}
      <motion.div variants={iv} className="card p-5">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp size={16} className="text-emerald-400" />
          <h2 className="text-sm font-semibold text-white">Spend by Category ({baseCurrency})</h2>
        </div>
        {baseCats.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 rounded-xl" style={{ height: 160, background: "var(--color-bg-elevated)", border: "1px dashed var(--color-border)" }}>
            <InboxIcon size={18} style={{ color: "var(--color-text-muted)" }} />
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>No category data yet</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={baseCats} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
              <XAxis type="number" tick={{ fill: "#475569", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `${currencySymbol}${(v / 1000).toFixed(0)}K`} />
              <YAxis type="category" dataKey="category" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} width={140} />
              <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, color: "#f8fafc" }} formatter={(v: unknown) => [`${currencySymbol}${(v as number).toLocaleString()}`, ""]} />
              <Bar dataKey="total" fill="#10b981" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </motion.div>

      {/* Tabs */}
      <motion.div variants={iv} className="flex gap-2 flex-wrap items-center">
        {(["all", "anomalies", "recurring", "subscriptions"] as const).map(tab => (
          <button key={tab}
            onClick={() => { setActiveTab(tab); if (tab === "subscriptions" && !subscriptionData) handleAnalyzeSubscriptions(); }}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${activeTab === tab ? "bg-blue-500 text-white" : "text-slate-400 hover:text-white"}`}
            style={activeTab !== tab ? { background: "var(--color-bg-card)", border: "1px solid var(--color-border)" } : {}}>
            {tab === "all" ? "All Expenses"
              : tab === "anomalies" ? `Anomalies (${anomalies.length})`
              : tab === "recurring" ? `Recurring (${expenses.filter(e => e.is_recurring).length})`
              : "Subscriptions"}
          </button>
        ))}
        {activeTab === "anomalies" && (
          <button onClick={() => setEnrichAnomalies(v => !v)}
            className={`ml-auto px-3 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all ${enrichAnomalies ? "bg-violet-500 text-white" : "text-slate-400"}`}
            style={!enrichAnomalies ? { background: "var(--color-bg-card)", border: "1px solid rgba(139,92,246,0.4)" } : {}}>
            <Sparkles size={11} /> {enrichAnomalies ? "Insights Enabled ✓" : "Enable Insights"}
          </button>
        )}
      </motion.div>

      {/* Subscriptions Tab */}
      {activeTab === "subscriptions" && (
        <motion.div variants={iv} className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <RepeatIcon size={16} className="text-blue-400" />
              <h2 className="text-sm font-semibold text-white">Subscription Analysis</h2>
              <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(59,130,246,0.1)", color: "#60a5fa" }}>autonomous_engine</span>
            </div>
            <button onClick={handleAnalyzeSubscriptions} disabled={subscriptionLoading}
              className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold text-white"
              style={{ background: "rgba(59,130,246,0.2)", border: "1px solid rgba(59,130,246,0.3)" }}>
              {subscriptionLoading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />} Re-analyze
            </button>
          </div>

          {subscriptionLoading ? (
            <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="card shimmer h-20" />)}</div>
          ) : !subscriptionData ? (
            <div className="card p-12 flex flex-col items-center gap-3">
              <InboxIcon size={32} style={{ color: "var(--color-text-muted)" }} />
              <p className="text-white font-medium">Running subscription analysis…</p>
            </div>
          ) : (
            <div className="space-y-4">
              {subscriptionData.summary && (
                <div className="p-4 rounded-xl" style={{ background: "rgba(59,130,246,0.08)", border: "1px solid rgba(59,130,246,0.2)" }}>
                  <p className="text-sm text-white">{subscriptionData.summary}</p>
                </div>
              )}
              {subscriptionData.total_monthly != null && (
                <div className="card p-4 flex items-center justify-between">
                  <span className="text-sm" style={{ color: "var(--color-text-muted)" }}>Total Monthly Subscriptions</span>
                  <p className="text-xl font-black text-blue-400">
                    {currencySymbol}{(subscriptionData.total_monthly as number || 0).toLocaleString()}
                  </p>
                </div>
              )}
              {subscriptionData.saas_duplicates && Object.keys(subscriptionData.saas_duplicates).length > 0 && (
                <div className="card p-4 space-y-3">
                  <p className="text-xs font-semibold text-rose-400 flex items-center gap-1">
                    <AlertTriangle size={12} /> SaaS Duplicates &amp; Waste Detected
                  </p>

                  {/* Total savings */}
                  {subscriptionData.saas_duplicates.total_potential_savings != null && (
                    <div className="flex items-center justify-between p-3 rounded-xl" style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.2)" }}>
                      <span className="text-sm text-white font-semibold">Total Potential Savings</span>
                      <p className="text-xl font-black text-emerald-400">
                        {currencySymbol}{(subscriptionData.saas_duplicates?.total_potential_savings as number || 0).toLocaleString()}
                      </p>
                    </div>
                  )}

                  {/* Duplicate groups */}
                  {Array.isArray(subscriptionData.saas_duplicates.duplicate_groups) && subscriptionData.saas_duplicates.duplicate_groups.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-slate-400 mb-2">Duplicate Groups</p>
                      <div className="space-y-2">
                        {(subscriptionData.saas_duplicates.duplicate_groups as Record<string, unknown>[]).map((g, i) => (
                          <div key={i} className="p-2.5 rounded-lg text-xs" style={{ background: "rgba(244,63,94,0.06)", border: "1px solid rgba(244,63,94,0.15)" }}>
                            <div className="flex items-center justify-between">
                              <span className="font-semibold text-rose-300">{g.category as string || g.group as string || `Group ${i+1}`}</span>
                              {g.potential_savings != null && <span className="text-emerald-400 font-bold">save ${Number(g.potential_savings).toLocaleString()}</span>}
                            </div>
                            {!!(g.vendors) && Array.isArray(g.vendors) && (
                              <p className="text-slate-400 mt-0.5">{(g.vendors as string[]).join(" · ")}</p>
                            )}
                            {!!(g.recommended_vendor) && <p className="text-blue-400 mt-0.5">→ Keep: {String(g.recommended_vendor)}</p>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Underutilized */}
                  {Array.isArray(subscriptionData.saas_duplicates.underutilized) && subscriptionData.saas_duplicates.underutilized.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-slate-400 mb-2">Underutilized Subscriptions</p>
                      <div className="space-y-1.5">
                        {(subscriptionData.saas_duplicates.underutilized as Record<string, unknown>[]).map((u, i) => (
                          <div key={i} className="flex items-center justify-between p-2 rounded-lg text-xs" style={{ background: "var(--color-bg-elevated)" }}>
                            <span className="text-white">{u.vendor as string || u.name as string || `Item ${i+1}`}</span>
                            {u.monthly_cost != null && <span className="text-amber-400">${Number(u.monthly_cost).toLocaleString()}/mo</span>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Consolidation opportunities */}
                  {Array.isArray(subscriptionData.saas_duplicates.consolidation_opportunities) && subscriptionData.saas_duplicates.consolidation_opportunities.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-slate-400 mb-2">Consolidation Opportunities</p>
                      <div className="space-y-1.5">
                        {(subscriptionData.saas_duplicates.consolidation_opportunities as Record<string, unknown>[]).map((o, i) => (
                          <div key={i} className="p-2 rounded-lg text-xs" style={{ background: "var(--color-bg-elevated)" }}>
                            <div className="flex items-center justify-between">
                              <span className="text-white font-semibold">{o.category as string || `Opportunity ${i+1}`}</span>
                              {o.savings != null && <span className="text-emerald-400">save ${Number(o.savings).toLocaleString()}</span>}
                            </div>
                            {!!(o.action) && <p className="text-slate-400 mt-0.5">→ {String(o.action)}</p>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Fallback: any other keys we didn't handle */}
                  {Object.entries(subscriptionData.saas_duplicates)
                    .filter(([k]) => !["duplicate_groups","underutilized","consolidation_opportunities","total_potential_savings","summary"].includes(k))
                    .map(([k, v]) => typeof v === "string" || typeof v === "number" ? (
                      <div key={k} className="flex items-center justify-between py-1.5 text-xs" style={{ borderTop: "1px solid var(--color-border)" }}>
                        <span style={{ color: "var(--color-text-muted)" }}>{k.replace(/_/g, " ")}</span>
                        <span className="text-white font-semibold">{String(v)}</span>
                      </div>
                    ) : null)
                  }
                </div>
              )}

              {subscriptionData.recommendations && subscriptionData.recommendations.length > 0 && (
                <div className="card p-4">
                  <p className="text-xs font-semibold text-emerald-400 mb-3">System Recommendations</p>
                  <ul className="space-y-2">
                    {subscriptionData.recommendations.map((r, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-white">
                        <span className="text-emerald-400 mt-0.5 flex-shrink-0">→</span> {r}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </motion.div>
      )}

      {/* Expense List (all/anomalies/recurring) */}
      {activeTab !== "subscriptions" && (
        allLoading ? (
          <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="card p-4 shimmer h-14" />)}</div>
        ) : displayed.length === 0 ? (
          <div className="card p-12 flex flex-col items-center gap-3">
            <InboxIcon size={32} style={{ color: "var(--color-text-muted)" }} />
            <p className="text-white font-medium">No expenses found</p>
          </div>
        ) : (
          <div className="space-y-2">
            {displayed.map(exp => (
              <motion.div key={exp.id} layout className="card p-4 hover:border-blue-500/20 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {exp.is_anomaly && <AlertTriangle size={14} className="text-rose-400 flex-shrink-0" />}
                    <div>
                      <p className="text-sm font-medium text-white truncate max-w-xs">{exp.description}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(59,130,246,0.1)", color: "#60a5fa" }}>
                          {exp.category || "Uncategorized"}
                        </span>
                        {exp.department && <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{exp.department}</span>}
                        {exp.vendor_name && <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>· {exp.vendor_name}</span>}
                      </div>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-sm font-bold text-white">
                      {CURRENCY_SYMBOLS[exp.currency] || "$"}{exp.amount?.toLocaleString()}
                    </p>
                    <div className="flex items-center gap-1 mt-0.5 justify-end">
                      {exp.is_anomaly && <span className="badge badge-danger text-xs">anomaly</span>}
                      {exp.is_recurring && <span className="badge badge-neutral text-xs">recurring</span>}
                      <span className={`badge text-xs ${exp.status === "flagged" ? "badge-danger" : exp.status === "categorized" ? "badge-success" : "badge-neutral"}`}>
                        {exp.status}
                      </span>
                    </div>
                  </div>
                </div>
                {exp.is_anomaly && exp.anomaly_reason && (
                  <div className="mt-2 px-3 py-1.5 rounded-lg text-xs" style={{ background: "rgba(244,63,94,0.08)", color: "#fca5a5" }}>
                    ⚠️ {exp.anomaly_reason}
                  </div>
                )}
                {exp.ai_explanation && (
                  <div className="mt-2 px-3 py-2 rounded-lg text-xs" style={{ background: "rgba(139,92,246,0.08)", border: "1px solid rgba(139,92,246,0.15)", color: "#c4b5fd" }}>
                    <span className="font-semibold text-violet-400">Insight: </span>{exp.ai_explanation}
                  </div>
                )}
                {exp.similar_past_anomalies && exp.similar_past_anomalies.length > 0 && (
                  <div className="mt-2 px-3 py-2 rounded-lg" style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
                    <p className="text-xs font-semibold text-slate-400 mb-1">Similar past anomalies ({exp.similar_past_anomalies.length})</p>
                    {exp.similar_past_anomalies.map(s => (
                      <div key={s.id} className="flex items-center justify-between text-xs py-0.5">
                        <span style={{ color: "var(--color-text-muted)" }}>{s.description || s.id.slice(0, 8)}</span>
                        <span className="text-emerald-400 font-semibold">{((s.score || 0) * 100).toFixed(0)}% match</span>
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        )
      )}

      <AddExpenseModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["expenses"] });
          queryClient.invalidateQueries({ queryKey: ["expense-categories"] });
          queryClient.invalidateQueries({ queryKey: ["anomalies"] });
        }}
        defaultCurrency={baseCurrency}
      />
    </motion.div>
  );
}