/**
 * Type-safe API client for subscription endpoints.
 * All calls go through the Next.js secure proxy /api/backend → FastAPI.
 */
import { apiFetch } from "@/lib/api";

export interface SubscriptionPlan {
  id: string;
  slug: "free" | "starter" | "pro" | "enterprise";
  name: string;
  description: string;
  price_monthly_inr: number;
  price_monthly_usd: number;       // 0 for free
  display_price: string;           // e.g. "₹999"
  display_price_usd: string;       // e.g. "$12"
  razorpay_plan_id: string | null;
  razorpay_plan_id_usd: string | null;
  max_invoices_per_month: number;
  max_prompts_per_month: number;
  sort_order: number;
}

export interface OrganizationSubscription {
  id: string;
  org_id: string;
  status: "free" | "active" | "past_due" | "cancelled" | "paused";
  plan: SubscriptionPlan;
  razorpay_subscription_id: string | null;
  billing_currency: "INR" | "USD";  // currency used at checkout
  current_period_start: string | null;
  current_period_end: string | null;
  invoices_used: number;
  prompts_used: number;
  created_at: string;
}

export interface CreateSubscriptionResponse {
  razorpay_subscription_id: string;
  short_url: string;
  plan: SubscriptionPlan;
  key_id: string;
}

/** Fetch all available plans (public, no auth needed) */
export async function getPlans(): Promise<{
  plans: SubscriptionPlan[];
  detected_currency: "INR" | "USD";  // backend-detected from caller IP
}> {
  return apiFetch("/subscriptions/plans");
}

/** Fetch current org's subscription + usage */
export async function getCurrentSubscription(): Promise<OrganizationSubscription> {
  return apiFetch("/subscriptions/current");
}

/** Create a Razorpay subscription for a plan slug.
 *  currency: "INR" for India, "USD" for international (default: "INR")
 */
export async function createSubscription(
  plan_slug: string,
  currency: "INR" | "USD" = "INR"
): Promise<CreateSubscriptionResponse> {
  return apiFetch("/subscriptions/create", {
    method: "POST",
    body: JSON.stringify({ plan_slug, currency }),
  });
}

/** Verify Razorpay payment signature (called after user pays) */
export async function verifySubscriptionPayment(params: {
  razorpay_payment_id: string;
  razorpay_subscription_id: string;
  razorpay_signature: string;
}): Promise<{ status: string; subscription_id: string }> {
  return apiFetch("/subscriptions/verify", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

/** Cancel the active subscription */
export async function cancelSubscription(): Promise<{ status: string }> {
  return apiFetch("/subscriptions/cancel", { method: "POST" });
}
