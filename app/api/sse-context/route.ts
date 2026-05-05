/**
 * /api/sse-context — Lightweight endpoint to return session context for SSE.
 *
 * The browser can't use the full /api/backend proxy for SSE because Vercel's
 * Node.js serverless functions have a 10-second timeout — which kills long-
 * lived streaming connections.
 *
 * Solution: SSE consumers call this endpoint first (fast, < 100ms) to get the
 * org/user context + internal token, then open the SSE connection DIRECTLY to
 * the FastAPI backend, bypassing Vercel entirely. The stream has no timeout.
 */
import { auth } from "@/auth";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  const session = await auth();

  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  return NextResponse.json({
    orgId:     session.user.orgId   ?? "",
    userId:    session.user.id      ?? "",
    userEmail: session.user.email   ?? "",
    token:     process.env.BACKEND_API_SECRET ?? "",
  });
}
