# Calm Authority — Full App Redesign (HeatMAP-Frontend)

**Approved by user 2026-06-10.** Direction: "Calm Authority" — clean, trustworthy,
modern-government-grade. Scope: all 4 tabs (MAP / ALERTS / SAFETY / PROFILE).

## Design principles
1. **Reserved warning colour.** Warm orange `#E8702A` (and the red/amber risk ramp)
   appears ONLY where it encodes risk. Never decorative. This extends the existing
   anti-panic philosophy (calm map bands, "risk not confirmed heatwave" legend).
2. **Thai-first.** Default copy Thai, EN via existing i18n toggle.
3. **Legible authority.** Larger Thai-friendly type scale, generous spacing,
   strong heading/body contrast. No glassmorphism/gradient noise.
4. **Transparency for credibility.** Model version, data source, timestamp visible —
   designed for YSC judges as much as the public.

## Tokens (constants/theme.ts rewrite — single source)
- Navy primary `#16324F`, deep text `#10243A`, surface off-white `#F7F9FB`,
  card white `#FFFFFF`, hairline `#E3E9EF`.
- Risk ramp (calm): safe `#3E7D5B` (muted green), watch `#C98A2D` (muted amber),
  warning `#C75B39` (muted vermilion), extreme `#A93226`. Orange accent `#E8702A`.
- Radius 12, soft shadow (y2 blur8 8%), 4pt spacing grid.
- Components: `Card`, `RiskBadge`, `StatTile`, `SectionHeader`.

## Screens
- **MAP (hero):** real pan/zoom interactive map (user request 2026-06-10:
  "Google-Maps-like but OpenStreetMap to save cost"). Stack — all free:
  Leaflet (already in the app) + OSM data + CARTO Positron light tiles
  (desaturated, matches theme; free tier). Warm circles only on at-risk
  provinces (tap → popup with level + probability, fed by `/api/forecast/map`);
  navy user-location marker; floating "พื้นที่ของคุณ" card (risk %, CTA
  "ต้องทำยังไง", toggle "🛣️ เส้นทางเลี่ยง"); timestamp chip; anti-panic legend.
  **Risk-avoiding routes:** normal route (grey dashed) vs avoiding route (navy)
  around warning zones. Mockup uses hardcoded polylines; production options
  (free, OSM-based): OSRM demo server (no avoid support — needs detour
  heuristic via waypoints) or **Valhalla on FOSSGIS (`valhalla1.openstreetmap.de`,
  supports `exclude_polygons`) — preferred**, or OpenRouteService free key
  (`avoid_polygons`). Pass warning-province circles as the avoid polygons.
- **ALERTS:** two tier cards (เตือนภัย / เฝ้าระวัง) with counts + top-province
  chips; calm 7-day calendar; weather strip.
- **SAFETY:** advice cards grouped by time-of-day (ก่อนออกแดด / กลางวัน / ฉุกเฉิน),
  big icons, plain language.
- **PROFILE:** clean settings groups (จังหวัด, ภาษา, ขนาดอักษร, ธีม) + "เกี่ยวกับระบบ"
  (model lgbm-v1, แหล่งข้อมูล Open-Meteo/ERA5, นิยามคลื่นความร้อน, เวลาอัปเดต).

## Process
1. Static interactive HTML mockup (`docs/calm-authority-mockup.html`, phone frame,
   tab switching) → user review gate.
2. After approval: implementation plan (writing-plans) → per-tab implementation on
   the feat branch → lint + bun test + Playwright verify → PR to master →
   sync-frontend auto-deploys Vercel.

## Out of scope
- No backend/API changes. No new data. LIFF/checklist routes restyled only if time
  permits after the 4 tabs.
