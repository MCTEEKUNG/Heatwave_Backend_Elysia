/**
 * LINE Flex / text message builders.
 *
 * These return plain message objects (no network). The webhook and push modules
 * pass them to the LINE client. Kept dependency-free so they're trivially
 * testable and reusable.
 */

import type { LineMessage } from "./client";

export type RiskLevel = "low" | "moderate" | "high" | "extreme";

/** Numeric rank for comparing risk levels (low < moderate < high < extreme). */
export const RISK_RANK: Record<RiskLevel, number> = {
  low: 0,
  moderate: 1,
  high: 2,
  extreme: 3,
};

export function riskRank(level: string): number {
  return RISK_RANK[(level as RiskLevel)] ?? -1;
}

const RISK_META: Record<RiskLevel, { th: string; color: string; emoji: string }> = {
  low: { th: "ต่ำ", color: "#2E7D32", emoji: "🟢" },
  moderate: { th: "ปานกลาง", color: "#F9A825", emoji: "🟡" },
  high: { th: "สูง", color: "#EF6C00", emoji: "🟠" },
  extreme: { th: "รุนแรง", color: "#C62828", emoji: "🔴" },
};

function riskMeta(level: string) {
  return RISK_META[(level as RiskLevel)] ?? { th: level, color: "#607D8B", emoji: "⚪" };
}

export interface ForecastDay {
  target_date: string | Date;
  risk_level: string;
  probability?: number | string | null;
  swbgt_pred?: number | string | null;
}

function fmtDate(d: string | Date): string {
  const date = typeof d === "string" ? new Date(d) : d;
  if (isNaN(date.getTime())) return String(d);
  // YYYY-MM-DD (UTC-safe slice of ISO)
  return date.toISOString().slice(0, 10);
}

function fmtPct(p: number | string | null | undefined): string {
  if (p === null || p === undefined) return "-";
  const n = typeof p === "string" ? parseFloat(p) : p;
  if (!Number.isFinite(n)) return "-";
  return `${Math.round(n * 100)}%`;
}

/**
 * Flex bubble showing a multi-day forecast for one province.
 */
export function forecastFlex(provinceName: string, days: ForecastDay[]): LineMessage {
  const rows = days.map((d) => {
    const meta = riskMeta(d.risk_level);
    return {
      type: "box",
      layout: "horizontal",
      contents: [
        {
          type: "text",
          text: fmtDate(d.target_date),
          size: "sm",
          color: "#555555",
          flex: 4,
        },
        {
          type: "text",
          text: `${meta.emoji} ${meta.th}`,
          size: "sm",
          color: meta.color,
          weight: "bold",
          flex: 4,
          align: "center",
        },
        {
          type: "text",
          text: fmtPct(d.probability),
          size: "sm",
          color: "#555555",
          flex: 2,
          align: "end",
        },
      ],
    };
  });

  return {
    type: "flex",
    altText: `พยากรณ์คลื่นความร้อน ${provinceName}`,
    contents: {
      type: "bubble",
      header: {
        type: "box",
        layout: "vertical",
        contents: [
          { type: "text", text: "พยากรณ์คลื่นความร้อน", color: "#FFFFFF", size: "sm" },
          { type: "text", text: provinceName, color: "#FFFFFF", size: "xl", weight: "bold" },
        ],
        backgroundColor: "#EF6C00",
        paddingAll: "16px",
      },
      body: {
        type: "box",
        layout: "vertical",
        spacing: "sm",
        contents:
          rows.length > 0
            ? rows
            : [{ type: "text", text: "ยังไม่มีข้อมูลพยากรณ์", size: "sm", color: "#999999" }],
      },
      footer: {
        type: "box",
        layout: "vertical",
        contents: [
          {
            type: "text",
            text: "ความเสี่ยง = โอกาสเกิดวันคลื่นความร้อน",
            size: "xxs",
            color: "#AAAAAA",
            wrap: true,
          },
        ],
      },
    },
  };
}

/**
 * Flex bubble for a single-day alert push.
 */
export function alertFlex(
  provinceName: string,
  date: string | Date,
  riskLevel: string
): LineMessage {
  const meta = riskMeta(riskLevel);
  return {
    type: "flex",
    altText: `เตือนภัยคลื่นความร้อน ${provinceName} (${meta.th}) ${fmtDate(date)}`,
    contents: {
      type: "bubble",
      header: {
        type: "box",
        layout: "vertical",
        contents: [
          { type: "text", text: `${meta.emoji} เตือนภัยคลื่นความร้อน`, color: "#FFFFFF", weight: "bold" },
        ],
        backgroundColor: meta.color,
        paddingAll: "16px",
      },
      body: {
        type: "box",
        layout: "vertical",
        spacing: "md",
        contents: [
          { type: "text", text: provinceName, size: "xl", weight: "bold" },
          {
            type: "box",
            layout: "baseline",
            contents: [
              { type: "text", text: "วันที่", size: "sm", color: "#888888", flex: 2 },
              { type: "text", text: fmtDate(date), size: "sm", flex: 5 },
            ],
          },
          {
            type: "box",
            layout: "baseline",
            contents: [
              { type: "text", text: "ระดับ", size: "sm", color: "#888888", flex: 2 },
              { type: "text", text: meta.th, size: "sm", weight: "bold", color: meta.color, flex: 5 },
            ],
          },
          {
            type: "text",
            text: "ดื่มน้ำให้เพียงพอ หลีกเลี่ยงกิจกรรมกลางแจ้งช่วงแดดจัด และดูแลกลุ่มเปราะบาง",
            size: "sm",
            color: "#555555",
            wrap: true,
          },
        ],
      },
    },
  };
}

/** Plain text helper. */
export function textMessage(text: string): LineMessage {
  return { type: "text", text };
}
