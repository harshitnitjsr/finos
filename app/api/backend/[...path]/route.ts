/**
 * /api/backend/[...path] — Secure proxy to the FastAPI backend.
 *
 * - Authenticates the request via Auth.js session
 * - Injects X-Org-ID and X-User-ID headers so FastAPI can scope
 *   all queries to the correct organisation without hardcoding
 * - Strips cookies before forwarding (backend doesn't need them)
 * - Passes SSE (text/event-stream) responses through without buffering
 *   so streaming endpoints work correctly
 *
 * CRITICAL: `dynamic = 'force-dynamic'` prevents Next.js from buffering
 * the upstream response. Without this, SSE streams are collected in full
 * before being delivered to the client, breaking all streaming.
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

// Force dynamic rendering — prevents response caching/buffering
export const dynamic = "force-dynamic";
// Node.js runtime required because Auth.js relies on native Node crypto modules
export const runtime = "nodejs";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function handler(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const session = await auth();

  // All backend routes require authentication
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { path } = await params;
  const backendPath = path.join("/");
  const search = req.nextUrl.search ?? "";
  const hasTrailingSlash = req.nextUrl.pathname.endsWith("/");
  const finalPath = hasTrailingSlash ? `${backendPath}/` : backendPath;
  const url = `${BACKEND}/api/v1/${finalPath}${search}`;

  // Build forwarded headers
  const headers = new Headers();
  headers.set("Content-Type", req.headers.get("Content-Type") ?? "application/json");
  headers.set("Accept", req.headers.get("Accept") ?? "application/json");

  // Org context — injected server-side from JWT, cannot be spoofed by clients
  if (session.user.orgId) {
    headers.set("X-Org-ID", session.user.orgId);
  }
  headers.set("X-User-ID", session.user.id);
  headers.set("X-User-Email", session.user.email ?? "");

  // Internal auth token — proves this request came from Next.js server, not a
  // direct client call. FastAPI validates this with constant-time comparison.
  const internalToken = process.env.BACKEND_API_SECRET || "f5664602f7550f18456e3a4dce2d6789f6edeb2d3c01d6ff0ea231749654d585";
  if (internalToken) {
    headers.set("X-Internal-Token", internalToken);
  }

  const bodyData = req.method !== "GET" && req.method !== "HEAD" ? await req.blob() : undefined;

  const backendRes = await fetch(url, {
    method: req.method,
    headers,
    body: bodyData,
    cache: "no-store", // CRITICAL: disables Next.js internal fetch caching/buffering
  });

  const contentType = backendRes.headers.get("Content-Type") ?? "application/json";

  // ── SSE / streaming pass-through ──────────────────────────────────────────
  // Do NOT buffer text/event-stream — pipe the body directly so tokens
  // reach the browser as they are generated.
  if (contentType.includes("text/event-stream")) {
    return new NextResponse(backendRes.body, {
      status: backendRes.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  }

  // ── Standard JSON / binary responses ──────────────────────────────────────
  const resBody = await backendRes.arrayBuffer();

  return new NextResponse(resBody, {
    status: backendRes.status,
    headers: {
      "Content-Type": contentType,
    },
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
