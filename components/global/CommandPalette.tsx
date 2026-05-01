"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Search, FileText, CreditCard, CheckSquare, BarChart3, Bot, Landmark, Workflow, X } from "lucide-react";

const COMMANDS = [
  { label: "Go to Dashboard", href: "/dashboard", icon: BarChart3, group: "Navigation" },
  { label: "View Invoices", href: "/dashboard/invoices", icon: FileText, group: "Navigation" },
  { label: "View Expenses", href: "/dashboard/expenses", icon: CreditCard, group: "Navigation" },
  { label: "Approval Queue", href: "/dashboard/approvals", icon: CheckSquare, group: "Navigation" },
  { label: "AI Agents", href: "/dashboard/agents", icon: Bot, group: "Navigation" },
  { label: "Treasury", href: "/dashboard/treasury", icon: Landmark, group: "Navigation" },
  { label: "Workflows", href: "/dashboard/workflows", icon: Workflow, group: "Navigation" },
  { label: "Analytics", href: "/dashboard/analytics", icon: BarChart3, group: "Navigation" },
];

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const router = useRouter();

  const filtered = query
    ? COMMANDS.filter(c => c.label.toLowerCase().includes(query.toLowerCase()))
    : COMMANDS;

  const execute = useCallback((href: string) => {
    router.push(href);
    onClose();
    setQuery("");
  }, [router, onClose]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        open ? onClose() : undefined;
      }
      if (!open) return;
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowDown") setSelected(s => Math.min(s + 1, filtered.length - 1));
      if (e.key === "ArrowUp") setSelected(s => Math.max(s - 1, 0));
      if (e.key === "Enter" && filtered[selected]) execute(filtered[selected].href);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, filtered, selected, execute, onClose]);

  useEffect(() => { setSelected(0); }, [query]);
  useEffect(() => { if (open) setQuery(""); }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50"
            style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
            onClick={onClose}
          />
          <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]">
            <motion.div
              initial={{ opacity: 0, y: -20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className="w-full max-w-lg rounded-2xl overflow-hidden"
              style={{
                background: "var(--color-bg-elevated)",
                border: "1px solid var(--color-border-hover)",
                boxShadow: "0 25px 80px rgba(0,0,0,0.8), 0 0 0 1px rgba(59,130,246,0.1)",
              }}
            >
              {/* Search Input */}
              <div className="flex items-center gap-3 px-4 py-4 border-b" style={{ borderColor: "var(--color-border)" }}>
                <Search size={18} style={{ color: "var(--color-text-muted)" }} />
                <input
                  autoFocus
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="Search pages, actions, invoices..."
                  className="flex-1 bg-transparent text-white text-sm outline-none placeholder:text-slate-500"
                />
                <button onClick={onClose}>
                  <X size={16} style={{ color: "var(--color-text-muted)" }} />
                </button>
              </div>

              {/* Results */}
              <div className="py-2 max-h-80 overflow-y-auto">
                {filtered.length === 0 && (
                  <div className="px-4 py-8 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>
                    No results for "{query}"
                  </div>
                )}
                {filtered.map((cmd, i) => (
                  <button
                    key={cmd.href}
                    onClick={() => execute(cmd.href)}
                    onMouseEnter={() => setSelected(i)}
                    className="w-full flex items-center gap-3 px-4 py-3 text-sm text-left transition-colors"
                    style={{
                      background: i === selected ? "rgba(59,130,246,0.1)" : "transparent",
                      color: i === selected ? "#3b82f6" : "var(--color-text-secondary)",
                      borderLeft: i === selected ? "2px solid #3b82f6" : "2px solid transparent",
                    }}
                  >
                    <cmd.icon size={16} />
                    <span>{cmd.label}</span>
                    <span className="ml-auto text-xs" style={{ color: "var(--color-text-muted)" }}>
                      {cmd.group}
                    </span>
                  </button>
                ))}
              </div>

              {/* Footer */}
              <div className="flex items-center gap-4 px-4 py-2.5 border-t" style={{ borderColor: "var(--color-border)" }}>
                {[["↑↓", "navigate"], ["↵", "select"], ["esc", "close"]].map(([key, label]) => (
                  <span key={key} className="flex items-center gap-1.5 text-xs" style={{ color: "var(--color-text-muted)" }}>
                    <kbd className="px-1.5 py-0.5 rounded font-mono text-xs"
                      style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border)" }}>
                      {key}
                    </kbd>
                    {label}
                  </span>
                ))}
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
