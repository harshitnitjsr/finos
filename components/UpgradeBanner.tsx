"use client";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Zap, X, ArrowRight } from "lucide-react";
import Link from "next/link";
import { getCurrentSubscription, type OrganizationSubscription } from "@/lib/subscriptions";

/**
 * UpgradeBanner
 *
 * Shown automatically when:
 *  - User is on Free plan
 *  - Usage hits ≥ 80% of plan limit on any resource
 *
 * Dismissible per session (localStorage key).
 */
export default function UpgradeBanner() {
  const [sub, setSub] = useState<OrganizationSubscription | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Check if already dismissed this session
    if (sessionStorage.getItem("upgrade_banner_dismissed")) {
      setDismissed(true);
      return;
    }
    getCurrentSubscription()
      .then(setSub)
      .catch(() => {/* silent */});
  }, []);

  const dismiss = () => {
    sessionStorage.setItem("upgrade_banner_dismissed", "1");
    setDismissed(true);
  };

  if (!sub || dismissed) return null;

  const plan = sub.plan;
  const isFree = sub.status === "free";
  const invPct = plan.max_invoices_per_month > 0
    ? (sub.invoices_used / plan.max_invoices_per_month) * 100
    : 0;
  const promptPct = plan.max_prompts_per_month > 0
    ? (sub.prompts_used / plan.max_prompts_per_month) * 100
    : 0;

  // Show if on free plan OR any resource is ≥ 80% used
  const shouldShow = isFree || invPct >= 80 || promptPct >= 80;
  if (!shouldShow) return null;

  const isNearLimit = invPct >= 80 || promptPct >= 80;
  const isAtLimit = invPct >= 100 || promptPct >= 100;

  let message = "You're on the Free plan. Upgrade to unlock more invoices and AI prompts.";
  if (isAtLimit) {
    message = "You've hit your plan limit! Upgrade now to continue processing invoices.";
  } else if (isNearLimit) {
    const res = invPct >= promptPct ? "invoices" : "AI prompts";
    message = `You've used ${Math.round(Math.max(invPct, promptPct))}% of your ${res} limit. Consider upgrading.`;
  }

  const accentColor = isAtLimit ? "#f43f5e" : isNearLimit ? "#f59e0b" : "#8b5cf6";

  return (
    <AnimatePresence>
      <motion.div
        id="upgrade-banner"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.3 }}
        className="flex items-center justify-between gap-4 px-4 py-2.5 rounded-xl mx-4 mb-3"
        style={{
          background: `${accentColor}11`,
          border: `1px solid ${accentColor}33`,
        }}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <Zap size={14} style={{ color: accentColor, flexShrink: 0 }} />
          <p className="text-xs truncate" style={{ color: "var(--color-text-secondary)" }}>
            {message}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <Link
            href="/pricing"
            id="upgrade-banner-cta"
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-90"
            style={{
              background: `${accentColor}22`,
              color: accentColor,
              border: `1px solid ${accentColor}44`,
            }}
          >
            Upgrade <ArrowRight size={11} />
          </Link>
          <button
            id="upgrade-banner-dismiss"
            onClick={dismiss}
            className="p-1 rounded-lg transition-all hover:opacity-70"
            style={{ color: "var(--color-text-muted)" }}
            aria-label="Dismiss"
          >
            <X size={13} />
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
