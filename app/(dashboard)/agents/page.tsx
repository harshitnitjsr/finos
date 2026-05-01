"use client";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Bot, Activity, Cpu, Zap, InboxIcon, Clock } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
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
const MODEL_LABELS: Record<string, string> = {
  "gpt-4o":      "GPT-4o",
  "gpt-4o-mini": "GPT-4o Mini",
};

function useAgents() {
  return useQuery({
    queryKey: ["agents-status"],
    queryFn: async () => {
      const r = await fetch(`${API}/api/v1/agents/status`);
      if (!r.ok) throw new Error("Failed");
      return r.json();
    },
    refetchInterval: 15000,
  });
}

export default function AgentsPage() {
  const { data, isLoading } = useAgents();
  const agents: Record<string, unknown>[] = data?.agents || [];

  return (
    <motion.div variants={cv} initial="hidden" animate="show" className="space-y-6">
      <motion.div variants={iv} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">AI Agents</h1>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
            {data ? `${data.active}/${data.total} agents active` : "Loading agent registry…"}
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl" style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.2)" }}>
          <div className="w-2 h-2 rounded-full bg-emerald-400 pulse-emerald" />
          <span className="text-xs font-semibold text-emerald-400">Model Router Active</span>
        </div>
      </motion.div>

      {/* Model Router Status */}
      <motion.div variants={iv} className="card p-5" style={{ borderColor: "rgba(139,92,246,0.2)" }}>
        <div className="flex items-center gap-3 mb-4">
          <Cpu size={18} className="text-violet-400" />
          <h2 className="text-base font-semibold text-white">Model Router Configuration</h2>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {[
            { task: "Reasoning & Insights", model: "GPT-4o", color: "#8b5cf6" },
            { task: "OCR Extraction", model: "GPT-4o Mini", color: "#3b82f6" },
            { task: "Classification", model: "GPT-4o Mini", color: "#10b981" },
            { task: "Compliance Checks", model: "GPT-4o", color: "#f43f5e" },
            { task: "Financial Forecasting", model: "GPT-4o", color: "#f59e0b" },
            { task: "Vector Embeddings", model: "text-embedding-3-small", color: "#06b6d4" },
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
                        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                          {isActive ? "Active" : "Idle"}
                        </span>
                      </div>
                    </div>
                  </div>
                  <span className="text-xs px-2 py-1 rounded-lg font-medium" style={{ background: tc.bg, color: tc.color }}>
                    {agent.task as string}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="p-2 rounded-lg" style={{ background: "var(--color-bg-elevated)" }}>
                    <div className="flex items-center gap-1 mb-1">
                      <Activity size={10} style={{ color: "var(--color-text-muted)" }} />
                      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>24h calls</span>
                    </div>
                    <p className="text-sm font-bold text-white">{(agent.requests_24h as number) ?? "—"}</p>
                  </div>
                  <div className="p-2 rounded-lg" style={{ background: "var(--color-bg-elevated)" }}>
                    <div className="flex items-center gap-1 mb-1">
                      <Clock size={10} style={{ color: "var(--color-text-muted)" }} />
                      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Avg latency</span>
                    </div>
                    <p className="text-sm font-bold text-white">
                      {(agent.avg_latency_ms as number) ? `${agent.avg_latency_ms}ms` : "—"}
                    </p>
                  </div>
                  <div className="p-2 rounded-lg" style={{ background: "var(--color-bg-elevated)" }}>
                    <div className="flex items-center gap-1 mb-1">
                      <Zap size={10} style={{ color: "var(--color-text-muted)" }} />
                      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Tokens</span>
                    </div>
                    <p className="text-sm font-bold text-white">
                      {(agent.tokens_24h as number) ? `${((agent.tokens_24h as number) / 1000).toFixed(0)}K` : "—"}
                    </p>
                  </div>
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
    </motion.div>
  );
}
