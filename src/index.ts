import { Elysia } from "elysia";
import { cors } from "@elysiajs/cors";
import {
  getProvinces,
  getProvinceForecast,
  getForecastMap,
  getThresholds,
} from "./routes/forecast";
import { getSql } from "./db";
import { verifySignature } from "./line/signature";
import { createLineClient } from "./line/client";
import { handleEvents, type LineEvent } from "./line/webhook";

// CORS whitelist from env (comma-separated). Falls back to a sensible local
// default when ALLOWED_ORIGINS is unset so the app never crashes on boot.
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || "")
  .split(",")
  .map((o) => o.trim())
  .filter(Boolean);
const corsOrigin: string[] | boolean =
  ALLOWED_ORIGINS.length > 0 ? ALLOWED_ORIGINS : ["http://localhost:3000"];

export const app = new Elysia()
  .use(cors({ origin: corsOrigin }))
  .get("/", () => ({
    service: "Heatwave AI Backend",
    version: "1.0.0",
    status: "running"
  }))

  .get("/api/health", () => ({
    status: "healthy",
    timestamp: new Date().toISOString()
  }))

  // --- Phase 3: Forecast Service API (private `heatwave` schema via postgres) ---

  .get("/api/provinces", async ({ set }) => {
    try {
      const rows = await getProvinces();
      return rows;
    } catch (error: any) {
      set.status = 503;
      return { error: error.message };
    }
  })

  .get("/api/forecast/province/:id", async ({ params, query, set }) => {
    const id = Number(params.id);
    if (!Number.isInteger(id) || id <= 0) {
      set.status = 400;
      return { error: "Invalid province id" };
    }
    let days = Number(query.days ?? 7);
    if (!Number.isInteger(days) || days <= 0) days = 7;
    if (days > 16) days = 16;

    try {
      const rows = await getProvinceForecast(id, days);
      return rows;
    } catch (error: any) {
      set.status = 503;
      return { error: error.message };
    }
  })

  .get("/api/forecast/map", async ({ set }) => {
    try {
      const rows = await getForecastMap();
      return rows;
    } catch (error: any) {
      set.status = 503;
      return { error: error.message };
    }
  })

  .get("/api/thresholds/:id", async ({ params, set }) => {
    const id = Number(params.id);
    if (!Number.isInteger(id) || id <= 0) {
      set.status = 400;
      return { error: "Invalid province id" };
    }
    try {
      const rows = await getThresholds(id);
      return { province_id: id, thresholds: rows };
    } catch (error: any) {
      set.status = 503;
      return { error: error.message };
    }
  })

  // --- Phase 4: LINE Messaging API webhook ---
  //
  // LINE signs the RAW request body with HMAC-SHA256 (channel secret). We must
  // verify against the exact bytes received, so a per-route `parse` hook returns
  // the body as a raw string (this does NOT affect the JSON parsing of other
  // POST routes).
  //
  // Returns 401 only on signature mismatch. For valid requests we always return
  // 200 quickly (even if individual event handling errors) so LINE does not
  // retry — errors are caught and logged inside handleEvents.
  .post(
    "/api/line/webhook",
    async ({ body, headers, set }) => {
      const rawBody = typeof body === "string" ? body : "";
      const signature = headers["x-line-signature"];
      const channelSecret = process.env.LINE_CHANNEL_SECRET || "";

      if (!verifySignature(rawBody, signature, channelSecret)) {
        set.status = 401;
        return { error: "Invalid signature" };
      }

      // Parse the verified raw body.
      let events: LineEvent[] = [];
      try {
        const parsed = JSON.parse(rawBody || "{}");
        events = Array.isArray(parsed.events) ? parsed.events : [];
      } catch {
        // Body verified but not JSON — ack with 200 so LINE does not retry.
        set.status = 200;
        return { ok: true, handled: 0 };
      }

      if (events.length === 0) {
        return { ok: true, handled: 0 };
      }

      try {
        const sql = getSql();
        const line = createLineClient();
        const results = await handleEvents({ sql, line }, events);
        return { ok: true, handled: results.length };
      } catch (error: any) {
        // Never surface 5xx to LINE for a transient backend issue (e.g. DB or
        // LINE client misconfig). LINE retries non-2xx, so we ack with 200.
        console.error("[line.webhook] fatal:", error?.message ?? error);
        set.status = 200;
        return { ok: false, handled: 0 };
      }
    },
    {
      // Deliver the raw request body as a string for this route only.
      parse: async ({ request }) => await request.text(),
    }
  );

// Start the server only when this file is run directly (not when imported by
// tests). `import.meta.main` is true under `bun run src/index.ts` and in the
// Docker entrypoint, so deployment behaviour is unchanged.
if (import.meta.main) {
  app.listen(process.env.PORT || 3000);
  console.log(
    `🦊 Heatwave AI Backend running at ${app.server?.hostname}:${app.server?.port}`
  );
}
