/**
 * /api/backend/[...path] — Secure proxy to the FastAPI backend.
 *
 * - Authenticates the request via Auth.js session
 * - Injects X-Org-ID and X-User-ID headers so FastAPI can scope
 *   all queries to the correct organisation without hardcoding
 * - Strips cookies before forwarding (backend doesn't need them)
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

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
  const url = `${BACKEND}/api/v1/${backendPath}${search}`;

  // Build forwarded headers
  const headers = new Headers();
  headers.set("Content-Type", req.headers.get("Content-Type") ?? "application/json");
  headers.set("Accept", "application/json");

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

  const bodyBuffer =
    req.method !== "GET" && req.method !== "HEAD"
      ? Buffer.from(await req.arrayBuffer())
      : undefined;

  const backendRes = await fetch(url, {
    method: req.method,
    headers,
    body: bodyBuffer,
  });

  const resBody = await backendRes.arrayBuffer();

  return new NextResponse(resBody, {
    status: backendRes.status,
    headers: {
      "Content-Type":
        backendRes.headers.get("Content-Type") ?? "application/json",
    },
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
