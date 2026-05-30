/**
 * Integration test for the SHIPPED webhook route in src/index.ts: raw-body
 * handling + signature verification at the Elysia layer, exercised via the real
 * exported `app` with `app.handle()` (no socket, no real LINE).
 *
 * The channel secret is set before importing index.ts so the route's
 * `process.env.LINE_CHANNEL_SECRET` lookup sees it. No DATABASE_URL is set, so
 * event handling that needs the DB throws internally — the route catches it and
 * still returns 200 (LINE must not see a 5xx). The 401 path needs no DB at all.
 */
import { describe, it, expect, beforeAll } from "bun:test";
import { createHmac } from "crypto";

const SECRET = "route-secret";
process.env.LINE_CHANNEL_SECRET = SECRET;
// Ensure no DB is configured for this test process.
delete process.env.DATABASE_URL;

// Import AFTER setting env so the module reads the secret at request time
// (it reads process.env per-request, but be explicit about ordering anyway).
let app: { handle: (req: Request) => Promise<Response> };
beforeAll(async () => {
  ({ app } = (await import("../index")) as any);
});

function sign(body: string): string {
  return createHmac("sha256", SECRET).update(body, "utf8").digest("base64");
}

function req(body: string, signature: string | null) {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (signature !== null) headers["x-line-signature"] = signature;
  return new Request("http://localhost/api/line/webhook", {
    method: "POST",
    headers,
    body,
  });
}

describe("POST /api/line/webhook (real app)", () => {
  it("returns 200 for a valid signature with empty events", async () => {
    const body = JSON.stringify({ destination: "x", events: [] });
    const res = await app.handle(req(body, sign(body)));
    expect(res.status).toBe(200);
    const json: any = await res.json();
    expect(json.ok).toBe(true);
    expect(json.handled).toBe(0);
  });

  it("returns 401 for a bad signature (one char flipped)", async () => {
    const body = JSON.stringify({ destination: "x", events: [] });
    const good = sign(body);
    const bad = (good[0] === "A" ? "B" : "A") + good.slice(1);
    const res = await app.handle(req(body, bad));
    expect(res.status).toBe(401);
  });

  it("returns 401 when the signature header is missing", async () => {
    const res = await app.handle(req("{}", null));
    expect(res.status).toBe(401);
  });

  it("returns 401 when the body is tampered after signing", async () => {
    const body = JSON.stringify({ events: [] });
    const sig = sign(body);
    const res = await app.handle(req(body + " ", sig));
    expect(res.status).toBe(401);
  });

  it("still returns 200 (not 5xx) when event handling needs the DB but it is absent", async () => {
    // Valid signature + a real event → getSql() throws (no DATABASE_URL) →
    // route catches and returns 200 so LINE does not retry.
    const body = JSON.stringify({
      events: [{ type: "follow", replyToken: "rt", source: { userId: "U1" } }],
    });
    const res = await app.handle(req(body, sign(body)));
    expect(res.status).toBe(200);
  });

  it("does not regress other JSON POST routes (/api/predict still parses JSON)", async () => {
    // /api/predict uses Elysia's auto JSON body; the per-route raw `parse` on the
    // webhook must not affect it. We expect a normal (non-401) JSON response.
    const res = await app.handle(
      new Request("http://localhost/api/predict", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ model: "balanced_rf", inputData: "a,b\n1,2" }),
      })
    );
    // It will fail to actually run python here, but the body must have parsed
    // (status 200 with a JSON result object, not a 400 validation error).
    expect(res.status).toBe(200);
    const json: any = await res.json();
    expect(json).toHaveProperty("success");
    expect(json.model).toBe("balanced_rf");
  });
});
