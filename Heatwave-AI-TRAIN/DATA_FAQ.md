# HeatAI — Data Q&A

ตอบคำถามเกี่ยวกับข้อมูลที่ใช้ใน Training และ Prediction ของ HeatAI

---

## 1️⃣ ERA5 Variables ที่ใช้มีอะไรบ้าง?

ERA5 คือฐานข้อมูล **Reanalysis** จาก ECMWF (European Centre for Medium-Range Weather Forecasts)  
โปรเจกต์นี้ใช้เฉพาะ **Surface Level** (ชั้นพื้นผิว) ไม่ได้ใช้ Pressure Level

| ตัวย่อ | ชื่อเต็ม                | หน่วย       | คำอธิบาย                                               |
| ------ | ----------------------- | ----------- | ------------------------------------------------------ |
| `t2m`  | 2m Temperature          | Kelvin → °C | **อุณหภูมิอากาศ** ที่ความสูง 2 เมตรจากพื้นดิน 🌡️       |
| `d2m`  | 2m Dewpoint Temperature | Kelvin → °C | **อุณหภูมิจุดน้ำค้าง** — ใช้คำนวณความชื้นสัมพัทธ์ (RH) |
| `sp`   | Surface Pressure        | Pascal      | **ความกดอากาศ** ที่พื้นผิว                             |
| `u10`  | 10m U-wind Component    | m/s         | **ความเร็วลมแนวตะวันออก-ตะวันตก**                      |
| `v10`  | 10m V-wind Component    | m/s         | **ความเร็วลมแนวเหนือ-ใต้**                             |

### ❌ ตัวแปรที่ไม่มีในโปรเจกต์นี้

| ตัวแปร                     | เหตุผล                                    |
| -------------------------- | ----------------------------------------- |
| **Solar Radiation** (SSRD) | ไม่ได้อยู่ใน feature list ของ config.yaml |
| **Soil Temperature**       | ไม่ได้ดาวน์โหลด                           |
| **Total Precipitation**    | ไม่ได้ดาวน์โหลด                           |

> [!NOTE]
> ERA5 มีตัวแปรอีกกว่า 200 ตัว แต่โปรเจกต์นี้เลือกมาเฉพาะ 5 ตัวข้างต้นที่เกี่ยวข้องโดยตรงกับการคำนวณ Heat Index

---

## 2️⃣ NDVI ใช้จาก Satellite อะไร?

**ตอบ: MODIS (MOD13A3)** — ผลิตโดย NASA

| รายการ                  | รายละเอียด                              |
| ----------------------- | --------------------------------------- |
| **Product**             | MOD13A3 (Terra MODIS)                   |
| **Collection**          | Version 6.1 (ล่าสุด)                    |
| **Temporal Resolution** | **รายเดือน** (Monthly Composite)        |
| **Spatial Resolution**  | **1 km**                                |
| **ช่วงเวลา**            | 2000–2025 (ตรงกับ ERA5 training period) |
| **แหล่งดาวน์โหลด**      | Google Earth Engine (GEE)               |

### เปรียบเทียบตัวเลือก Satellite NDVI

| Satellite            | Resolution | Period                | เหตุผลที่ไม่เลือก                |
| -------------------- | ---------- | --------------------- | -------------------------------- |
| **MODIS (เลือก)** ✅ | 1 km       | ตั้งแต่ 2000          | ครอบคลุมปีที่ต้องการทุกปี        |
| Landsat 7/8          | 30 m       | 1999–ปัจจุบัน         | ซับซ้อนมาก, มีช่องว่าง (SLC-off) |
| Sentinel-2           | 10 m       | ตั้งแต่ 2015 เท่านั้น | ไม่ครอบคลุมปี 2000–2014          |

---

## 3️⃣ Resolution ของข้อมูล

### ERA5 (Climate Data)

| รายการ                  | ค่า                                                   |
| ----------------------- | ----------------------------------------------------- |
| **Spatial Resolution**  | **0.25° × 0.25°** (~27 km ที่เส้นศูนย์สูตร)           |
| **Temporal Resolution** | รายชั่วโมง (Hourly) → โปรเจกต์นี้ใช้ผ่าน NetCDF รายปี |
| **ช่วงเวลา**            | 2000–2025 (26 ปี) — climatology 2000–2019, train 2020–2024, val 2025 |
| **Projection**          | Geographic (WGS84 / EPSG:4326)                        |

### NDVI (MODIS MOD13A3)

| รายการ                                | ค่า                                       |
| ------------------------------------- | ----------------------------------------- |
| **Spatial Resolution (raw)**          | **1 km × 1 km**                           |
| **Projection (raw)**                  | Sinusoidal (MODIS native)                 |
| **Spatial Resolution (หลัง process)** | **~0.25°** (Resample ให้ตรงกับ ERA5 grid) |
| **Temporal Resolution**               | Monthly Composite                         |
| **Projection (หลัง process)**         | Geographic (WGS84 / EPSG:4326)            |

> [!TIP]
> NDVI ถูก Reproject + Resample จาก 1 km (Sinusoidal) → 0.25° (WGS84) เพื่อให้ grid ตรงกับ ERA5 โดย `utils/ndvi_processor.py`

---

## 4️⃣ Label Heatwave สร้างยังไง?

โปรเจกต์นี้รองรับหลายวิธีการ label ผ่าน `config.heatwave_label.method` — เลือกวิธีที่เหมาะกับบริบทประเทศไทย

### วิธีปัจจุบัน (WBGT Mode — ค่า Default สำหรับประเทศไทย)

ประเทศไทยร้อนและชื้นสูง การใช้แค่อุณหภูมิอากาศ (Tmax) ไม่เพียงพอ เพราะเหงื่อไม่ระเหยได้ดีในอากาศชื้น WBGT (Wet-Bulb Globe Temperature) เป็นมาตรฐานที่กระทรวงสาธารณสุขไทยและกรมสวัสดิการและคุ้มครองแรงงานใช้อยู่แล้ว

```
heatwave = 1  ถ้า  WBGT >= 32.0°C  ติดต่อกัน >= 2 วัน ที่ตำแหน่งเดิม
heatwave = 0  ถ้า  ไม่เป็นไปตามเงื่อนไขข้างต้น
```

**สูตร WBGT (ABoM approximation, Lemke & Kjellstrom 2012):**

```
Step 1: RH (%) = Magnus formula จาก t2m_c + d2m_c
Step 2: e (hPa) = (RH/100) × 6.105 × exp(17.27·T / (237.7+T))
Step 3: WBGT = 0.567·T + 0.393·e + 3.94
Step 4: ถ้า WBGT >= 32°C ติดต่อกัน >= 2 วัน → label = 1
```

**เหตุผลที่เลือก 32°C:** ตรงกับระดับ "Extreme Caution" ของ OSHA/NIOSH และคำแนะนำสาธารณสุขไทย

### วิธีอื่นที่รองรับ (เลือกใน config.yaml)

| method | คำอธิบาย | เหมาะกับ |
|--------|----------|----------|
| `wbgt` ✅ | WBGT ≥ 32°C / ≥ 2 วัน | **Default — เหมาะสุดสำหรับไทย** |
| `heat_index` | HI ≥ 35°C / ≥ 2 วัน | ใช้ได้ — เป็นวิธีเดิม |
| `ehf` | Tmax เกิน Percentile 95 ของ climatology / ≥ 3 วัน | ดีที่สุดสำหรับงานวิจัย |
| `tropical_night` | Tmin ≥ 26°C / ≥ 2 คืน | ดูความล้มเหลวของการฟื้นตัวตอนกลางคืน |

### วิธีเก่า (Heat Index Mode — ยังเรียกใช้ได้ผ่าน config)

```
heatwave = 1  ถ้า  Heat Index >= 35.0°C  ติดต่อกัน >= 2 วัน
```

**ที่มาของ Heat Index:**

```
Step 1: RH (%) = Magnus formula จาก t2m_c + d2m_c
Step 2: Heat Index (°C) = Rothfusz Regression จาก t2m_c + RH
Step 3: ถ้า Heat Index >= 35°C ติดต่อกัน >= 2 วัน → label = 1
```

**ตัวอย่างที่แสดงให้เห็นความสำคัญ:**

| สถานการณ์                  | t2m  | RH    | Heat Index | Label               |
| -------------------------- | ---- | ----- | ---------- | ------------------- |
| กทม. ช่วงก่อนฝน (ร้อนชื้น) | 35°C | 84.5% | **59.7°C** | ✅ **1 (Heatwave)** |
| ภาคเหนือฤดูแล้ง (ร้อนแห้ง) | 35°C | 21.8% | **33.3°C** | ✅ **0 (Normal)**   |

### วิธีเก่า (Temperature Mode — ยังเรียกใช้ได้ผ่าน config)

```
heatwave = 1  ถ้า  t2m_c >= 35.0°C
heatwave = 0  ถ้า  t2m_c <  35.0°C
```

เปลี่ยนได้ใน `config/config.yaml`:

```yaml
data:
  labeling_method: "temperature" # เปลี่ยนจาก "heat_index" เป็น "temperature"
```

### เปรียบเทียบกับวิธีอื่น

| วิธี                             | โปรเจกต์นี้          | หมายเหตุ                           |
| -------------------------------- | -------------------- | ---------------------------------- |
| **Fixed Threshold (Heat Index)** | ✅ ใช้ (ค่า default) | เหมาะกับการ classify แบบ real-time |
| Fixed Threshold (Temperature)    | รองรับ (legacy mode) | ง่าย แต่ละเลยความชื้น              |
| **Percentile Threshold (P90)**   | ❌ ไม่ได้ใช้         | ต้องการข้อมูลอ้างอิง baseline      |
| **Consecutive Days** (≥3 วัน)    | ❌ ไม่ได้ใช้         | ต้องการ time-series per location   |
| Temperature Anomaly              | ❌ ไม่ได้ใช้         | ต้องการ climatological mean        |
