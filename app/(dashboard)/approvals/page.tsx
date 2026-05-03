"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { CheckCircle, XCircle, Clock, AlertTriangle, InboxIcon, ChevronDown, ChevronUp } from "lucide-react";
import PageContextHelp from "@/components/global/PageContextHelp";

import { apiFetch } from "@/lib/api";
const cv = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } };
const iv = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.3 } } };
const CURRENCY_SYMBOLS: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£", JPY: "¥" };

interface ApprovalsResponse {
  approvals: Record<string, unknown>[];
  total: number;
  counts: Record<string, number>;
}

function useApprovals(status?: string) {
  return useQuery<ApprovalsResponse>({
    queryKey: ["approvals", status],
    queryFn: () => {
      const params = new URLSearchParams({ limit: "50" });
      if (status) params.set("status", status);
      return apiFetch<ApprovalsResponse>(`/approvals/?${params}`);
    },
    refetchInterval: 10000,
  });
}

export default function ApprovalsPage() {
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined);
  const [expanded, setExpanded] = useState<string | null>(null);
  const qc = useQueryClient();

  const { data, isLoading } = useApprovals(filterStatus);
  const approvals: Record<string, unknown>[] = data?.approvals || [];

  const actionMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" }) =>
      apiFetch(`/approvals/${id}/${action}`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approvals"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const STATUSES = [undefined, "pending", "approved", "rejected", "escalated"];
  const STATUS_LABELS: Record<string, string> = { pending: "Pending", approved: "Approved", rejected: "Rejected", escalated: "Escalated" };

  const counts = data?.counts || {};

  return (
    <motion.div variants={cv} initial="hidden" animate="show" className="space-y-5">
      <motion.div variants={iv} className="flex items-center justify-between">
        <div>
          <div className="flex items-center">
            <h1 className="text-2xl font-bold text-white">Approval Center</h1>
            <PageContextHelp
              pageName="Approval Center"
              why="Not all actions can be fully autonomous. Certain high-risk or high-value transactions require human oversight before funds are dispersed."
              what="This page acts as a centralized inbox for all tasks that the AI assistants have escalated to humans. You get full context on why the AI escalated the task, including risk scores and policy checks."
              how="Review the 'AI Analysis' box for each pending item. If the AI flagged a policy violation, evaluate whether to approve or reject the payment. Your action here signals the automated system to resume."
            />
          </div>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
            {counts.pending ?? "—"} pending · {counts.approved ?? "—"} approved · {counts.rejected ?? "—"} rejected
          </p>
        </div>
      </motion.div>

      {/* Status Filters */}
      <motion.div variants={iv} className="flex gap-2 overflow-x-auto pb-1">
        {STATUSES.map(s => (
          <button key={s ?? "all"} onClick={() => setFilterStatus(s)}
            className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${filterStatus === s ? "bg-blue-500 text-white" : "text-slate-400 hover:text-white"}`}
            style={filterStatus !== s ? { background: "var(--color-bg-card)", border: "1px solid var(--color-border)" } : {}}>
            {s == null ? `All (${data?.total ?? "—"})` : `${STATUS_LABELS[s] || s} (${counts[s] ?? 0})`}
          </button>
        ))}
      </motion.div>

      {/* Approvals List */}
      <div className="space-y-3">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card p-4 space-y-2">
              <div className="shimmer h-4 w-40 rounded" /><div className="shimmer h-3 w-64 rounded" />
            </div>
          ))
        ) : approvals.length === 0 ? (
          <div className="card p-16 flex flex-col items-center gap-3">
            <InboxIcon size={36} style={{ color: "var(--color-text-muted)" }} />
            <p className="text-white font-semibold">No approvals found</p>
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {filterStatus === "pending" ? "All caught up — no pending approvals!" : "No items in this status"}
            </p>
          </div>
        ) : (
          approvals.map(appr => {
            const isExpanded = expanded === appr.id;
            const isPending = appr.status === "pending";
            return (
              <motion.div key={appr.id as string} layout className="card overflow-hidden">
                <div className="p-5 cursor-pointer" onClick={() => setExpanded(isExpanded ? null : appr.id as string)}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${appr.risk_level === "high" || appr.risk_level === "critical" ? "bg-rose-500/10" : appr.risk_level === "medium" ? "bg-amber-500/10" : "bg-emerald-500/10"}`}>
                        {appr.risk_level === "high" || appr.risk_level === "critical" ? <AlertTriangle size={16} className="text-rose-400" /> :
                          appr.status === "approved" ? <CheckCircle size={16} className="text-emerald-400" /> :
                            appr.status === "rejected" ? <XCircle size={16} className="text-rose-400" /> :
                              <Clock size={16} className="text-amber-400" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold text-white">
                            Invoice #{(appr.invoice_id as string)?.slice(0, 8) || "—"}
                          </p>
                          <span className={`badge text-xs ${appr.status === "approved" ? "badge-success" : appr.status === "rejected" ? "badge-danger" : appr.status === "escalated" ? "badge-warning" : "badge-neutral"}`}>
                            {appr.status as string}
                          </span>
                        </div>
                        <p className="text-xs mt-1 truncate" style={{ color: "var(--color-text-muted)" }}>
                          AI: {appr.ai_recommendation as string} — {(appr.ai_explanation as string)?.slice(0, 80)}…
                        </p>
                        <div className="flex items-center gap-3 mt-1.5">
                          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                            Assigned: {appr.assigned_to as string || "Unassigned"}
                          </span>
                          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                            Risk score: {(appr.risk_score as number)?.toFixed(0)}/100
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0 flex items-center gap-3">
                      <div>
                        <p className="text-lg font-bold text-white">
                          {CURRENCY_SYMBOLS[appr.currency as string] || "$"}{(appr.amount as number)?.toLocaleString()}
                        </p>
                        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{appr.currency as string}</p>
                      </div>
                      {isExpanded ? <ChevronUp size={16} style={{ color: "var(--color-text-muted)" }} /> : <ChevronDown size={16} style={{ color: "var(--color-text-muted)" }} />}
                    </div>
                  </div>
                </div>

                {/* Expanded Detail */}
                {isExpanded && (
                  <div className="px-5 pb-5 border-t" style={{ borderColor: "var(--color-border)" }}>
                    <div className="pt-4 space-y-3">
                      {!!(appr.ai_explanation as string) && (
                        <div className="p-3 rounded-xl" style={{ background: "rgba(59,130,246,0.08)", border: "1px solid rgba(59,130,246,0.15)" }}>
                          <p className="text-xs font-semibold text-blue-400 mb-1">AI Analysis</p>
                          <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{appr.ai_explanation as string}</p>
                        </div>
                      )}
                      {((appr.policy_checks as { policy: string; passed: boolean }[])?.length ?? 0) > 0 && (
                        <div>
                          <p className="text-xs font-semibold text-white mb-2">Policy Checks</p>
                          {(appr.policy_checks as { policy: string; passed: boolean }[]).map((pc, i) => (
                            <div key={i} className="flex items-center gap-2 text-xs">
                              {pc.passed ? <CheckCircle size={12} className="text-emerald-400" /> : <XCircle size={12} className="text-rose-400" />}
                              <span style={{ color: "var(--color-text-secondary)" }}>{pc.policy}</span>
                              <span className={pc.passed ? "text-emerald-400" : "text-rose-400"}>{pc.passed ? "Pass" : "Fail"}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {isPending && (
                        <div className="flex gap-3 pt-2">
                          <button
                            onClick={() => actionMutation.mutate({ id: appr.id as string, action: "approve" })}
                            disabled={actionMutation.isPending}
                            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-50"
                            style={{ background: "rgba(16,185,129,0.15)", color: "#10b981", border: "1px solid rgba(16,185,129,0.3)" }}>
                            {actionMutation.isPending && actionMutation.variables?.id === appr.id && actionMutation.variables?.action === "approve" ? (
                              <><span className="w-3 h-3 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin"></span> Processing...</>
                            ) : (
                              <><CheckCircle size={14} /> Approve</>
                            )}
                          </button>
                          <button
                            onClick={() => actionMutation.mutate({ id: appr.id as string, action: "reject" })}
                            disabled={actionMutation.isPending}
                            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-50"
                            style={{ background: "rgba(244,63,94,0.1)", color: "#f43f5e", border: "1px solid rgba(244,63,94,0.2)" }}>
                            {actionMutation.isPending && actionMutation.variables?.id === appr.id && actionMutation.variables?.action === "reject" ? (
                              <><span className="w-3 h-3 border-2 border-rose-400 border-t-transparent rounded-full animate-spin"></span> Processing...</>
                            ) : (
                              <><XCircle size={14} /> Reject</>
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </motion.div>
            );
          })
        )}
      </div>
    </motion.div>
  );
}
