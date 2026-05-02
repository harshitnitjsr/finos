/**
 * Creates the Auth.js required tables (users, accounts, sessions,
 * verification_token) plus the app-specific user_profiles table
 * (links users to their organisation).
 *
 * This script is idempotent — safe to run multiple times.
 * It does NOT touch the FastAPI / SQLAlchemy managed tables.
 *
 * Run with: npx tsx lib/migrate.ts
 */
import pool from "./db";

async function migrate() {
  const client = await pool.connect();
  console.log("🔗 Connected to PostgreSQL");

  try {
    await client.query("BEGIN");

    // ── Auth.js required tables ──────────────────────────────────────────────

    await client.query(`
      CREATE TABLE IF NOT EXISTS users (
        id               UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
        name             TEXT,
        email            TEXT UNIQUE,
        "emailVerified"  TIMESTAMPTZ,
        image            TEXT
      )
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS accounts (
        id                   UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
        "userId"             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        type                 TEXT NOT NULL,
        provider             TEXT NOT NULL,
        "providerAccountId"  TEXT NOT NULL,
        refresh_token        TEXT,
        access_token         TEXT,
        expires_at           BIGINT,
        id_token             TEXT,
        scope                TEXT,
        session_state        TEXT,
        token_type           TEXT,
        UNIQUE(provider, "providerAccountId")
      )
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS sessions (
        id             UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
        "sessionToken" TEXT NOT NULL UNIQUE,
        "userId"       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires        TIMESTAMPTZ NOT NULL
      )
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS verification_token (
        identifier TEXT NOT NULL,
        token      TEXT NOT NULL UNIQUE,
        expires    TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (identifier, token)
      )
    `);

    // ── App-specific: links users → organisations ────────────────────────────

    await client.query(`
      CREATE TABLE IF NOT EXISTS user_profiles (
        id                   UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
        user_id              UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        org_id               VARCHAR(36),
        role                 VARCHAR(50)  NOT NULL DEFAULT 'owner',
        onboarding_complete  BOOLEAN      NOT NULL DEFAULT FALSE,
        created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
      )
    `);

    // Ensure organisations table has an owner_user_id column (added via migration,
    // the FastAPI models create the base table on startup)
    await client.query(`
      DO $$
      BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM information_schema.columns
          WHERE table_name = 'organizations' AND column_name = 'owner_user_id'
        ) THEN
          ALTER TABLE organizations ADD COLUMN owner_user_id UUID REFERENCES users(id);
        END IF;
      END;
      $$
    `);

    // Ensure created_at / updated_at have server-side defaults on organizations
    // (FastAPI's SQLAlchemy creates the table without DEFAULT expressions)
    await client.query(`
      DO $$
      BEGIN
        BEGIN
          ALTER TABLE organizations ALTER COLUMN created_at SET DEFAULT NOW();
        EXCEPTION WHEN undefined_column THEN NULL;
        END;
        BEGIN
          ALTER TABLE organizations ALTER COLUMN updated_at SET DEFAULT NOW();
        EXCEPTION WHEN undefined_column THEN NULL;
        END;
      END;
      $$
    `);

    // Indexes
    await client.query(`CREATE INDEX IF NOT EXISTS ix_user_profiles_user_id ON user_profiles(user_id)`);
    await client.query(`CREATE INDEX IF NOT EXISTS ix_user_profiles_org_id  ON user_profiles(org_id)`);
    await client.query(`CREATE INDEX IF NOT EXISTS ix_accounts_user_id      ON accounts("userId")`);
    await client.query(`CREATE INDEX IF NOT EXISTS ix_sessions_user_id      ON sessions("userId")`);

    await client.query("COMMIT");
    console.log("✅ Auth tables migrated successfully");
  } catch (err) {
    await client.query("ROLLBACK");
    console.error("❌ Migration failed:", err);
    process.exit(1);
  } finally {
    client.release();
    await pool.end();
  }
}

migrate();
