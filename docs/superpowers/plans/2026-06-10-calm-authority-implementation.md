# Calm Authority — React Native Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the user-approved Calm Authority redesign (spec:
`docs/superpowers/specs/2026-06-10-calm-authority-redesign-design.md`, visual
reference: `docs/calm-authority-mockup.html`) in `HeatMAP-Frontend/` — all 4
screens + floating liquid-glass tab bar + province-choropleth hero map + Trip
Advisor.

**Architecture:** Token-first: rewrite VALUES in `constants/theme.ts` while
keeping export names so the app never breaks mid-migration. Then one shared
`GlassTabBar` replaces the 4 duplicated per-screen bottom navs. Then screen-by-
screen restyle (MAP → ALERTS → SAFETY → PROFILE), web-first (Vercel is the
judged surface; native degrades gracefully). Trip Advisor last (most net-new).

**Tech Stack:** Expo 55 / RN 0.83 / expo-router 55 / react-leaflet 5 (web map)
/ react-native-maps (native) / reanimated 4. Fonts via @expo-google-fonts.

---

## Pre-verified facts (2026-06-10 — do not re-derive)

- Native Tabs bar is HIDDEN (`tabBarStyle:{display:'none'}` in
  `app/(tabs)/_layout.tsx`); each of `app/(tabs)/{map,alerts,settings}.tsx` +
  `app/checklist.tsx` renders its own bottom nav via `BottomNavStyle` from
  `constants/theme.ts` (e.g. map.tsx:536-538). SAFETY tab = `/checklist`
  (outside the (tabs) group), PROFILE = `/settings`.
- `constants/theme.ts` (474 lines) exports: `DesignTokens`, `Breakpoints`,
  `useResponsive`, `Colors` (light/dark), `GlassStyle`, `BottomNavStyle`
  (+ possibly more — grep before editing). Old theme = "Warm Minimal" orange
  `#E67E22` glassmorphism. Screens import these names everywhere → KEEP NAMES.
- File sizes: map.tsx 895, alerts.tsx 825, checklist.tsx 718, settings.tsx 563,
  theme.ts 474, components/map/MapGrid.tsx 501.
- Deps already present: leaflet 1.9.4 + react-leaflet 5 (web map), @types/leaflet,
  react-native-maps (native), expo-haptics, reanimated. NOT present: expo-blur,
  Thai fonts (@expo-google-fonts has inter/open-sans/space-grotesk only).
- Web map already Leaflet (live site shows "Leaflet | © OpenStreetMap").
- Backend data: `GET /api/forecast/map` → per-province rows incl. `province_id,
  probability, risk_level, model_version, generated_at`; `/api/provinces` has
  `name_th, name_en, region, lat, lon`. Prod URL in `HeatMAP-Frontend/.env`
  (`EXPO_PUBLIC_API_URL=https://heatwave-backend-elysia.onrender.com`).
- Choropleth boundaries: `https://raw.githubusercontent.com/apisit/thailand.json/master/thailand.json`
  (1.2 MB, 77 features, `properties.name` = **English** province name → join on
  `provinces.name_en`; verify odd spellings e.g. "Phangnga", "Lop Buri" at runtime;
  fall back to circle markers for unmatched names).
- Design tokens (from spec): navy `#16324F`, deep text `#10243A`, navy-soft
  `#3D5A77`, bg `#F7F9FB`, card `#FFFFFF`, hairline `#E3E9EF`, muted `#6B7C8D`;
  risk ramp safe `#3E7D5B` / watch `#C98A2D` / warning `#C75B39` / extreme
  `#A93226`; accent `#E8702A` (risk-only). Radius 12. Fonts: display
  "Bai Jamjuree", body "Anuphan".
- Trip Advisor decision (user-approved): NO route-avoidance. Show (1) warning
  provinces crossed + clock time, (2) departure-time shift out of 11:00–16:00
  peak, (3) rest advisory. Routing: OSRM public demo
  `https://router.project-osrm.org/route/v1/driving/{lon},{lat};{lon},{lat}?overview=full&geometries=geojson`
  (free, no key). Zone test = point-in-polygon of sampled route coords vs
  warning-province GeoJSON polygons.

## Verify loop (every task)

```powershell
cd HeatMAP-Frontend ; bun run lint        # must be 0 errors
# visual (web): bunx expo start --web --port 8082 (CI=1) → Playwright on http://localhost:8082
```
Commit per task to `feat/clean-era5-ndvi-dataset`. Deploy happens ONLY at the
end via PR to master (sync-frontend.yml auto-pushes to Vercel) — user-gated.

---

### Task 1: Calm Authority tokens (theme.ts values; names unchanged)

- [ ] Grep all exports of `constants/theme.ts` and all `DesignTokens.X` usages to know the full surface.
- [ ] Rewrite values: primaryColor→`#16324F`; secondaryColor→`#3D5A77`; accentColor→`#E8702A`; severityColors {extreme:`#A93226`, medium:`#C98A2D`, low:`#3E7D5B`} + add `warning:'#C75B39'`; text/surface/border per token table above; `Colors.light` background `#F7F9FB`, tint navy; `Colors.dark` = navy-deep surfaces (desaturated, not inverted). Update `GlassStyle`/`BottomNavStyle` to the glass recipe (white .58–.9, border rgba(255,255,255,.7), shadow rgba(16,36,58,.18)).
- [ ] Add `RiskColors` + `RiskBg` named exports (safe/watch/warning/extreme + soft backgrounds `#EAF3EE #F8F0E1 #F8E9E3 #F5E3E1`) and `Fonts = { display:'BaiJamjuree_700Bold', displaySemi:'BaiJamjuree_600SemiBold', body:'Anuphan_400Regular', bodyMedium:'Anuphan_500Medium', bodySemi:'Anuphan_600SemiBold' }`.
- [ ] `bun run lint` → 0 errors; commit `design(theme): Calm Authority tokens`.

### Task 2: Thai fonts

- [ ] `bun add @expo-google-fonts/anuphan @expo-google-fonts/bai-jamjuree`
- [ ] In `app/_layout.tsx` (root): load via `useFonts` ({Anuphan_400Regular,_500Medium,_600SemiBold} + {BaiJamjuree_600SemiBold,_700Bold}) alongside existing fonts; keep splash until loaded (follow existing pattern).
- [ ] Lint + visual spot-check; commit `design(fonts): Anuphan body + Bai Jamjuree display`.

### Task 3: Shared floating GlassTabBar

**Files:** Create `components/ui/GlassTabBar.tsx`; modify the 4 screens to use it (delete their per-screen bottomNav blocks + related styles).

- [ ] Component: `usePathname()`+`router.replace` navigation; 4 items (แผนที่ `/map`, แจ้งเตือน `/alerts`, ปลอดภัย `/checklist`, โปรไฟล์ `/settings`); absolute bottom 14 / left 16 / right 16, height 64, borderRadius 999; glass = `Platform.OS==='web'` ? `{backgroundColor:'rgba(255,255,255,.58)', backdropFilter:'blur(18px) saturate(170%)'}` (cast style as any for web-only prop) : `{backgroundColor:'rgba(255,255,255,.92)'}`; border 1px rgba(255,255,255,.72); navy sliding pill behind active item (Reanimated `withSpring` translateX, index*itemWidth), active icon/label white, inactive `#3D5A77`; icons = existing `IconSymbol`/@expo/vector-icons (map/bell/shield/person), labels 10px `Fonts.bodySemi`; min hit 44pt; haptics on press (expo-haptics, native only).
- [ ] Replace in map.tsx, alerts.tsx, settings.tsx, checklist.tsx: render `<GlassTabBar/>` last in the screen root; remove old bottomNav JSX + styles; screens' scroll content adds bottom padding ~104.
- [ ] Lint; Playwright web check (bar floats, pill slides, content scrolls beneath); commit `design(nav): shared floating liquid-glass tab bar`.

### Task 4: MAP hero — full-bleed + province choropleth

**Files:** Modify `app/(tabs)/map.tsx` + `components/map/*` (web path).

- [ ] Web map full-bleed: container absolute inset 0 (StyleSheet.absoluteFill); tiles → CARTO Positron `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png` attribution '© OpenStreetMap, © CARTO'.
- [ ] Choropleth: fetch thailand.json once (module-level cache); build name_en→{risk_level,probability,name_th} from existing forecast-map data (risk_level: map server tiers to safe/watch/warning/extreme ramp); `<GeoJSON>` styled per province (risk: fill lvColor .32 / stroke #fff 1; neutral: fill #7E93A6 .04 / stroke #B3C4D2 .6); popup = name_th + ระดับ + %; unmatched names → keep existing marker fallback + console.warn.
- [ ] Floating UI per mockup: hero-pill "แผนที่ความเสี่ยง · 77 จังหวัด" (top-left, glass), tier chip top-right (count of watch+ provinces), user card bottom (above tab bar, glass, bottom:92): location name, ระดับ + โอกาส %, CTA "ต้องทำยังไง" → /checklist, "🧭 วางแผนเดินทาง" button (Task 7 wires it; until then hidden behind `TRIP_ADVISOR_ENABLED=false` const), minilegend 4 dots + anti-panic note.
- [ ] Native (react-native-maps) minimal parity: keep existing behavior; only re-skin overlays with new tokens (no choropleth on native this pass — note as TODO).
- [ ] Lint + Playwright (choropleth visible, popups work, card floats); commit `feat(map): full-bleed hero + 77-province choropleth (web)`.

### Task 5: ALERTS restyle

- [ ] Tier cards per mockup: 🔴 เตือนภัย count + top-3 province chips + "+N จังหวัด", 🟡 เฝ้าระวัง same (data = existing client roll-up in alerts.tsx; chips from sorted probability). Left border 3px tier colour; counts in `Fonts.display` 38px.
- [ ] Restyle calendar (warm cells only on risk days, today outlined navy) + weather strip + section headers (`SectionHeader` style: 12.5px uppercase letter-spacing muted) with new tokens. Remove glassmorphism leftovers.
- [ ] Lint + visual; commit `design(alerts): tier cards + calm calendar`.

### Task 6: SAFETY (checklist.tsx) restyle

- [ ] Regroup content into ก่อนออกจากบ้าน / ช่วงกลางวัน 11:00–15:00 / สัญญาณอันตราย per mockup copy (น้ำดื่ม, เสื้อผ้า, เลี่ยงกลางแจ้ง, กลุ่มเสี่ยง, heat stroke + โทร 1669 with warning colour + left border). Advice card = 42px icon tile + title 14.5 `Fonts.displaySemi` + body 12.5 muted.
- [ ] Lint + visual; commit `design(safety): time-of-day advice cards`.

### Task 7: PROFILE (settings.tsx) restyle + "เกี่ยวกับระบบพยากรณ์"

- [ ] Regroup settings rows (การแจ้งเตือนของฉัน: จังหวัด, LINE / การแสดงผล: ภาษา, ขนาดอักษร, ธีม) in clean cards (setrow pattern: 13px vertical, hairline dividers).
- [ ] About card: โมเดล `LightGBM · lgbm-v1` · ครอบคลุม 77 จังหวัด/7 วัน · แหล่งข้อมูล Open-Meteo/ERA5 (1991–2025) · อัปเดตล่าสุด = `generated_at` from forecast data · paragraph นิยามคลื่นความร้อน (p95 percentile + ≥2 วันติด) — copy from mockup PROFILE tab.
- [ ] Lint + visual; commit `design(profile): settings groups + model transparency card`.

### Task 8: Trip Advisor (web)

**Files:** Create `services/tripAdvisor.ts` + `components/map/TripAdvisorCard.tsx`; wire in map.tsx (`TRIP_ADVISOR_ENABLED=true`).

- [ ] `services/tripAdvisor.ts`: `planTrip(origin:{lat,lon}, dest:{lat,lon}, riskByProvince, geojson)` → fetch OSRM demo route (geojson geometry + duration); sample geometry every ~10th coord; point-in-polygon (ray-cast helper, pure fn) vs warning/watch province polygons → zones crossed with entry-time estimate (cumulative duration fraction); recommendation: departure before 09:00 if any warning zone entered within 11:00–16:00 window; returns `{durationMin, zones:[{name_th, level, etaClock}], advice, warnSegment:LatLng[]}`. Unit-testable pure parts split out (`pointInPolygon`, `zoneCrossings`).
- [ ] UI: destination = province picker (reuse `ProvinceSelector`); card per mockup (loc row, ⚠️ zones row, 🕘 advice row, ⛽ rest advisory, ปิดแผนเดินทาง); route polyline navy + warn segments dashed `#C75B39`; banner chip.
- [ ] Lint + Playwright (plan trip ชลบุรี→ขอนแก่น returns route, zones listed); commit `feat(map): trip advisor — zones crossed + departure-time advice (OSRM free)`.

### Task 9: Final verification + deploy PR

- [ ] `bun run lint` 0 errors; root `bun test` still 40 pass; Playwright full pass: 4 tabs, glass bar slide, choropleth popups, trip advisor, two-tier alerts.
- [ ] Push feat branch. Create PR to master titled `feat(frontend): Calm Authority redesign (hero map, glass nav, trip advisor)` — body lists screens + notes merge = Vercel deploy. DO NOT merge (user-gated).
- [ ] Update memory (track-m + prod-render-correctness pointer) + this plan's execution log.

---

## Execution log

- Task 1 ✅ tokens rewritten in place (`a195b0a`) — lint 0 errors.
- Task 2 ✅ fonts installed + loaded in root layout (same commit).
- Task 3 ✅ `components/ui/GlassTabBar.tsx` + replaced 4 per-screen navs (`bdc6a9b`).
  Verified on expo web: renders, navigates, pill follows active tab. NOTE:
  expo-router keeps hidden tab screens mounted → duplicate zero-size tab bars in
  DOM (pre-existing pattern, harmless; Playwright must filter `width>0`).
- Task 4 ✅ (core) — MapGrid: CARTO Positron tiles + 77-province GeoJSON
  choropleth (module-cached fetch, name-normalised join `normalizeProvinceName`/
  `riskForFeatureName`, popups TH, grid kept as loading/native fallback at
  calmer opacity); map.tsx: `mapPoints` state + `provinceRisk` useMemo
  (riskLevelToSeverity→safe/watch/warning/extreme) passed to MapGrid; navy user
  marker. Verified live: tile=cartocdn light_all, overlay paths=77, real
  boundaries shaded by live forecast. GOTCHA: Metro on Windows did NOT hot-pick
  these edits — needed `expo start --clear` restart before the new bundle served.
- Task 4 (remaining polish, optional): hero top banner/legend already re-toned
  via tokens; full mockup-style usercard/minilegend restructure not yet done.
- Tasks 5–8 ⏳ not started (alerts tier cards, safety regroup, profile about-card,
  trip advisor). Task 9 (PR to master) pending after those.
