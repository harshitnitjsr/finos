/**
 * POST /api/onboarding — Creates the organisation in PostgreSQL and links
 *                         it to the authenticated user via user_profiles.
 * GET  /api/onboarding — Returns the current user's org + onboarding status.
 *
 * This writes directly to the same `organizations` table that FastAPI uses,
 * so the backend immediately picks up the org_id from session headers.
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";
import { randomUUID } from "crypto";

/* ── helpers ──────────────────────────────────────────────────────────────── */

function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .slice(0, 80);
}

async function uniqueSlug(base: string): Promise<string> {
  let slug = slugify(base);
  let suffix = 0;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const candidate = suffix === 0 ? slug : `${slug}-${suffix}`;
    const { rows } = await query(
      "SELECT id FROM organizations WHERE slug = $1 LIMIT 1",
      [candidate]
    );
    if (rows.length === 0) return candidate;
    suffix++;
  }
}

/* ── GET ──────────────────────────────────────────────────────────────────── */

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { rows } = await query(
    `SELECT up.org_id, up.onboarding_complete, up.role,
            o.name AS org_name, o.default_currency, o.fiscal_year_start,
            o.settings
     FROM   user_profiles up
     LEFT JOIN organizations o ON o.id = up.org_id
     WHERE  up.user_id = $1
     LIMIT  1`,
    [session.user.id]
  );

  if (rows.length === 0) {
    return NextResponse.json({ onboardingComplete: false });
  }

  const r = rows[0];
  return NextResponse.json({
    onboardingComplete: r.onboarding_complete,
    orgId: r.org_id,
    orgName: r.org_name,
    defaultCurrency: r.default_currency,
    fiscalYearStart: r.fiscal_year_start,
    role: r.role,
    settings: r.settings,
  });
}

/* ── POST ─────────────────────────────────────────────────────────────────── */

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  const {
    orgName,
    industry,
    companySize,
    defaultCurrency = "USD",
    fiscalYearStart = 1,
  } = body as {
    orgName?: string;
    industry?: string;
    companySize?: string;
    defaultCurrency?: string;
    fiscalYearStart?: number;
  };

  if (!orgName?.trim()) {
    return NextResponse.json(
      { error: "Organisation name is required" },
      { status: 400 }
    );
  }

  const userId = session.user.id;

  // ── Prevent duplicate onboarding ──────────────────────────────────────────
  const existing = await query(
    `SELECT org_id FROM user_profiles WHERE user_id = $1 AND onboarding_complete = TRUE LIMIT 1`,
    [userId]
  );
  if (existing.rows.length > 0) {
    const orgId = existing.rows[0].org_id as string;
    const orgRow = await query("SELECT name FROM organizations WHERE id = $1", [orgId]);
    return NextResponse.json({
      ok: true,
      orgId,
      orgName: orgRow.rows[0]?.name ?? orgName,
      onboardingComplete: true,
    });
  }

  // ── Create organisation ───────────────────────────────────────────────────
  const orgId = randomUUID();
  const slug = await uniqueSlug(orgName);

  await query(
    `INSERT INTO organizations
       (id, name, slug, default_currency, fiscal_year_start, owner_user_id, settings)
     VALUES ($1, $2, $3, $4, $5, $6, $7)
     ON CONFLICT (slug) DO NOTHING`,
    [
      orgId,
      orgName.trim(),
      slug,
      defaultCurrency,
      fiscalYearStart,
      userId,
      JSON.stringify({ industry, companySize }),
    ]
  );

  // ── Upsert user profile (links user → org) ────────────────────────────────
  await query(
    `INSERT INTO user_profiles (user_id, org_id, onboarding_complete, role, created_at, updated_at)
     VALUES ($1, $2, TRUE, 'owner', NOW(), NOW())
     ON CONFLICT (user_id)
     DO UPDATE SET org_id = $2, onboarding_complete = TRUE, updated_at = NOW()`,
    [userId, orgId]
  );

  return NextResponse.json({
    ok: true,
    orgId,
    orgName: orgName.trim(),
    onboardingComplete: true,
  });
}
