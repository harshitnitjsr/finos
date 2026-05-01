"use client";
import Link from "next/link";
import { Bot, Zap } from "lucide-react";
import { motion } from "framer-motion";

const CLERK_ENABLED =
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.startsWith("pk_live_") ||
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.startsWith("pk_test_");

export default function SignUpPage() {
  if (!CLERK_ENABLED) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--color-bg-primary)" }}>
        <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
          className="w-full max-w-md px-8 py-10 rounded-2xl text-center"
          style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border)" }}>
          <div className="w-14 h-14 rounded-2xl animated-gradient flex items-center justify-center mx-auto mb-5">
            <Bot size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-black text-white mb-2">AFOS</h1>
          <p className="text-sm mb-6" style={{ color: "var(--color-text-muted)" }}>Sign-up requires Clerk configuration.</p>
          <Link href="/dashboard" className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-bold"
            style={{ background: "linear-gradient(135deg, #3b82f6, #8b5cf6)", color: "white" }}>
            <Zap size={15} /> Enter Dashboard
          </Link>
        </motion.div>
      </div>
    );
  }

  const { SignUp } = require("@clerk/nextjs");
  return (
    <div className="min-h-screen flex" style={{ background: "var(--color-bg-primary)" }}>
      <div className="flex-1 flex items-center justify-center px-6">
        <SignUp />
      </div>
    </div>
  );
}
