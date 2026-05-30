/**
 * Smoke test for the DB connection layer.
 *
 *   bun run src/smoke.ts
 *
 * - If DATABASE_URL is NOT set: prints clear guidance and exits 0 (does not fail).
 * - If DATABASE_URL is set: connects and runs
 *     select count(*) from heatwave.provinces
 *   to prove the direct-Postgres path to the private `heatwave` schema works.
 */

import { hasDatabaseUrl, getSql, closeSql } from "./db";

async function main() {
  if (!hasDatabaseUrl()) {
    console.log(
      "[smoke] DATABASE_URL is not set.\n" +
        "        Set DATABASE_URL to the Supabase Postgres connection string (pooler)\n" +
        "        to enable the backend's access to the private `heatwave` schema, e.g.:\n" +
        "          DATABASE_URL=postgresql://postgres.<ref>:<pw>@<host>:6543/postgres?sslmode=require\n" +
        "        Skipping connection test."
    );
    process.exit(0);
  }

  console.log("[smoke] DATABASE_URL set — attempting connection to heatwave schema...");
  try {
    const sql = getSql();
    const rows = await sql`SELECT count(*)::int AS count FROM heatwave.provinces`;
    console.log(`[smoke] OK — heatwave.provinces has ${rows[0].count} rows.`);
  } catch (err: any) {
    console.error(`[smoke] FAILED — ${err.message}`);
    await closeSql();
    process.exit(1);
  }

  await closeSql();
  process.exit(0);
}

main();
