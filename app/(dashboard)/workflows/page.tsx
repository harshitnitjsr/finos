"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { RefreshCw, InboxIcon, CheckCircle, Clock, AlertCircle, XCircle, Loader2 } from "lucide-react";

import { apiFetch } from "@/lib/api";
const cv = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const iv = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };

interface WorkflowsResponse {
  workflows: Record<string, unknown>[];
  counts: Record<string, number>;
}

function useWorkflows() {
  return useQuery<WorkflowsResponse>({
    queryKey: ["workflows"],
    queryFn: () => apiFetch<WorkflowsResponse>("/workflows/?limit=50"),
    refetchInterval: 3000,
  });
}

interface WorkflowStep { id: number; name: string; status: string; }
interface WorkflowItem {
  id: string;
  name: string;
  status: string;
  workflow_type?: string;
  retry_count?: number;
  started_at?: string;
  error?: string;
  steps: WorkflowStep[];
}

const STATUS_CONFIG = {
  completed: { icon: CheckCircle, color: "#10b981", bg: "rgba(16,185,129,0.1)", badge: "badge-success" },
  running:   { icon: Loader2,     color: "#3b82f6", bg: "rgba(59,130,246,0.1)", badge: "badge-info" },
  pending:   { icon: Clock,       color: "#f59e0b", bg: "rgba(245,158,11,0.1)", badge: "badge-warning" },
  failed:    { icon: XCircle,     color: "#f43f5e", bg: "rgba(244,63,94,0.1)", badge: "badge-danger" },
  retrying:  { icon: RefreshCw,   color: "#8b5cf6", bg: "rgba(139,92,246,0.1)", badge: "badge-warning" },
};

export default function WorkflowsPage() {
  const { data, isLoading } = useWorkflows();
  const qc = useQueryClient();
  const workflows: WorkflowItem[] = (data?.workflows as WorkflowItem[] | undefined) || [];
  const counts: Record<string, number> = data?.counts || {};

  const retryMutation = useMutation({
    mutationFn: (id: string) => apiFetch(`/workflows/${id}/retry`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workflows"] }),
  });

  return (
    <motion.div variants={cv} initial="hidden" animate="show" className="space-y-5">
      <motion.div variants={iv} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Workflow Monitor</h1>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
            Live orchestration — auto-refreshes every 3s
          </p>
        </div>
        <div className="flex gap-2">
          {Object.entries(counts).map(([status, count]) => {
            const cfg = STATUS_CONFIG[status as keyof typeof STATUS_CONFIG];
            return (
              <div key={status} className="px-3 py-1.5 rounded-lg text-xs font-semibold" style={{ background: cfg?.bg || "var(--color-bg-elevated)", color: cfg?.color || "var(--color-text-secondary)", border: "1px solid var(--color-border)" }}>
                {count} {status}
              </div>
            );
          })}
        </div>
      </motion.div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card p-5 space-y-3">
              <div className="shimmer h-5 w-48 rounded" /><div className="shimmer h-2 w-full rounded-full" />
            </div>
          ))}
        </div>
      ) : workflows.length === 0 ? (
        <div className="card p-16 flex flex-col items-center gap-3">
          <InboxIcon size={36} style={{ color: "var(--color-text-muted)" }} />
          <p className="text-white font-semibold">No workflows running</p>
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Workflows start automatically when invoices are uploaded</p>
        </div>
      ) : (
        <div className="space-y-3">
          {workflows.map(wf => {
            const cfg = STATUS_CONFIG[wf.status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.pending;
            const StatusIcon = cfg.icon;
            const steps = wf.steps || [];
            const done = steps.filter(s => s.status === "completed").length;
            const progress = steps.length > 0 ? Math.round((done / steps.length) * 100) : 0;
            const isFailed = wf.status === "failed";

            return (
              <motion.div key={wf.id as string} layout className="card p-5">
                <div className="flex items-start justify-between gap-4 mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: cfg.bg, border: `1px solid ${cfg.color}30` }}>
                      <StatusIcon size={18} style={{ color: cfg.color }} className={wf.status === "running" ? "animate-spin" : undefined} />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-white">{wf.name}</p>
                      <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>
                        {wf.workflow_type} · retry #{wf.retry_count || 0}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`badge text-xs ${cfg.badge}`}>{wf.status}</span>
                    {isFailed && (
                      <button
                        onClick={() => retryMutation.mutate(wf.id as string)}
                        disabled={retryMutation.isPending}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-90"
                        style={{ background: "rgba(139,92,246,0.15)", color: "#8b5cf6", border: "1px solid rgba(139,92,246,0.3)" }}>
                        <RefreshCw size={11} /> Retry
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="mb-4">
                  <div className="flex justify-between mb-1.5">
                    <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{progress}% complete</span>
                    {wf.started_at && <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{new Date(wf.started_at).toLocaleTimeString()}</span>}
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill transition-all duration-500" style={{
                      width: `${progress}%`,
                      background: isFailed ? "var(--color-accent-rose)" : progress === 100 ? "var(--color-accent-emerald)" : "#3b82f6"
                    }} />
                  </div>
                </div>

                {/* Step Timeline */}
                {steps.length > 0 && (
                  <div className="flex items-center gap-2">
                    {steps.map((step, idx) => {
                      const sCfg = step.status === "completed" ? { bg: "#10b981", text: "text-emerald-400" } :
                        step.status === "running" ? { bg: "#3b82f6", text: "text-blue-400" } :
                          step.status === "failed" ? { bg: "#f43f5e", text: "text-rose-400" } :
                            { bg: "#475569", text: "text-slate-500" };
                      return (
                        <div key={step.id} className="flex items-center gap-2 flex-1">
                          <div className="flex flex-col items-center gap-1">
                            <div className="w-3 h-3 rounded-full" style={{ background: sCfg.bg }} />
                            <span className={`text-xs font-medium ${sCfg.text} whitespace-nowrap`}>{step.name}</span>
                          </div>
                          {idx < steps.length - 1 && (
                            <div className="h-px flex-1" style={{ background: step.status === "completed" ? "#10b981" : "var(--color-border)" }} />
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Error */}
                {wf.error && (
                  <div className="mt-3 p-3 rounded-xl" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)" }}>
                    <div className="flex items-center gap-2">
                      <AlertCircle size={12} className="text-rose-400" />
                      <span className="text-xs text-rose-400 font-medium">Error</span>
                    </div>
                    <p className="text-xs mt-1" style={{ color: "var(--color-text-secondary)" }}>{wf.error as string}</p>
                  </div>
                )}
              </motion.div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
}
