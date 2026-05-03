"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Landmark, TrendingDown, Calendar, InboxIcon, AlertCircle, PieChart, Target } from "lucide-react";
import PageContextHelp from "@/components/global/PageContextHelp";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from "recharts";

import { apiFetch } from "@/lib/api";
const cv = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const iv = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };
const CURRENCY_SYMBOLS: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£", JPY: "¥" };

interface CashPosition { currency: string; account: string; current_balance: number; outflow: number; }
interface BurnItem { currency: string; amount: number; }
interface RunwayAnalysis {
  /* Treasury endpoint fields */
  months_remaining?: number; monthly_burn_rate?: number; burn_rate_trend?: string; runway_status?: string;
  /* Forecasting agent fields */
  current_burn_rate?: number; runway_months?: number; runway_days?: number; confidence?: number;
  scenarios?: Record<string, { burn_rate: number; runway_months: number }>;
  top_burn_categories?: { category: string; monthly_avg: number }[];
  reduction_opportunities?: { category: string; potential_reduction: number; action: string }[];
  [key: string]: unknown;
}
interface TreasuryResp { upcoming_payments: Record<string, unknown>[]; monthly_burn: BurnItem[]; runway_days?: number; monthly_history_usd: { month: string; spend: number }[]; }
interface PositionResp { positions: CashPosition[]; }
interface ForecastResp { cash_flow_forecast: { month: string; inflow: number; outflow: number; net: number }[]; confidence?: number; runway_analysis?: RunwayAnalysis; }
interface BudgetCategory { category: string; monthly_projections: { month: string; projected: number }[]; }
interface BudgetResp { budget_by_category?: BudgetCategory[]; categories?: Record<string, unknown>[]; summary?: string; monthly_forecasts?: any[]; }

function useTreasury() {
  return useQuery<TreasuryResp>({
    queryKey: ["treasury-summary"],
    queryFn: () => apiFetch<TreasuryResp>("/treasury/summary"),
    refetchInterval: 60000,
  });
}
function useCashPosition() {
  return useQuery<PositionResp>({
    queryKey: ["cash-position"],
    queryFn: () => apiFetch<PositionResp>("/treasury/cash-position"),
    refetchInterval: 60000,
  });
}
function useForecast() {
  return useQuery<ForecastResp>({
    queryKey: ["treasury-forecast"],
    queryFn: () => apiFetch<ForecastResp>("/treasury/forecast"),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}
function useBudget(months: number) {
  return useQuery<BudgetResp>({
    queryKey: ["treasury-budget", months],
    queryFn: () => apiFetch<BudgetResp>(`/treasury/budget?months_ahead=${months}`),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

export default function TreasuryPage() {
  const [activeTab, setActiveTab] = useState<"overview" | "budget" | "runway">("overview");
  const [budgetMonths, setBudgetMonths] = useState(3);

  const { data: summary, isLoading: summaryLoading } = useTreasury();
  const { data: position, isLoading: positionLoading } = useCashPosition();
  const { data: forecast } = useForecast();
  const { data: budget, isLoading: budgetLoading } = useBudget(budgetMonths);

  const upcomingPayments = summary?.upcoming_payments || [];
  const monthlyBurn: BurnItem[] = summary?.monthly_burn || [];
  const positions: CashPosition[] = position?.positions || [];
  const forecastData = forecast?.cash_flow_forecast || [];
  const historyData = summary?.monthly_history_usd || [];
  const runway = forecast?.runway_analysis;

  return (
    <motion.div variants={cv} initial="hidden" animate="show" className="space-y-6">
      <motion.div variants={iv} className="flex items-center justify-between">
        <div>
          <div className="flex items-center">
            <h1 className="text-2xl font-bold text-white">Treasury Intelligence</h1>
            <PageContextHelp
              pageName="Treasury Intelligence"
              why="Treasury management is critical for understanding organizational runway and liquidity. This page provides real-time visibility into cash flow."
              what="You get live cash positions derived directly from invoice records, alongside an AI-powered forecast projecting your runway based on recent historical burn."
              how="Use the AI Budget Forecast to identify categories where spend is trending up. The Runway analysis will tell you exactly how many days of cash remain based on current burn."
            />
          </div>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
            Cash positions derived from invoice records · AI-powered forecasting
          </p>
        </div>
        {/* Tabs */}
        <div className="flex gap-2">
          {(["overview", "budget", "runway"] as const).map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${activeTab === tab ? "bg-blue-500 text-white" : "text-slate-400 hover:text-white"}`}
              style={activeTab !== tab ? { background: "var(--color-bg-card)", border: "1px solid var(--color-border)" } : {}}>
              {tab === "overview" ? "Overview" : tab === "budget" ? "Budget Forecast" : "Runway"}
            </button>
          ))}
        </div>
      </motion.div>

      {activeTab === "overview" && (
        <>
          {/* Cash Positions */}
          <motion.div variants={iv}>
            <h2 className="text-sm font-semibold text-white mb-3">Cash Positions by Currency</h2>
            {positionLoading ? (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {Array.from({ length: 4 }).map((_, i) => <div key={i} className="card p-4 shimmer h-24" />)}
              </div>
            ) : positions.length === 0 ? (
              <div className="card p-8 flex flex-col items-center gap-2">
                <InboxIcon size={24} style={{ color: "var(--color-text-muted)" }} />
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>No cash position data</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {positions.map(pos => (
                  <div key={pos.currency as string} className="card p-4">
                    <div className="flex items-center justify-between mb-2">
                      <Landmark size={16} className="text-blue-400" />
                      <span className="text-xs font-bold text-blue-400">{pos.currency as string}</span>
                    </div>
                    <p className="text-xl font-bold text-white">
                      {CURRENCY_SYMBOLS[pos.currency as string] || ""}{((pos.current_balance as number) / 1000).toFixed(0)}K
                    </p>
                    <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>{pos.account as string}</p>
                    <div className="mt-2 pt-2" style={{ borderTop: "1px solid var(--color-border)" }}>
                      <div className="flex justify-between text-xs">
                        <span style={{ color: "var(--color-text-muted)" }}>Outflow</span>
                        <span className="text-rose-400">−{CURRENCY_SYMBOLS[pos.currency as string] || ""}{((pos.outflow as number) / 1000).toFixed(0)}K</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </motion.div>

          {/* Burn + History */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <motion.div variants={iv} className="card p-5">
              <div className="flex items-center gap-2 mb-3">
                <TrendingDown size={16} className="text-amber-400" />
                <h2 className="text-sm font-semibold text-white">Monthly Burn</h2>
              </div>
              {summaryLoading ? (
                <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="shimmer h-10 rounded-lg" />)}</div>
              ) : monthlyBurn.length === 0 ? (
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>No expense data</p>
              ) : (
                <div className="space-y-3">
                  {monthlyBurn.map(b => (
                    <div key={b.currency} className="flex items-center justify-between p-3 rounded-xl" style={{ background: "var(--color-bg-elevated)" }}>
                      <span className="text-sm font-medium text-white">{b.currency}</span>
                      <span className="text-sm font-bold text-rose-400">-{CURRENCY_SYMBOLS[b.currency] || ""}{b.amount.toLocaleString()}</span>
                    </div>
                  ))}
                  {summary?.runway_days != null && (
                    <div className="p-3 rounded-xl" style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.2)" }}>
                      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Estimated USD Runway</p>
                      <p className="text-xl font-bold text-emerald-400">{summary.runway_days} days</p>
                    </div>
                  )}
                </div>
              )}
            </motion.div>

            <motion.div variants={iv} className="card p-5 lg:col-span-2">
              <h2 className="text-sm font-semibold text-white mb-3">Historical Monthly Spend (USD)</h2>
              {summaryLoading ? (
                <div className="shimmer rounded-xl" style={{ height: 160 }} />
              ) : historyData.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-2 rounded-xl" style={{ height: 160, background: "var(--color-bg-elevated)", border: "1px dashed var(--color-border)" }}>
                  <InboxIcon size={18} style={{ color: "var(--color-text-muted)" }} />
                  <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>No historical data</p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={historyData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                    <XAxis dataKey="month" tick={{ fill: "#475569", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "#475569", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `$${(v / 1000).toFixed(0)}K`} />
                    <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, color: "#f8fafc" }} formatter={(v: unknown) => [`$${(v as number).toLocaleString()}`, ""]} />
                    <Bar dataKey="spend" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </motion.div>
          </div>

          {/* AI Forecast */}
          {forecast && forecastData.length > 0 && (
            <motion.div variants={iv} className="card p-5">
              <div className="flex items-center gap-2 mb-4">
                <AlertCircle size={16} className="text-violet-400" />
                <h2 className="text-sm font-semibold text-white">AI Cash Flow Forecast</h2>
                <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(139,92,246,0.1)", color: "#8b5cf6" }}>
                  {forecast.confidence ? `${(forecast.confidence * 100).toFixed(0)}% confidence` : "AI generated"}
                </span>
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={forecastData}>
                  <defs>
                    <linearGradient id="inGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} /><stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="outGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.2} /><stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="month" tick={{ fill: "#475569", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#475569", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `$${(v / 1000).toFixed(0)}K`} />
                  <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, color: "#f8fafc" }} formatter={(v: unknown) => [`$${(v as number).toLocaleString()}`, ""]} />
                  <Area type="monotone" dataKey="inflow" name="Inflow" stroke="#10b981" strokeWidth={2} fill="url(#inGrad)" />
                  <Area type="monotone" dataKey="outflow" name="Outflow" stroke="#f43f5e" strokeWidth={2} fill="url(#outGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </motion.div>
          )}

          {/* Upcoming Payments */}
          <motion.div variants={iv} className="card p-5">
            <div className="flex items-center gap-2 mb-4">
              <Calendar size={16} className="text-amber-400" />
              <h2 className="text-sm font-semibold text-white">Upcoming Payments</h2>
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>— from pending/approved invoices</span>
            </div>
            {summaryLoading ? (
              <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="shimmer h-12 rounded-xl" />)}</div>
            ) : upcomingPayments.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-8">
                <InboxIcon size={24} style={{ color: "var(--color-text-muted)" }} />
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>No upcoming payments in the next 30 days</p>
              </div>
            ) : (
              <div className="space-y-2">
                {upcomingPayments.map((p, i) => (
                  <div key={i} className="flex items-center justify-between p-3 rounded-xl" style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
                    <div>
                      <p className="text-sm font-medium text-white">
                        {p.description as string || p.invoice_number as string || `Invoice #${(p.invoice_id as string)?.slice(0, 8)}`}
                      </p>
                      <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>
                        Due {p.due_date ? new Date(p.due_date as string).toLocaleDateString() : "—"}
                        {p.days_until != null && ` · ${(p.days_until as number) <= 0 ? "Overdue" : `${p.days_until} days`}`}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-bold text-white">
                        {CURRENCY_SYMBOLS[p.currency as string] || "$"}{(p.amount as number)?.toLocaleString()}
                      </p>
                      <span className={`badge text-xs ${(p.days_until as number) <= 3 ? "badge-danger" : (p.days_until as number) <= 7 ? "badge-warning" : "badge-neutral"}`}>
                        {p.risk_level as string}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        </>
      )}

      {/* BUDGET TAB — GET /treasury/budget */}
      {activeTab === "budget" && (
        <motion.div variants={iv} className="space-y-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <PieChart size={16} className="text-violet-400" />
              <h2 className="text-sm font-semibold text-white">AI Budget Forecast</h2>
              <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(139,92,246,0.1)", color: "#8b5cf6" }}>forecasting_agent</span>
            </div>
            <div className="flex gap-2">
              {[1, 3, 6, 12].map(m => (
                <button key={m} onClick={() => setBudgetMonths(m)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${budgetMonths === m ? "bg-violet-500 text-white" : "text-slate-400"}`}
                  style={budgetMonths !== m ? { background: "var(--color-bg-card)", border: "1px solid var(--color-border)" } : {}}>
                  {m}M
                </button>
              ))}
            </div>
          </div>

          {budgetLoading ? (
            <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="card shimmer h-20" />)}</div>
          ) : !budget ? (
            <div className="card p-16 flex flex-col items-center gap-3">
              <InboxIcon size={36} style={{ color: "var(--color-text-muted)" }} />
              <p className="text-white font-semibold">No budget data — add expenses first</p>
            </div>
          ) : (
            <>
              {budget.summary && (
                <div className="p-4 rounded-xl" style={{ background: "rgba(139,92,246,0.08)", border: "1px solid rgba(139,92,246,0.2)" }}>
                  <p className="text-sm text-white">{budget.summary}</p>
                </div>
              )}
              <div className="space-y-3">
                {(() => {
                  const aggregated: Record<string, number> = {};
                  if (budget.monthly_forecasts) {
                    budget.monthly_forecasts.forEach((mf: any) => {
                      if (mf.categories) {
                        mf.categories.forEach((c: any) => {
                          aggregated[c.category] = (aggregated[c.category] || 0) + (c.projected || c.allocated || 0);
                        });
                      }
                    });
                  } else if (budget.categories || budget.budget_by_category) {
                     const cats = budget.categories || budget.budget_by_category || [];
                     cats.forEach((c: any) => {
                         aggregated[c.category] = (aggregated[c.category] || 0) + (c.projected || c.allocated || 0);
                     });
                  }
                  
                  return Object.entries(aggregated)
                    .sort((a, b) => b[1] - a[1])
                    .map(([catName, total], i) => (
                    <div key={i} className="flex items-center justify-between p-3 rounded-xl" style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
                      <div>
                        <p className="text-sm font-semibold text-white">{catName}</p>
                        <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>Projected for next {budgetMonths} month(s)</p>
                      </div>
                      <p className="text-sm font-bold text-violet-400">
                        ${(total / 1000).toFixed(1)}K
                      </p>
                    </div>
                  ));
                })()}
              </div>
            </>
          )}
        </motion.div>
      )}

      {/* RUNWAY TAB */}
      {activeTab === "runway" && (
        <motion.div variants={iv} className="space-y-5">
          <div className="flex items-center gap-2">
            <Target size={16} className="text-emerald-400" />
            <h2 className="text-sm font-semibold text-white">Runway Analysis</h2>
            <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(16,185,129,0.1)", color: "#10b981" }}>forecasting_agent</span>
          </div>

          {!runway ? (
            <div className="card p-12 flex flex-col items-center gap-3">
              <InboxIcon size={32} style={{ color: "var(--color-text-muted)" }} />
              <p className="text-white font-semibold">No runway data available</p>
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Generated with the cash flow forecast</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Hero metrics */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {runway.runway_months != null && (
                  <div className="card p-5 text-center" style={{ borderColor: "rgba(16,185,129,0.3)" }}>
                    <p className="text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>Runway (months)</p>
                    <p className="text-4xl font-bold text-emerald-400">{Number(runway.runway_months).toFixed(1)}</p>
                  </div>
                )}
                {runway.runway_days != null && (
                  <div className="card p-5 text-center">
                    <p className="text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>Runway (days)</p>
                    <p className="text-4xl font-bold text-blue-400">{Number(runway.runway_days).toLocaleString()}</p>
                  </div>
                )}
                {runway.current_burn_rate != null && (
                  <div className="card p-5 text-center">
                    <p className="text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>Monthly Burn</p>
                    <p className="text-2xl font-bold text-rose-400">${Number(runway.current_burn_rate).toLocaleString()}</p>
                  </div>
                )}
                {runway.confidence != null && (
                  <div className="card p-5 text-center">
                    <p className="text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>Confidence</p>
                    <p className="text-2xl font-bold text-violet-400">{(Number(runway.confidence) * 100).toFixed(0)}%</p>
                  </div>
                )}
              </div>

              {/* Scenarios */}
              {runway.scenarios && typeof runway.scenarios === "object" && (
                <div className="card p-5">
                  <p className="text-xs font-semibold text-slate-400 mb-3">Scenarios</p>
                  <div className="grid grid-cols-3 gap-3">
                    {Object.entries(runway.scenarios as Record<string, Record<string, number>>).map(([scenario, vals]) => (
                      <div key={scenario} className="p-3 rounded-xl" style={{
                        background: scenario === "optimistic" ? "rgba(16,185,129,0.06)" : scenario === "pessimistic" ? "rgba(244,63,94,0.06)" : "rgba(59,130,246,0.06)",
                        border: `1px solid ${scenario === "optimistic" ? "rgba(16,185,129,0.2)" : scenario === "pessimistic" ? "rgba(244,63,94,0.2)" : "rgba(59,130,246,0.2)"}`,
                      }}>
                        <p className="text-xs font-semibold capitalize mb-2" style={{ color: scenario === "optimistic" ? "#10b981" : scenario === "pessimistic" ? "#f43f5e" : "#3b82f6" }}>
                          {scenario}
                        </p>
                        {Object.entries(vals || {}).map(([k, v]) => (
                          <div key={k} className="flex justify-between text-xs">
                            <span style={{ color: "var(--color-text-muted)" }}>{k.replace(/_/g, " ")}</span>
                            <span className="text-white font-semibold">
                              {k.includes("burn") ? `$${Number(v).toLocaleString()}` : `${Number(v).toFixed(1)} mo`}
                            </span>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Top Burn Categories */}
              {Array.isArray(runway.top_burn_categories) && runway.top_burn_categories.length > 0 && (
                <div className="card p-5">
                  <p className="text-xs font-semibold text-slate-400 mb-3">Top Burn Categories</p>
                  <div className="space-y-2">
                    {(runway.top_burn_categories as { category: string; monthly_avg: number }[]).map((cat, i) => (
                      <div key={i} className="flex items-center justify-between p-2 rounded-lg" style={{ background: "var(--color-bg-elevated)" }}>
                        <span className="text-sm text-white">{cat.category}</span>
                        <span className="text-sm font-bold text-rose-400">${Number(cat.monthly_avg).toLocaleString()}/mo</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Reduction Opportunities */}
              {Array.isArray(runway.reduction_opportunities) && runway.reduction_opportunities.length > 0 && (
                <div className="card p-5">
                  <p className="text-xs font-semibold text-emerald-400 mb-3">Reduction Opportunities</p>
                  <div className="space-y-2">
                    {(runway.reduction_opportunities as { category: string; potential_reduction: number; action: string }[]).map((opp, i) => (
                      <div key={i} className="p-3 rounded-xl" style={{ background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.15)" }}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-semibold text-white">{opp.category}</span>
                          <span className="text-sm font-bold text-emerald-400">-${Number(opp.potential_reduction).toLocaleString()}</span>
                        </div>
                        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>→ {opp.action}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Per-currency runway bars */}
          {summary?.runway_days != null && monthlyBurn.length > 0 && (
            <div className="card p-5">
              <h3 className="text-sm font-semibold text-white mb-3">Estimated Days Remaining per Currency</h3>
              <div className="space-y-3">
                {monthlyBurn.map(b => {
                  const posData = positions.find(p => p.currency === b.currency);
                  const balance = posData?.current_balance ?? 0;
                  const days = b.amount > 0 ? Math.round((balance as number) / b.amount * 30) : 0;
                  const pct = b.amount > 0 ? Math.min(days / 365 * 100, 100) : 0;
                  return (
                    <div key={b.currency}>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-white">{b.currency}</span>
                        <span style={{ color: "var(--color-text-muted)" }}>{days > 0 ? `${days} days` : "—"}</span>
                      </div>
                      <div className="h-2 rounded-full" style={{ background: "var(--color-bg-elevated)" }}>
                        <div className="h-2 rounded-full transition-all" style={{ width: `${pct}%`, background: pct > 60 ? "#10b981" : pct > 30 ? "#f59e0b" : "#f43f5e" }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </motion.div>
      )}
    </motion.div>
  );
}

