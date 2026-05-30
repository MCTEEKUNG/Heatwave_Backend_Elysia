# Heatwave-AI: เกณฑ์รายจังหวัด + LINE OA — Master Plan Index

> **For agentic workers:** นี่คือดัชนีของแผน 5 เฟส แต่ละเฟสมีไฟล์แผนของตัวเองและชิปได้อิสระ
> Spec ต้นทาง: `docs/superpowers/specs/2026-05-30-region-thresholds-line-oa-design.md`
> รีวิวงานวิจัย: `RESEARCH_REVIEW_2026-05-30.md`

**Goal:** เปลี่ยน Heatwave-AI ให้พยากรณ์คลื่นความร้อนรายจังหวัด (77) ด้วยเกณฑ์ percentile เฉพาะพื้นที่จากข้อมูลจริง แล้วส่งถึงผู้ใช้ผ่าน LINE OA

**Architecture:** Python ML (Open-Meteo → sWBGT → percentile label → forecasting model) เขียน forecast ลง Supabase Postgres ผ่าน pg_cron รายวัน; Bun/Elysia เสิร์ฟ API + LINE webhook + push; Expo/Vercel เป็นเว็บ + LIFF

**Tech Stack:** Python (pandas, scikit-learn, lightgbm, requests, pytest) · Bun/Elysia/TypeScript · Supabase (Postgres + pg_cron) · LINE Messaging API + LIFF · Expo/React Native

---

## ลำดับเฟส (ทำเรียงกัน — แต่ละเฟสมี acceptance ของตัวเอง)

| เฟส | ไฟล์แผน | สรุป | ขึ้นกับ |
|----|---------|------|--------|
| 1 | `2026-05-30-phase1-data-labels.md` ✅ | Open-Meteo ingest, sWBGT, percentile รายจังหวัด, label + persistence, temporal split | — |
| 2 | `2026-05-30-phase2-model.md` (รอสร้าง) | reframe เป็น forecasting t+k, ตัด leakage, calibrate, เมตริกจริง | เฟส 1 |
| 3 | `2026-05-30-phase3-forecast-service.md` (รอสร้าง) | Supabase schema, pg_cron forecast job, Elysia API | เฟส 2 |
| 4 | `2026-05-30-phase4-line-oa.md` (รอสร้าง) | webhook+push+interactive+rich menu+LIFF | เฟส 3 |
| 5 | `2026-05-30-phase5-frontend.md` (รอสร้าง) | province selector, map จริง, LIFF route | เฟส 3 (ขนานกับ 4 ได้) |

> เฟส 2–5: ให้รัน `superpowers:writing-plans` ต่อทีละเฟสเมื่อถึงคิว (CLI agent ทำได้) — ดู "การใช้ใน CLI" ด้านล่าง

---

## เตรียมก่อนเริ่ม (Prerequisites)

**Secrets (`.env` ที่ root — อย่า commit, มีใน `.gitignore` แล้ว):**
```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
LINE_CHANNEL_SECRET=
LINE_CHANNEL_ACCESS_TOKEN=
LIFF_ID=
# Open-Meteo ไม่ต้องใช้ key
```
- สร้าง `.env.example` (ค่าว่าง) commit ได้
- บัญชีที่ต้องเตรียม: Supabase project, LINE Messaging API channel + LIFF (สร้างก่อนเฟส 4)

**ติดตั้ง dependency เพิ่ม (เฟส 1):**
```bash
pip install requests lightgbm scikit-learn pandas numpy pytest
```

---

## การใช้ใน Claude Code CLI

1. เปิด repo นี้ใน CLI
2. สั่ง: *"อ่าน docs/superpowers/plans/2026-05-30-phase1-data-labels.md แล้ว execute ทีละ task ด้วย superpowers:executing-plans"*
3. จบเฟส 1 → สั่ง: *"ใช้ superpowers:writing-plans สร้างแผนเฟส 2 จาก spec ส่วน §5"* แล้ว execute
4. ทำซ้ำจนครบเฟส 5
5. ระหว่างทาง: commit บ่อย, รัน test ทุก task (TDD)

> เหตุผลที่ไม่เขียนเฟส 2–5 ล่วงหน้าทั้งหมด: รายละเอียด (เช่น test ของ LINE webhook, schema จริง) ขึ้นกับผลของเฟสก่อนหน้า การเขียนตอนถึงคิวจะตรงและไม่มี placeholder ตามหลัก writing-plans

---

## Definition of Done (ทั้งโปรเจกต์)
- [ ] เฟส 1: dataset + `province_thresholds` 77 จังหวัด, ไม่มี feature ที่ reproduce label
- [ ] เฟส 2: โมเดล calibrated, PR-AUC/MCC/F2 > baseline บน test 2025
- [ ] เฟส 3: `/api/forecast/map` คืนค่าจริง 77 จังหวัด, cron ทำงาน
- [ ] เฟส 4: LINE push/reply/rich menu/LIFF ใช้งานจริง
- [ ] เฟส 5: เว็บ + LIFF แสดง forecast จริง (ไม่มี `Math.sin`)
