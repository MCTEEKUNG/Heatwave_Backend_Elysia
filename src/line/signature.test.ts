import { describe, it, expect } from "bun:test";
import { createHmac } from "crypto";
import { verifySignature } from "./signature";

const SECRET = "test-channel-secret";

function sign(body: string, secret = SECRET): string {
  return createHmac("sha256", secret).update(body, "utf8").digest("base64");
}

describe("verifySignature", () => {
  it("accepts a correct HMAC-SHA256 base64 signature", () => {
    const body = JSON.stringify({ events: [], destination: "x" });
    expect(verifySignature(body, sign(body), SECRET)).toBe(true);
  });

  it("rejects a tampered body", () => {
    const body = JSON.stringify({ events: [], destination: "x" });
    const sig = sign(body);
    expect(verifySignature(body + " ", sig, SECRET)).toBe(false);
  });

  it("rejects a signature made with a different secret", () => {
    const body = "{}";
    expect(verifySignature(body, sign(body, "other"), SECRET)).toBe(false);
  });

  it("rejects a wrong-length signature without throwing", () => {
    const body = "{}";
    expect(verifySignature(body, "short", SECRET)).toBe(false);
  });

  it("rejects when the header is missing", () => {
    expect(verifySignature("{}", null, SECRET)).toBe(false);
    expect(verifySignature("{}", undefined, SECRET)).toBe(false);
  });

  it("rejects when the secret is missing", () => {
    expect(verifySignature("{}", sign("{}"), "")).toBe(false);
  });

  it("is sensitive to the exact raw bytes (no re-serialization)", () => {
    // Two JSON strings that parse equal but differ in whitespace must differ.
    const a = '{"a":1}';
    const b = '{ "a": 1 }';
    const sigA = sign(a);
    expect(verifySignature(a, sigA, SECRET)).toBe(true);
    expect(verifySignature(b, sigA, SECRET)).toBe(false);
  });
});
