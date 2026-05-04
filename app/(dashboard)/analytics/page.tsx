"use client";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { BarChart3, TrendingUp, PieChart as PieIcon, Download, InboxIcon } from "lucide-react";
import PageContextHelp from "@/components/global/PageContextHelp";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, PieChart, Pie, Cell,
} from "recharts";

import { apiFetch } from "@/lib/api";
const cv = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const iv = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };
const COLORS = ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#f43f5e", "#06b6d4", "#ec4899", "#84cc16"];

interface TrendPoint { date: string; amount: number; currency: string; }
interface TrendResp { data: TrendPoint[]; base_currency: string; }
interface CategoryPoint { category: string; total: number; currency: string; }
interface CategoryResp { data: CategoryPoint[]; base_currency: string; }
interface VendorPoint { name: string; total: number; currency: string; }
interface VendorResp { data: VendorPoint[]; base_currency: string; }

function useTrend(days: number) {
  return useQuery<TrendResp>({
    queryKey: ["spend-trend", days],
    queryFn: () => apiFetch<TrendResp>(`/analytics/spend-trend?days=${days}`),
  });
}
function useCategories(days: number) {
  return useQuery<CategoryResp>({
    queryKey: ["category-breakdown", days],
    queryFn: () => apiFetch<CategoryResp>(`/analytics/category-breakdown?days=${days}`),
  });
}
function useVendors(days: number) {
  return useQuery<VendorResp>({
    queryKey: ["vendor-breakdown", days],
    queryFn: () => apiFetch<VendorResp>(`/analytics/vendor-breakdown?days=${days}`),
  });
}

function EmptyChart({ height, message }: { height: number; message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl"
      style={{ height, background: "var(--color-bg-elevated)", border: "1px dashed var(--color-border)" }}>
      <InboxIcon size={18} style={{ color: "var(--color-text-muted)" }} />
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{message}</p>
    </div>
  );
}

export default function AnalyticsPage() {
  const { data: trendResp, isLoading: trendLoading } = useTrend(90);
  const { data: catResp, isLoading: catLoading } = useCategories(90);
  const { data: vendorResp, isLoading: vendorLoading } = useVendors(90);

  const baseCurrency = trendResp?.base_currency || catResp?.base_currency || "USD";
  const CURRENCY_SYMBOLS: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£", JPY: "¥" };
  const currencySymbol = CURRENCY_SYMBOLS[baseCurrency] || "$";

  const trendData = (trendResp?.data || [])
    .map((d: { date: string; amount: number; currency: string }) => ({
      date: d.date ? new Date(d.date).toLocaleDateString("en", { month: "short", day: "numeric" }) : "",
      actual: d.amount,
      currency: d.currency,
    }));

  const categoryData = (catResp?.data || []);
  const vendorData = (vendorResp?.data || []);

  return (
    <motion.div variants={cv} initial="hidden" animate="show" className="space-y-6">
      <motion.div variants={iv} className="flex items-center justify-between">
        <div>
          <div className="flex items-center">
            <h1 className="text-2xl font-bold text-white">Financial Analytics</h1>
            <PageContextHelp
              pageName="Financial Analytics"
              why="Raw data isn't useful without visual trends. Analytics provides cross-departmental macro views of spending habits."
              what="You get fully interactive 90-day spend trends, dynamic category breakdowns, and top vendor charts, all aggregated live from your financial records."
              how="Analyze the 'Spend by Category' pie chart to identify where capital is flowing. Use the 'Top Vendors' bar chart to negotiate bulk discounts with your highest-volume suppliers."
            />
          </div>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
            Deep dive into spend, vendors, and policy compliance
          </p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all hover:bg-slate-800"
          style={{ background: "var(--color-bg-card)", color: "var(--color-text-primary)", border: "1px solid var(--color-border)" }}>
          <Download size={14} /> Export CSV
        </button>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Spend Trend */}
        <motion.div variants={iv} className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={16} className="text-blue-400" />
            <h2 className="text-base font-semibold text-white">90-Day Spend Trend</h2>
          </div>
          {trendLoading ? (
            <div className="shimmer rounded-xl" style={{ height: 260 }} />
          ) : trendData.length === 0 ? (
            <EmptyChart height={260} message="No spend trend data available" />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={trendData}>
                <defs>
                  <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" tick={{ fill: "#475569", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#475569", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `${currencySymbol}${(v / 1000).toFixed(0)}K`} />
                <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, color: "#f8fafc" }} formatter={(v: unknown) => [`${currencySymbol}${(v as number).toLocaleString()}`, ""]} />
                <Area type="monotone" dataKey="actual" stroke="#3b82f6" strokeWidth={2} fill="url(#trendGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </motion.div>

        {/* Category Breakdown */}
        <motion.div variants={iv} className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <PieIcon size={16} className="text-emerald-400" />
            <h2 className="text-base font-semibold text-white">Spend by Category</h2>
          </div>
          {catLoading ? (
            <div className="shimmer rounded-xl" style={{ height: 260 }} />
          ) : categoryData.length === 0 ? (
            <EmptyChart height={260} message="No category data available" />
          ) : (
            <div className="flex items-center">
              <div className="w-1/2">
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie data={categoryData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} dataKey="total" paddingAngle={2}>
                      {categoryData.map((_: unknown, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, color: "#f8fafc" }} formatter={(v: unknown) => [`${currencySymbol}${(v as number).toLocaleString()}`, ""]} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="w-1/2 pl-4 space-y-3">
                {categoryData.slice(0, 6).map((d: { category: string; total: number; currency: string }, i: number) => {
                  const max = categoryData[0]?.total || 1;
                  return (
                    <div key={i} className="flex flex-col">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <div className="w-2.5 h-2.5 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                          <span className="text-xs font-medium text-white truncate max-w-[100px]">{d.category}</span>
                        </div>
                        <span className="text-xs font-semibold text-white">{currencySymbol}{(d.total / 1000).toFixed(0)}K</span>
                      </div>
                      <div className="progress-bar h-1">
                        <div className="progress-fill" style={{ background: COLORS[i % COLORS.length], width: `${(d.total / max) * 100}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </motion.div>

        {/* Top Vendors */}
        <motion.div variants={iv} className="card p-5 lg:col-span-2">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 size={16} className="text-violet-400" />
            <h2 className="text-base font-semibold text-white">Top Vendors by Spend</h2>
          </div>
          {vendorLoading ? (
            <div className="shimmer rounded-xl" style={{ height: 260 }} />
          ) : vendorData.length === 0 ? (
            <EmptyChart height={260} message="No vendor data available" />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={vendorData.slice(0, 10)}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: "#475569", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#475569", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `${currencySymbol}${(v / 1000).toFixed(0)}K`} />
                <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, color: "#f8fafc" }} cursor={{ fill: "rgba(255,255,255,0.05)" }} formatter={(v: unknown) => [`${currencySymbol}${(v as number).toLocaleString()}`, ""]} />
                <Bar dataKey="total" fill="#8b5cf6" radius={[4, 4, 0, 0]} barSize={36} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </motion.div>
      </div>
    </motion.div>
  );
}
