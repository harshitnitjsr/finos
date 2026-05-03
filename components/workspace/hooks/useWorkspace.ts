"use client";
import { useState, useEffect, useCallback, useRef } from "react";

const API_BASE = "/api/backend/workspace-chats";

export interface WorkspaceMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  agent_name?: string;
  agent_id?: string;
  intent?: string;
  tool_calls?: Array<{ tool: string; args: Record<string, unknown>; turn: number }>;
  memory_used?: boolean;
  memory_sources?: string[];
  tokens_used?: number;
  duration_ms?: number;
  created_at?: string;
  // optimistic UI
  isStreaming?: boolean;
}

export interface WorkspaceChat {
  id: string;
  title: string;
  session_id: string;
  model: string;
  message_count: number;
  last_message_preview?: string;
  created_at: string;
  updated_at: string;
}

interface UseWorkspaceReturn {
  chats: WorkspaceChat[];
  activeChatId: string | null;
  activeChat: WorkspaceChat | null;
  messages: WorkspaceMessage[];
  isLoading: boolean;
  isSending: boolean;
  isLoadingMessages: boolean;
  error: string | null;
  /** run_id of the currently active SSE stream — used to poll /chat/run/{id}/context */
  activeRunId: string | null;
  /** Tool calls accumulated from SSE tool_call events — zero-latency, no polling needed */
  activeLiveTools: { tool: string; args: Record<string, unknown>; turn: number }[];
  /** Agent name from the SSE agent event — available immediately */
  activeAgentName: string | null;
  /** Intent from the SSE agent event */
  activeIntent: string | null;
  createChat: () => Promise<WorkspaceChat | null>;
  selectChat: (chatId: string) => Promise<void>;
  deleteChat: (chatId: string) => Promise<void>;
  renameChat: (chatId: string, title: string) => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
  clearError: () => void;
}

export function useWorkspace(): UseWorkspaceReturn {
  const [chats, setChats] = useState<WorkspaceChat[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<WorkspaceMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  // SSE-sourced live state — populated synchronously from events, no polling delay
  const [activeLiveTools, setActiveLiveTools] = useState<{ tool: string; args: Record<string, unknown>; turn: number }[]>([]);
  const [activeAgentName, setActiveAgentName] = useState<string | null>(null);
  const [activeIntent, setActiveIntent] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const activeChat = chats.find((c) => c.id === activeChatId) ?? null;

  // ── Load chat list ────────────────────────────────────────────────────────
  const loadChats = useCallback(async () => {
    try {
      const res = await fetch(API_BASE);
      if (!res.ok) throw new Error(`Failed to load chats: ${res.status}`);
      const data = await res.json();
      setChats(data.chats ?? []);
    } catch (e) {
      setError(String(e));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadChats(); }, [loadChats]);

  // ── Load messages for active chat ─────────────────────────────────────────
  const loadMessages = useCallback(async (chatId: string) => {
    setIsLoadingMessages(true);
    setMessages([]);
    try {
      const res = await fetch(`${API_BASE}/${chatId}/messages`);
      if (!res.ok) throw new Error(`Failed to load messages: ${res.status}`);
      const data = await res.json();
      setMessages(
        (data.messages ?? []).map((m: WorkspaceMessage) => ({
          ...m,
          tool_calls: m.tool_calls ?? [],
          memory_sources: m.memory_sources ?? [],
        }))
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setIsLoadingMessages(false);
    }
  }, []);

  // ── Create new chat ───────────────────────────────────────────────────────
  const createChat = useCallback(async (): Promise<WorkspaceChat | null> => {
    try {
      const res = await fetch(API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "New Chat" }),
      });
      if (!res.ok) throw new Error(`Failed to create chat: ${res.status}`);
      const chat: WorkspaceChat = await res.json();
      setChats((prev) => [chat, ...prev]);
      setActiveChatId(chat.id);
      setMessages([]);
      return chat;
    } catch (e) {
      setError(String(e));
      return null;
    }
  }, []);

  // ── Select chat ───────────────────────────────────────────────────────────
  const selectChat = useCallback(async (chatId: string) => {
    if (chatId === activeChatId) return;
    setActiveChatId(chatId);
    await loadMessages(chatId);
  }, [activeChatId, loadMessages]);

  // ── Delete (archive) chat ─────────────────────────────────────────────────
  const deleteChat = useCallback(async (chatId: string) => {
    try {
      await fetch(`${API_BASE}/${chatId}`, { method: "DELETE" });
      setChats((prev) => prev.filter((c) => c.id !== chatId));
      if (activeChatId === chatId) {
        setActiveChatId(null);
        setMessages([]);
      }
    } catch (e) {
      setError(String(e));
    }
  }, [activeChatId]);

  // ── Rename chat ───────────────────────────────────────────────────────────
  const renameChat = useCallback(async (chatId: string, title: string) => {
    try {
      const res = await fetch(`${API_BASE}/${chatId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) throw new Error("Rename failed");
      const updated: WorkspaceChat = await res.json();
      setChats((prev) =>
        prev.map((c) => (c.id === chatId ? updated : c))
      );
    } catch (e) {
      setError(String(e));
    }
  }, []);

  // ── Send message (streaming) ──────────────────────────────────────────────
  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isSending) return;

    let chatId = activeChatId;

    // Auto-create a chat if none is active
    if (!chatId) {
      const newChat = await createChat();
      if (!newChat) return;
      chatId = newChat.id;
    }

    // Optimistic user message
    const optimisticUserId = `opt_u_${Date.now()}`;
    const optimisticAsstId = `opt_a_${Date.now()}`;
    const optimisticUser: WorkspaceMessage = {
      id: optimisticUserId,
      role: "user",
      content: text.trim(),
      created_at: new Date().toISOString(),
    };
    const optimisticAsst: WorkspaceMessage = {
      id: optimisticAsstId,
      role: "assistant",
      content: "",
      isStreaming: true,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUser, optimisticAsst]);
    setIsSending(true);

    abortRef.current = new AbortController();

    try {
      const res = await fetch(
        `/api/backend/workspace-chats/${chatId}/messages/stream`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
          },
          body: JSON.stringify({ message: text.trim() }),
          signal: abortRef.current.signal,
        }
      );

      if (!res.ok) throw new Error(`Send failed: ${res.status}`);

      // State accumulated from SSE events
      let agentName = "AI Agent";
      let agentId = "";
      let intent = "";
      let toolCalls: WorkspaceMessage["tool_calls"] = [];
      let totalTokens = 0;
      let durationMs = 0;
      let memoryUsed = false;
      let memorySources: string[] = [];
      let finalMsgId = optimisticAsstId;

      const { parseSSEStream } = await import("@/lib/sse");

      for await (const evt of parseSSEStream(res)) {
        const type = evt.type as string;

        if (type === "agent") {
          agentName = (evt.agent as string) ?? agentName;
          agentId   = (evt.agent_id as string) ?? agentId;
          intent    = (evt.intent as string) ?? intent;
          // Capture run_id for context polling
          const emittedRunId = evt.run_id as string | undefined;
          if (emittedRunId) {
            console.debug("[AFOS] ✅ run_id captured:", emittedRunId, "agent:", agentName);
            setActiveRunId(emittedRunId);
          } else {
            console.warn("[AFOS] ❌ agent event has no run_id:", evt);
          }
          // Immediately expose agent name/intent — zero latency, no polling delay
          setActiveAgentName(agentName);
          setActiveIntent(intent);

          // Show agent badge immediately
          setMessages((prev) =>
            prev.map((m) =>
              m.id === optimisticAsstId
                ? { ...m, agent_name: agentName, agent_id: agentId, intent }
                : m
            )
          );
        } else if (type === "tool_call") {
          const tc = {
            tool: (evt.tool as string) ?? "",
            args: (evt.args as Record<string, unknown>) ?? {},
            turn: (evt.turn as number) ?? 0,
          };
          toolCalls = [...toolCalls, tc];
          // Push to live overlay state immediately (no polling delay)
          setActiveLiveTools((prev) => [...prev, tc]);

          setMessages((prev) =>
            prev.map((m) =>
              m.id === optimisticAsstId
                ? { ...m, tool_calls: toolCalls }
                : m
            )
          );
        } else if (type === "token") {
          const token = (evt.content as string) ?? "";
          setMessages((prev) =>
            prev.map((m) =>
              m.id === optimisticAsstId
                ? { ...m, content: m.content + token, isStreaming: true }
                : m
            )
          );
        } else if (type === "done") {
          toolCalls    = (evt.tool_calls as typeof toolCalls) ?? toolCalls;
          totalTokens  = (evt.total_tokens as number) ?? 0;
          durationMs   = (evt.duration_ms as number) ?? 0;
          memoryUsed   = (evt.memory_used as boolean) ?? false;
          memorySources = (evt.sources as string[]) ?? [];
          finalMsgId   = (evt.message_id as string) ?? optimisticAsstId;

          // Finalise the streaming bubble
          setMessages((prev) =>
            prev.map((m) =>
              m.id === optimisticAsstId
                ? {
                    ...m,
                    id: finalMsgId,
                    isStreaming: false,
                    tool_calls: toolCalls,
                    tokens_used: totalTokens,
                    duration_ms: durationMs,
                    memory_used: memoryUsed,
                    memory_sources: memorySources,
                    agent_name: agentName,
                    agent_id: agentId,
                    intent,
                  }
                : m
            )
          );

          // Update sidebar chat item
          setChats((prev) =>
            prev.map((c) => {
              if (c.id !== chatId) return c;
              const autoTitle =
                c.title === "New Chat" ? text.slice(0, 80) : c.title;
              return {
                ...c,
                title: autoTitle,
                message_count: c.message_count + 2,
                updated_at: new Date().toISOString(),
              };
            })
          );
        } else if (type === "error") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === optimisticAsstId
                ? {
                    ...m,
                    content:
                      `⚠️ ${(evt.message as string) || "Unknown error"}`,
                    isStreaming: false,
                  }
                : m
            )
          );
        }
      }
    } catch (e: unknown) {
      if ((e as { name?: string }).name === "AbortError") {
        // Remove the optimistic pair on manual stop
        setMessages((prev) =>
          prev.filter(
            (m) => m.id !== optimisticAsstId && m.id !== optimisticUserId
          )
        );
        return;
      }
      setMessages((prev) =>
        prev.map((m) =>
          m.id === optimisticAsstId
            ? {
                ...m,
                content:
                  "⚠️ Failed to reach the AFOS backend. Please check the server.",
                isStreaming: false,
              }
            : m
        )
      );
    } finally {
      setIsSending(false);
      setActiveRunId(null);
      setActiveLiveTools([]);
      setActiveAgentName(null);
      setActiveIntent(null);
      abortRef.current = null;
    }
  }, [activeChatId, isSending, createChat]);

  return {
    chats,
    activeChatId,
    activeChat,
    messages,
    isLoading,
    isSending,
    isLoadingMessages,
    error,
    activeRunId,
    activeLiveTools,
    activeAgentName,
    activeIntent,
    createChat,
    selectChat,
    deleteChat,
    renameChat,
    sendMessage,
    clearError: () => setError(null),
  };
}
