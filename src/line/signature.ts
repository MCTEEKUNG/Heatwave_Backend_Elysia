import { createHmac, timingSafeEqual } from "crypto";

/**
 * Verify a LINE webhook request signature.
 *
 * LINE signs the *raw* request body with HMAC-SHA256 using the channel secret
 * and sends the base64-encoded digest in the `X-Line-Signature` header. We
 * recompute it over the same raw body and compare in constant time.
 *
 * @param rawBody         the exact raw request body string (must NOT be re-serialized)
 * @param signatureHeader the value of the `x-line-signature` header
 * @param channelSecret   the LINE channel secret
 * @returns true if the signature is valid
 */
export function verifySignature(
  rawBody: string,
  signatureHeader: string | null | undefined,
  channelSecret: string | null | undefined
): boolean {
  if (!signatureHeader || !channelSecret) return false;

  const expected = createHmac("sha256", channelSecret)
    .update(rawBody, "utf8")
    .digest("base64");

  const a = Buffer.from(expected, "utf8");
  const b = Buffer.from(signatureHeader, "utf8");

  // timingSafeEqual throws on length mismatch; guard first.
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}
