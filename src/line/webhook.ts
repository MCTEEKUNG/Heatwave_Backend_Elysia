/**
 * LINE webhook event routing.
 *
 * `handleEvents` is dependency-injected with `{ sql, line }` so it is unit
 * testable with a mocked tagged-template `sql` and a mocked LINE client.
 *
 * Supported events:
 *  - follow         → greet + prompt to set a province (quick replies)
 *  - message.text   → match a Thai/English province name → reply 7-day forecast
 *  - message.location → nearest province → reply forecast
 *  - postback       → set_province / subscribe → upsert line_users / subscriptions
 */

import type { Sql } from "postgres";
import type { LineClient } from "./client";
import { forecastFlex, textMessage, type ForecastDay } from "./flex";
import { nearestProvince, type ProvincePoint } from "./nearest";

export interface WebhookDeps {
  sql: Sql;
  line: LineClient;
}

// --- Minimal LINE event types (only the fields we use) ---
export interface LineEvent {
  type: string;
  replyToken?: string;
  source?: { userId?: string; type?: string };
  message?: {
    type: string;
    text?: string;
    latitude?: number;
    longitude?: number;
  };
  postback?: { data?: string };
}

interface ProvinceRow extends ProvincePoint {
  code?: string;
}

const FORECAST_DAYS = 7;

/** Parse a postback `data` string of `key=value&key2=value2` into a map. */
export function parsePostback(data: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const part of data.split("&")) {
    if (!part) continue;
    const idx = part.indexOf("=");
    if (idx === -1) {
      out[decodeURIComponent(part)] = "";
    } else {
      out[decodeURIComponent(part.slice(0, idx))] = decodeURIComponent(part.slice(idx + 1));
    }
  }
  return out;
}

function normalize(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, "");
}

/** Find a province whose Thai or English name matches the text (loose). */
export function matchProvinceByName(
  text: string,
  provinces: ProvinceRow[]
): ProvinceRow | null {
  const q = normalize(text);
  if (!q) return null;
  // Exact (normalized) match first.
  for (const p of provinces) {
    if (normalize(p.name_th) === q || normalize(p.name_en) === q) return p;
  }
  // Then containment either direction (e.g. "จังหวัดเชียงใหม่" / "chiang mai province").
  for (const p of provinces) {
    const th = normalize(p.name_th);
    const en = normalize(p.name_en);
    if (q.includes(th) || th.includes(q) || q.includes(en) || en.includes(q)) {
      return p;
    }
  }
  return null;
}

async function loadProvinces(sql: Sql): Promise<ProvinceRow[]> {
  const rows = await sql`
    SELECT id, name_th, name_en, lat, lon
    FROM heatwave.provinces
    ORDER BY id ASC
  `;
  return rows as unknown as ProvinceRow[];
}

async function loadForecast(sql: Sql, provinceId: number): Promise<ForecastDay[]> {
  const rows = await sql`
    SELECT target_date, risk_level, probability, swbgt_pred
    FROM heatwave.forecasts
    WHERE province_id = ${provinceId}
      AND generated_at = (
        SELECT MAX(generated_at) FROM heatwave.forecasts WHERE province_id = ${provinceId}
      )
      AND target_date >= current_date
    ORDER BY target_date ASC
    LIMIT ${FORECAST_DAYS}
  `;
  return rows as unknown as ForecastDay[];
}

async function upsertUser(sql: Sql, userId: string): Promise<void> {
  await sql`
    INSERT INTO heatwave.line_users (line_user_id)
    VALUES (${userId})
    ON CONFLICT (line_user_id) DO NOTHING
  `;
}

async function setDefaultProvince(
  sql: Sql,
  userId: string,
  provinceId: number
): Promise<void> {
  await sql`
    INSERT INTO heatwave.line_users (line_user_id, default_province_id)
    VALUES (${userId}, ${provinceId})
    ON CONFLICT (line_user_id)
    DO UPDATE SET default_province_id = ${provinceId}
  `;
}

async function subscribe(
  sql: Sql,
  userId: string,
  provinceId: number,
  minRisk: string
): Promise<void> {
  await sql`
    INSERT INTO heatwave.subscriptions (line_user_id, province_id, min_risk_level, active)
    VALUES (${userId}, ${provinceId}, ${minRisk}, true)
    ON CONFLICT (line_user_id, province_id)
    DO UPDATE SET min_risk_level = ${minRisk}, active = true
  `;
}

async function replyForecast(
  deps: WebhookDeps,
  replyToken: string,
  province: ProvinceRow
): Promise<void> {
  const days = await loadForecast(deps.sql, province.id);
  await deps.line.reply(replyToken, [forecastFlex(province.name_th, days)]);
}

const GREETING =
  "สวัสดีค่ะ! ยินดีต้อนรับสู่ Heatwave-AI 🌡️\n" +
  "พิมพ์ชื่อจังหวัด หรือส่งตำแหน่งที่ตั้ง (location) เพื่อดูพยากรณ์คลื่นความร้อน 7 วันข้างหน้า\n" +
  "หรือพิมพ์ชื่อจังหวัดที่ต้องการตั้งเป็นพื้นที่หลักได้เลยค่ะ";

/** Route a single event. Errors are caught by the caller. */
async function handleEvent(deps: WebhookDeps, event: LineEvent): Promise<void> {
  const { sql, line } = deps;
  const userId = event.source?.userId;

  switch (event.type) {
    case "follow": {
      if (userId) await upsertUser(sql, userId);
      if (event.replyToken) {
        await line.reply(event.replyToken, [textMessage(GREETING)]);
      }
      return;
    }

    case "message": {
      const msg = event.message;
      if (!msg || !event.replyToken) return;

      if (msg.type === "location" && msg.latitude != null && msg.longitude != null) {
        const provinces = await loadProvinces(sql);
        const nearest = nearestProvince(msg.latitude, msg.longitude, provinces) as
          | ProvinceRow
          | null;
        if (nearest) {
          await replyForecast(deps, event.replyToken, nearest);
        } else {
          await line.reply(event.replyToken, [
            textMessage("ไม่พบจังหวัดที่ใกล้เคียงตำแหน่งของคุณค่ะ"),
          ]);
        }
        return;
      }

      if (msg.type === "text" && msg.text) {
        const provinces = await loadProvinces(sql);
        const matched = matchProvinceByName(msg.text, provinces);
        if (matched) {
          await replyForecast(deps, event.replyToken, matched);
        } else {
          await line.reply(event.replyToken, [
            textMessage(
              `ไม่พบจังหวัด "${msg.text}" ค่ะ ลองพิมพ์ชื่อจังหวัดเป็นภาษาไทย เช่น "เชียงใหม่"`
            ),
          ]);
        }
        return;
      }
      return;
    }

    case "postback": {
      const data = event.postback?.data ?? "";
      const params = parsePostback(data);
      const action = params.action;

      if (!userId) return;

      if (action === "set_province" && params.province_id) {
        const pid = Number(params.province_id);
        if (Number.isInteger(pid)) {
          await setDefaultProvince(sql, userId, pid);
          if (event.replyToken) {
            await line.reply(event.replyToken, [
              textMessage("ตั้งจังหวัดหลักเรียบร้อยแล้วค่ะ ✅"),
            ]);
          }
        }
        return;
      }

      if (action === "subscribe" && params.province_id) {
        const pid = Number(params.province_id);
        const minRisk = params.min_risk_level || "high";
        if (Number.isInteger(pid)) {
          await upsertUser(sql, userId);
          await subscribe(sql, userId, pid, minRisk);
          if (event.replyToken) {
            await line.reply(event.replyToken, [
              textMessage(`สมัครรับการแจ้งเตือนแล้วค่ะ 🔔 (ระดับ ${minRisk} ขึ้นไป)`),
            ]);
          }
        }
        return;
      }
      return;
    }

    default:
      return;
  }
}

/**
 * Handle a batch of webhook events. Each event is processed independently;
 * an error in one event does not abort the others (LINE retries non-2xx, so we
 * must not let a single failing event sink the whole webhook response).
 *
 * @returns per-event results for observability/testing.
 */
export async function handleEvents(
  deps: WebhookDeps,
  events: LineEvent[]
): Promise<Array<{ ok: boolean; type: string; error?: string }>> {
  const results: Array<{ ok: boolean; type: string; error?: string }> = [];
  for (const event of events) {
    try {
      await handleEvent(deps, event);
      results.push({ ok: true, type: event.type });
    } catch (err: any) {
      console.error(`[line.webhook] event '${event.type}' failed:`, err?.message ?? err);
      results.push({ ok: false, type: event.type, error: err?.message ?? String(err) });
    }
  }
  return results;
}
