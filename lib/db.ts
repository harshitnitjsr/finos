/**
 * Singleton PostgreSQL connection pool for the Next.js layer.
 * Connects to the same Postgres instance as the FastAPI backend.
 * Uses environment variables so it works in dev and production.
 */
import { Pool, QueryResultRow } from "pg";

declare global {
  // Prevent multiple pool instances in dev with Next.js hot-reload
  // eslint-disable-next-line no-var
  var __pgPool: Pool | undefined;
}

function createPool(): Pool {
  const connectionString = process.env.DATABASE_URL;

  if (connectionString) {
    return new Pool({ connectionString, max: 10 });
  }

  // Fallback: individual params (matching docker-compose defaults)
  return new Pool({
    host: process.env.DB_HOST ?? "localhost",
    port: parseInt(process.env.DB_PORT ?? "5433"),
    database: process.env.DB_NAME ?? "afos_db",
    user: process.env.DB_USER ?? "afos",
    password: process.env.DB_PASSWORD ?? "afos_password",
    max: 10,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 5_000,
  });
}

// In development, reuse pool across hot-reloads to avoid exhausting connections
const pool: Pool =
  process.env.NODE_ENV === "production"
    ? createPool()
    : (globalThis.__pgPool ??= createPool());

export default pool;

/**
 * Run a SQL query against PostgreSQL and return typed rows.
 * Usage: const { rows } = await query<MyRow>("SELECT ...", [params])
 */
export async function query<T extends QueryResultRow = Record<string, unknown>>(
  sql: string,
  params?: unknown[]
) {
  const client = await pool.connect();
  try {
    return await client.query<T>(sql, params);
  } finally {
    client.release();
  }
}
