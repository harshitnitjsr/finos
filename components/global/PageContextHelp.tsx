"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Info, X, HelpCircle, Target, Lightbulb } from "lucide-react";

interface PageContextHelpProps {
  pageName: string;
  why: string;
  what: string;
  how: string;
}

export default function PageContextHelp({ pageName, why, what, how }: PageContextHelpProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="w-6 h-6 ml-3 rounded-full flex items-center justify-center transition-all hover:bg-white/10"
        title={`Learn about ${pageName}`}
      >
        <Info size={16} className="text-slate-400 hover:text-white transition-colors" />
      </button>

      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsOpen(false)}
              className="fixed inset-0 z-[100]"
              style={{ background: "rgba(0,0,0,0.4)", backdropFilter: "blur(4px)" }}
            />

            {/* Modal */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[101] w-[90vw] max-w-lg rounded-2xl overflow-hidden"
              style={{
                background: "var(--color-bg-elevated)",
                border: "1px solid var(--color-border)",
                boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.3)",
              }}
            >
              {/* Header */}
              <div
                className="px-6 py-4 flex items-center justify-between"
                style={{ borderBottom: "1px solid var(--color-border)", background: "rgba(255,255,255,0.02)" }}
              >
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: "linear-gradient(135deg, #3b82f6, #8b5cf6)" }}>
                    <Info size={16} className="text-white" />
                  </div>
                  <h2 className="text-lg font-bold text-white">About {pageName}</h2>
                </div>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
                >
                  <X size={18} style={{ color: "var(--color-text-muted)" }} />
                </button>
              </div>

              {/* Content */}
              <div className="p-6 space-y-6">
                {/* Why */}
                <div className="flex gap-4">
                  <div className="mt-0.5">
                    <HelpCircle size={18} className="text-blue-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white mb-1">Why this page?</h3>
                    <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>
                      {why}
                    </p>
                  </div>
                </div>

                {/* What */}
                <div className="flex gap-4">
                  <div className="mt-0.5">
                    <Target size={18} className="text-violet-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white mb-1">What you get</h3>
                    <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>
                      {what}
                    </p>
                  </div>
                </div>

                {/* How */}
                <div className="flex gap-4">
                  <div className="mt-0.5">
                    <Lightbulb size={18} className="text-emerald-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white mb-1">How to analyze</h3>
                    <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>
                      {how}
                    </p>
                  </div>
                </div>
              </div>
              
              {/* Footer */}
              <div className="px-6 py-4 flex justify-end" style={{ borderTop: "1px solid var(--color-border)", background: "rgba(255,255,255,0.02)" }}>
                <button
                  onClick={() => setIsOpen(false)}
                  className="px-4 py-2 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90"
                  style={{ background: "linear-gradient(135deg, #3b82f6, #8b5cf6)" }}
                >
                  Got it
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
