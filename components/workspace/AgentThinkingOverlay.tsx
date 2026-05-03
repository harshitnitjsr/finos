"use client";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, Wrench, Brain, ChevronRight, CheckCircle2 } from "lucide-react";
import type { ReasoningContext, ToolCallRecord } from "./hooks/useAgentThinking";

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

const INTENT_LABELS: Record<string, string> = {
  expense_query:    "Analyzing expenses",
  invoice_query:    "Checking invoices",
  compliance_check: "Running compliance check",
  vendor_query:     "Looking up vendors",
  treasury_query:   "Checking treasury",
  approval_query:   "Reviewing approvals",
  general_finance:  "Processing request",
  forecasting:      "Generating forecast",
};

interface LiveTool { tool: string; args?: Record<string, unknown>; turn?: number; }

interface AgentThinkingOverlayProps {
  context: ReasoningContext | null;
  isStreaming: boolean;
  hasContent: boolean;
  /** Zero-latency SSE-sourced tool list — shown immediately when tool_call fires */
  liveTools?: LiveTool[];
  /** Zero-latency SSE-sourced agent name */
  liveAgentName?: string | null;
  /** Zero-latency SSE-sourced intent */
  liveIntent?: string | null;
}

export default function AgentThinkingOverlay({
  context,
  isStreaming,
  hasContent,
  liveTools = [],
  liveAgentName = null,
  liveIntent = null,
}: AgentThinkingOverlayProps) {
  if (!isStreaming) return null;

  // Merge: SSE data is primary (zero latency); Redis context enriches with current_tool
  const agentName  = liveAgentName  ?? context?.agent_name  ?? null;
  const intent     = liveIntent     ?? context?.intent      ?? null;

  // Tool list: use SSE live tools immediately — Redis context used only for current_tool marker
  const toolCalls: ToolCallRecord[] = liveTools.length > 0
    ? liveTools
    : (context?.tool_calls ?? []);

  const currentTool = context?.current_tool;   // from Redis — marks which is running
  const turn        = context?.current_turn ?? (liveTools.length > 0 ? liveTools[liveTools.length - 1]?.turn ?? 0 : 0);

  const agentColor  = (agentName && AGENT_COLORS[agentName]) || "#8b5cf6";
  const intentLabel = (intent && INTENT_LABELS[intent]) || "Processing…";

  // ── Slim bar shown above streaming text ────────────────────────────────────
  if (hasContent) {
    return (
      <AnimatePresence>
        {/* Always show slim bar while streaming — even before tools arrive */}
        <motion.div
          key="slim-bar"
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          className="mb-3 overflow-hidden"
        >
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs"
            style={{
              background: `${agentColor}0d`,
              border: `1px solid ${agentColor}25`,
            }}
          >
            <motion.div
              className="w-1.5 h-1.5 rounded-full flex-shrink-0"
              style={{ background: agentColor }}
              animate={{ opacity: [1, 0.4, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <span style={{ color: agentColor }} className="font-semibold flex-shrink-0">
              {agentName || "AI Agent"}
            </span>
            {toolCalls.length > 0 && (
              <>
                <ChevronRight size={10} style={{ color: agentColor, opacity: 0.6 }} />
                <span className="text-slate-400 truncate">
                  {toolCalls.map(tc => tc.tool).join(" → ")}
                </span>
              </>
            )}
            {toolCalls.length === 0 && intent && (
              <>
                <span className="text-slate-600">·</span>
                <span className="text-slate-400">{intentLabel}</span>
              </>
            )}
          </div>
        </motion.div>
      </AnimatePresence>
    );
  }

  // ── Full panel shown before tokens appear ──────────────────────────────────
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
      className="py-2"
    >
      {/* Agent identity row */}
      <div className="flex items-center gap-2 mb-3">
        <div
          className="w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: `${agentColor}18`, border: `1px solid ${agentColor}30` }}
        >
          <Brain size={12} style={{ color: agentColor }} />
        </div>
        <span className="text-xs font-bold" style={{ color: agentColor }}>
          {agentName || "AI Agent"}
        </span>
        {intent && (
          <>
            <span className="text-slate-600">·</span>
            <span className="text-xs text-slate-400">{intentLabel}</span>
          </>
        )}
        <div className="ml-auto flex items-center gap-1.5">
          <Loader2 size={11} className="animate-spin text-slate-500" />
          {turn > 0 && <span className="text-xs text-slate-500">turn {turn}/6</span>}
        </div>
      </div>

      {/* Tool call timeline — populated from SSE events immediately */}
      {toolCalls.length > 0 ? (
        <div className="space-y-1.5 mb-3 ml-1">
          {toolCalls.map((tc, i) => {
            const isLast = i === toolCalls.length - 1;
            // A tool is "running" if it's last AND either Redis says so OR no done signal yet
            const isCurrent = isLast && (currentTool === tc.tool || !currentTool);
            return (
              <motion.div
                key={`${tc.tool}-${i}`}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className="flex items-center gap-2"
              >
                <div className="flex-shrink-0">
                  {isCurrent ? (
                    <motion.div
                      className="w-4 h-4 rounded flex items-center justify-center"
                      style={{ background: `${agentColor}20`, border: `1px solid ${agentColor}40` }}
                      animate={{ opacity: [1, 0.5, 1] }}
                      transition={{ duration: 1, repeat: Infinity }}
                    >
                      <Wrench size={9} style={{ color: agentColor }} />
                    </motion.div>
                  ) : (
                    <div className="w-4 h-4 rounded flex items-center justify-center" style={{ background: "rgba(71,85,105,0.25)" }}>
                      <CheckCircle2 size={9} className="text-emerald-400" />
                    </div>
                  )}
                </div>
                <span className="text-xs font-mono" style={{ color: isCurrent ? agentColor : "#64748b" }}>
                  {tc.tool}
                </span>
                {isCurrent && (
                  <motion.span
                    className="text-xs text-slate-500"
                    animate={{ opacity: [1, 0, 1] }}
                    transition={{ duration: 1, repeat: Infinity }}
                  >
                    running…
                  </motion.span>
                )}
              </motion.div>
            );
          })}
        </div>
      ) : (
        /* Pulsing dots while waiting for first tool_call SSE event */
        <div className="flex items-center gap-1.5 ml-1">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: agentColor }}
              animate={{ scale: [1, 1.4, 1], opacity: [0.4, 1, 0.4] }}
              transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
            />
          ))}
          <span className="text-xs text-slate-500 ml-1">
            {agentName ? intentLabel : "Routing to agent…"}
          </span>
        </div>
      )}
    </motion.div>
  );
}
