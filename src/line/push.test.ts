import { describe, it, expect } from "bun:test";
import { runAlertPush } from "./push";
import type { LineClient, LineMessage } from "./client";

interface SqlCall {
  text: string;
  values: unknown[];
}

/**
 * Mock sql: returns the candidate join rows for the SELECT, records INSERTs.
 */
function makeMockSql(candidateRows: any[]) {
  const calls: SqlCall[] = [];
  const inserts: SqlCall[] = [];
  const sql = ((strings: TemplateStringsArray, ...values: unknown[]) => {
    const text = strings.join("?");
    calls.push({ text, values });
    if (/INSERT INTO heatwave\.alerts_log/i.test(text)) {
      inserts.push({ text, values });
      return Promise.resolve([]);
    }
    if (/FROM heatwave\.forecasts/i.test(text)) {
      return Promise.resolve(candidateRows);
    }
    return Promise.resolve([]);
  }) as any;
  return { sql, calls, inserts };
}

function makeMockLine() {
  const multicasts: Array<{ to: string[]; messages: LineMessage[] }> = [];
  const line: LineClient = {
    async reply() {
      return {};
    },
    async push() {
      return {};
    },
    async multicast(to, messages) {
      multicasts.push({ to, messages });
      return {};
    },
  };
  return { line, multicasts };
}

describe("runAlertPush", () => {
  it("multicasts one message per province and logs each recipient", async () => {
    const rows = [
      { line_user_id: "U1", province_id: 2, name_th: "เชียงใหม่", target_date: "2026-05-31", risk_level: "high", min_risk_level: "high" },
      { line_user_id: "U2", province_id: 2, name_th: "เชียงใหม่", target_date: "2026-05-31", risk_level: "high", min_risk_level: "moderate" },
      { line_user_id: "U3", province_id: 1, name_th: "กรุงเทพมหานคร", target_date: "2026-05-31", risk_level: "extreme", min_risk_level: "high" },
    ];
    const { sql, inserts } = makeMockSql(rows);
    const { line, multicasts } = makeMockLine();

    const res = await runAlertPush({ sql, line });

    expect(res.provincesPushed).toBe(2);
    expect(res.messagesSent).toBe(2);
    expect(res.recipients).toBe(3);
    expect(res.logged).toBe(3);
    expect(multicasts.length).toBe(2);
    // The province-2 multicast goes to U1 + U2.
    const cmGroup = multicasts.find((m) => m.to.includes("U1"));
    expect(cmGroup?.to.sort()).toEqual(["U1", "U2"]);
    expect(cmGroup?.messages[0].type).toBe("flex");
    expect(inserts.length).toBe(3);
  });

  it("filters out rows below the subscriber's min_risk_level (numeric rank)", async () => {
    const rows = [
      // moderate < high → excluded
      { line_user_id: "U1", province_id: 2, name_th: "เชียงใหม่", target_date: "2026-05-31", risk_level: "moderate", min_risk_level: "high" },
      // high >= high → included
      { line_user_id: "U2", province_id: 2, name_th: "เชียงใหม่", target_date: "2026-05-31", risk_level: "high", min_risk_level: "high" },
    ];
    const { sql } = makeMockSql(rows);
    const { line, multicasts } = makeMockLine();

    const res = await runAlertPush({ sql, line });

    expect(res.recipients).toBe(1);
    expect(res.skipped).toBe(1);
    expect(multicasts[0].to).toEqual(["U2"]);
  });

  it("does NOT order risk levels alphabetically (extreme >= high passes)", async () => {
    // Alphabetically 'extreme' < 'high'; numeric rank must say extreme>=high.
    const rows = [
      { line_user_id: "U1", province_id: 1, name_th: "กรุงเทพมหานคร", target_date: "2026-05-31", risk_level: "extreme", min_risk_level: "high" },
    ];
    const { sql } = makeMockSql(rows);
    const { line, multicasts } = makeMockLine();
    const res = await runAlertPush({ sql, line });
    expect(res.recipients).toBe(1);
    expect(multicasts.length).toBe(1);
  });

  it("does not log sends when multicast fails", async () => {
    const rows = [
      { line_user_id: "U1", province_id: 2, name_th: "เชียงใหม่", target_date: "2026-05-31", risk_level: "high", min_risk_level: "high" },
    ];
    const { sql, inserts } = makeMockSql(rows);
    const line: LineClient = {
      async reply() { return {}; },
      async push() { return {}; },
      async multicast() { throw new Error("LINE 429"); },
    };
    const res = await runAlertPush({ sql, line });
    expect(res.messagesSent).toBe(0);
    expect(res.logged).toBe(0);
    expect(inserts.length).toBe(0);
  });

  it("returns zeros when there are no eligible rows", async () => {
    const { sql } = makeMockSql([]);
    const { line, multicasts } = makeMockLine();
    const res = await runAlertPush({ sql, line });
    expect(res.provincesPushed).toBe(0);
    expect(res.messagesSent).toBe(0);
    expect(multicasts.length).toBe(0);
  });

  it("batches recipients into groups of <=500", async () => {
    const rows = Array.from({ length: 1200 }, (_, i) => ({
      line_user_id: `U${i}`,
      province_id: 2,
      name_th: "เชียงใหม่",
      target_date: "2026-05-31",
      risk_level: "high",
      min_risk_level: "high",
    }));
    const { sql } = makeMockSql(rows);
    const { line, multicasts } = makeMockLine();
    const res = await runAlertPush({ sql, line });
    // 1200 → 500 + 500 + 200 = 3 multicast calls
    expect(multicasts.length).toBe(3);
    expect(multicasts[0].to.length).toBe(500);
    expect(multicasts[2].to.length).toBe(200);
    expect(res.recipients).toBe(1200);
  });
});
