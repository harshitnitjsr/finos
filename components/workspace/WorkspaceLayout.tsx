"use client";
import WorkspaceSidebar from "./WorkspaceSidebar";
import WorkspaceChatView from "./WorkspaceChatView";
import { useWorkspace } from "./hooks/useWorkspace";
import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, X } from "lucide-react";

export default function WorkspaceLayout() {
  const {
    chats,
    activeChatId,
    activeChat,
    messages,
    isLoading,
    isSending,
    isLoadingMessages,
    error,
    createChat,
    selectChat,
    deleteChat,
    renameChat,
    sendMessage,
    clearError,
  } = useWorkspace();

  return (
    <div
      className="flex h-full overflow-hidden"
      style={{ background: "var(--color-bg-primary)" }}
    >
      {/* Left sidebar */}
      <WorkspaceSidebar
        chats={chats}
        activeChatId={activeChatId}
        isLoading={isLoading}
        onNewChat={createChat}
        onSelectChat={selectChat}
        onDeleteChat={deleteChat}
        onRenameChat={renameChat}
      />

      {/* Main chat area */}
      <div className="flex-1 flex flex-col overflow-hidden relative">
        <WorkspaceChatView
          chat={activeChat}
          messages={messages}
          isLoadingMessages={isLoadingMessages}
          isSending={isSending}
          onSend={sendMessage}
        />

        {/* Error toast */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 16 }}
              className="absolute bottom-24 left-1/2 -translate-x-1/2 flex items-center gap-2.5 px-4 py-3 rounded-xl"
              style={{
                background: "rgba(244,63,94,0.12)",
                border: "1px solid rgba(244,63,94,0.25)",
                boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
                maxWidth: 480,
              }}
            >
              <AlertCircle size={15} className="text-rose-400 flex-shrink-0" />
              <span className="text-sm text-rose-300 flex-1">{error}</span>
              <button onClick={clearError} className="p-0.5">
                <X size={13} style={{ color: "var(--color-text-muted)" }} />
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
