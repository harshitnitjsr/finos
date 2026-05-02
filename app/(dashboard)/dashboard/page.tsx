"use client";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  TrendingUp, TrendingDown, AlertTriangle, CheckSquare,
  Workflow, Bot, DollarSign, Zap, ArrowRight, Clock, InboxIcon,
  Activity, Shield
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

const COLORS = ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#f43f5e", "#06b6d4"];
const CS: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£", JPY: "¥" };

const cv = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const iv = { hidden: { opacity: 0, y: 18 }, show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" as const } } };

interface DashboardResp { kpis: Record<string, unknown>; charts: Record<string, unknown>; recent_invoices?: unknown[]; }
interface InsightsResp { status?: string; headline?: string; bullets?: string[]; summary?: string; key_metrics?: unknown[]; recommendations?: unknown[]; }
interface ApprovalsResp { approvals: Record<string, unknown>[]; total: number; counts: Record<string, number>; }
interface WorkflowsResp { workflows: Record<string, unknown>[]; counts: Record<string, number>; }

function useAnalytics() {
  return useQuery<DashboardResp>({
    queryKey: ["dashboard"],
    queryFn: () => apiFetch<DashboardResp>("/analytics/dashboard"),
    refetchInterval: 30000,
  });
}
function useInsights() {
  return useQuery<InsightsResp>({
    queryKey: ["executive-summary"],
    queryFn: () => apiFetch<InsightsResp>("/insights/executive-summary"),
    staleTime: 5 * 60 * 1000, retry: false,
  });
}
function useApprovals() {
  return useQuery<ApprovalsResp>({
    queryKey: ["approvals-preview"],
    queryFn: () => apiFetch<ApprovalsResp>("/approvals/?status=pending&limit=5"),
    refetchInterval: 15000,
  });
}
function useWorkflows() {
  return useQuery<WorkflowsResp>({
    queryKey: ["workflows-preview"],
    queryFn: () => apiFetch<WorkflowsResp>("/workflows/?limit=5"),
    refetchInterval: 5000,
  });
}

export default function DashboardPage() {
  const { data: analytics, isLoading } = useAnalytics();
  const { data: insights, isLoading: insightsLoading } = useInsights();
  const { data: approvalsData } = useApprovals();
  const { data: workflowsData } = useWorkflows();

  type SpendItem = { currency: string; total: number; change_pct?: number };
  type TrendPoint = { date: string; amount: number };
  type CategoryItem = { category: string; amount: number; currency: string };

  const kpis = analytics?.kpis as Record<string, unknown> || {};
  const charts = analytics?.charts as Record<string, unknown> || {};

  const usdSpend = (kpis.monthly_spend as SpendItem[] | undefined)?.find(s => s.currency === "USD");
  const currUsdSpend = usdSpend?.total || 0;
  const spendChangePct = usdSpend?.change_pct;

  const trendData = ((charts.expense_trend as TrendPoint[] | undefined) || []).map(d => ({
    date: d.date ? new Date(d.date).toLocaleDateString("en", { month: "short", day: "numeric" }) : "",
    v: d.amount,
  }));
  const categoryData = (charts.category_breakdown as CategoryItem[] | undefined) || [];
  const approvals = approvalsData?.approvals || [];
  const workflows = workflowsData?.workflows || [];

  return (
    <motion.div variants={cv} initial="hidden" animate="show" className="space-y-5 max-w-[1400px]">

      {/* ── Header ── */}
      <motion.div variants={iv} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Financial Operations</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--color-text-secondary)" }}>
            {new Date().toLocaleDateString("en", { weekday: "long", month: "long", day: "numeric" })}
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl" style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.2)" }}>
          <span className="w-2 h-2 rounded-full bg-emerald-400 pulse-emerald" />
          <span className="text-xs font-semibold text-emerald-400">Live</span>
        </div>
      </motion.div>

      {/* ── AI Banner ── */}
      <motion.div variants={iv} className="card p-4" style={{ borderColor: "rgba(59,130,246,0.25)", background: "linear-gradient(135deg, rgba(59,130,246,0.05) 0%, rgba(139,92,246,0.05) 100%)" }}>
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-xl animated-gradient flex items-center justify-center flex-shrink-0">
            <Bot size={16} className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-bold text-blue-400 uppercase tracking-wider">AI Insight Agent</span>
              {insights && (
                <span className={`badge text-xs ${insights.status === "healthy" ? "badge-success" : insights.status === "warning" ? "badge-warning" : "badge-danger"}`}>
                  {insights.status}
                </span>
              )}
            </div>
            {insightsLoading ? (
              <div className="space-y-1.5">
                <div className="shimmer h-3.5 w-3/4 rounded" />
                <div className="shimmer h-3 w-full rounded" />
              </div>
            ) : insights ? (
              <>
                <p className="text-sm font-semibold text-white leading-snug">{insights.headline}</p>
                {(insights.bullets?.length ?? 0) > 0 && (
                  <div className="flex flex-wrap gap-x-4 mt-1.5">
                    {insights.bullets?.slice(0, 3).map((b: string, i: number) => (
                      <span key={i} className="flex items-center gap-1 text-xs" style={{ color: "var(--color-text-secondary)" }}>
                        <Zap size={9} className="text-blue-400 flex-shrink-0" />{b}
                      </span>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                Insight agent offline — add OPENAI_API_KEY to backend/.env to enable
              </p>
            )}
          </div>
        </div>
      </motion.div>

      {/* ── KPI Cards ── */}
      <motion.div variants={iv} className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {[
          {
            label: "Monthly Spend", sub: "USD",
            value: isLoading ? null : currUsdSpend ? `$${(currUsdSpend / 1000).toFixed(1)}K` : "—",
            detail: spendChangePct != null ? `${spendChangePct >= 0 ? "+" : ""}${spendChangePct}% vs last month` : "No prior data",
            trend: spendChangePct != null ? (spendChangePct > 0 ? "up" : spendChangePct < 0 ? "down" : null) : null,
            trendVal: spendChangePct != null ? `${spendChangePct >= 0 ? "+" : ""}${spendChangePct}%` : undefined,
            Icon: DollarSign, color: "#3b82f6", glow: "rgba(59,130,246,0.12)", border: "rgba(59,130,246,0.2)",
          },
          {
            label: "Pending Approvals", sub: "Require review",
            value: isLoading ? null : kpis.pending_approvals != null ? String(kpis.pending_approvals) : "—",
            detail: (kpis.pending_approvals as number) > 0 ? "Awaiting your action" : "All caught up ✓",
            trend: null, trendVal: undefined,
            Icon: CheckSquare, color: "#f59e0b", glow: "rgba(245,158,11,0.1)", border: "rgba(245,158,11,0.2)",
          },
          {
            label: "AI Anomalies", sub: "Last 30 days",
            value: isLoading ? null : kpis.anomaly_count != null ? String(kpis.anomaly_count) : "—",
            detail: (kpis.anomaly_count as number) > 0 ? "Flagged by AI agents" : "No anomalies detected",
            trend: (kpis.anomaly_count as number) > 0 ? "up" as const : null, trendVal: undefined,
            Icon: AlertTriangle, color: "#f43f5e", glow: "rgba(244,63,94,0.1)", border: "rgba(244,63,94,0.2)",
          },
          {
            label: "Active Workflows", sub: "Running + pending",
            value: isLoading ? null : kpis.active_workflows != null ? String(kpis.active_workflows) : "—",
            detail: "Automated pipelines",
            trend: null, trendVal: undefined,
            Icon: Workflow, color: "#8b5cf6", glow: "rgba(139,92,246,0.1)", border: "rgba(139,92,246,0.2)",
          },
        ].map((kpi) => (
          <div key={kpi.label} className="card p-4" style={{ borderColor: kpi.border }}>
            <div className="flex items-center justify-between mb-3">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: kpi.glow }}>
                <kpi.Icon size={15} style={{ color: kpi.color }} />
              </div>
              {kpi.trendVal && (
                <span className={`flex items-center gap-0.5 text-xs font-bold ${kpi.trend === "up" ? "text-rose-400" : "text-emerald-400"}`}>
                  {kpi.trend === "up" ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                  {kpi.trendVal}
                </span>
              )}
            </div>
            {kpi.value === null ? (
              <>
                <div className="shimmer h-7 w-16 rounded mb-1" />
                <div className="shimmer h-3 w-24 rounded" />
              </>
            ) : (
              <>
                <div className="text-2xl font-black text-white tracking-tight leading-none">{kpi.value}</div>
                <div className="text-xs mt-1.5" style={{ color: "var(--color-text-muted)" }}>{kpi.detail}</div>
              </>
            )}
            <div className="text-xs font-semibold mt-2.5" style={{ color: "var(--color-text-secondary)" }}>{kpi.label}</div>
          </div>
        ))}
      </motion.div>

      {/* ── Charts ── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Spend Trend */}
        <motion.div variants={iv} className="card p-5 xl:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-white">Spend Trend</h2>
              <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>30-day rolling actual</p>
            </div>
            <Link href="/analytics" className="flex items-center gap-1 text-xs font-semibold text-blue-400 hover:text-blue-300 transition-colors">
              Deep dive <ArrowRight size={11} />
            </Link>
          </div>
          {isLoading ? (
            <div className="shimmer rounded-xl" style={{ height: 200 }} />
          ) : trendData.length === 0 ? (
            <Empty h={200} msg="No spend data — upload an invoice to get started" />
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={trendData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="aGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="date" tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => `$${(v / 1000).toFixed(0)}K`} width={44} />
                <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, color: "#f8fafc", fontSize: 12 }} formatter={(v: unknown) => [`$${(v as number).toLocaleString()}`, "Spend"]} />
                <Area type="monotone" dataKey="v" name="Spend" stroke="#3b82f6" strokeWidth={2} fill="url(#aGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </motion.div>

        {/* Category Pie */}
        <motion.div variants={iv} className="card p-5">
          <h2 className="text-sm font-bold text-white mb-0.5">Spend by Category</h2>
          <p className="text-xs mb-3" style={{ color: "var(--color-text-muted)" }}>Last 90 days</p>
          {isLoading ? (
            <div className="shimmer rounded-xl" style={{ height: 200 }} />
          ) : categoryData.length === 0 ? (
            <Empty h={200} msg="No category data yet" />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={140}>
                <PieChart>
                  <Pie data={categoryData} cx="50%" cy="50%" innerRadius={38} outerRadius={62} dataKey="amount" paddingAngle={2}>
                    {categoryData.map((_: unknown, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, color: "#f8fafc", fontSize: 12 }} formatter={(v: unknown) => [`$${(v as number).toLocaleString()}`, ""]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2 mt-1">
                {categoryData.slice(0, 5).map((d: { category: string; amount: number }, i: number) => (
                  <div key={i} className="flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
                      <span className="text-xs truncate" style={{ color: "var(--color-text-secondary)" }}>{d.category}</span>
                    </div>
                    <span className="text-xs font-bold text-white ml-2 flex-shrink-0">${(d.amount / 1000).toFixed(0)}K</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </motion.div>
      </div>

      {/* ── Bottom Row ── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Pending Approvals */}
        <motion.div variants={iv} className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Shield size={14} className="text-amber-400" />
              <h2 className="text-sm font-bold text-white">Pending Approvals</h2>
              {approvals.length > 0 && (
                <span className="badge badge-warning text-xs">{approvals.length}</span>
              )}
            </div>
            <Link href="/approvals" className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300">
              All <ArrowRight size={11} />
            </Link>
          </div>
          {approvals.length === 0 ? (
            <Empty h={110} msg="No pending approvals — all caught up!" />
          ) : (
            <div className="space-y-2">
              {approvals.map((a: Record<string, unknown>, i: number) => (
                <div key={i} className="flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors"
                  style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${a.risk_level === "high" || a.risk_level === "critical" ? "bg-rose-400" : a.risk_level === "medium" ? "bg-amber-400" : "bg-emerald-400"}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-white truncate">
                      Invoice #{(a.invoice_id as string)?.slice(0, 8) || "—"}
                    </p>
                    <p className="text-xs mt-0.5 truncate" style={{ color: "var(--color-text-muted)" }}>
                      {a.ai_recommendation as string || "Pending AI review"}
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-xs font-bold text-white">
                      {CS[a.currency as string] || "$"}{(a.amount as number)?.toLocaleString()}
                    </p>
                    <span className={`text-xs badge ${a.risk_level === "high" || a.risk_level === "critical" ? "badge-danger" : a.risk_level === "medium" ? "badge-warning" : "badge-success"}`}>
                      {a.risk_level as string}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </motion.div>

        {/* Workflows */}
        <motion.div variants={iv} className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity size={14} className="text-violet-400" />
              <h2 className="text-sm font-bold text-white">Active Workflows</h2>
            </div>
            <Link href="/workflows" className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300">
              All <ArrowRight size={11} />
            </Link>
          </div>
          {workflows.length === 0 ? (
            <Empty h={110} msg="No workflows — upload an invoice to trigger pipeline" />
          ) : (
            <div className="space-y-2">
              {workflows.map((w: Record<string, unknown>, i: number) => {
                const steps = (w.steps as { status: string }[]) || [];
                const done = steps.filter(s => s.status === "completed").length;
                const pct = steps.length > 0 ? Math.round((done / steps.length) * 100) : 0;
                const col = w.status === "completed" ? "#10b981" : w.status === "failed" ? "#f43f5e" : "#3b82f6";
                return (
                  <div key={i} className="px-3 py-2.5 rounded-xl" style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-semibold text-white truncate mr-2">{w.name as string}</span>
                      <span className={`badge text-xs flex-shrink-0 ${w.status === "running" ? "badge-info" : w.status === "completed" ? "badge-success" : w.status === "failed" ? "badge-danger" : "badge-neutral"}`}>
                        {w.status as string}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="progress-bar flex-1">
                        <div className="progress-fill" style={{ width: `${pct}%`, background: col }} />
                      </div>
                      <span className="text-xs flex-shrink-0 font-mono" style={{ color: "var(--color-text-muted)" }}>{pct}%</span>
                    </div>
                    {!!(w.started_at as string) && (
                      <div className="flex items-center gap-1 mt-1">
                        <Clock size={9} style={{ color: "var(--color-text-muted)" }} />
                        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                          {new Date(w.started_at as string).toLocaleTimeString()}
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </motion.div>
      </div>

    </motion.div>
  );
}

function Empty({ h, msg }: { h: number; msg: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl"
      style={{ height: h, background: "var(--color-bg-elevated)", border: "1px dashed var(--color-border)" }}>
      <InboxIcon size={18} style={{ color: "var(--color-text-muted)" }} />
      <p className="text-xs text-center px-4" style={{ color: "var(--color-text-muted)" }}>{msg}</p>
    </div>
  );
}
