"use client";
import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plus, Search, Trash2, Edit2, Check, X,
  MessageSquare, Clock, ChevronRight
} from "lucide-react";
import type { WorkspaceChat } from "./hooks/useWorkspace";

function formatRelativeTime(dateStr: string): string {
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

interface WorkspaceSidebarProps {
  chats: WorkspaceChat[];
  activeChatId: string | null;
  isLoading: boolean;
  onNewChat: () => void;
  onSelectChat: (id: string) => void;
  onDeleteChat: (id: string) => void;
  onRenameChat: (id: string, title: string) => void;
}

export default function WorkspaceSidebar({
  chats,
  activeChatId,
  isLoading,
  onNewChat,
  onSelectChat,
  onDeleteChat,
  onRenameChat,
}: WorkspaceSidebarProps) {
  const [search, setSearch] = useState("");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const filtered = chats.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase()) ||
    (c.last_message_preview ?? "").toLowerCase().includes(search.toLowerCase())
  );

  const startRename = useCallback((chat: WorkspaceChat) => {
    setRenamingId(chat.id);
    setRenameValue(chat.title);
  }, []);

  const commitRename = useCallback(() => {
    if (renamingId && renameValue.trim()) {
      onRenameChat(renamingId, renameValue.trim());
    }
    setRenamingId(null);
    setRenameValue("");
  }, [renamingId, renameValue, onRenameChat]);

  const cancelRename = useCallback(() => {
    setRenamingId(null);
    setRenameValue("");
  }, []);

  return (
    <div
      className="flex flex-col h-full"
      style={{
        width: 280,
        background: "var(--color-bg-secondary)",
        borderRight: "1px solid var(--color-border)",
      }}
    >
      {/* Header */}
      <div
        className="flex-shrink-0 px-4 pt-5 pb-3"
        style={{ borderBottom: "1px solid var(--color-border)" }}
      >
        <div className="flex items-center gap-2 mb-4">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ background: "linear-gradient(135deg, #3b82f6, #8b5cf6)" }}
          >
            <MessageSquare size={13} className="text-white" />
          </div>
          <span className="font-bold text-sm" style={{ color: "var(--color-text-primary)" }}>
            AI Workspace
          </span>
        </div>

        {/* New Chat Button */}
        <motion.button
          id="workspace-new-chat"
          onClick={onNewChat}
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.98 }}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium transition-all"
          style={{
            background: "linear-gradient(135deg, rgba(59,130,246,0.15), rgba(139,92,246,0.1))",
            border: "1px solid rgba(59,130,246,0.2)",
            color: "#93c5fd",
          }}
        >
          <Plus size={15} />
          New Chat
        </motion.button>
      </div>

      {/* Search */}
      <div className="flex-shrink-0 px-4 py-3">
        <div
          className="flex items-center gap-2 px-3 py-2 rounded-xl"
          style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}
        >
          <Search size={13} style={{ color: "var(--color-text-muted)" }} />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search chats…"
            className="flex-1 bg-transparent text-xs outline-none placeholder:opacity-40"
            style={{ color: "var(--color-text-secondary)" }}
          />
          {search && (
            <button onClick={() => setSearch("")}>
              <X size={12} style={{ color: "var(--color-text-muted)" }} />
            </button>
          )}
        </div>
      </div>

      {/* Chat section label */}
      {filtered.length > 0 && (
        <div className="px-4 mb-1">
          <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--color-text-muted)" }}>
            {search ? `${filtered.length} result${filtered.length !== 1 ? "s" : ""}` : "Recent chats"}
          </span>
        </div>
      )}

      {/* Chat List */}
      <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-0.5">
        {isLoading ? (
          // Skeleton
          Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-14 rounded-xl mx-2 shimmer"
              style={{ marginBottom: 4 }}
            />
          ))
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-center px-4">
            <MessageSquare size={24} style={{ color: "var(--color-text-muted)", marginBottom: 8 }} />
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {search ? "No chats match your search" : "No conversations yet"}
            </p>
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {filtered.map((chat) => {
              const isActive = chat.id === activeChatId;
              const isRenaming = renamingId === chat.id;

              return (
                <motion.div
                  key={chat.id}
                  layout
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  className="group relative"
                >
                  <button
                    onClick={() => !isRenaming && onSelectChat(chat.id)}
                    className="w-full text-left px-3 py-2.5 rounded-xl transition-all duration-150"
                    style={{
                      background: isActive
                        ? "rgba(59,130,246,0.12)"
                        : "transparent",
                      border: isActive
                        ? "1px solid rgba(59,130,246,0.2)"
                        : "1px solid transparent",
                    }}
                  >
                    {/* Active indicator */}
                    {isActive && (
                      <div
                        className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 rounded-r"
                        style={{ background: "linear-gradient(135deg, #3b82f6, #8b5cf6)" }}
                      />
                    )}

                    {isRenaming ? (
                      <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                        <input
                          autoFocus
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") commitRename();
                            if (e.key === "Escape") cancelRename();
                          }}
                          className="flex-1 bg-transparent text-xs outline-none"
                          style={{
                            color: "var(--color-text-primary)",
                            borderBottom: "1px solid rgba(59,130,246,0.4)",
                          }}
                        />
                        <button onClick={commitRename} className="p-0.5">
                          <Check size={11} className="text-emerald-400" />
                        </button>
                        <button onClick={cancelRename} className="p-0.5">
                          <X size={11} style={{ color: "var(--color-text-muted)" }} />
                        </button>
                      </div>
                    ) : (
                      <div className="pr-8">
                        <p
                          className="text-xs font-medium truncate leading-snug"
                          style={{ color: isActive ? "#93c5fd" : "var(--color-text-secondary)" }}
                        >
                          {chat.title}
                        </p>
                        {chat.last_message_preview && (
                          <p
                            className="text-xs truncate mt-0.5 leading-snug"
                            style={{ color: "var(--color-text-muted)" }}
                          >
                            {chat.last_message_preview}
                          </p>
                        )}
                        <div className="flex items-center gap-1 mt-1">
                          <Clock size={8} style={{ color: "var(--color-text-muted)" }} />
                          <span className="text-xs" style={{ color: "var(--color-text-muted)", fontSize: 10 }}>
                            {formatRelativeTime(chat.updated_at)}
                          </span>
                          {chat.message_count > 0 && (
                            <>
                              <span style={{ color: "var(--color-text-muted)", fontSize: 10 }}>·</span>
                              <span style={{ color: "var(--color-text-muted)", fontSize: 10 }}>
                                {chat.message_count} msgs
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    )}
                  </button>

                  {/* Action buttons (show on hover) */}
                  {!isRenaming && (
                    <div
                      className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <button
                        onClick={(e) => { e.stopPropagation(); startRename(chat); }}
                        className="w-6 h-6 rounded-md flex items-center justify-center transition-colors hover:bg-white/10"
                        title="Rename"
                      >
                        <Edit2 size={10} style={{ color: "var(--color-text-muted)" }} />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); onDeleteChat(chat.id); }}
                        className="w-6 h-6 rounded-md flex items-center justify-center transition-colors hover:bg-rose-500/10"
                        title="Delete"
                      >
                        <Trash2 size={10} className="text-rose-400" />
                      </button>
                    </div>
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </div>

      {/* Footer */}
      <div
        className="flex-shrink-0 px-4 py-3"
        style={{ borderTop: "1px solid var(--color-border)" }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-1.5 h-1.5 rounded-full bg-emerald-400"
            style={{ boxShadow: "0 0 6px rgba(16,185,129,0.6)" }}
          />
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            8 agents · LangGraph · GPT-4o
          </span>
        </div>
      </div>
    </div>
  );
}
