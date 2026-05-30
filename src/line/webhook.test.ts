import { describe, it, expect } from "bun:test";
import { handleEvents, matchProvinceByName, parsePostback, type LineEvent } from "./webhook";
import type { LineClient, LineMessage } from "./client";

const PROVINCES = [
  { id: 1, name_th: "กรุงเทพมหานคร", name_en: "Bangkok", lat: 13.7563, lon: 100.5018 },
  { id: 2, name_th: "เชียงใหม่", name_en: "Chiang Mai", lat: 18.7883, lon: 98.9853 },
];

const FORECAST = [
  { target_date: "2026-05-31", risk_level: "high", probability: 0.7, swbgt_pred: 33 },
  { target_date: "2026-06-01", risk_level: "moderate", probability: 0.4, swbgt_pred: 31 },
];

interface SqlCall {
  text: string;
  values: unknown[];
}

/**
 * Build a mock tagged-template `sql` that records calls and returns canned rows
 * based on simple substring matching of the SQL text.
 */
function makeMockSql() {
  const calls: SqlCall[] = [];
  const sql = ((strings: TemplateStringsArray, ...values: unknown[]) => {
    const text = strings.join("?");
    calls.push({ text, values });
    if (/FROM heatwave\.provinces/i.test(text)) {
      return Promise.resolve(PROVINCES);
    }
    if (/FROM heatwave\.forecasts/i.test(text)) {
      return Promise.resolve(FORECAST);
    }
    // INSERT / UPDATE statements
    return Promise.resolve([]);
  }) as any;
  return { sql, calls };
}

function makeMockLine() {
  const replies: Array<{ replyToken: string; messages: LineMessage[] }> = [];
  const pushes: Array<{ to: string; messages: LineMessage[] }> = [];
  const multicasts: Array<{ to: string[]; messages: LineMessage[] }> = [];
  const line: LineClient = {
    async reply(replyToken, messages) {
      replies.push({ replyToken, messages });
      return {};
    },
    async push(to, messages) {
      pushes.push({ to, messages });
      return {};
    },
    async multicast(to, messages) {
      multicasts.push({ to, messages });
      return {};
    },
  };
  return { line, replies, pushes, multicasts };
}

describe("parsePostback", () => {
  it("parses key=value pairs", () => {
    expect(parsePostback("action=subscribe&province_id=2&min_risk_level=high")).toEqual({
      action: "subscribe",
      province_id: "2",
      min_risk_level: "high",
    });
  });
  it("decodes URI components", () => {
    expect(parsePostback("name=%E0%B9%80%E0%B8%8A%E0%B8%B5%E0%B8%A2%E0%B8%87")).toEqual({
      name: "เชียง",
    });
  });
});

describe("matchProvinceByName", () => {
  it("matches Thai exact", () => {
    expect(matchProvinceByName("เชียงใหม่", PROVINCES)?.id).toBe(2);
  });
  it("matches English case-insensitive", () => {
    expect(matchProvinceByName("BANGKOK", PROVINCES)?.id).toBe(1);
  });
  it("matches with extra words", () => {
    expect(matchProvinceByName("จังหวัดเชียงใหม่", PROVINCES)?.id).toBe(2);
  });
  it("returns null for unknown", () => {
    expect(matchProvinceByName("xyz", PROVINCES)).toBeNull();
  });
});

describe("handleEvents", () => {
  it("greets and upserts user on follow", async () => {
    const { sql, calls } = makeMockSql();
    const { line, replies } = makeMockLine();
    const events: LineEvent[] = [
      { type: "follow", replyToken: "rt1", source: { userId: "U1" } },
    ];
    const res = await handleEvents({ sql, line }, events);
    expect(res[0].ok).toBe(true);
    expect(replies.length).toBe(1);
    expect(replies[0].messages[0].type).toBe("text");
    expect(calls.some((c) => /INSERT INTO heatwave\.line_users/i.test(c.text))).toBe(true);
  });

  it("replies forecast for a text province name", async () => {
    const { sql } = makeMockSql();
    const { line, replies } = makeMockLine();
    const events: LineEvent[] = [
      {
        type: "message",
        replyToken: "rt2",
        source: { userId: "U1" },
        message: { type: "text", text: "เชียงใหม่" },
      },
    ];
    await handleEvents({ sql, line }, events);
    expect(replies.length).toBe(1);
    expect(replies[0].messages[0].type).toBe("flex");
    expect(replies[0].messages[0].altText).toContain("เชียงใหม่");
  });

  it("replies a not-found text message for an unknown province", async () => {
    const { sql } = makeMockSql();
    const { line, replies } = makeMockLine();
    const events: LineEvent[] = [
      {
        type: "message",
        replyToken: "rt3",
        source: { userId: "U1" },
        message: { type: "text", text: "นครนอกโลก" },
      },
    ];
    await handleEvents({ sql, line }, events);
    expect(replies[0].messages[0].type).toBe("text");
  });

  it("resolves nearest province for a location message", async () => {
    const { sql } = makeMockSql();
    const { line, replies } = makeMockLine();
    const events: LineEvent[] = [
      {
        type: "message",
        replyToken: "rt4",
        source: { userId: "U1" },
        message: { type: "location", latitude: 18.7, longitude: 99.0 },
      },
    ];
    await handleEvents({ sql, line }, events);
    expect(replies[0].messages[0].type).toBe("flex");
    expect(replies[0].messages[0].altText).toContain("เชียงใหม่");
  });

  it("sets default province on set_province postback", async () => {
    const { sql, calls } = makeMockSql();
    const { line, replies } = makeMockLine();
    const events: LineEvent[] = [
      {
        type: "postback",
        replyToken: "rt5",
        source: { userId: "U1" },
        postback: { data: "action=set_province&province_id=2" },
      },
    ];
    await handleEvents({ sql, line }, events);
    expect(calls.some((c) => /default_province_id/i.test(c.text))).toBe(true);
    expect(replies.length).toBe(1);
  });

  it("subscribes on subscribe postback", async () => {
    const { sql, calls } = makeMockSql();
    const { line } = makeMockLine();
    const events: LineEvent[] = [
      {
        type: "postback",
        source: { userId: "U1" },
        postback: { data: "action=subscribe&province_id=2&min_risk_level=extreme" },
      },
    ];
    await handleEvents({ sql, line }, events);
    const subCall = calls.find((c) => /INSERT INTO heatwave\.subscriptions/i.test(c.text));
    expect(subCall).toBeDefined();
    expect(subCall!.values).toContain("extreme");
    expect(subCall!.values).toContain("U1");
  });

  it("isolates errors: one failing event does not abort others", async () => {
    // sql throws for the forecast lookup, succeeds elsewhere.
    const calls: SqlCall[] = [];
    const sql = ((strings: TemplateStringsArray, ...values: unknown[]) => {
      const text = strings.join("?");
      calls.push({ text, values });
      if (/FROM heatwave\.provinces/i.test(text)) return Promise.resolve(PROVINCES);
      if (/FROM heatwave\.forecasts/i.test(text)) return Promise.reject(new Error("db down"));
      return Promise.resolve([]);
    }) as any;
    const { line, replies } = makeMockLine();
    const events: LineEvent[] = [
      { type: "message", replyToken: "a", source: { userId: "U1" }, message: { type: "text", text: "เชียงใหม่" } },
      { type: "follow", replyToken: "b", source: { userId: "U2" } },
    ];
    const res = await handleEvents({ sql, line }, events);
    expect(res[0].ok).toBe(false);
    expect(res[1].ok).toBe(true);
    // follow greeting still delivered
    expect(replies.some((r) => r.replyToken === "b")).toBe(true);
  });
});
