# คู่มือการดาวน์โหลด NDVI Data สำหรับ HeatAI

NDVI สำหรับโปรเจกต์นี้ดึงมาจาก **MODIS MOD13A3** ผ่าน **Google Earth Engine (GEE)**

---

## ขั้นตอนที่ 1 — สมัครบัญชี Google Earth Engine

1. ไปที่ [https://earthengine.google.com](https://earthengine.google.com)
2. คลิก **"Get Started"**
3. เลือก **"Noncommercial"** → เลือก **"Academia and Research"**
4. กรอกข้อมูล Project แล้วรอการอนุมัติ (ปกติ **ไม่เกิน 1 วัน**)

> [!NOTE]
> GEE ฟรีสำหรับงานวิจัยและการศึกษา ไม่มีค่าใช้จ่าย

---

## ขั้นตอนที่ 2 — ติดตั้ง earthengine-api และ Authenticate

เปิด terminal ภายใน virtual environment แล้วรัน:

```bash
# ติดตั้ง (น่าจะติดตั้งแล้วจาก requirements.txt)
pip install earthengine-api>=0.1.380

# ยืนยันตัวตนกับ Google (ทำครั้งเดียวต่อเครื่อง)
earthengine authenticate
```

คำสั่ง `authenticate` จะเปิด browser ให้ **login ด้วย Google Account เดียวกับที่สมัคร GEE** แล้ว copy token กลับมาใส่ใน terminal

---

## ขั้นตอนที่ 3 — ดาวน์โหลด NDVI ไป Google Drive

```bash
cd c:\Users\ASUS\Desktop\HeatAI-model-Predic\Heatwave-AI-TRAIN
python utils/ndvi_downloader.py
```

สคริปต์จะ submit Export Tasks (1 task ต่อปี = 16 tasks สำหรับ 2000–2015)

> [!WARNING]
> GEE Export ทำงาน **Asynchronous** — สคริปต์แค่ส่ง task ไป ยังไม่ได้ดาวน์โหลดมาทันที
> ต้องรอใน GEE Console ก่อน (ปกติ 30–60 นาทีต่อ task)

ตรวจสอบสถานะ task ที่:
👉 [https://code.earthengine.google.com/tasks](https://code.earthengine.google.com/tasks)

---

## ขั้นตอนที่ 4 — Download Files จาก Google Drive

หลัง Tasks เสร็จทั้งหมด จะมีโฟลเดอร์ `HeatAI_NDVI` ใน Google Drive

1. เปิด [Google Drive](https://drive.google.com)
2. เข้าโฟลเดอร์ `HeatAI_NDVI`
3. Download ไฟล์ `.tif` ทั้งหมด (จะมีปีละ 1 ไฟล์ = 16 ไฟล์)
4. วางไฟล์ทั้งหมดใน:

```
Heatwave-AI-TRAIN/data/ndvi/
├── NDVI_Thailand_2000.tif
├── NDVI_Thailand_2001.tif
├── ...
└── NDVI_Thailand_2015.tif
```

---

## ขั้นตอนที่ 5 — Process NDVI ให้ตรงกับ ERA5 Grid

```bash
python utils/ndvi_processor.py
```

สคริปต์จะ:

1. Load .tif ทั้งหมด → scale ×0.0001
2. Reproject จาก Sinusoidal → WGS84
3. Resample จาก 1km → ERA5 grid (0.25°)
4. Fill NaN (cloud masking)
5. สร้าง lag features (ndvi_lag1, ndvi_lag2)
6. บันทึกเป็น `data/ndvi/ndvi_aligned_era5.nc`

---

## ขั้นตอนที่ 6 — เปิดใช้ NDVI ใน Config และ Retrain

แก้ไข `config/config.yaml`:

```yaml
ndvi:
  enabled: true # เปลี่ยนจาก false → true
```

แล้ว Retrain โมเดลใหม่:

```bash
python main.py --mode train
# หรือ Start.bat → [1] Train ALL
```

---

## ⏱️ ประมาณเวลารวม

| ขั้นตอน                     | เวลา                                      |
| --------------------------- | ----------------------------------------- |
| สมัคร GEE Account           | ~1 วัน (รออนุมัติ)                        |
| Authenticate                | 5 นาที                                    |
| GEE Export Tasks (16 tasks) | ~8–16 ชั่วโมง (async ช่วง server ไม่ยุ่ง) |
| Download จาก Drive          | ~10–30 นาที (ขึ้นกับ internet)            |
| `ndvi_processor.py`         | ~15–30 นาที                               |
| Retrain โมเดล               | ~30–60 นาที                               |

---

## ทางเลือกอื่นหาก GEE ยุ่งยากเกินไป

| ทางเลือก                 | ข้อดี                        | ข้อเสีย                                      |
| ------------------------ | ---------------------------- | -------------------------------------------- |
| **GEE (แนะนำ)**          | ฟรี, Cloud masking อัตโนมัติ | ต้องรออนุมัติ account                        |
| NASA Earthdata (LP DAAC) | ดาวน์โหลดตรง                 | ต้องจัดการ tiles + projection เอง, ขนาด ~8GB |
| AppEEARS (NASA)          | UI ง่ายกว่า LP DAAC          | ช้า, ขึ้นกับ queue                           |
