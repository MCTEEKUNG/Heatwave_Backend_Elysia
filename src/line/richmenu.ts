/**
 * Rich menu setup script.
 *
 *   bun run src/line/richmenu.ts
 *
 * Creates the 6-cell Heatwave-AI rich menu via the LINE Messaging API, uploads
 * no image here (image upload is a separate manual/automated step), and sets it
 * as the default rich menu.
 *
 * GUARD: if LINE_CHANNEL_ACCESS_TOKEN is unset, prints guidance and exits 0 so
 * CI / dry runs never fail. Does NOT make real calls unless the token is set.
 *
 * Layout (2500 x 1686, 3 columns x 2 rows):
 *   ┌───────────────┬───────────────┬───────────────┐
 *   │ พยากรณ์วันนี้   │ 7 วันข้างหน้า  │ ตั้งค่าพื้นที่    │
 *   ├───────────────┼───────────────┼───────────────┤
 *   │ แผนที่ (LIFF)  │ คู่มือรับมือ    │ แชร์           │
 *   └───────────────┴───────────────┴───────────────┘
 */

const W = 2500;
const H = 1686;
const COL = Math.floor(W / 3); // 833
const ROW = Math.floor(H / 2); // 843

const LIFF_ID = process.env.LIFF_ID || "<LIFF_ID>";

interface RichMenuArea {
  bounds: { x: number; y: number; width: number; height: number };
  action: Record<string, unknown>;
}

function cell(col: number, row: number, action: Record<string, unknown>): RichMenuArea {
  return {
    bounds: { x: col * COL, y: row * ROW, width: COL, height: ROW },
    action,
  };
}

export const RICH_MENU = {
  size: { width: W, height: H },
  selected: true,
  name: "heatwave-main",
  chatBarText: "เมนู Heatwave",
  areas: [
    cell(0, 0, { type: "postback", label: "พยากรณ์วันนี้", data: "action=forecast_today", displayText: "พยากรณ์วันนี้" }),
    cell(1, 0, { type: "postback", label: "7 วันข้างหน้า", data: "action=forecast_week", displayText: "พยากรณ์ 7 วัน" }),
    cell(2, 0, { type: "postback", label: "ตั้งค่าพื้นที่", data: "action=set_area", displayText: "ตั้งค่าพื้นที่" }),
    cell(0, 1, { type: "uri", label: "แผนที่", uri: `https://liff.line.me/${LIFF_ID}` }),
    cell(1, 1, { type: "postback", label: "คู่มือรับมือความร้อน", data: "action=guide", displayText: "คู่มือรับมือความร้อน" }),
    cell(2, 1, { type: "uri", label: "แชร์", uri: "https://line.me/R/nv/recommendOA/@heatwave" }),
  ] satisfies RichMenuArea[],
};

async function main() {
  const token = process.env.LINE_CHANNEL_ACCESS_TOKEN;
  if (!token) {
    console.log(
      "[richmenu] LINE_CHANNEL_ACCESS_TOKEN is not set.\n" +
        "           Set LINE_CHANNEL_ACCESS_TOKEN (and optionally LIFF_ID) to create\n" +
        "           the rich menu, then run:  bun run src/line/richmenu.ts\n" +
        "           After creation, upload a 2500x1686 PNG/JPEG image and set it as default.\n" +
        "           Skipping (no real API call)."
    );
    console.log("[richmenu] Menu definition that WOULD be created:");
    console.log(JSON.stringify(RICH_MENU, null, 2));
    process.exit(0);
  }

  const base = "https://api.line.me";
  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  console.log("[richmenu] Creating rich menu...");
  const createRes = await fetch(`${base}/v2/bot/richmenu`, {
    method: "POST",
    headers,
    body: JSON.stringify(RICH_MENU),
  });
  if (!createRes.ok) {
    console.error(`[richmenu] create failed: ${createRes.status} ${await createRes.text()}`);
    process.exit(1);
  }
  const { richMenuId } = (await createRes.json()) as { richMenuId: string };
  console.log(`[richmenu] created: ${richMenuId}`);

  console.log(
    "[richmenu] NOTE: upload a 2500x1686 image to\n" +
      `           POST https://api-data.line.me/v2/bot/richmenu/${richMenuId}/content\n` +
      "           (Content-Type image/png or image/jpeg) before it can display."
  );

  console.log("[richmenu] Setting as default rich menu...");
  const setRes = await fetch(`${base}/v2/bot/user/all/richmenu/${richMenuId}`, {
    method: "POST",
    headers,
  });
  if (!setRes.ok) {
    console.error(`[richmenu] set default failed: ${setRes.status} ${await setRes.text()}`);
    process.exit(1);
  }
  console.log("[richmenu] default rich menu set. Done.");
  process.exit(0);
}

// Run only when executed directly (not when imported by tests).
if (import.meta.main) {
  main();
}
