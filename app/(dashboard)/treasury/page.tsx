"use client";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Landmark, TrendingDown, Calendar, InboxIcon, AlertCircle } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from "recharts";

import { apiFetch } from "@/lib/api";
const cv = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const iv = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };
const CURRENCY_SYMBOLS: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£", JPY: "¥" };

interface CashPosition { currency: string; account: string; current_balance: number; outflow: number; }
interface BurnItem { currency: string; amount: number; }
interface TreasuryResp { upcoming_payments: Record<string, unknown>[]; monthly_burn: BurnItem[]; runway_days?: number; monthly_history_usd: { month: string; spend: number }[]; }
interface PositionResp { positions: CashPosition[]; }
interface ForecastResp { cash_flow_forecast: { month: string; inflow: number; outflow: number; net: number }[]; confidence?: number; }

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

export default function TreasuryPage() {
  const { data: summary, isLoading: summaryLoading } = useTreasury();
  const { data: position, isLoading: positionLoading } = useCashPosition();
  const { data: forecast } = useForecast();

  const upcomingPayments = summary?.upcoming_payments || [];
  const monthlyBurn: BurnItem[] = summary?.monthly_burn || [];
  const positions: CashPosition[] = position?.positions || [];
  const forecastData = forecast?.cash_flow_forecast || [];
  const historyData = summary?.monthly_history_usd || [];

  return (
    <motion.div variants={cv} initial="hidden" animate="show" className="space-y-6">
      <motion.div variants={iv}>
        <h1 className="text-2xl font-bold text-white">Treasury Intelligence</h1>
        <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
          Cash positions derived from invoice records · AI-powered forecasting
        </p>
      </motion.div>

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

      {/* Runway + Burn */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <motion.div variants={iv} className="card p-5">
          <div className="flex items-center gap-2 mb-3">
            <TrendingDown size={16} className="text-amber-400" />
            <h2 className="text-sm font-semibold text-white">Monthly Burn</h2>
          </div>
          {summaryLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => <div key={i} className="shimmer h-10 rounded-lg" />)}
            </div>
          ) : monthlyBurn.length === 0 ? (
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>No expense data</p>
          ) : (
            <div className="space-y-3">
              {monthlyBurn.map(b => (
                <div key={b.currency} className="flex items-center justify-between p-3 rounded-xl" style={{ background: "var(--color-bg-elevated)" }}>
                  <span className="text-sm font-medium text-white">{b.currency}</span>
                  <span className="text-sm font-bold text-rose-400">
                    -{CURRENCY_SYMBOLS[b.currency] || ""}{b.amount.toLocaleString()}
                  </span>
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

        {/* Historical USD Spend Chart */}
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
    </motion.div>
  );
}
