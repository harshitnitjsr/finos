"use client";
import { useRef, useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Activity, Sparkles } from "lucide-react";
import WorkspaceMessageBubble from "./MessageBubble";
import WorkspaceInput from "./WorkspaceInput";
import AgentThinkingOverlay from "./AgentThinkingOverlay";
import { useAgentThinking } from "./hooks/useAgentThinking";
import type { WorkspaceMessage, WorkspaceChat } from "./hooks/useWorkspace";

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

const SUGGESTED_PROMPTS = [
  { emoji: "🔥", text: "What's our burn rate this month?", label: "Burn Rate" },
  { emoji: "🚨", text: "Show me anomalous expenses", label: "Anomalies" },
  { emoji: "✅", text: "Any pending approvals right now?", label: "Approvals" },
  { emoji: "⚠️", text: "Which vendors are high risk?", label: "Risk" },
  { emoji: "🛫", text: "Calculate our cash runway", label: "Runway" },
  { emoji: "🎯", text: "Give me a financial health snapshot", label: "Dashboard" },
];

function LoadingSkeleton() {
  return (
    <div className="space-y-6 p-6">
      {[1, 0.7, 0.85].map((w, i) => (
        <div key={i} className={`flex gap-4 ${i % 2 === 0 ? "flex-row-reverse" : "flex-row"}`}>
          <div className="w-8 h-8 rounded-xl shimmer flex-shrink-0" />
          <div className="space-y-2 flex-1" style={{ maxWidth: `${w * 75}%` }}>
            <div className="h-4 rounded-lg shimmer" />
            <div className="h-4 rounded-lg shimmer" style={{ width: "80%" }} />
            <div className="h-4 rounded-lg shimmer" style={{ width: "60%" }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState({ onPrompt }: { onPrompt: (text: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full py-16 px-6">
      {/* Hero icon */}
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="relative mb-6"
      >
        <div
          className="w-20 h-20 rounded-3xl flex items-center justify-center"
          style={{
            background: "linear-gradient(135deg, rgba(59,130,246,0.15), rgba(139,92,246,0.15))",
            border: "1px solid rgba(59,130,246,0.2)",
            boxShadow: "0 0 60px rgba(59,130,246,0.08)",
          }}
        >
          <Activity size={32} className="text-blue-400" />
        </div>
        <motion.div
          className="absolute -top-1 -right-1 w-6 h-6 rounded-full flex items-center justify-center"
          style={{ background: "linear-gradient(135deg, #f59e0b, #f97316)" }}
          animate={{ scale: [1, 1.15, 1] }}
          transition={{ duration: 2, repeat: Infinity }}
        >
          <Sparkles size={11} className="text-white" />
        </motion.div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="text-center mb-8"
      >
        <h2 className="text-2xl font-bold mb-2" style={{ color: "var(--color-text-primary)" }}>
          AFOS AI Workspace
        </h2>
        <p className="text-sm leading-relaxed max-w-sm" style={{ color: "var(--color-text-muted)" }}>
          Your intelligent financial co-pilot. Ask anything about expenses, invoices, vendors, treasury, compliance, and more.
        </p>
      </motion.div>

      {/* Agent badges */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.2 }}
        className="flex flex-wrap gap-1.5 justify-center mb-8 max-w-md"
      >
        {Object.entries(AGENT_COLORS).map(([name, color]) => (
          <span
            key={name}
            className="text-xs px-2.5 py-1 rounded-lg font-medium"
            style={{
              background: `${color}14`,
              border: `1px solid ${color}28`,
              color,
            }}
          >
            {name}
          </span>
        ))}
      </motion.div>

      {/* Suggested prompts */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.3 }}
        className="w-full max-w-xl"
      >
        <p
          className="text-xs font-semibold uppercase tracking-wider text-center mb-3"
          style={{ color: "var(--color-text-muted)" }}
        >
          Suggested prompts
        </p>
        <div className="grid grid-cols-2 gap-2">
          {SUGGESTED_PROMPTS.map((p, i) => (
            <motion.button
              key={i}
              onClick={() => onPrompt(p.text)}
              whileHover={{ scale: 1.02, borderColor: "rgba(59,130,246,0.3)" }}
              whileTap={{ scale: 0.98 }}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.35 + i * 0.05 }}
              className="flex items-start gap-2.5 text-left p-3 rounded-xl transition-all"
              style={{
                background: "rgba(255,255,255,0.02)",
                border: "1px solid rgba(255,255,255,0.07)",
              }}
            >
              <span className="text-lg leading-none mt-0.5">{p.emoji}</span>
              <div>
                <p className="text-xs font-semibold mb-0.5" style={{ color: "var(--color-text-secondary)" }}>
                  {p.label}
                </p>
                <p className="text-xs leading-snug" style={{ color: "var(--color-text-muted)" }}>
                  {p.text}
                </p>
              </div>
            </motion.button>
          ))}
        </div>
      </motion.div>
    </div>
  );
}

interface WorkspaceChatViewProps {
  chat: WorkspaceChat | null;
  messages: WorkspaceMessage[];
  isLoadingMessages: boolean;
  isSending: boolean;
  activeRunId?: string | null;
  /** Zero-latency tool calls from SSE events */
  activeLiveTools?: { tool: string; args: Record<string, unknown>; turn: number }[];
  /** Agent name from SSE agent event */
  activeAgentName?: string | null;
  /** Intent from SSE agent event */
  activeIntent?: string | null;
  onSend: (text: string) => void;
  onStop?: () => void;
}

export default function WorkspaceChatView({
  chat,
  messages,
  isLoadingMessages,
  isSending,
  activeRunId = null,
  activeLiveTools = [],
  activeAgentName = null,
  activeIntent = null,
  onSend,
  onStop,
}: WorkspaceChatViewProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  // Poll Redis for current_tool marker (enriches live SSE data)
  const thinkingContext = useAgentThinking(activeRunId, isSending);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleCopy = useCallback((msgId: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(msgId);
    setTimeout(() => setCopiedId(null), 2000);
  }, []);

  const handleEdit = useCallback((content: string) => {
    setEditValue(content);
  }, []);

  const handleSendWithClear = useCallback((text: string) => {
    onSend(text);
    setEditValue("");
  }, [onSend]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      {chat && (
        <div
          className="flex-shrink-0 flex items-center gap-3 px-6 py-4"
          style={{ borderBottom: "1px solid var(--color-border)" }}
        >
          <div>
            <h1
              className="text-sm font-bold truncate max-w-md"
              style={{ color: "var(--color-text-primary)" }}
            >
              {chat.title}
            </h1>
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {chat.message_count > 0
                ? `${chat.message_count} messages · ${chat.model}`
                : `New conversation · ${chat.model}`}
            </p>
          </div>

          {/* Live indicator */}
          <div className="ml-auto flex items-center gap-1.5 px-2 py-1 rounded-lg"
            style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.18)" }}>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"
              style={{ boxShadow: "0 0 6px rgba(16,185,129,0.6)" }} />
            <span className="text-xs font-semibold text-emerald-400">Live</span>
          </div>
        </div>
      )}

      {/* Messages */}
      <div
        className="flex-1 overflow-y-auto"
        style={{ scrollbarWidth: "thin", scrollbarColor: "rgba(255,255,255,0.08) transparent" }}
      >
        {isLoadingMessages ? (
          <LoadingSkeleton />
        ) : messages.length === 0 ? (
          <EmptyState onPrompt={handleSendWithClear} />
        ) : (
          <div className="max-w-3xl mx-auto px-6 py-6 space-y-6">
            <AnimatePresence initial={false}>
              {messages.map((msg) => (
                <WorkspaceMessageBubble
                  key={msg.id}
                  msg={msg}
                  isCopied={copiedId === msg.id}
                  onCopy={(text) => handleCopy(msg.id, text)}
                  onEdit={msg.role === "user" ? handleEdit : undefined}
                  onRegenerate={msg.role === "assistant" ? undefined : undefined}
                  // Pass overlay only for the streaming assistant bubble
                  thinkingOverlay={
                    msg.isStreaming ? (
                      <AgentThinkingOverlay
                        context={thinkingContext}
                        isStreaming={!!msg.isStreaming}
                        hasContent={msg.content.length > 0}
                        liveTools={activeLiveTools}
                        liveAgentName={activeAgentName}
                        liveIntent={activeIntent}
                      />
                    ) : null
                  }
                />
              ))}
            </AnimatePresence>
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="max-w-3xl w-full mx-auto" style={{ paddingBottom: 0 }}>
        <WorkspaceInput
          onSend={handleSendWithClear}
          isSending={isSending}
          onStop={onStop}
          disabled={false}
          initialValue={editValue}
          onClear={() => setEditValue("")}
        />
      </div>
    </div>
  );
}
