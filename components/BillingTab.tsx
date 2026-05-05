"use client";
import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  CreditCard, CheckCircle2, AlertTriangle, Loader2,
  Zap, ArrowRight, XCircle, RefreshCw,
} from "lucide-react";
import toast from "react-hot-toast";
import Link from "next/link";
import {
  getCurrentSubscription, cancelSubscription,
  type OrganizationSubscription,
} from "@/lib/subscriptions";

const iv = { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0, transition: { duration: 0.3 } } };

function UsageMeter({
  label,
  used,
  max,
  accent,
}: { label: string; used: number; max: number; accent: string }) {
  const unlimited = max === -1;
  const pct = unlimited ? 0 : Math.min((used / max) * 100, 100);
  const isWarning = !unlimited && pct >= 80;
  const isFull = !unlimited && pct >= 100;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span style={{ color: "var(--color-text-muted)" }}>{label}</span>
        <span
          className="font-semibold"
          style={{ color: isFull ? "#f43f5e" : isWarning ? "#f59e0b" : "var(--color-text-secondary)" }}
        >
          {unlimited ? "Unlimited" : `${used.toLocaleString()} / ${max.toLocaleString()}`}
        </span>
      </div>
      {!unlimited && (
        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.08)" }}>
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{
              width: `${pct}%`,
              background: isFull ? "#f43f5e" : isWarning ? "#f59e0b" : accent,
            }}
          />
        </div>
      )}
    </div>
  );
}

const STATUS_COLOR: Record<string, string> = {
  free: "rgba(100,116,139,0.8)",
  active: "#10b981",
  past_due: "#f59e0b",
  cancelled: "#f43f5e",
  paused: "#f59e0b",
};

const STATUS_LABEL: Record<string, string> = {
  free: "Free Plan",
  active: "Active",
  past_due: "Past Due",
  cancelled: "Cancelled",
  paused: "Paused",
};

export default function BillingTab() {
  const [sub, setSub] = useState<OrganizationSubscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await getCurrentSubscription();
      setSub(data);
    } catch {
      toast.error("Failed to load subscription info");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCancel = async () => {
    if (!confirm("Cancel your subscription? You will be downgraded to the Free plan at the end of the current period.")) return;
    setCancelling(true);
    try {
      await cancelSubscription();
      toast.success("Subscription cancelled. You will stay on the current plan until period ends.");
      await load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Cancel failed");
    } finally {
      setCancelling(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center py-16">
        <Loader2 size={28} className="animate-spin" style={{ color: "var(--color-text-muted)" }} />
      </div>
    );
  }

  if (!sub) return null;

  const plan = sub.plan;
  const isActive = sub.status === "active";
  const isFree = sub.status === "free";
  const canCancel = isActive && !!sub.razorpay_subscription_id;
  const periodEnd = sub.current_period_end
    ? new Date(sub.current_period_end).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })
    : null;

  return (
    <div className="p-6 space-y-6">
      {/* Current plan card */}
      <motion.div
        variants={iv}
        initial="hidden"
        animate="show"
        className="rounded-xl p-5 space-y-1"
        style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: "rgba(139,92,246,0.1)", border: "1px solid rgba(139,92,246,0.2)" }}
            >
              <CreditCard size={18} style={{ color: "#a78bfa" }} />
            </div>
            <div>
              <p className="text-base font-bold text-white">{plan.name} Plan</p>
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {plan.price_monthly_inr === 0
                  ? "Free forever"
                  : `₹${plan.price_monthly_inr.toLocaleString("en-IN")} / month`}
              </p>
            </div>
          </div>

          <span
            className="px-2.5 py-1 rounded-full text-xs font-bold"
            style={{
              background: STATUS_COLOR[sub.status] + "22",
              color: STATUS_COLOR[sub.status],
              border: `1px solid ${STATUS_COLOR[sub.status]}44`,
            }}
          >
            {STATUS_LABEL[sub.status] ?? sub.status}
          </span>
        </div>

        {periodEnd && (
          <p className="text-xs pt-1" style={{ color: "var(--color-text-muted)" }}>
            {isActive ? "Renews" : "Expires"}: {periodEnd}
          </p>
        )}
      </motion.div>

      {/* Usage meters */}
      <motion.div
        variants={iv}
        initial="hidden"
        animate="show"
        className="rounded-xl p-5 space-y-4"
        style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}
      >
        <p className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
          Monthly Usage
        </p>
        <UsageMeter
          label="Invoices"
          used={sub.invoices_used}
          max={plan.max_invoices_per_month}
          accent="#3b82f6"
        />
        <UsageMeter
          label="AI Prompts"
          used={sub.prompts_used}
          max={plan.max_prompts_per_month}
          accent="#8b5cf6"
        />
      </motion.div>

      {/* Actions */}
      <motion.div variants={iv} initial="hidden" animate="show" className="flex flex-wrap gap-3">
        {(isFree || sub.status === "cancelled") && (
          <Link
            href="/pricing"
            id="billing-upgrade-btn"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all hover:opacity-90"
            style={{
              background: "rgba(139,92,246,0.15)",
              color: "#a78bfa",
              border: "1px solid rgba(139,92,246,0.3)",
            }}
          >
            <Zap size={14} /> Upgrade Plan <ArrowRight size={14} />
          </Link>
        )}

        <button
          id="billing-refresh-btn"
          onClick={load}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all hover:opacity-90"
          style={{
            background: "rgba(59,130,246,0.08)",
            color: "#64748b",
            border: "1px solid var(--color-border)",
          }}
        >
          <RefreshCw size={13} /> Refresh
        </button>

        {canCancel && (
          <button
            id="billing-cancel-btn"
            onClick={handleCancel}
            disabled={cancelling}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-50"
            style={{
              background: "rgba(244,63,94,0.08)",
              color: "#f43f5e",
              border: "1px solid rgba(244,63,94,0.2)",
            }}
          >
            {cancelling ? <Loader2 size={13} className="animate-spin" /> : <XCircle size={13} />}
            Cancel Subscription
          </button>
        )}
      </motion.div>

      {/* Info note */}
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        Payments are processed securely by{" "}
        <span className="font-semibold text-white">Razorpay</span>. Usage counters reset at the start of each billing cycle.
      </p>
    </div>
  );
}
