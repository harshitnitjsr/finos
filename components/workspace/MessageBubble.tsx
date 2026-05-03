"use client";
import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Bot, User, Copy, Check, RefreshCw, Edit2,
  ChevronDown, ChevronRight, Wrench, CheckCircle2,
  Zap, Clock, Database
} from "lucide-react";
import MarkdownRenderer from "./MarkdownRenderer";
import type { WorkspaceMessage } from "./hooks/useWorkspace";

const AGENT_COLORS: Record<string, string> = {
  "Expense Intelligence": "#10b981",
  "Invoice Intelligence": "#3b82f6",
  "Compliance Agent":     "#f43f5e",
  "Insight Agent":        "#8b5cf6",
  "Treasury Agent":       "#f59e0b",
  "Vendor Intelligence":  "#06b6d4",
  "Approval Agent":       "#ec4899",
  "Forecasting Agent":    "#6366f1",
};

const SOURCE_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  redis:      { label: "Redis",  color: "#f59e0b", bg: "rgba(245,158,11,0.08)" },
  postgresql: { label: "SQL",    color: "#10b981", bg: "rgba(16,185,129,0.08)" },
  qdrant:     { label: "Qdrant", color: "#8b5cf6", bg: "rgba(139,92,246,0.08)" },
};

const TOOL_ICONS: Record<string, string> = {
  query_expenses: "💳", get_anomalous_expenses: "🚨",
  get_category_spend_summary: "📊", get_recurring_subscriptions: "🔄",
  query_invoices: "📄", get_overdue_invoices: "⏰",
  get_invoice_pipeline_summary: "🔀", get_vendor_invoice_history: "🏪",
  get_burn_rate: "🔥", get_upcoming_payments: "💰",
  get_monthly_spend_trend: "📈", calculate_runway: "🛫",
  query_vendors: "🏢", search_vendor: "🔍",
  get_high_risk_vendors: "⚠️", get_vendor_spend_distribution: "📉",
  get_pending_approvals: "✅", evaluate_policy_rules: "📋",
  get_high_risk_items: "🛡️", get_historical_spend_data: "📅",
  analyze_category_trend: "📐", get_financial_dashboard_snapshot: "🎯",
  get_agent_activity_logs: "🤖",
};

function ToolCallsSection({ toolCalls }: { toolCalls: WorkspaceMessage["tool_calls"] }) {
  const [expanded, setExpanded] = useState(false);
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="flex items-center gap-1.5 text-xs transition-colors hover:opacity-80"
        style={{ color: "var(--color-text-muted)" }}
      >
        {expanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        <Wrench size={10} />
        <span>{toolCalls.length} tool{toolCalls.length !== 1 ? "s" : ""} used</span>
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-2 space-y-1.5 overflow-hidden"
          >
            {toolCalls.map((tc, i) => (
              <div
                key={i}
                className="flex items-start gap-2 px-3 py-2 rounded-lg"
                style={{ background: "rgba(59,130,246,0.04)", border: "1px solid rgba(59,130,246,0.1)" }}
              >
                <span className="text-sm flex-shrink-0 mt-0.5">{TOOL_ICONS[tc.tool] ?? "🔧"}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-mono font-semibold text-blue-300">{tc.tool}</span>
                    <CheckCircle2 size={9} className="text-emerald-400 flex-shrink-0" />
                  </div>
                  {Object.keys(tc.args || {}).length > 0 && (
                    <div className="mt-0.5 text-xs font-mono" style={{ color: "var(--color-text-muted)" }}>
                      {Object.entries(tc.args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

interface MessageBubbleProps {
  msg: WorkspaceMessage;
  onCopy: (text: string) => void;
  onEdit?: (content: string) => void;
  onRegenerate?: () => void;
  isCopied: boolean;
  /** Optional live thinking overlay (only passed for streaming assistant messages) */
  thinkingOverlay?: React.ReactNode | null;
}

export default function WorkspaceMessageBubble({
  msg, onCopy, onEdit, onRegenerate, isCopied, thinkingOverlay,
}: MessageBubbleProps) {
  const isUser = msg.role === "user";
  const agentColor = msg.agent_name ? (AGENT_COLORS[msg.agent_name] ?? "#8b5cf6") : "#10b981";
  const [hovered, setHovered] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={`group flex gap-4 ${isUser ? "flex-row-reverse" : "flex-row"}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Avatar */}
      <div
        className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-1"
        style={{
          background: isUser
            ? "linear-gradient(135deg, #2563eb, #1d4ed8)"
            : `rgba(139,92,246,0.12)`,
          border: !isUser ? "1px solid rgba(139,92,246,0.25)" : "none",
          boxShadow: isUser ? "0 2px 12px rgba(37,99,235,0.3)" : "none",
        }}
      >
        {isUser
          ? <User size={14} className="text-white" />
          : <Bot size={14} style={{ color: agentColor }} />
        }
      </div>

      {/* Content */}
      <div className={`flex-1 max-w-[82%] space-y-2 flex flex-col ${isUser ? "items-end" : "items-start"}`}>
        {/* Agent badge */}
        {!isUser && msg.agent_name && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold" style={{ color: agentColor }}>
              {msg.agent_name}
            </span>
            {msg.intent && (
              <span
                className="text-xs px-2 py-0.5 rounded-md"
                style={{ background: "rgba(255,255,255,0.04)", color: "var(--color-text-muted)" }}
              >
                {msg.intent.replace(/_/g, " ")}
              </span>
            )}
          </div>
        )}

        {/* Bubble */}
        <div
          className="rounded-2xl leading-relaxed"
          style={{
            background: isUser
              ? "linear-gradient(135deg, #2563eb, #1d4ed8)"
              : "rgba(255,255,255,0.03)",
            border: !isUser ? "1px solid rgba(255,255,255,0.07)" : "none",
            borderRadius: isUser ? "20px 20px 6px 20px" : "20px 20px 20px 6px",
            padding: "12px 16px",
            boxShadow: isUser ? "0 4px 20px rgba(37,99,235,0.2)" : "none",
          }}
        >
          {/* Streaming state — overlay takes over from plain dots */}
          {msg.isStreaming ? (
            <div>
              {thinkingOverlay}
              {/* Show growing text once tokens start */}
              {msg.content.length > 0 && (
                <MarkdownRenderer content={msg.content} />
              )}
              {/* Fallback pulsing dots if no overlay and no content yet */}
              {!thinkingOverlay && msg.content.length === 0 && (
                <div className="flex items-center gap-1.5 py-1">
                  {[0, 1, 2].map((i) => (
                    <motion.span
                      key={i}
                      className="w-2 h-2 rounded-full bg-violet-400"
                      animate={{ opacity: [0.3, 1, 0.3], y: [0, -4, 0] }}
                      transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
                    />
                  ))}
                </div>
              )}
            </div>
          ) : isUser ? (
            <p className="text-sm leading-relaxed text-white" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
              {msg.content}
            </p>
          ) : (
            <MarkdownRenderer content={msg.content} />
          )}
        </div>

        {/* Tool calls */}
        {!isUser && msg.tool_calls && msg.tool_calls.length > 0 && (
          <ToolCallsSection toolCalls={msg.tool_calls} />
        )}

        {/* Memory sources */}
        {!isUser && msg.memory_used && msg.memory_sources && msg.memory_sources.length > 0 && (
          <div className="flex items-center gap-1 flex-wrap">
            <Database size={10} style={{ color: "var(--color-text-muted)" }} />
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>memory:</span>
            {msg.memory_sources.map((s) => {
              const cfg = SOURCE_CONFIG[s];
              if (!cfg) return null;
              return (
                <span
                  key={s}
                  className="text-xs px-1.5 py-0.5 rounded font-mono font-medium"
                  style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.color}28` }}
                >
                  {cfg.label}
                </span>
              );
            })}
          </div>
        )}

        {/* Metrics */}
        {!isUser && (msg.tokens_used || msg.duration_ms) && (
          <div className="flex items-center gap-4">
            {msg.tokens_used ? (
              <span className="flex items-center gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
                <Zap size={9} className="text-amber-400" />{msg.tokens_used} tokens
              </span>
            ) : null}
            {msg.duration_ms ? (
              <span className="flex items-center gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
                <Clock size={9} />{msg.duration_ms}ms
              </span>
            ) : null}
          </div>
        )}

        {/* Action toolbar (shows on hover) */}
        <AnimatePresence>
          {hovered && !msg.isStreaming && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15 }}
              className="flex items-center gap-1"
            >
              {/* Copy */}
              <button
                onClick={() => onCopy(msg.content)}
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs transition-all"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.07)",
                  color: "var(--color-text-muted)",
                }}
                title="Copy message"
              >
                {isCopied ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                {isCopied ? "Copied" : "Copy"}
              </button>

              {/* Edit (user only) */}
              {isUser && onEdit && (
                <button
                  onClick={() => onEdit(msg.content)}
                  className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs transition-all"
                  style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.07)",
                    color: "var(--color-text-muted)",
                  }}
                  title="Edit & resend"
                >
                  <Edit2 size={11} /> Edit
                </button>
              )}

              {/* Regenerate (assistant only) */}
              {!isUser && onRegenerate && (
                <button
                  onClick={onRegenerate}
                  className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs transition-all"
                  style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.07)",
                    color: "var(--color-text-muted)",
                  }}
                  title="Regenerate response"
                >
                  <RefreshCw size={11} /> Regenerate
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
