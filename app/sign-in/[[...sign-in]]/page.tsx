"use client";
import Link from "next/link";
import { Bot, Zap, Shield, BarChart3, FileText } from "lucide-react";
import { motion } from "framer-motion";

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center p-6" style={{ background: "var(--color-bg-primary)" }}>
      <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
        {/* Left — Branding */}
        <motion.div initial={{ opacity: 0, x: -24 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5 }}>
          <div className="w-14 h-14 rounded-2xl animated-gradient flex items-center justify-center mb-6">
            <Bot size={28} className="text-white" />
          </div>
          <h1 className="text-4xl font-black text-white mb-3 leading-tight">
            Autonomous<br />Financial OS
          </h1>
          <p className="text-base mb-8" style={{ color: "var(--color-text-secondary)" }}>
            AI-native financial execution infrastructure for modern businesses.
          </p>
          <div className="space-y-3">
            {[
              { Icon: Shield, title: "Policy-Driven Compliance", desc: "Automated risk scoring and approval workflows" },
              { Icon: BarChart3, title: "Real-time Analytics", desc: "Live spend intelligence across all currencies" },
              { Icon: FileText, title: "AI Invoice Processing", desc: "OCR + extraction + duplicate detection" },
            ].map(({ Icon, title, desc }) => (
              <div key={title} className="flex items-start gap-3 p-3 rounded-xl" style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border)" }}>
                <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: "rgba(59,130,246,0.1)" }}>
                  <Icon size={15} className="text-blue-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">{title}</p>
                  <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Right — Login Card */}
        <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }}>
          <div className="card p-8 rounded-2xl">
            <h2 className="text-xl font-bold text-white mb-1">Welcome back</h2>
            <p className="text-sm mb-6" style={{ color: "var(--color-text-muted)" }}>
              Sign in to access your financial dashboard
            </p>

            <div className="p-4 rounded-xl mb-5" style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.2)" }}>
              <p className="text-xs font-bold text-amber-400 mb-1">🔑 Running in Demo Mode</p>
              <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                Add real Clerk keys to <code className="text-blue-400 font-mono">.env.local</code> to enable full authentication.
                Click below to explore the dashboard with seeded demo data.
              </p>
            </div>

            <Link
              href="/dashboard"
              className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl text-sm font-bold transition-all hover:opacity-90 mb-4"
              style={{ background: "linear-gradient(135deg, #3b82f6, #8b5cf6)", color: "white" }}
            >
              <Zap size={15} /> Enter Dashboard →
            </Link>

            <p className="text-xs text-center" style={{ color: "var(--color-text-muted)" }}>
              Demo data pre-seeded · All features available
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
