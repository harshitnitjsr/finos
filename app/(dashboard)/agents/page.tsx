"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Bot, Activity, Cpu, Zap, InboxIcon, Clock, List, CheckCircle2, XCircle } from "lucide-react";
import PageContextHelp from "@/components/global/PageContextHelp";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

import { apiFetch } from "@/lib/api";
const cv = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const iv = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };

const TASK_COLORS: Record<string, { bg: string; color: string }> = {
  extraction:    { bg: "rgba(59,130,246,0.1)",   color: "#3b82f6" },
  classification:{ bg: "rgba(16,185,129,0.1)",   color: "#10b981" },
  compliance:    { bg: "rgba(244,63,94,0.1)",    color: "#f43f5e" },
  reasoning:     { bg: "rgba(139,92,246,0.1)",   color: "#8b5cf6" },
  forecast:      { bg: "rgba(245,158,11,0.1)",   color: "#f59e0b" },
  routing:       { bg: "rgba(6,182,212,0.1)",    color: "#06b6d4" },
};
const MODEL_LABELS: Record<string, string> = { "gpt-4o": "Advanced Logic AI", "gpt-4o-mini": "Fast Logic AI" };

interface AgentsResponse { agents: Record<string, unknown>[]; active: number; total: number; }
interface ToolSummaryItem { tool_name: string; agent_name: string; total_calls: number; avg_duration_ms: number; success_rate: number; }
interface ToolSummaryResp { tools: ToolSummaryItem[]; }
interface ToolLogItem { id: string; agent_name: string; tool_name: string; run_id: string; input_summary?: string; output_summary?: string; duration_ms: number; status: string; error?: string; created_at: string; }
interface ToolLogsResp { total: number; tool_logs: ToolLogItem[]; }

function useAgents() {
  return useQuery<AgentsResponse>({
    queryKey: ["agents-status"],
    queryFn: () => apiFetch<AgentsResponse>("/agents/status"),
    refetchInterval: 15000,
  });
}
function useToolSummary() {
  return useQuery<ToolSummaryResp>({
    queryKey: ["agents-tool-summary"],
    queryFn: () => apiFetch<ToolSummaryResp>("/agents/tool-logs/summary"),
    staleTime: 30000,
  });
}
function useToolLogs(limit: number) {
  return useQuery<ToolLogsResp>({
    queryKey: ["agents-tool-logs", limit],
    queryFn: () => apiFetch<ToolLogsResp>(`/agents/tool-logs?limit=${limit}`),
    staleTime: 15000,
  });
}

export default function AgentsPage() {
  const [activeTab, setActiveTab] = useState<"agents" | "tool-logs">("agents");
  const [logLimit, setLogLimit] = useState(50);

  const { data, isLoading } = useAgents();
  const { data: toolSummary } = useToolSummary();
  const { data: toolLogs } = useToolLogs(logLimit);

  const agents: Record<string, unknown>[] = data?.agents || [];
  const tools: ToolSummaryItem[] = toolSummary?.tools || [];
  const logs: ToolLogItem[] = toolLogs?.tool_logs || [];

  return (
    <motion.div variants={cv} initial="hidden" animate="show" className="space-y-6">
      <motion.div variants={iv} className="flex items-center justify-between">
        <div>
          <div className="flex items-center">
            <h1 className="text-2xl font-bold text-white">AI Agents</h1>
            <PageContextHelp
              pageName="AI Agents"
              why="The system is driven by a team of autonomous AI assistants. You need visibility into exactly what these assistants are doing in the background."
              what="This page provides a live view of the AI team. You can monitor the health of specific assistants (like the Categorization AI or Insight AI) and view their recent actions."
              how="Switch to the 'Tool Execution Logs' tab to see exactly what external systems the AI assistants are interacting with in real-time. This provides complete transparency into their autonomous actions."
            />
          </div>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
            {data ? `${data.active}/${data.total} agents active` : "Loading agent registry…"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-2">
            {(["agents", "tool-logs"] as const).map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${activeTab === tab ? "bg-blue-500 text-white" : "text-slate-400 hover:text-white"}`}
                style={activeTab !== tab ? { background: "var(--color-bg-card)", border: "1px solid var(--color-border)" } : {}}>
                {tab === "agents" ? "Agents" : `Tool Logs (${toolLogs?.total ?? "…"})`}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl" style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.2)" }}>
            <div className="w-2 h-2 rounded-full bg-emerald-400 pulse-emerald" />
            <span className="text-xs font-semibold text-emerald-400">Model Router Active</span>
          </div>
        </div>
      </motion.div>

      {activeTab === "agents" && (
        <>
          {/* Model Router Status */}
          <motion.div variants={iv} className="card p-5" style={{ borderColor: "rgba(139,92,246,0.2)" }}>
            <div className="flex items-center gap-3 mb-4">
              <Cpu size={18} className="text-violet-400" />
              <h2 className="text-base font-semibold text-white">Model Router Configuration</h2>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
              {[
                { task: "Reasoning & Insights", model: "Advanced Logic AI", color: "#8b5cf6" },
                { task: "OCR Extraction", model: "Fast Logic AI", color: "#3b82f6" },
                { task: "Classification", model: "Fast Logic AI", color: "#10b981" },
                { task: "Compliance Checks", model: "Advanced Logic AI", color: "#f43f5e" },
                { task: "Financial Forecasting", model: "Advanced Logic AI", color: "#f59e0b" },
                { task: "Vector Embeddings", model: "Semantic Indexer", color: "#06b6d4" },
              ].map(r => (
                <div key={r.task} className="p-3 rounded-xl" style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
                  <p className="text-xs font-semibold text-white">{r.task}</p>
                  <div className="flex items-center gap-1.5 mt-1">
                    <div className="w-1.5 h-1.5 rounded-full" style={{ background: r.color }} />
                    <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{r.model}</span>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Agent Cards */}
          {isLoading ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="card p-5 space-y-3">
                  <div className="shimmer h-5 w-40 rounded" />
                  <div className="shimmer h-4 w-full rounded" />
                  <div className="shimmer h-3 w-3/4 rounded" />
                </div>
              ))}
            </div>
          ) : agents.length === 0 ? (
            <div className="card p-16 flex flex-col items-center gap-3">
              <InboxIcon size={36} style={{ color: "var(--color-text-muted)" }} />
              <p className="text-white font-semibold">No agents registered</p>
            </div>
          ) : (
            <motion.div variants={iv} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {agents.map(agent => {
                const tc = TASK_COLORS[agent.task as string] || TASK_COLORS.reasoning;
                const isActive = agent.status === "active";
                return (
                  <div key={agent.id as string} className="card p-5 hover:border-blue-500/20 transition-colors">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: tc.bg, border: `1px solid ${tc.color}30` }}>
                          <Bot size={18} style={{ color: tc.color }} />
                        </div>
                        <div>
                          <p className="text-sm font-bold text-white">{agent.name as string}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <div className={`w-1.5 h-1.5 rounded-full ${isActive ? "bg-emerald-400" : "bg-slate-500"}`} />
                            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{isActive ? "Active" : "Idle"}</span>
                          </div>
                        </div>
                      </div>
                      <span className="text-xs px-2 py-1 rounded-lg font-medium" style={{ background: tc.bg, color: tc.color }}>
                        {agent.task as string}
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      {[
                        { icon: <Activity size={10} style={{ color: "var(--color-text-muted)" }} />, label: "24h calls", value: agent.requests_24h as number ?? "—" },
                        { icon: <Clock size={10} style={{ color: "var(--color-text-muted)" }} />, label: "Avg latency", value: (agent.avg_latency_ms as number) ? `${agent.avg_latency_ms}ms` : "—" },
                        { icon: <Zap size={10} style={{ color: "var(--color-text-muted)" }} />, label: "Tokens", value: (agent.tokens_24h as number) ? `${((agent.tokens_24h as number) / 1000).toFixed(0)}K` : "—" },
                      ].map(stat => (
                        <div key={stat.label} className="p-2 rounded-lg" style={{ background: "var(--color-bg-elevated)" }}>
                          <div className="flex items-center gap-1 mb-1">{stat.icon}<span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{stat.label}</span></div>
                          <p className="text-sm font-bold text-white">{String(stat.value)}</p>
                        </div>
                      ))}
                    </div>

                    <div className="flex items-center justify-between mt-3 pt-3" style={{ borderTop: "1px solid var(--color-border)" }}>
                      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                        {MODEL_LABELS[agent.model as string] || agent.model as string}
                      </span>
                      {agent.last_active ? (
                        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                          Last: {new Date(agent.last_active as string).toLocaleTimeString()}
                        </span>
                      ) : (
                        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>No recent activity</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </motion.div>
          )}
        </>
      )}

      {/* TOOL LOGS TAB */}
      {activeTab === "tool-logs" && (
        <motion.div variants={iv} className="space-y-5">
          {/* Tool Usage Summary Bar Chart */}
          {tools.length > 0 && (
            <div className="card p-5">
              <div className="flex items-center gap-2 mb-4">
                <List size={16} className="text-blue-400" />
                <h2 className="text-sm font-semibold text-white">Tool Usage Summary</h2>
                <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(59,130,246,0.1)", color: "#60a5fa" }}>24h</span>
              </div>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={tools.slice(0, 10)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="tool_name" tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, color: "#f8fafc" }} />
                  <Bar dataKey="total_calls" name="Total Calls" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
                {tools.slice(0, 6).map(t => (
                  <div key={t.tool_name} className="p-3 rounded-xl" style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
                    <p className="text-xs font-bold text-white truncate">{t.tool_name}</p>
                    <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>{t.agent_name}</p>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs text-blue-400">{t.total_calls} calls</span>
                      <span className="text-xs" style={{ color: t.success_rate > 0.9 ? "#10b981" : "#f59e0b" }}>
                        {(t.success_rate * 100).toFixed(0)}% ok
                      </span>
                    </div>
                    <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>avg {t.avg_duration_ms.toFixed(0)}ms</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Per-call Log Table */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Activity size={16} className="text-emerald-400" />
                <h2 className="text-sm font-semibold text-white">Tool Call Log</h2>
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{toolLogs?.total ?? 0} total</span>
              </div>
              <div className="flex gap-2">
                {[25, 50, 100].map(n => (
                  <button key={n} onClick={() => setLogLimit(n)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${logLimit === n ? "bg-emerald-500 text-white" : "text-slate-400"}`}
                    style={logLimit !== n ? { background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" } : {}}>
                    {n}
                  </button>
                ))}
              </div>
            </div>

            {logs.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-12">
                <InboxIcon size={28} style={{ color: "var(--color-text-muted)" }} />
                <p className="text-white font-medium">No tool logs yet</p>
              </div>
            ) : (
              <div className="space-y-1.5">
                {logs.map(log => (
                  <div key={log.id} className="flex items-start gap-3 p-3 rounded-xl hover:border-blue-500/20 transition-colors"
                    style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
                    <div className="flex-shrink-0 mt-0.5">
                      {log.status === "success" || log.status === "completed"
                        ? <CheckCircle2 size={14} className="text-emerald-400" />
                        : <XCircle size={14} className="text-rose-400" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-bold text-white">{log.tool_name}</span>
                        <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(59,130,246,0.1)", color: "#60a5fa" }}>{log.agent_name}</span>
                        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{log.duration_ms}ms</span>
                      </div>
                      {log.input_summary && (
                        <p className="text-xs mt-0.5 truncate" style={{ color: "var(--color-text-muted)" }}>→ {log.input_summary}</p>
                      )}
                      {log.error && (
                        <p className="text-xs mt-0.5 text-rose-400">{log.error}</p>
                      )}
                    </div>
                    <span className="text-xs flex-shrink-0" style={{ color: "var(--color-text-muted)" }}>
                      {new Date(log.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
