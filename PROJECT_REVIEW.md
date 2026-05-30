# Heatwave-AI — รายงานวิเคราะห์โปรเจกต์และแนวทางพัฒนาต่อ

> วันที่: 9 พฤษภาคม 2026
> ขอบเขต: HeatMAP-Frontend, Heatwave-AI-Backend-Elysia, Heatwave-AI-TRAIN, Era5/NDVI data, deployment stack

---

## 1. ภาพรวมของโปรเจกต์

Heatwave-AI เป็นระบบ Full-Stack สำหรับพยากรณ์ "คลื่นความร้อน" (heatwave) ในประเทศไทย โครงสร้างประกอบด้วย 4 ส่วนหลัก:

1. **HeatMAP-Frontend** — แอป React Native/Expo (iOS / Android / Web) แสดง 5 หน้าจอ (Map, Forecast, Alerts, Safety Guide, Settings)
2. **Heatwave-AI-Backend-Elysia** — API Server บน Bun + Elysia (TypeScript) มี 11 endpoint รันทับด้วย Python ML runtime
3. **Heatwave-AI-TRAIN** — ไปป์ไลน์ฝึกโมเดล Python ครอบคลุม 5 โมเดล (Balanced RF, XGBoost, LightGBM, MLP, KAN)
4. **Era5-data-2000-2026 + ndvi/** — ข้อมูล ERA5 NetCDF 26 ปี + MODIS NDVI

Deploy: Backend บน Render (Docker), Frontend บน Vercel, โหลด `.pkl` จาก Hugging Face

---

## 2. ข้อดี (Strengths)

### 2.1 สถาปัตยกรรมและการออกแบบระบบ
- **แยกหน้าที่ (separation of concerns) ชัดเจน** — Train / Serve / UI แยกกัน ทำให้ deploy แยก scale แยกได้
- **เอกสาร ARCHITECTURE.md เขียนได้ดีมาก** มี Mermaid diagrams ครบ flow ตั้งแต่ user กดปุ่ม → Python → Open-Meteo → model.predict() → JSON response
- **เลือก stack เหมาะกับงาน**: Bun+Elysia เร็ว I/O bound, Expo จบในโค้ดเดียวสำหรับ mobile+web, Python คงเป็นภาษามาตรฐานของ ML
- **Monorepo ดี** — ทุกส่วนอยู่ใน repo เดียว มี `docker-compose.yml` สำหรับ dev local

### 2.2 ความถูกต้องเชิงวิทยาศาสตร์ของโดเมน
- เลือกใช้ **WBGT (Wet-Bulb Globe Temperature)** เป็น label หลัก แทน "อุณหภูมิอากาศ" — ถูกต้องตามบริบทเมืองร้อนชื้นของไทย เพราะเหงื่อระเหยยากเมื่อ RH สูง
- Threshold 32 °C ตรงกับเกณฑ์ของกรมอนามัย (MoPH) และ ISO 7243
- มี **labeling method หลายแบบ** (`wbgt | heat_index | ehf | tropical_night`) ปรับเปลี่ยนผ่าน config ได้
- **Heat Index ใช้ Rothfusz regression** ไม่ใช่ Steadman เก่า — ถูกต้องตามมาตรฐาน NWS
- **RH คำนวณด้วย August-Roche-Magnus** — สูตรมาตรฐานของอุตุนิยมวิทยา

### 2.3 ข้อมูลที่ใช้
- **ERA5 ครอบคลุม 26 ปี** (2000–2025) — เพียงพอจะจับความผันผวน inter-annual
- **NDVI จาก MODIS MOD13A3** เพิ่มข้อมูลพืชพันธุ์/ความชื้นดิน เป็นตัวแปรที่งานพยากรณ์อากาศไทยมักไม่ใส่
- มี **NDVI lag 0/1/2 เดือน** จับ memory effect ของพืชพันธุ์
- Year-based split (Train: 2020–2024, Val: 2025) ป้องกัน **temporal leakage** ได้ถูกต้อง

### 2.4 ความปลอดภัยฝั่ง Backend
- ใช้ `child_process.spawn(...)` ไม่ผ่าน shell → **กัน command injection** ได้
- Whitelist validation (`VALID_MODELS`)
- Rate limit 60 req/min/IP
- Payload size cap (1 MB CSV)
- Process timeout 120 วินาที kill -9 หาก hang
- temp file ใช้ UUID ใน `tmpdir()` ไม่ชนกัน
- **Structured JSON logging** เตรียมพร้อมสำหรับ log aggregator
- Cleanup ไฟล์ forecast เก่า (เก็บ 50 ไฟล์ล่าสุด) — ป้องกัน disk เต็ม

### 2.5 UX / Frontend
- ใช้ **Expo Router** มี typed routes
- มี hooks เป็นชั้นๆ (`useForecast`, `useWeather`, `useLocation`, `useSettings`) แยก state จาก UI
- API client มี **timeout 15 วินาที + retry 2 ครั้ง + exponential backoff** — production-grade
- **i18n** EN/TH, รองรับ dark mode, font scaling
- Risk levels 4 tier (low/moderate/high/extreme) แมพไปสีที่ออกแบบมาให้ผู้พิการสายตาแยกได้ (เขียว/เหลือง/ส้ม/แดง)

### 2.6 DevOps / Deployment
- Single `Dockerfile.render` โหลด Bun+Python ในภาพเดียว
- Health check `/api/health` ผูกกับ Render
- AutoDeploy on push (`render.yaml`)
- โมเดล `.pkl` แยกอยู่ Hugging Face — repo ไม่บวมจาก binary

---

## 3. ข้อเสีย / จุดที่ต้องปรับปรุง (Weaknesses)

### 3.1 คุณภาพโมเดล — **ปัญหาที่ใหญ่ที่สุด**

Leaderboard ปัจจุบันใน `experiments/results/leaderboard.json`:

| Rank | Model               | Accuracy | Precision | Recall | F1     | ROC-AUC |
|------|---------------------|---------:|----------:|-------:|-------:|--------:|
| 1    | LightGBM            | 0.9981   | 0.4815    | 1.0000 | 0.6500 | 0.999   |
| 2    | Balanced RF         | 0.5407   | 0.0128    | 0.6752 | 0.0250 | 0.6512  |
| 3    | KAN                 | 0.9982   | 0.0000    | 0.0000 | 0.0000 | null    |
| 4    | MLP                 | 0.9982   | 0.0000    | 0.0000 | 0.0000 | null    |
| 5    | XGBoost             | 0.9982   | 0.0000    | 0.0000 | 0.0000 | 0.8777  |

ประเด็น:
1. **3 ใน 5 โมเดล (XGBoost / MLP / KAN) F1 = 0** — ทำนาย "ไม่มี heatwave" ตลอด เพราะ class imbalance รุนแรง (positive rate ~0.2%) แต่ XGBoost/MLP/KAN ไม่ได้ใส่ `scale_pos_weight` / `class_weight` / focal loss / SMOTE — เลย **collapse ไปทาง majority class**
2. **Balanced RF ในโปรดักชัน F1 เพียง 0.025** (precision 1.28%) — แทบไร้ประโยชน์ false positive แทบทั้งหมด
3. **LightGBM เป็นตัวที่ดีที่สุด (F1 = 0.65) แต่ไม่ได้ deploy** — `MODEL_REGISTRY` ใน `predictor.py` มีแค่ `balanced_rf`
4. **leaderboard ขัดแย้งกับไฟล์ผลลัพธ์**: `balanced_random_forest_result.json` แสดง F1 = 0.9999 (timestamp 2026-04-01) ขณะ leaderboard บันทึก F1 = 0.025 (2026-04-06) → **ฝึกซ้ำแล้วได้ผลต่างกันมาก แสดงว่า reproducibility มีปัญหา** (อาจเป็นจาก data leakage รอบแรก, การ split ต่างกัน, หรือ random seed ไม่ stabilized จริง)

### 3.2 Feature Engineering ค่อนข้างบาง
- ใช้แค่ 8 features: `t2m, d2m, sp, u10, v10, ndvi, ndvi_lag1, ndvi_lag2`
- **ขาด temporal features**: rolling mean/max ย้อน 3/7/14/30 วัน, anomaly จาก climatology, day-of-year sine/cosine
- **ขาด spatial features**: latitude/longitude ไม่ได้เป็น feature ของโมเดล
- **ขาด synoptic features**: pressure anomalies, geopotential height, ridge index
- **NDVI ใช้แค่ seasonal climatology ตอน inference** (`NDVI_SEASONAL` dict ใน `forecast.py`) → real-time vegetation stress ไม่ถูกใช้

### 3.3 Inference / Production
- **One point fits all**: `forecast.py` default lat=13.75 lon=100.50 (กรุงเทพ) แต่หน้าจอ Map สังเคราะห์ความหลากหลายเชิงพื้นที่ด้วย `Math.sin(lng * 0.15)` — **ค่าใน Map ส่วนใหญ่จึงไม่ได้มาจากโมเดล แต่เป็นการสุ่ม fake** (ดู `app/(tabs)/map.tsx` บรรทัด ~95)
- **Spawn Python ทุก request**: cold start Python interpreter + load `.pkl` ใหม่ทุกครั้ง — ช้า + กิน CPU/memory ต่อเนื่อง
- **ไม่มี caching layer** — request ซ้ำ lat/lon/day เดียวกัน ก็ยังต้อง spawn ใหม่
- **In-memory rate limiter** ใน `Map<string, …>` reset ทุกครั้ง backend restart และไม่ทำงานข้าม instance
- **ไฟล์ forecast เก็บใน `experiments/forecasts/`** บน Render filesystem ซึ่งเป็น **ephemeral** — ทุกครั้ง deploy ใหม่ข้อมูลหาย
- **Predictor มี silent fallback อันตราย**: ถ้าหา `scaler.pkl` ไม่เจอจะ "ใช้ raw features" ต่อโดยไม่ throw error → output ผิดเงียบๆ
- **ไม่มี persistent DB** (Postgres) ในระบบ — ทุกอย่างเป็นไฟล์ JSON

### 3.4 ความปลอดภัย / Operational
- ไม่มี **authentication** บน `/api/forecast` ใครๆ ก็เรียก spawn Python ได้ → **DoS โดยใช้ทรัพยากรจริง**
- ไม่มี **CSRF protection** (ส่วนใหญ่ API stateless ไม่จำเป็น แต่ควรพิจารณา)
- CORS ตั้ง `cors()` อนุญาตทุก origin — production ควรกำหนด whitelist
- **ไม่มี Sentry / Datadog / observability** — มีแค่ `console.log` JSON
- **Render free tier**: spin-down 15 นาที → user รออ่านครั้งแรก 30+ วินาที (frontend ตั้ง 45 วิ ก็ยังไม่พอกับ Python forecast ที่ใช้เวลาเอง)
- **ไม่มี CI/CD pipeline** (`package.json` test script เป็น `"Error: no test specified"`)
- **ไม่มี unit tests / integration tests / e2e tests** ทั้ง backend + frontend

### 3.5 Frontend
- หน้า **alerts.tsx** ไม่ได้เชื่อมกับ push notification จริง — แสดงแค่ปฏิทิน, ไม่มีตัว trigger เมื่อ probability เกิน threshold
- หน้า **Map** ใช้ค่า severity จาก *อุณหภูมิ* (`temp >= 41 ? 'extreme'`) ไม่ใช่จาก *probability* ของโมเดล → **ขัดแย้งกับหน้า Forecast**
- ไม่มี indicator ว่า forecast cache อายุเท่าไร — user อาจดูข้อมูลค้างหลายวันโดยไม่รู้
- ไม่มี **offline mode** / cached state
- หน้า Map ไม่ได้ใช้ MapBox / Mapnik tile จริง — แต่ใช้ `react-native-maps` กับ leaflet ผสม Native/Web — โค้ดสองชุด

### 3.6 หนี้ทางเทคนิค (Tech Debt)
- `forecast.py` มี argument `--cycles` ที่ "ignored — kept for API compatibility" → API drift, ควรลบ
- `Dockerfile.render` ติดตั้ง `xgboost`, `lightgbm` แต่ดาวน์โหลดเฉพาะ `balanced_random_forest_model.pkl` → image อ้วนเกินจำเป็น
- `requirements.txt` แตกต่างกันระหว่าง backend/train แต่หลายตัวซ้ำ ไม่มีการ pin version (`>=` แทนที่จะเป็น `==`) → reproducibility ต่ำ
- 2 repository (backend) ทับซ้อนกัน — มี `.git` ใน `Heatwave-AI-Backend-Elysia/` และ `.git` ใน root → confusing สำหรับคนเข้ามาใหม่
- ไฟล์ขนาดใหญ่ (`Era5-data-2000-2026/*.nc`, `ndvi/*.tif`) commit ตรงๆ ไม่ใช้ Git LFS / DVC

---

## 4. แนวทางพัฒนาต่อ (Roadmap)

แบ่งเป็น 4 ระยะ จากเร่งด่วนที่สุดไปลึกที่สุด

### Phase 1 — แก้ไขปัญหา "ใช้งานจริงไม่ได้" (0–1 เดือน)

| ลำดับ | งาน | เหตุผล | ความยาก |
|-------|-----|--------|---------|
| P1.1 | **แก้ class imbalance ของทุกโมเดล** — ใส่ `scale_pos_weight=neg/pos` ใน XGBoost, `is_unbalance=True` หรือ `class_weight='balanced'` ใน LightGBM, `pos_weight` ใน BCEWithLogitsLoss ของ MLP/KAN, ทดลอง SMOTE/ADASYN กับโมเดลที่ไม่มี class weight built-in | F1 = 0 ของ 3 โมเดล แก้ได้ตรงจุดนี้ | 2 วัน |
| P1.2 | **Deploy LightGBM** เพิ่มเข้า `MODEL_REGISTRY` ใน `predictor.py` และเพิ่มไฟล์ใน Hugging Face → set เป็น default model ใน frontend | LightGBM F1 = 0.65 vs balanced_rf 0.025 — ปรับโปรดักชันให้ใช้โมเดลที่ดีกว่า | 1 วัน |
| P1.3 | **ปรับ threshold ของ probability** ตาม PR-curve / Youden's J — ตอนนี้ทำนาย binary จาก 0.5 default ทำให้ precision พัง | precision 0.48 ของ LightGBM แปลว่า threshold สูงขึ้นจะดีขึ้น | 1 วัน |
| P1.4 | **เพิ่ม unit + integration tests** อย่างน้อย: preprocessing, predictor, API endpoints ผ่าน vitest/bun:test + pytest | ไม่มี test → ปรับโค้ดแล้วอาจพังโดยไม่รู้ | 4 วัน |
| P1.5 | **แก้ silent fallback ของ scaler** ใน `predictor.py` ให้ raise error ถ้าไม่พบ `scaler.pkl` | ทุกวันนี้ output อาจผิดเงียบๆ | 0.5 วัน |
| P1.6 | **เพิ่ม Sentry หรือ structured error tracking** | ตอนนี้พังแล้วไม่รู้ | 0.5 วัน |
| P1.7 | **Pin version ใน requirements.txt** (==) + lock file สำหรับ Python | reproducibility | 0.5 วัน |
| P1.8 | **เปิด strict CORS** ใน production | เปิดทุก origin = อันตราย | 0.5 วัน |
| P1.9 | **ตรวจ leaderboard discrepancy** — รัน balanced_rf ใหม่กับ same seed/split ตรวจว่าเกิดอะไรขึ้นระหว่าง 2026-04-01 (F1=0.9999) กับ 2026-04-06 (F1=0.025) — เป็น data leakage หรือ bug? | ไม่รู้ก็แก้ไม่ได้ | 1 วัน |

**Deliverable Phase 1:** โมเดลที่ deploy จริงมี F1 ≥ 0.5, มี test ครอบคลุม critical path, มี Sentry alert

### Phase 2 — ยกระดับให้เป็น Production-grade (1–3 เดือน)

| ลำดับ | งาน | เหตุผล |
|-------|-----|--------|
| P2.1 | **เปลี่ยนการ generate forecast เป็น scheduled job** (cron 4 ครั้ง/วัน) แทน per-request → spawn Python | ใช้ทรัพยากรน้อยลง 10–100 เท่า, latency ตอบจาก 30 วิ → 200 มิลลิวินาที |
| P2.2 | **Cache forecast ใน Redis (Upstash free tier) หรือ Postgres** + TTL 6 ชม. | ลด CPU + รองรับ horizontal scale |
| P2.3 | **เพิ่ม persistent DB (Render Postgres free)** เก็บ forecast history, prediction logs, drift metrics | ตอนนี้ JSON ภายใน container หาย ทุก deploy |
| P2.4 | **Spatial gridded forecast** — แทนจุดเดียว ทำเป็น grid 0.25° × 0.25° ครอบคลุม 77 จังหวัด (~120 cells) → cron job เดียว loop ทำทุก cell | Map page จะใช้ค่าจริง ไม่ใช่ `Math.sin()` fake |
| P2.5 | **API auth (API key หรือ Supabase JWT)** บน `/api/forecast` + ลด rate limit สำหรับ anonymous | ป้องกัน DoS / abuse |
| P2.6 | **Push notification trigger** เมื่อ probability วันถัดไปเกิน threshold + ใช้ `expo-notifications` ที่ติดตั้งอยู่แล้ว | หน้า alerts จะมีฟังก์ชันจริง |
| P2.7 | **Real-time NDVI** จาก MODIS Near-Real-Time (NRT) หรือ VIIRS | แทน climatology ทำให้จับ vegetation stress ของจริง |
| P2.8 | **CI/CD ผ่าน GitHub Actions** — lint, test, build, deploy preview env | ลดความเสี่ยง deploy พัง |
| P2.9 | **เพิ่ม temporal features** — rolling 3/7/14/30 วัน, anomaly จาก climatology, sin/cos day-of-year | เพิ่มประสิทธิภาพโมเดล |
| P2.10 | **A/B / Shadow mode** สำหรับโมเดลใหม่ | deploy โมเดลใหม่อย่างปลอดภัย |
| P2.11 | **Migrate ERA5/NDVI binary data ไป Git LFS หรือ S3 + DVC** | repo เบาขึ้น clone เร็วขึ้น |
| P2.12 | **Frontend offline mode** + แสดง "as of" timestamp ของ forecast cache | UX ดีขึ้น user เชื่อถือได้ |

**Deliverable Phase 2:** ระบบรองรับผู้ใช้หลักพันต่อวัน, latency P95 < 1 วิ, มี alert/notification ใช้งานได้, forecast ครอบคลุมทั้งประเทศ

### Phase 3 — เพิ่มมูลค่าทางวิทยาศาสตร์/ผู้ใช้ (3–6 เดือน)

1. **Temporal models** — LSTM / Temporal Convolutional / Transformer (Informer, TFT) บนลำดับเวลา 30 วันย้อน → ดีกว่า tabular แน่นอน
2. **Probabilistic forecasting** — Quantile Regression Forest หรือ NGBoost คืน prediction interval ไม่ใช่จุดเดียว → user เห็น uncertainty
3. **Ensemble** — รวม LightGBM + XGBoost + LSTM ผ่าน meta-learner
4. **Hospital admission integration** — ใช้ข้อมูลผู้ป่วย heat-related illness จากกระทรวงสาธารณสุข เป็น auxiliary label หรือ downstream task
5. **PM2.5 / Air Quality coupling** — ความร้อน + ฝุ่น เป็นปัจจัยร่วมที่อันตรายกว่าแต่ละตัว
6. **Sub-seasonal to Seasonal (S2S)** — extend horizon จาก 16 วัน → 30 / 90 วัน ใช้ ECMWF S2S data
7. **Personal heat exposure dashboard** — user ป้อน outdoor activity → ระบบเตือนชั่วโมงที่ปลอดภัย, ใช้ WBGT ที่ตำแหน่งจริง
8. **Open API + Developer Portal** — มี API key, doc, sandbox

### Phase 4 — Scaling และ Impact (6+ เดือน)

1. **ขยายไปประเทศอื่นในเอเชียตะวันออกเฉียงใต้** (เวียดนาม, ลาว, กัมพูชา, มาเลเซีย) — climate / culture ใกล้กัน, ใช้ ERA5 ได้เลย
2. **Partnership กับกรมอุตุฯ / กรมอนามัย / สสส.** — Heatwave-AI กลายเป็น input เข้าระบบเตือนภัยรัฐ
3. **Climate-change scenarios** — รัน CMIP6 projections ดู heatwave frequency ปี 2050
4. **Citizen science** — รับ user-submitted thermal sensor / mobile temperature → ground-truthing
5. **Policy dashboard** — ให้ผู้กำหนดนโยบายดู vulnerable populations × heat exposure × hospital capacity
6. **บทความวิชาการ + open-source release** — เผยแพร่งานสู่ community

---

## 5. ข้อเสนอเชิง Action ที่ทำได้ทันทีสัปดาห์นี้

ต่อจากการอ่าน คำแนะนำสั้นๆ ในระดับ commit:

1. ใน `Heatwave-AI-TRAIN/models/xgboost_model.py` ใส่ `scale_pos_weight = neg_count / pos_count` ตอน fit
2. ใน `Heatwave-AI-TRAIN/models/lightgbm_model.py` เปิด `is_unbalance=True` หรือ `class_weight='balanced'`
3. ใน `Heatwave-AI-TRAIN/models/mlp_model.py` และ `kan_model.py` มีการคำนวณ `pos_weight` ใน `BCEWithLogitsLoss` อยู่แล้ว — ตรวจสอบว่าทำงานถูก หรือ NaN ไหม (ผลลัพธ์ F1=0 แปลว่าน่าจะ predict 0 หมดอยู่ดี อาจมี bug)
4. ใน `Heatwave-AI-Backend-Elysia/prediction/predictor.py` ขยาย `MODEL_REGISTRY` รวม `lightgbm`, `xgboost`, `mlp`, `kan` ให้ครบ และให้ `BACKEND` รองรับการเปลี่ยน default model
5. ใน `Heatwave-AI-Backend-Elysia/Dockerfile.render` เพิ่มบรรทัด `wget` สำหรับ `lightgbm_model.pkl`, `xgboost_model.pkl` ฯลฯ
6. ตั้ง GitHub Action สำหรับ `bun test` และ `pytest` (แม้จะยังไม่มี test ก็เริ่ม fail-skeleton ไว้)
7. เพิ่ม `.env.example` ทั้ง 2 repo + เปลี่ยน CORS ให้อ่านจาก env

---

## 6. สรุปผู้บริหาร (Executive Summary)

โปรเจกต์นี้มี **โครงสร้างทางวิศวกรรมที่ดีและถูกต้องตามทฤษฎี** ในระดับที่ใกล้เคียง production-ready: monorepo ชัดเจน, choice ของ tech stack เหมาะสม, security ฝั่ง backend แน่นกว่ามาตรฐานทั่วไป, การเลือก label (WBGT) สอดคล้องกับสภาพภูมิอากาศไทย, และข้อมูล ERA5+NDVI 26 ปีเพียงพอให้สร้างโมเดลที่มีคุณค่า

อย่างไรก็ตาม **ปัญหาคอขวดหลักคือ "คุณภาพโมเดลใน production"**: 3 ใน 5 โมเดลทำนาย F1=0 (predict majority class ตลอด), โมเดลที่ deploy อยู่จริง (Balanced RF) มี F1 = 0.025 ในรอบล่าสุด ขณะโมเดลดีที่สุด (LightGBM, F1 = 0.65) ไม่ได้ deploy นอกจากนี้หน้า Map ใช้ค่าสังเคราะห์ด้วย `Math.sin()` แทนผลโมเดลจริง ทำให้สิ่งที่ผู้ใช้เห็นไม่ตรงกับสิ่งที่ระบบทำนายได้

**ลำดับความสำคัญแนะนำ**:
1. (สัปดาห์นี้) แก้ class imbalance ใน 4 โมเดลที่เหลือ + deploy LightGBM
2. (เดือนนี้) ใส่ test, persistent DB, Sentry, scheduled job แทน spawn-on-request
3. (ไตรมาสนี้) Spatial gridded forecast 77 จังหวัด + push notification + temporal features
4. (ครึ่งปี) Temporal models + probabilistic forecast + ขยายเขตภูมิประเทศ

หากดำเนินการตาม Phase 1 ได้ครบ Heatwave-AI จะเปลี่ยนจาก "demo ใช้งานพอได้" → "ระบบที่ผู้ใช้ในไทยเชื่อถือและพึ่งพาในชีวิตจริงได้"

---

*รายงานนี้สร้างเมื่อ 9 พฤษภาคม 2026 จากการอ่านโค้ดและไฟล์ผลการทดลองตรง — ไม่ใช่เอกสารเก่า*
