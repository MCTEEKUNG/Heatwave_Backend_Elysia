import postgres, { type Sql } from "postgres";

/**
 * Direct Postgres connection layer for the private `heatwave` schema.
 *
 * IMPORTANT: The `heatwave` schema is NOT exposed to Supabase's Data API
 * (PostgREST), so supabase-js cannot read it. We connect to Postgres directly
 * using the `postgres` package and a `DATABASE_URL` (the Supabase connection
 * string / pooler). All queries are parameterized SQL against `heatwave.*`.
 *
 * The client is created lazily so that simply importing this module does NOT
 * throw when `DATABASE_URL` is unset (the smoke test relies on this).
 */

let _sql: Sql | null = null;

/** Returns true if a DATABASE_URL is configured. */
export function hasDatabaseUrl(): boolean {
  return Boolean(process.env.DATABASE_URL);
}

/**
 * Returns the singleton postgres client, constructing it on first use.
 * Throws a clear error if DATABASE_URL is not set.
 */
export function getSql(): Sql {
  if (_sql) return _sql;

  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error(
      "DATABASE_URL is not set. Provide the Supabase Postgres connection string (pooler) so the backend can query the private `heatwave` schema."
    );
  }

  // `prepare: false` is required for the Supabase transaction-mode pooler
  // (port 6543 / pgBouncer), which does not support prepared statements.
  // `ssl: 'require'` ensures TLS even if the URL omits sslmode.
  _sql = postgres(url, {
    prepare: false,
    ssl: "require",
    max: 5,
    idle_timeout: 20,
    connect_timeout: 15,
  });

  return _sql;
}

/** Closes the singleton connection (used by scripts / graceful shutdown). */
export async function closeSql(): Promise<void> {
  if (_sql) {
    await _sql.end({ timeout: 5 });
    _sql = null;
  }
}
