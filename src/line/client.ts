/**
 * Thin LINE Messaging API client using `fetch` (no SDK).
 *
 * Reads the channel access token from `LINE_CHANNEL_ACCESS_TOKEN` unless one is
 * passed explicitly (handy for tests). All methods POST JSON to api.line.me and
 * return the parsed JSON response (or throw on a non-2xx with the body text).
 */

const LINE_API = "https://api.line.me";

export interface LineMessage {
  type: string;
  [key: string]: unknown;
}

export interface LineClient {
  reply(replyToken: string, messages: LineMessage[]): Promise<unknown>;
  push(to: string, messages: LineMessage[]): Promise<unknown>;
  multicast(to: string[], messages: LineMessage[]): Promise<unknown>;
}

export interface LineClientOptions {
  accessToken?: string;
  /** Override for tests; defaults to global fetch. */
  fetchImpl?: typeof fetch;
  baseUrl?: string;
}

export function createLineClient(opts: LineClientOptions = {}): LineClient {
  const token = opts.accessToken ?? process.env.LINE_CHANNEL_ACCESS_TOKEN ?? "";
  const doFetch = opts.fetchImpl ?? fetch;
  const base = opts.baseUrl ?? LINE_API;

  async function post(path: string, payload: unknown): Promise<unknown> {
    if (!token) {
      throw new Error(
        "LINE_CHANNEL_ACCESS_TOKEN is not set — cannot call the LINE Messaging API."
      );
    }
    const res = await doFetch(`${base}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`LINE API ${path} failed: ${res.status} ${text}`);
    }
    // Some endpoints return empty bodies; guard JSON parsing.
    const text = await res.text().catch(() => "");
    return text ? JSON.parse(text) : {};
  }

  return {
    reply(replyToken, messages) {
      return post("/v2/bot/message/reply", { replyToken, messages });
    },
    push(to, messages) {
      return post("/v2/bot/message/push", { to, messages });
    },
    multicast(to, messages) {
      // LINE multicast accepts up to 500 recipient ids per call.
      return post("/v2/bot/message/multicast", { to, messages });
    },
  };
}
