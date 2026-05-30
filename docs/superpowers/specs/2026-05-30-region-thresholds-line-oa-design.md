# Design Spec — เกณฑ์ Heatwave รายจังหวัด + เชื่อมต่อ LINE OA (พร้อมแก้ ML pipeline)

> วันที่: 2026-05-30
> สถานะ: อนุมัติดีไซน์แล้ว (A1 + B1 + roadmap 5 เฟส) — รอ user review ก่อนแตกเป็น implementation plan
> เป้าหมายปลายทาง: รันต่อใน Claude Code CLI

---

## 1. ภาพรวมและเป้าหมาย (Overview & Goals)

ยกระดับ Heatwave-AI จาก demo (ที่ ML core ยังมี leakage + forecast ใช้ `np.random`) ให้เป็นระบบเตือนภัยคลื่นความร้อน **รายจังหวัด** ที่ผู้ใช้เชื่อถือได้ และส่งถึงผู้ใช้ผ่าน **LINE OA**

**3 เป้าหมายหลัก:**
1. **เกณฑ์รายจังหวัด** — แต่ละจังหวัดมี threshold ของตัวเอง (percentile จาก climatology ของจังหวัดนั้น)
2. **ML ที่มีความหมายจริง** — ทำนาย *ล่วงหน้า* จากข้อมูลจริง (Open-Meteo) ตัด target leakage + temporal leakage
3. **ช่องทาง LINE OA ครบ** — Push แจ้งเตือน + ถาม-ตอบ interactive + Rich menu + LIFF ฝังเว็บ

**ตัวชี้วัดความสำเร็จ (Success criteria):**
- โมเดลรายงาน **PR-AUC / MCC / F2 / Brier** ที่สมจริง (ไม่ใช่ F1 = 0.9999) และดีกว่า baseline (climatological persistence)
- ทุกจังหวัดใน 77 จังหวัดมี forecast รายวันจริงใน DB (ไม่มี `Math.sin` / `np.random`)
- LINE OA push แจ้งเตือนตามพื้นที่ที่ผู้ใช้ subscribe ได้จริง + ตอบคำถามรายจังหวัดได้

---

## 2. การตัดสินใจเชิงสถาปัตยกรรม (ที่อนุมัติแล้ว)

| จุด | เลือก | เหตุผล |
|----|-------|--------|
| **A. โมเดลรายจังหวัด** | **A1 — โมเดลกลางตัวเดียว + target สัมพัทธ์** | เทรนครั้งเดียว, เกณฑ์รายจังหวัดฝังผ่าน percentile climatology, positive ไม่กระจาย, scale ได้ |
| **B. Backend/Infra** | **B1 — ต่อยอด Bun/Elysia + Supabase** | ใช้ของเดิม + Supabase (Postgres + pg_cron + Auth) ที่ต่อ MCP ไว้แล้ว |

**Non-goals (YAGNI ตัดออกในรอบนี้):**
- ❌ 77 โมเดลแยก (A2), การ rewrite เป็น FastAPI (B2)
- ❌ Temporal models (LSTM/Transformer) — ไว้เฟสถัดไป (ดู §10)
- ❌ ขยายไปประเทศอื่น, climate-change scenarios, hospital data
- ❌ ระดับอำเภอ — เริ่มที่จังหวัดก่อน

---

## 3. สถาปัตยกรรมรวม (System Architecture)

```
[Open-Meteo API]──(ERA5 history + forecast, ไม่ต้อง API key)
       │
       ▼
[Python ML pipeline]  ── เฟส 1–2: sWBGT, climatology percentile รายจังหวัด, label, train, calibrate
       │  (.pkl + thresholds)
       ▼
[Supabase Postgres] ◄── pg_cron รายวัน ─► [Forecast job (Python)]  ── เฟส 3
   provinces / thresholds / forecasts / line_users / subscriptions / alerts_log
       ▲                         │
       │ REST                    │ หลัง cron → หา province เกิน threshold
       ▼                         ▼
[Bun/Elysia API] ──────► [LINE Messaging API]  ── เฟส 4 (push/reply/rich menu)
       ▲                         ▲
       │ /api/forecast/*         │ webhook + LIFF
       ▼                         │
[Expo Web (Vercel)] ─────────────┘  ── เฟส 5 (province UI + LIFF page)
```

---

## 4. เฟส 1 — Data & Labels (รากฐาน ตัด leakage)

### 4.1 แหล่งข้อมูล: Open-Meteo
- **Historical Weather API** (ERA5, ตั้งแต่ 1940) สำหรับ **เทรน** — ดึงรายจังหวัดที่ centroid (lat/lon) ของแต่ละจังหวัด, ช่วง **1991–2025**
- ตัวแปรที่ดึง (รายวัน + บาง pressure-level):
  - heat: `temperature_2m_max/min/mean`, `dewpoint_2m`, `relative_humidity_2m`, `apparent_temperature`, `wet_bulb_temperature_2m`
  - synoptic: `surface_pressure`, `geopotential_height_500hPa` (anomaly), wind `wind_speed_10m`
  - land/solar: `soil_moisture_0_to_7cm` (+ ชั้นลึก), `shortwave_radiation`
- ไม่ต้องใช้ API key; license CC-BY 4.0 (เชิงพาณิชย์ตรวจ terms)

### 4.2 คำนวณ sWBGT (Simplified shade WBGT — Australian BoM)
ใช้ค่าประมาณแบบร่ม (ไม่ต้องมี globe thermometer):
```
e = (RH/100) · 6.105 · exp(17.27·Ta / (237.7 + Ta))     # water vapor pressure (hPa)
sWBGT = 0.567·Ta + 0.393·e + 3.94                         # °C
```
> หมายเหตุใน spec: นี่คือ **shade WBGT** ที่ไม่รวมผลรังสีดวงอาทิตย์โดยตรง — documented limitation; ถ้าต้องการ WBGT เต็มต้องประมาณ globe temp จาก solar radiation (ไว้เฟสถัดไป)

### 4.3 Climatology percentile รายจังหวัด
- ฐาน **1991–2020** (WMO 30-year normal)
- ต่อจังหวัด คำนวณ **percentile ของ sWBGT_max แบบ day-of-year windowed** (หน้าต่าง ±7 วันรอบ doy เพื่อลด seasonal bias): `p90, p95, p975`
- เก็บลงตาราง `province_thresholds`

### 4.4 Label heatwave (percentile + persistence)
```
is_hot_day(prov, date)   = sWBGT_max(prov,date) ≥ p95(prov, doy)
heatwave_day(prov, date) = is_hot_day เป็นจริง และเป็นส่วนของ run ที่ยาว ≥ 2 วันติดต่อกัน
```
→ ตรงนิยาม WMO/TMD (anomaly เทียบค่าปกติ + ต่อเนื่อง) แทน `heat_index ≥ 41` รายแถว

### 4.5 Temporal split (ตัด temporal leakage)
- **Train: ≤ 2023 | Validation: 2024 | Test (held-out): 2025**
- climatology percentile คำนวณจาก **ช่วง baseline เท่านั้น** (ไม่แตะ val/test)
- **ลบ `train_test_split` แบบสุ่มทิ้งจาก `src/preprocessing.py`**

**Deliverable เฟส 1:** dataset สะอาดมี label ถูกต้อง + `province_thresholds` 77 จังหวัดใน Supabase
**Acceptance:** label rate สมเหตุสมผล (~ไม่กี่ %); ไม่มีคอลัมน์ที่นิยาม label อยู่ในชุด features

---

## 5. เฟส 2 — Model (เปลี่ยนเป็น forecasting จริง)

### 5.1 กรอบปัญหา (ตัด target leakage)
ทำนาย **P(heatwave_day ที่ t+k)** สำหรับ k = 1..7 วัน จาก predictors ที่รู้ ณ **≤ t เท่านั้น**
- ใช้ **horizon-as-feature**: โมเดลกลางตัวเดียว, ต่อ `horizon_k` เข้าไปใน features
- **ห้ามใส่** sWBGT/heat_index ของ "วันเป้าหมาย" เป็น feature (นั่นคือ label) — features เป็น lagged/anomaly ของอดีตเท่านั้น

### 5.2 Features (ทั้งหมด ณ ≤ t)
- climatology รายจังหวัด: `p95(doy)`, ค่าเฉลี่ย/ส่วนเบี่ยงเบนรายจังหวัด, `lat`, `lon`
- ปฏิทิน: `sin/cos(doy)`
- antecedent/anomaly: rolling mean/max ของ sWBGT, Tmax, RH ที่ 3/7/14/30 วันย้อนหลัง + anomaly เทียบ climatology
- synoptic/land: `geopotential_500_anomaly`, `soil_moisture`, NDVI (lag 0/1/2 เดือน)
- `horizon_k`

### 5.3 โมเดล + การจัดการ imbalance + calibration
- หลัก: **LightGBM** (`is_unbalance=True` หรือ `scale_pos_weight=neg/pos`); เทียบ XGBoost/Balanced RF
- **Calibrate** ความน่าจะเป็น (isotonic บน validation) — สำคัญเพราะแอปแสดง probability และใช้ตัดสิน push
- จูน **decision threshold** ด้วย PR-curve / Youden / Fβ (ไม่ใช้ 0.5)
- ระวัง resampling ทำ calibration เพี้ยน (ดูงานวิจัย §9)

### 5.4 การประเมิน (เมตริกที่มีความหมาย)
- รายงาน **PR-AUC, MCC, F2, ROC-AUC, Brier + reliability curve** ทั้งภาพรวมและรายจังหวัด/รายภาค
- เทียบ **baseline**: climatological persistence + "ทายว่าไม่เกิดตลอด"
- คาดหวัง F1 ตกจาก ~0.99 → เลขสมจริง = สัญญาณที่ถูกต้อง
- SHAP เพื่อยืนยันโมเดลเรียนตัวขับฟิสิกส์จริง ไม่ใช่ leak

**Deliverable เฟส 2:** `.pkl` (model + calibrator + threshold) + รายงานเมตริกจริง + feature list ที่ไม่มี leakage
**Acceptance:** PR-AUC/MCC > baseline อย่างมีนัย; ไม่มี feature ที่ reproduce label ได้

---

## 6. เฟส 3 — Forecast Service + DB

### 6.1 งานตามเวลา (Scheduled job)
- **Supabase pg_cron** (หรือ Render cron) รันรายวัน (เช่น 06:00 ICT):
  1. ดึง Open-Meteo **forecast** + ประวัติล่าสุดสำหรับ centroid 77 จังหวัด (Open-Meteo ให้สูงสุด ~16 วัน แต่ใช้เพื่อประกอบ feature เป็นหลัก)
  2. ประกอบ lagged/anomaly features (ใช้ประวัติล่าสุด)
  3. รันโมเดลให้คะแนนเฉพาะ horizon ที่โมเดลรองรับ **k = 1–7 วัน** → prob + predicted_label + risk_level ต่อจังหวัด/วัน
  4. เขียนลง `forecasts` (upsert ตาม province_id + target_date + generated_at)

### 6.2 DB schema (Supabase Postgres)
```sql
provinces(id pk, name_th, name_en, region, lat, lon)
province_thresholds(province_id fk, doy int, metric text,  -- 'sWBGT'
                    p90 numeric, p95 numeric, p975 numeric,
                    baseline_period text, primary key(province_id, doy, metric))
forecasts(id pk, province_id fk, target_date date, generated_at timestamptz,
          horizon_days int, prob numeric, predicted_label bool,
          risk_level text,  -- low|moderate|high|extreme
          swbgt_pred numeric, model_version text,
          unique(province_id, target_date, generated_at))
line_users(line_user_id pk, display_name, lang default 'th',
           default_province_id fk, created_at timestamptz default now())
subscriptions(id pk, line_user_id fk, province_id fk,
              min_risk_level text default 'high', active bool default true,
              unique(line_user_id, province_id))
alerts_log(id pk, line_user_id fk, province_id fk, target_date date,
           risk_level text, sent_at timestamptz, line_message_id text)
```
- เปิด **RLS**; service-role key ใช้เฉพาะฝั่ง backend (ไม่ leak ไป client)
- risk_level map: prob → low/moderate/high/extreme (เกณฑ์จาก calibrated prob)

### 6.3 API (Bun/Elysia เพิ่มจากของเดิม)
- `GET /api/provinces` — รายชื่อ + centroid
- `GET /api/forecast/province/:id?days=7` — forecast ล่าสุดรายจังหวัด
- `GET /api/forecast/map` — ค่าล่าสุดทุกจังหวัด (ให้หน้า Map ใช้ของจริง)
- `GET /api/thresholds/:province_id`
- `POST /api/line/webhook` — รับ event จาก LINE (ดูเฟส 4)
- คง security เดิม (rate limit, payload cap); **ปิด CORS เป็น whitelist**; แก้ config path (`config/config.yaml` ↔ root `config.yaml`)

**Deliverable เฟส 3:** forecast รายจังหวัด/วันใน DB + API ใช้งานได้ + cron ทำงาน
**Acceptance:** เรียก `/api/forecast/map` ได้ค่าจริง 77 จังหวัด มี `generated_at`

---

## 7. เฟส 4 — LINE OA (ครบ 4 โหมด)

### 7.1 ตั้งค่า (LINE Developers)
- **Messaging API channel** + **LIFF app**
- secrets ใน `.env` (ห้าม commit): `LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN`, `LIFF_ID`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- Webhook URL ชี้ `POST /api/line/webhook`; **ตรวจ `X-Line-Signature`** (HMAC-SHA256 ด้วย channel secret) ทุก request

### 7.2 Push แจ้งเตือนอัตโนมัติ
- หลัง cron (เฟส 3): query จังหวัดที่ `risk_level ≥ subscription.min_risk_level`
- หา subscribers → **multicast** Flex message (batch ≤ 500 ราย/ครั้ง), respect monthly quota
- **idempotency** ผ่าน `alerts_log` (กันส่งซ้ำ target_date เดียวกัน)
- guard: **ไม่ push ถ้า** model coverage/confidence ไม่ถึงเกณฑ์ (ตามคำเตือน §9)

### 7.3 Interactive (ถาม-ตอบ)
จัดการใน webhook:
- `follow` → ทักทาย + ชวนตั้งจังหวัด (quick reply / LIFF)
- `message: location` → หา **จังหวัดที่ใกล้ centroid ที่สุด** → ตอบ Flex forecast 7 วัน
- `message: text` (ชื่อจังหวัด) → ตอบ forecast จังหวัดนั้น (fuzzy match ชื่อไทย)
- `postback` (จาก rich menu / quick reply) → ดำเนินการ (ดู/ตั้งค่า/subscribe)

### 7.4 Rich menu
6 ช่อง: `พยากรณ์วันนี้` / `7 วันข้างหน้า` / `ตั้งค่าพื้นที่` / `แผนที่ (เปิด LIFF)` / `คู่มือรับมือความร้อน` / `แชร์`

### 7.5 LIFF (ฝังเว็บแอป)
- LIFF app URL = เว็บ Expo บน Vercel route `/liff`
- `liff.init` → `liff.getProfile()` ผูก `line_user_id` กับ `subscriptions`
- เปิดแผนที่/forecast ภายใน LINE ใช้ข้อมูลชุดเดียวกับเว็บ

**Deliverable เฟส 4:** LINE bot push + reply + rich menu + LIFF ใช้งานได้จริง
**Acceptance:** subscribe จังหวัด → ได้ push เมื่อ risk ถึงเกณฑ์; ส่ง location → ได้ forecast ถูกจังหวัด

---

## 8. เฟส 5 — Frontend (Expo)

- **Province selector** + hook `useForecast(provinceId)` เรียก `/api/forecast/province/:id`
- **หน้า Map**: แทน `Math.sin(lng*0.15)` ด้วยข้อมูลจริงจาก `/api/forecast/map` (severity จาก **probability/risk_level** ไม่ใช่จากอุณหภูมิดิบ)
- แสดง **"as of" timestamp** (`generated_at`) + สถานะ cache
- route `/liff` รองรับการเปิดใน LINE (อ่าน LIFF context)
- หน้า Forecast/Alerts ใช้ข้อมูลชุดเดียวกับ LINE (consistency)

**Deliverable เฟส 5:** เว็บ + ในแอป LINE แสดงข้อมูลตรงกัน เป็นค่าจริงจากโมเดล
**Acceptance:** เลือกจังหวัด → เห็น forecast จริง; Map ไม่มีค่าสุ่ม

---

## 9. คำเตือนจากงานวิจัย (ฝังใน implementation)
- โมเดล ML/DL มัก **ประเมิน humid heatwave ต่ำกว่าจริง** → ไทยเป็น humid; เน้น lead time สั้น (1–7 วัน), จัดการความชื้น/WBGT ดี ๆ, ประเมิน impact-centric
- **Calibrate ก่อน push** — probability ที่ไม่ calibrate ทำให้แจ้งเตือนพลาด
- **accuracy หลอกตา** ที่ positive ต่ำ — ใช้ PR-AUC/MCC/F2 + reliability เป็นหลัก
- อย่าใช้ resampling พร่ำเพรื่อ — กระทบ calibration
(อ้างอิงเต็มใน `RESEARCH_REVIEW_2026-05-30.md`)

---

## 10. ส่วนขยายอนาคต (หลัง 5 เฟส)
- Temporal models (LSTM/CNN/TFT) บนลำดับ 30 วัน; probabilistic forecast (prediction interval)
- WBGT เต็ม (รวม globe จาก solar radiation)
- EHF/HEHF (acclimatization 3-วัน vs 30-วัน) เป็น label ทางเลือก
- A/B / shadow deployment; observability (Sentry)

---

## 11. สมมุติฐาน & คำถามเปิด (ยืนยันตอนทำ)
- **สมมุติฐาน:** centroid รายจังหวัด 1 จุดเป็นตัวแทนได้พอ (จังหวัดใหญ่/ภูมิประเทศหลากหลายอาจต้องหลายจุด — ไว้พิจารณา)
- **สมมุติฐาน:** Open-Meteo forecast horizon ~7–16 วันพอสำหรับเตือนภัย
- **คำถามเปิด:** ใช้ Supabase pg_cron หรือ Render cron รันงาน Python? (pg_cron เรียก edge function / external trigger) — ตัดสินตอนเฟส 3
- **คำถามเปิด:** centroid 77 จังหวัดเอาจาก dataset ไหน (เตรียม seed table)
- **คำถามเปิด:** เกณฑ์ map prob → risk_level (low/mod/high/extreme) ตั้งค่าเริ่มต้นเท่าไร

---

## 12. ลำดับ implementation (สำหรับ writing-plans)
1. เฟส 1 (data+label+threshold+temporal split) → 2. เฟส 2 (model+calibrate+metrics)
3. เฟส 3 (DB+forecast job+API) → 4. เฟส 4 (LINE OA) → 5. เฟส 5 (frontend)
แต่ละเฟสชิปได้อิสระและมี acceptance ของตัวเอง
