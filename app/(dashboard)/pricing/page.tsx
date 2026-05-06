"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  CheckCircle2, Zap, Building2, Sparkles,
  ArrowRight, Loader2, ShieldCheck,
} from "lucide-react";
import toast from "react-hot-toast";
import { useSession } from "next-auth/react";
import {
  getPlans,
  getCurrentSubscription,
  createSubscription,
  verifySubscriptionPayment,
  type SubscriptionPlan,
  type OrganizationSubscription,
} from "@/lib/subscriptions";

declare global {
  interface Window { Razorpay: any; }
}

/* ── Motion variants ─────────────────────────────────────────────────────── */
const cv = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const iv = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };

/* Currency is detected server-side from the caller's real IP address.
 * The backend returns detected_currency: "INR" | "USD" in the /plans response.
 * This correctly handles VPN, proxies, and all network configurations. */

/* ── Plan metadata ───────────────────────────────────────────────────────── */
const PLAN_ICONS: Record<string, React.ElementType> = {
  free:       Sparkles,
  starter:    Zap,
  pro:        CheckCircle2,
  enterprise: Building2,
};

const PLAN_ACCENT: Record<string, string> = {
  free:       "rgba(100,116,139,0.7)",
  starter:    "rgba(59,130,246,0.7)",
  pro:        "rgba(139,92,246,0.8)",
  enterprise: "rgba(245,158,11,0.7)",
};

const PLAN_GRADIENT: Record<string, string> = {
  free:       "rgba(100,116,139,0.08)",
  starter:    "rgba(59,130,246,0.08)",
  pro:        "rgba(139,92,246,0.1)",
  enterprise: "rgba(245,158,11,0.08)",
};

const PLAN_FEATURES: Record<string, string[]> = {
  free: [
    "5 invoice uploads — trial only",
    "10 AI chat prompts — trial only",
    "Expires 30 days after signup",
    "Full platform access during trial",
  ],
  starter: [
    "100 invoice uploads / month",
    "500 AI chat prompts / month",
    "AI OCR invoice extraction",
    "Duplicate detection & risk scoring",
    "Approval workflows",
    "Vendor & analytics dashboard",
  ],
  pro: [
    "1,000 invoice uploads / month",
    "5,000 AI chat prompts / month",
    "Everything in Starter",
    "Priority support",
  ],
  enterprise: [
    "Unlimited invoice uploads",
    "Unlimited AI chat prompts",
    "Everything in Pro",
  ],
};

/* ── Payment script loader ───────────────────────────────────────────────── */
function loadCheckoutScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (document.getElementById("checkout-script")) { resolve(true); return; }
    const script = document.createElement("script");
    script.id = "checkout-script";
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

/* ── Plan Card ───────────────────────────────────────────────────────────── */
function PlanCard({
  plan,
  isPopular,
  currentSub,
  userName,
  userEmail,
  isIndia,
  onActivated,
}: {
  plan: SubscriptionPlan;
  isPopular: boolean;
  currentSub: OrganizationSubscription | null;
  userName: string;
  userEmail: string;
  isIndia: boolean;
  onActivated: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const Icon   = PLAN_ICONS[plan.slug] ?? Zap;
  const accent = PLAN_ACCENT[plan.slug];

  const isFree    = plan.slug === "free";
  const isCurrent = currentSub?.plan?.slug === plan.slug;

  // Currency routing: India → INR, everyone else → USD
  const currency: "INR" | "USD" = isIndia ? "INR" : "USD";

  // Display price based on detected region
  const displayPrice = isFree
    ? "Free"
    : isIndia
    ? plan.display_price        // e.g. "₹999"
    : plan.display_price_usd;   // e.g. "$12"

  // Secondary line (opposite currency for reference)
  const secondaryPrice = isFree
    ? null
    : isIndia
    ? plan.price_monthly_usd > 0 ? `≈ $${plan.price_monthly_usd} USD` : null
    : plan.price_monthly_inr > 0 ? `≈ ₹${plan.price_monthly_inr.toLocaleString("en-IN")} INR` : null;

  const handleUpgrade = async () => {
    if (isFree || isCurrent) return;
    setLoading(true);

    try {
      const loaded = await loadCheckoutScript();
      if (!loaded) {
        toast.error("Could not load payment checkout. Check your internet connection.");
        return;
      }

      // Pass detected currency to backend — it will use the correct Razorpay plan ID
      const { razorpay_subscription_id, key_id } = await createSubscription(plan.slug, currency);

      const rzp = new window.Razorpay({
        key: key_id,
        subscription_id: razorpay_subscription_id,

        // Branding
        name: "Orqentra — Financial OS",
        description: `${plan.name} Plan · ${displayPrice} / month`,
        image: "/favicon.ico",

        // Pre-fill with real user data from session
        prefill: {
          name:  userName,
          email: userEmail,
        },

        theme: { color: "#7c3aed" },

        // Currency for this checkout — matches the Razorpay plan
        currency,

        // Called by Razorpay after successful payment
        handler: async (response: {
          razorpay_payment_id: string;
          razorpay_subscription_id: string;
          razorpay_signature: string;
        }) => {
          try {
            await verifySubscriptionPayment(response);
            toast.success(`🎉 Upgraded to ${plan.name}! Your new limits are now active.`);
            onActivated();
          } catch {
            toast.error(
              "Payment was received but server activation failed. " +
              "Your subscription will activate automatically within minutes via webhook. " +
              "Contact support if it doesn't."
            );
          }
        },

        modal: {
          ondismiss: () => {
            toast("Checkout closed. No payment was made.", { icon: "ℹ️" });
          },
        },
      });

      rzp.open();

    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Something went wrong";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const ctaLabel = () => {
    if (loading)   return <Loader2 size={14} className="animate-spin" />;
    if (isCurrent) return <><CheckCircle2 size={14} /> Current Plan</>;
    if (isFree)    return "Free — No payment needed";
    return <>Upgrade Now <ArrowRight size={13} /></>;
  };

  return (
    <motion.div
      variants={iv}
      className="relative flex flex-col rounded-2xl overflow-hidden"
      style={{
        background: `linear-gradient(135deg, ${PLAN_GRADIENT[plan.slug]}, var(--color-bg-elevated))`,
        border: `1px solid ${isPopular ? accent : "var(--color-border)"}`,
        boxShadow: isPopular ? `0 0 48px ${accent}22` : "none",
        transition: "transform 0.2s",
      }}
      whileHover={{ y: -4 }}
    >
      {/* Popular badge */}
      {isPopular && (
        <div
          className="absolute top-0 right-0 px-3 py-1 text-xs font-bold rounded-bl-xl"
          style={{ background: accent, color: "#fff" }}
        >
          MOST POPULAR
        </div>
      )}

      {/* Header */}
      <div className="p-6 pb-4">
        <div className="flex items-center gap-3 mb-5">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: accent + "22", border: `1px solid ${accent}55` }}
          >
            <Icon size={18} style={{ color: accent }} />
          </div>
          <div>
            <p className="text-base font-bold text-white">{plan.name}</p>
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{plan.description}</p>
          </div>
        </div>

        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-black text-white">{displayPrice}</span>
          {!isFree && (
            <span className="text-sm" style={{ color: "var(--color-text-muted)" }}> / month</span>
          )}
        </div>
        {!isFree && secondaryPrice && (
          <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>
            Billed monthly ·{" "}
            <span style={{ color: "rgba(167,139,250,0.65)" }}>{secondaryPrice}</span>
          </p>
        )}
        {!isFree && !secondaryPrice && (
          <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>Billed monthly</p>
        )}
      </div>

      {/* Divider */}
      <div className="mx-6 border-t" style={{ borderColor: "var(--color-border)" }} />

      {/* Features */}
      <div className="flex-1 p-6 space-y-2.5">
        {PLAN_FEATURES[plan.slug]?.map((feat) => (
          <div key={feat} className="flex items-start gap-2">
            <CheckCircle2
              size={13}
              className="flex-shrink-0 mt-0.5"
              style={{ color: accent }}
            />
            <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              {feat}
            </span>
          </div>
        ))}
      </div>

      {/* CTA */}
      <div className="p-6 pt-0">
        <button
          id={`pricing-cta-${plan.slug}`}
          onClick={handleUpgrade}
          disabled={isFree || isCurrent || loading}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold transition-all disabled:cursor-not-allowed hover:opacity-90"
          style={{
            background: isCurrent
              ? "rgba(16,185,129,0.1)"
              : isFree
              ? "rgba(100,116,139,0.08)"
              : accent + "20",
            color: isCurrent
              ? "#10b981"
              : isFree
              ? "var(--color-text-muted)"
              : accent,
            border: `1px solid ${
              isCurrent
                ? "rgba(16,185,129,0.25)"
                : isFree
                ? "var(--color-border)"
                : accent + "44"
            }`,
            opacity: (isFree || isCurrent) ? 0.7 : 1,
          }}
        >
          {ctaLabel()}
        </button>

        {!isFree && !isCurrent && (
          <p
            className="text-center text-xs mt-2 flex items-center justify-center gap-1"
            style={{ color: "var(--color-text-muted)" }}
          >
            <ShieldCheck size={10} /> Secure Payment
          </p>
        )}
      </div>
    </motion.div>
  );
}

/* ── Page ────────────────────────────────────────────────────────────────── */
export default function PricingPage() {
  const { data: session } = useSession();
  const [plans, setPlans]           = useState<SubscriptionPlan[]>([]);
  const [currentSub, setCurrentSub] = useState<OrganizationSubscription | null>(null);
  const [loading, setLoading]       = useState(true);

  // Currency is detected by the backend from the real request IP (works with VPN)
  const [isIndia, setIsIndia] = useState(true); // default INR until backend responds

  const userName  = session?.user?.name  ?? "";
  const userEmail = session?.user?.email ?? "";

  const loadData = async () => {
    setLoading(true);
    try {
      const [plansRes, subRes] = await Promise.all([
        getPlans(),
        getCurrentSubscription().catch(() => null),
      ]);
      setPlans(plansRes.plans);
      setCurrentSub(subRes);
      // Backend detects currency from the real IP — correctly handles VPN
      setIsIndia(plansRes.detected_currency === "INR");
    } catch {
      toast.error("Failed to load pricing data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <motion.div
      variants={cv}
      initial="hidden"
      animate="show"
      className="max-w-6xl mx-auto space-y-10 py-4"
    >
      {/* Hero */}
      <motion.div variants={iv} className="text-center space-y-3">
        <div className="flex items-center justify-center gap-2 flex-wrap">
        </div>

        <h1 className="text-4xl font-black text-white">
          Simple, Transparent Pricing
        </h1>
        <p className="text-base max-w-lg mx-auto" style={{ color: "var(--color-text-secondary)" }}>
          Start free — no credit card needed.{" "}
          {isIndia
            ? "Upgrade with your preferred payment method."
            : "International cards accepted worldwide — pay in USD."}
        </p>

        {/* Current plan status */}
        {currentSub && (
          <div
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs mt-1"
            style={{
              background: "rgba(16,185,129,0.08)",
              color: "#10b981",
              border: "1px solid rgba(16,185,129,0.2)",
            }}
          >
            <CheckCircle2 size={11} />
            You are on the <strong className="ml-0.5">{currentSub.plan.name}</strong> plan
            &nbsp;·&nbsp; {currentSub.invoices_used}/{currentSub.plan.max_invoices_per_month === -1 ? "∞" : currentSub.plan.max_invoices_per_month} invoices used
            {currentSub.plan.slug === "free" && currentSub.current_period_end && (
              <>
                &nbsp;·&nbsp;
                <span style={{ color: new Date(currentSub.current_period_end) < new Date() ? "#f87171" : "#fbbf24" }}>
                  {new Date(currentSub.current_period_end) < new Date()
                    ? "Trial expired"
                    : `Trial expires ${new Date(currentSub.current_period_end).toLocaleDateString(isIndia ? "en-IN" : "en-US", { day: "numeric", month: "short", year: "numeric" })}`
                  }
                </span>
              </>
            )}
          </div>
        )}
      </motion.div>

      {/* Plan cards */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 size={32} className="animate-spin text-violet-500" />
        </div>
      ) : (
        <motion.div
          variants={cv}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5"
        >
          {plans.map((plan) => (
            <PlanCard
              key={plan.slug}
              plan={plan}
              isPopular={plan.slug === "pro"}
              currentSub={currentSub}
              userName={userName}
              userEmail={userEmail}
              isIndia={isIndia}
              onActivated={loadData}
            />
          ))}
        </motion.div>
      )}



      {/* Footer */}
      <motion.div variants={iv} className="text-center space-y-1">
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          We never store your card details. All transactions are PCI DSS compliant.
        </p>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {isIndia
            ? "Billed in INR. UPI, cards, net banking, and wallets accepted."
            : "Billed in USD. International cards accepted."}
        </p>
      </motion.div>
    </motion.div>
  );
}
