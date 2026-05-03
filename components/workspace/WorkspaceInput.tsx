"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { motion } from "framer-motion";
import { Send, Square, Paperclip, Mic } from "lucide-react";

interface WorkspaceInputProps {
  onSend: (text: string) => void;
  isSending: boolean;
  onStop?: () => void;
  disabled?: boolean;
  placeholder?: string;
  initialValue?: string;
  onClear?: () => void;
}

export default function WorkspaceInput({
  onSend,
  isSending,
  onStop,
  disabled = false,
  placeholder = "Ask about your finances, cash flow, vendors, compliance…",
  initialValue = "",
  onClear,
}: WorkspaceInputProps) {
  const [value, setValue] = useState(initialValue);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Sync initialValue (for edit & resend)
  useEffect(() => {
    setValue(initialValue);
    if (initialValue && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [initialValue]);

  // Auto-grow textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [value]);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isSending || disabled) return;
    onSend(trimmed);
    setValue("");
    if (onClear) onClear();
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }, [value, isSending, disabled, onSend, onClear]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const charCount = value.length;
  const isOverLimit = charCount > 4000;

  return (
    <div className="flex-shrink-0 px-4 pb-4 pt-2">
      {/* Input container */}
      <div
        className="relative rounded-2xl transition-all duration-200"
        style={{
          background: "rgba(255,255,255,0.03)",
          border: `1px solid ${value ? "rgba(59,130,246,0.3)" : "rgba(255,255,255,0.08)"}`,
          boxShadow: value
            ? "0 0 0 3px rgba(59,130,246,0.06), 0 4px 24px rgba(0,0,0,0.3)"
            : "0 4px 24px rgba(0,0,0,0.2)",
        }}
      >
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          id="workspace-chat-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled || isSending}
          rows={1}
          className="w-full bg-transparent text-sm resize-none outline-none px-4 pt-3.5 pb-1"
          style={{
            color: "var(--color-text-primary)",
            maxHeight: "200px",
            scrollbarWidth: "none",
          }}
        />

        {/* Bottom bar */}
        <div className="flex items-center justify-between px-3 pb-3 pt-1">
          <div className="flex items-center gap-2">
            {/* Future: attach file */}
            <button
              className="w-7 h-7 rounded-lg flex items-center justify-center transition-all opacity-40 hover:opacity-60"
              style={{ color: "var(--color-text-muted)" }}
              title="Attach file (coming soon)"
              disabled
            >
              <Paperclip size={14} />
            </button>
            {/* Future: voice */}
            <button
              className="w-7 h-7 rounded-lg flex items-center justify-center transition-all opacity-40 hover:opacity-60"
              style={{ color: "var(--color-text-muted)" }}
              title="Voice mode (coming soon)"
              disabled
            >
              <Mic size={14} />
            </button>

            {/* Char count */}
            {charCount > 100 && (
              <span
                className="text-xs font-mono transition-colors"
                style={{ color: isOverLimit ? "#f43f5e" : "var(--color-text-muted)" }}
              >
                {charCount}/4000
              </span>
            )}
          </div>

          {/* Send / Stop */}
          <div className="flex items-center gap-2">
            {isSending ? (
              <motion.button
                id="workspace-stop-btn"
                onClick={onStop}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
                style={{
                  background: "rgba(244,63,94,0.15)",
                  border: "1px solid rgba(244,63,94,0.3)",
                  color: "#f43f5e",
                }}
              >
                <Square size={11} fill="currentColor" />
                Stop
              </motion.button>
            ) : (
              <motion.button
                id="workspace-send-btn"
                onClick={handleSend}
                disabled={!value.trim() || disabled || isOverLimit}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="w-9 h-9 rounded-xl flex items-center justify-center transition-all disabled:opacity-30"
                style={{
                  background: value.trim() && !disabled
                    ? "linear-gradient(135deg, #3b82f6, #8b5cf6)"
                    : "rgba(255,255,255,0.06)",
                  boxShadow: value.trim() && !disabled
                    ? "0 4px 16px rgba(59,130,246,0.3)"
                    : "none",
                }}
                title="Send message (Enter)"
              >
                <Send size={14} className="text-white" />
              </motion.button>
            )}
          </div>
        </div>
      </div>

      {/* Hint */}
      <p className="text-center text-xs mt-2" style={{ color: "var(--color-text-muted)" }}>
        <kbd
          className="px-1 py-0.5 rounded text-xs font-mono"
          style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)" }}
        >
          Enter
        </kbd>{" "}
        to send · <kbd
          className="px-1 py-0.5 rounded text-xs font-mono"
          style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)" }}
        >
          Shift+Enter
        </kbd>{" "}
        for new line
      </p>
    </div>
  );
}
