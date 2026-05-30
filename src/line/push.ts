/**
 * Alert push job.
 *
 * Finds tomorrow's forecasts whose `risk_level` meets each subscriber's
 * `min_risk_level`, groups recipients by province, multicasts one province-
 * specific alert flex, and records each send in `alerts_log` for idempotency.
 *
 * Risk levels are compared by NUMERIC RANK (low<moderate<high<extreme), not by
 * text — a plain SQL string compare would order them alphabetically (wrong).
 *
 * Dependency-injected with `{ sql, line }` for testability.
 */

import type { Sql } from "postgres";
import type { LineClient } from "./client";
import { alertFlex, riskRank } from "./flex";

export interface PushDeps {
  sql: Sql;
  line: LineClient;
}

export interface PushResult {
  target_date: string;
  provincesPushed: number;
  messagesSent: number;
  recipients: number;
  logged: number;
  skipped: number;
}

const MULTICAST_BATCH = 500; // LINE multicast hard limit per call.

interface CandidateRow {
  line_user_id: string;
  province_id: number;
  name_th: string;
  target_date: string;
  risk_level: string;
  min_risk_level: string;
}

function chunk<T>(arr: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

function dateKey(d: string | Date): string {
  if (d instanceof Date) return d.toISOString().slice(0, 10);
  return String(d).slice(0, 10);
}

/**
 * Run the alert push for tomorrow (relative to DB `current_date`).
 *
 * Selection: latest forecast batch per province whose target_date = tomorrow,
 * joined to active subscriptions, excluding (user, province, date) rows that
 * already exist in alerts_log. Final risk>=min_risk filtering is done in TS by
 * numeric rank so the comparison is correct regardless of SQL collation.
 */
export async function runAlertPush(deps: PushDeps): Promise<PushResult> {
  const { sql, line } = deps;

  const rows = (await sql`
    SELECT s.line_user_id,
           f.province_id,
           p.name_th,
           f.target_date,
           f.risk_level,
           s.min_risk_level
    FROM heatwave.forecasts f
    JOIN heatwave.subscriptions s
      ON s.province_id = f.province_id AND s.active = true
    JOIN heatwave.provinces p
      ON p.id = f.province_id
    WHERE f.target_date = current_date + 1
      AND f.generated_at = (
        SELECT MAX(generated_at) FROM heatwave.forecasts f2
        WHERE f2.province_id = f.province_id
      )
      AND NOT EXISTS (
        SELECT 1 FROM heatwave.alerts_log a
        WHERE a.line_user_id = s.line_user_id
          AND a.province_id = f.province_id
          AND a.target_date = f.target_date
      )
  `) as unknown as CandidateRow[];

  // Keep only rows meeting the subscriber's threshold (numeric rank compare).
  const eligible = rows.filter(
    (r) => riskRank(r.risk_level) >= riskRank(r.min_risk_level)
  );

  // Group eligible recipients by province (+ its single target_date / risk).
  interface Group {
    province_id: number;
    name_th: string;
    target_date: string;
    risk_level: string;
    users: string[];
  }
  const groups = new Map<number, Group>();
  for (const r of eligible) {
    let g = groups.get(r.province_id);
    if (!g) {
      g = {
        province_id: r.province_id,
        name_th: r.name_th,
        target_date: dateKey(r.target_date),
        risk_level: r.risk_level,
        users: [],
      };
      groups.set(r.province_id, g);
    }
    g.users.push(r.line_user_id);
  }

  let provincesPushed = 0;
  let messagesSent = 0;
  let recipients = 0;
  let logged = 0;

  for (const g of groups.values()) {
    if (g.users.length === 0) continue;
    const flex = alertFlex(g.name_th, g.target_date, g.risk_level);

    for (const batch of chunk(g.users, MULTICAST_BATCH)) {
      let messageId: string | null = null;
      try {
        await line.multicast(batch, [flex]);
        messagesSent += 1;
        recipients += batch.length;
        // multicast returns no per-recipient id; line_message_id stays null.
      } catch (err: any) {
        console.error(
          `[line.push] multicast failed for province ${g.province_id}:`,
          err?.message ?? err
        );
        continue; // do not log sends that did not go out
      }

      // Record each recipient for idempotency (skip duplicates defensively).
      for (const uid of batch) {
        try {
          await sql`
            INSERT INTO heatwave.alerts_log
              (line_user_id, province_id, target_date, risk_level, line_message_id)
            VALUES (${uid}, ${g.province_id}, ${g.target_date}, ${g.risk_level}, ${messageId})
            ON CONFLICT (line_user_id, province_id, target_date) DO NOTHING
          `;
          logged += 1;
        } catch (err: any) {
          console.error(
            `[line.push] alerts_log insert failed for ${uid}/${g.province_id}:`,
            err?.message ?? err
          );
        }
      }
    }
    provincesPushed += 1;
  }

  const target_date =
    eligible.length > 0 ? dateKey(eligible[0].target_date) : "";

  return {
    target_date,
    provincesPushed,
    messagesSent,
    recipients,
    logged,
    skipped: rows.length - eligible.length,
  };
}
