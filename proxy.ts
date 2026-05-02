/**
 * Next.js Middleware — Route Protection
 *
 * Guards three classes of routes:
 *   1. PROTECTED (/dashboard, /invoices, etc.)
 *      → unauthenticated  → /auth/signin
 *      → no org yet       → /onboarding
 *
 *   2. ONBOARDING (/onboarding)
 *      → already onboarded → /dashboard
 *      → not logged in     → /auth/signin
 *
 *   3. INTERNAL API PROXY (/api/backend/*)
 *      → unauthenticated → 401 JSON (so client gets a clean error)
 *      Note: /api/auth/* is always excluded (Auth.js own routes)
 *
 * Public routes (/, /auth/*, /api/auth/*) pass through untouched.
 */
import { auth } from "@/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const { nextUrl } = req;
  const session = req.auth;
  const isLoggedIn = !!session?.user;
  const onboarded = session?.user?.onboardingComplete ?? false;

  const path = nextUrl.pathname;

  // ── 1. Internal API proxy — must be authenticated ──────────────────────
  if (path.startsWith("/api/backend/")) {
    if (!isLoggedIn) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    if (!onboarded) {
      return NextResponse.json({ error: "Onboarding required" }, { status: 403 });
    }
    return NextResponse.next();
  }

  // ── 2. Dashboard & all protected app routes ─────────────────────────────
  const isProtected =
    path.startsWith("/dashboard") ||
    path.startsWith("/invoices") ||
    path.startsWith("/expenses") ||
    path.startsWith("/approvals") ||
    path.startsWith("/workflows") ||
    path.startsWith("/agents") ||
    path.startsWith("/treasury") ||
    path.startsWith("/analytics") ||
    path.startsWith("/settings") ||
    path.startsWith("/vendors");

  if (isProtected) {
    if (!isLoggedIn) {
      const signIn = new URL("/auth/signin", nextUrl);
      signIn.searchParams.set("callbackUrl", path);
      return NextResponse.redirect(signIn);
    }
    if (!onboarded) {
      return NextResponse.redirect(new URL("/onboarding", nextUrl));
    }
    return NextResponse.next();
  }

  // ── 3. Onboarding page ──────────────────────────────────────────────────
  if (path.startsWith("/onboarding")) {
    if (!isLoggedIn) {
      return NextResponse.redirect(new URL("/auth/signin", nextUrl));
    }
    if (onboarded) {
      return NextResponse.redirect(new URL("/dashboard", nextUrl));
    }
    return NextResponse.next();
  }

  // Everything else (/, /auth/signin) — allow through
  return NextResponse.next();
});

export const config = {
  matcher: [
    /*
     * Match all paths EXCEPT:
     * - _next/static  (static assets)
     * - _next/image   (image optimisation)
     * - favicon.ico, robots.txt
     * - Files with a static extension (images, fonts, etc.)
     * - /api/auth/*   (Auth.js built-in endpoints — must never be intercepted)
     */
    "/((?!_next/static|_next/image|favicon.ico|robots.txt|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|woff2?|ttf)|api/auth).*)",
  ],
};
