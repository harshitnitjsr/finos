import { handlers } from "@/auth";

// Re-export Auth.js v5 handlers for the App Router
// The type cast is required because next-auth@5 beta ships types for Next.js 14/15
// but the runtime behaviour is fully compatible with Next.js 16.
export const GET = handlers.GET as unknown as (req: Request) => Promise<Response>;
export const POST = handlers.POST as unknown as (req: Request) => Promise<Response>;
