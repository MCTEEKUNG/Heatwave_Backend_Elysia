/**
 * CLI entry to run the alert push job (intended for the post-forecast cron).
 *
 *   bun run src/line/push.run.ts
 *
 * GUARD: requires both DATABASE_URL and LINE_CHANNEL_ACCESS_TOKEN. If either is
 * missing it prints guidance and exits 0 (so dry runs / CI never fail). This
 * file does NOT call LINE unless the token is set.
 */
import { hasDatabaseUrl, getSql, closeSql } from "../db";
import { createLineClient } from "./client";
import { runAlertPush } from "./push";

async function main() {
  const hasToken = Boolean(process.env.LINE_CHANNEL_ACCESS_TOKEN);
  if (!hasDatabaseUrl() || !hasToken) {
    console.log(
      "[push] Missing config — skipping (exit 0).\n" +
        `        DATABASE_URL set: ${hasDatabaseUrl()}\n` +
        `        LINE_CHANNEL_ACCESS_TOKEN set: ${hasToken}\n` +
        "        Set both to run the alert push against the heatwave DB + LINE API."
    );
    process.exit(0);
  }

  try {
    const sql = getSql();
    const line = createLineClient();
    const result = await runAlertPush({ sql, line });
    console.log("[push] done:", JSON.stringify(result));
  } catch (err: any) {
    console.error("[push] FAILED —", err?.message ?? err);
    await closeSql();
    process.exit(1);
  }
  await closeSql();
  process.exit(0);
}

if (import.meta.main) {
  main();
}
