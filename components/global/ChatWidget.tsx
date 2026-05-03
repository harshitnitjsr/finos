"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare, X, Send, Bot, User, Trash2, Square,
  Zap, ChevronDown, ChevronRight, Activity, Wrench, CheckCircle2,
  Clock, Database
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  turn: number;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  agent?: string;
  agent_id?: string;
  intent?: string;
  tool_calls?: ToolCall[];
  total_tokens?: number;
  duration_ms?: number;
  timestamp?: string;
  memory_used?: boolean;
  sources?: string[];
  _streamingId?: string;  // internal: tracks the in-flight streaming bubble
}

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

const TOOL_ICONS: Record<string, string> = {
  query_expenses:               "💳",
  get_anomalous_expenses:       "🚨",
  get_category_spend_summary:   "📊",
  get_recurring_subscriptions:  "🔄",
  query_invoices:               "📄",
  get_overdue_invoices:         "⏰",
  get_invoice_pipeline_summary: "🔀",
  get_vendor_invoice_history:   "🏪",
  get_burn_rate:                "🔥",
  get_upcoming_payments:        "💰",
  get_monthly_spend_trend:      "📈",
  calculate_runway:             "🛫",
  query_vendors:                "🏢",
  search_vendor:                "🔍",
  get_high_risk_vendors:        "⚠️",
  get_vendor_spend_distribution:"📉",
  get_pending_approvals:        "✅",
  evaluate_policy_rules:        "📋",
  get_high_risk_items:          "🛡️",
  get_historical_spend_data:    "📅",
  analyze_category_trend:       "📐",
  get_financial_dashboard_snapshot: "🎯",
  get_agent_activity_logs:      "🤖",
};

const SUGGESTED_QUERIES = [
  "What's our burn rate this month?",
  "Show me anomalous expenses",
  "Any pending approvals?",
  "Which vendors are high risk?",
  "What's our cash runway?",
  "Summarize our financial health",
];

// ── Sub-components ────────────────────────────────────────────────────────────

function TypingDots() {
  return (
    <div className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="w-2 h-2 rounded-full bg-blue-400"
          animate={{ opacity: [0.3, 1, 0.3], y: [0, -4, 0] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
        />
      ))}
    </div>
  );
}

function ToolCallsSection({ toolCalls }: { toolCalls: ToolCall[] }) {
  const [expanded, setExpanded] = useState(false);
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="flex items-center gap-1.5 text-xs transition-colors"
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
                className="flex items-start gap-2 px-2.5 py-2 rounded-lg"
                style={{
                  background: "rgba(59,130,246,0.04)",
                  border: "1px solid rgba(59,130,246,0.1)",
                }}
              >
                <span className="text-sm flex-shrink-0 mt-0.5">
                  {TOOL_ICONS[tc.tool] || "🔧"}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-mono font-semibold text-blue-300">
                      {tc.tool}
                    </span>
                    <CheckCircle2 size={9} className="text-emerald-400 flex-shrink-0" />
                  </div>
                  {Object.keys(tc.args || {}).length > 0 && (
                    <div className="mt-0.5 text-xs font-mono" style={{ color: "var(--color-text-muted)" }}>
                      {Object.entries(tc.args)
                        .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
                        .join(", ")}
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

const SOURCE_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  redis:      { label: "Redis",      color: "#f59e0b", bg: "rgba(245,158,11,0.08)" },
  postgresql: { label: "SQL",        color: "#10b981", bg: "rgba(16,185,129,0.08)" },
  qdrant:     { label: "Qdrant",     color: "#8b5cf6", bg: "rgba(139,92,246,0.08)" },
};

function MemoryBadge({ sources }: { sources: string[] }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="flex items-center gap-1 mt-1 flex-wrap">
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>memory:</span>
      {sources.map((s) => {
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
  );
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  const agentColor = msg.agent ? (AGENT_COLORS[msg.agent] || "#8b5cf6") : "#10b981";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`flex gap-2.5 ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      {/* Avatar */}
      <div
        className="w-7 h-7 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5"
        style={{
          background: isUser
            ? "linear-gradient(135deg, #2563eb, #1d4ed8)"
            : `rgba(${isUser ? "59,130,246" : "139,92,246"},0.12)`,
          border: !isUser ? `1px solid rgba(139,92,246,0.25)` : "none",
        }}
      >
        {isUser
          ? <User size={13} className="text-white" />
          : <Bot size={13} style={{ color: agentColor }} />
        }
      </div>

      {/* Content */}
      <div className={`max-w-[82%] space-y-1 flex flex-col ${isUser ? "items-end" : "items-start"}`}>

        {/* Agent badge */}
        {!isUser && msg.agent && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs font-semibold" style={{ color: agentColor }}>
              {msg.agent}
            </span>
            {msg.intent && (
              <span
                className="text-xs px-1.5 py-0.5 rounded-md"
                style={{ background: "rgba(255,255,255,0.04)", color: "var(--color-text-muted)" }}
              >
                {msg.intent.replace(/_/g, " ")}
              </span>
            )}
          </div>
        )}

        {/* Bubble */}
        <div
          className="px-3.5 py-2.5 rounded-2xl text-xs leading-relaxed"
          style={{
            background: isUser
              ? "linear-gradient(135deg, #2563eb, #1d4ed8)"
              : "rgba(255,255,255,0.04)",
            border: !isUser ? "1px solid rgba(255,255,255,0.06)" : "none",
            color: isUser ? "#fff" : "var(--color-text-secondary)",
            borderRadius: isUser ? "18px 18px 6px 18px" : "18px 18px 18px 6px",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {msg.content}
        </div>

        {/* Tool calls */}
        {!isUser && msg.tool_calls && msg.tool_calls.length > 0 && (
          <ToolCallsSection toolCalls={msg.tool_calls} />
        )}

        {/* Memory sources */}
        {!isUser && msg.memory_used && msg.sources && msg.sources.length > 0 && (
          <MemoryBadge sources={msg.sources} />
        )}

        {/* Metrics */}
        {!isUser && (msg.total_tokens || msg.duration_ms) && (
          <div className="flex items-center gap-3 px-0.5">
            {msg.total_tokens ? (
              <span className="flex items-center gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
                <Zap size={8} className="text-amber-400" />{msg.total_tokens} tokens
              </span>
            ) : null}
            {msg.duration_ms ? (
              <span className="flex items-center gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
                <Clock size={8} />{msg.duration_ms}ms
              </span>
            ) : null}
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => `s_${Date.now()}`);
  const [unread, setUnread] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (open) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      setUnread(0);
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [open, messages]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;

    const userMsg: Message = {
      role: "user",
      content: text.trim(),
      timestamp: new Date().toISOString(),
    };

    // Optimistic assistant bubble (streaming)
    const streamingId = `stream_${Date.now()}`;
    const streamingMsg: Message = {
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
      _streamingId: streamingId,
    };

    setMessages((p) => [...p, userMsg, streamingMsg]);
    setInput("");
    setLoading(true);
    abortRef.current = new AbortController();

    try {
      const res = await fetch(`/api/backend/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
        },
        body: JSON.stringify({ message: text.trim(), session_id: sessionId }),
        signal: abortRef.current.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const { parseSSEStream } = await import("@/lib/sse");

      for await (const evt of parseSSEStream(res)) {
        const type = evt.type as string;

        if (type === "agent") {
          setMessages((p) =>
            p.map((m) =>
              (m as Message & { _streamingId?: string })._streamingId === streamingId
                ? {
                    ...m,
                    agent: evt.agent as string,
                    agent_id: evt.agent_id as string,
                    intent: evt.intent as string,
                  }
                : m
            )
          );
        } else if (type === "tool_call") {
          const tc = {
            tool: evt.tool as string,
            args: (evt.args as Record<string, unknown>) ?? {},
            turn: (evt.turn as number) ?? 0,
          };
          setMessages((p) =>
            p.map((m) => {
              const sm = m as Message & { _streamingId?: string };
              if (sm._streamingId !== streamingId) return m;
              return { ...m, tool_calls: [...(m.tool_calls ?? []), tc] };
            })
          );
        } else if (type === "token") {
          const token = (evt.content as string) ?? "";
          setMessages((p) =>
            p.map((m) => {
              const sm = m as Message & { _streamingId?: string };
              if (sm._streamingId !== streamingId) return m;
              return { ...m, content: m.content + token };
            })
          );
          if (!open) setUnread((u) => u + 1);
        } else if (type === "done") {
          setMessages((p) =>
            p.map((m) => {
              const sm = m as Message & { _streamingId?: string };
              if (sm._streamingId !== streamingId) return m;
              const updated = { ...m, _streamingId: undefined };
              if (evt.total_tokens) updated.total_tokens = evt.total_tokens as number;
              if (evt.duration_ms) updated.duration_ms = evt.duration_ms as number;
              if (evt.tool_calls) updated.tool_calls = evt.tool_calls as Message["tool_calls"];
              return updated;
            })
          );
        } else if (type === "error") {
          setMessages((p) =>
            p.map((m) => {
              const sm = m as Message & { _streamingId?: string };
              if (sm._streamingId !== streamingId) return m;
              return {
                ...m,
                content: `⚠️ ${(evt.message as string) || "Agent error"}. Please try again.`,
                _streamingId: undefined,
              };
            })
          );
        }
      }
    } catch (e: unknown) {
      if ((e as { name?: string }).name !== "AbortError") {
        setMessages((p) =>
          p.map((m) => {
            const sm = m as Message & { _streamingId?: string };
            if (sm._streamingId !== streamingId) return m;
            return {
              ...m,
              content: "⚠️ Unable to reach AFOS backend. Ensure the server is running on port 8000.",
              _streamingId: undefined,
            };
          })
        );
      } else {
        // Aborted — remove the empty streaming bubble
        setMessages((p) =>
          p.filter((m) => {
            const sm = m as Message & { _streamingId?: string };
            return sm._streamingId !== streamingId || m.content.length > 0;
          })
        );
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }, [loading, sessionId, open]);

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const clearChat = async () => {
    setMessages([]);
    setUnread(0);
    try { await fetch(`/api/backend/chat/${sessionId}`, { method: "DELETE" }); } catch { /* ignore */ }
  };

  const totalToolCalls = messages.reduce((n, m) => n + (m.tool_calls?.length || 0), 0);
  const memoryTurns = messages.filter((m) => m.role === "assistant" && m.memory_used).length;

  return (
    <>
      {/* ── Floating button ── */}
      <motion.button
        id="afos-chat-toggle"
        onClick={() => { setOpen((o) => !o); setUnread(0); }}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-2xl flex items-center justify-center"
        style={{
          background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
          boxShadow: "0 8px 32px rgba(59,130,246,0.4), 0 0 0 1px rgba(255,255,255,0.08)",
        }}
        whileHover={{ scale: 1.08, boxShadow: "0 12px 40px rgba(59,130,246,0.5)" }}
        whileTap={{ scale: 0.95 }}
        title="Open Orqentra AI Chat"
      >
        <AnimatePresence mode="wait">
          {open
            ? <motion.div key="x" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.15 }}><X size={22} className="text-white" /></motion.div>
            : <motion.div key="chat" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }} transition={{ duration: 0.15 }}><MessageSquare size={22} className="text-white" /></motion.div>
          }
        </AnimatePresence>
        {unread > 0 && !open && (
          <span className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-rose-500 flex items-center justify-center text-xs font-bold text-white border-2 border-gray-900">
            {unread}
          </span>
        )}
      </motion.button>

      {/* ── Chat panel ── */}
      <AnimatePresence>
        {open && (
          <motion.div
            id="afos-chat-panel"
            initial={{ opacity: 0, y: 24, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.95 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="fixed bottom-24 right-6 z-50 flex flex-col rounded-2xl overflow-hidden"
            style={{
              width: 440,
              height: 600,
              background: "rgba(9,12,24,0.98)",
              backdropFilter: "blur(32px)",
              border: "1px solid rgba(59,130,246,0.2)",
              boxShadow: "0 32px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.03)",
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-4 py-3 flex-shrink-0"
              style={{
                background: "linear-gradient(135deg, rgba(59,130,246,0.1), rgba(139,92,246,0.06))",
                borderBottom: "1px solid rgba(255,255,255,0.05)",
              }}
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: "linear-gradient(135deg, #3b82f6, #8b5cf6)" }}>
                  <Bot size={15} className="text-white" />
                </div>
                <div>
                  <p className="text-sm font-bold text-white leading-none">Orqentra AI</p>
                  <p className="text-xs mt-0.5 flex items-center gap-1.5" style={{ color: "var(--color-text-muted)" }}>
                    <span>8 autonomous agents</span>
                    {totalToolCalls > 0 && (
                      <span className="text-blue-400">· {totalToolCalls} tools</span>
                    )}
                    {memoryTurns > 0 && (
                      <span className="text-violet-400">· {memoryTurns} memory</span>
                    )}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg" style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.18)" }}>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" style={{ boxShadow: "0 0 6px rgba(16,185,129,0.6)" }} />
                  <span className="text-xs font-semibold text-emerald-400">Live</span>
                </div>
                {messages.length > 0 && (
                  <button onClick={clearChat} className="p-1.5 rounded-lg hover:bg-white/5 transition-colors" title="Clear conversation">
                    <Trash2 size={13} style={{ color: "var(--color-text-muted)" }} />
                  </button>
                )}
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4" style={{ scrollbarWidth: "none" }}>
              {messages.length === 0 ? (
                <div className="space-y-5 pt-2">
                  {/* Welcome */}
                  <div className="text-center">
                    <div
                      className="w-14 h-14 rounded-2xl mx-auto mb-3 flex items-center justify-center"
                      style={{ background: "linear-gradient(135deg, rgba(59,130,246,0.12), rgba(139,92,246,0.12))", border: "1px solid rgba(59,130,246,0.15)" }}
                    >
                      <Activity size={22} className="text-blue-400" />
                    </div>
                    <p className="text-white font-bold text-sm">Orqentra Financial Intelligence</p>
                    <p className="text-xs mt-1.5 leading-relaxed" style={{ color: "var(--color-text-muted)" }}>
                      8 specialized agents · Real DB queries · Tool call tracing
                    </p>
                  </div>

                  {/* Agent badges */}
                  <div className="flex flex-wrap gap-1.5 justify-center">
                    {Object.entries(AGENT_COLORS).map(([name, color]) => (
                      <span
                        key={name}
                        className="text-xs px-2 py-1 rounded-lg font-medium"
                        style={{ background: `${color}14`, border: `1px solid ${color}28`, color }}
                      >
                        {name}
                      </span>
                    ))}
                  </div>

                  {/* Suggested */}
                  <div className="space-y-1.5">
                    <p className="text-xs font-semibold uppercase tracking-wider px-0.5" style={{ color: "var(--color-text-muted)" }}>
                      Try asking
                    </p>
                    {SUGGESTED_QUERIES.map((q, i) => (
                      <button
                        key={i}
                        onClick={() => sendMessage(q)}
                        className="w-full text-left px-3 py-2 rounded-xl text-xs transition-all group"
                        style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", color: "var(--color-text-secondary)" }}
                      >
                        <span className="text-blue-400 mr-1.5 group-hover:mr-2 transition-all">→</span>{q}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="flex-shrink-0 p-3" style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>
              <div
                className="flex items-center gap-2 px-3 py-2.5 rounded-xl transition-all"
                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}
              >
                <input
                  ref={inputRef}
                  id="afos-chat-input"
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(input); } }}
                  placeholder="Ask about finances, cash flow, anomalies…"
                  disabled={loading}
                  className="flex-1 bg-transparent text-xs outline-none placeholder:opacity-35"
                  style={{ color: "var(--color-text-primary)" }}
                />
                {loading ? (
                  <button
                    id="afos-chat-stop"
                    onClick={stopGeneration}
                    className="w-7 h-7 rounded-lg flex items-center justify-center transition-all"
                    style={{ background: "rgba(244,63,94,0.15)", border: "1px solid rgba(244,63,94,0.25)" }}
                    title="Stop generation"
                  >
                    <Square size={10} fill="#f43f5e" className="text-rose-400" />
                  </button>
                ) : (
                  <button
                    id="afos-chat-send"
                    onClick={() => sendMessage(input)}
                    disabled={!input.trim()}
                    className="w-7 h-7 rounded-lg flex items-center justify-center transition-all disabled:opacity-25"
                    style={{ background: input.trim() ? "linear-gradient(135deg, #3b82f6, #8b5cf6)" : "rgba(255,255,255,0.05)" }}
                  >
                    <Send size={12} className="text-white" />
                  </button>
                )}
              </div>
              <p className="text-xs mt-1.5 text-center" style={{ color: "var(--color-text-muted)" }}>
                <Database size={9} className="inline mr-1" />
                Secure Core · End-to-End Encryption
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
