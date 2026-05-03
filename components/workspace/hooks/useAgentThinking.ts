/**
 * useAgentThinking
 * ─────────────────
 * Polls GET /api/backend/chat/run/{run_id}/context every 600ms while
 * `isStreaming` is true and a `runId` is available.
 *
 * Returns the live reasoning context so the UI can show:
 *   "Calling: search_invoices (turn 2/6)"
 *   "Agent: Expense Intelligence"
 *   "Tools called so far: [...list...]"
 *
 * Automatically clears itself when streaming ends.
 */
"use client";
import { useState, useEffect, useRef } from "react";

export interface ToolCallRecord {
  tool: string;
  args?: Record<string, unknown>;
  turn?: number;
}

export interface ReasoningContext {
  status: "running" | "calling_tool" | "done";
  agent_id?: string;
  agent_name?: string;
  intent?: string;
  current_turn?: number;
  current_tool?: string;
  tool_calls?: ToolCallRecord[];   // objects: {tool, args, turn}
  started_at?: string;
  updated_at?: string;
  total_tokens?: number;
  duration_ms?: number;
}

export function useAgentThinking(runId: string | null, isStreaming: boolean) {
  const [context, setContext] = useState<ReasoningContext | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Clear any existing polling
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    // Only poll when we have a run_id and the stream is active
    if (!runId || !isStreaming) {
      setContext(null);
      return;
    }

    const poll = async () => {
      try {
        const res = await fetch(`/api/backend/chat/run/${runId}/context`);
        console.debug("[AFOS] context poll →", res.status, "runId:", runId);
        if (res.status === 404) {
          setContext(null);
          if (intervalRef.current) clearInterval(intervalRef.current);
          return;
        }
        if (!res.ok) return;
        const data = await res.json();
        console.debug("[AFOS] context state:", data?.state);
        if (data?.state) {
          setContext(data.state as ReasoningContext);
        } else {
          setContext(null);
        }
      } catch {
        // Network error — ignore silently
      }
    };

    // Poll immediately then every 600ms
    poll();
    intervalRef.current = setInterval(poll, 600);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [runId, isStreaming]);

  // Clear context when streaming stops
  useEffect(() => {
    if (!isStreaming) {
      setContext(null);
    }
  }, [isStreaming]);

  return context;
}
