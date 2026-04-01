# รายงานวิเคราะห์แหล่งข้อมูล (Data Sources Analysis Report)
**โปรเจกต์:** HEATWAVE-AI-Prediction

จากการตรวจสอบและวิเคราะห์ซอร์สโค้ด (Source Code) ภายในโปรเจกต์อย่างละเอียด (ไม่เพียงแค่อ่านจากไฟล์ Markdown แต่ยืนยันจากการเขียนสคริปต์ดึงข้อมูลจริง) พบว่าโปรเจกต์นี้มีการใช้ข้อมูลจาก **2 แหล่งข้อมูลหลัก** เพื่อนำมาสร้างฟีเจอร์ (Features) ให้กับโมเดล AI ในการทำนายโอกาสเกิดคลื่นความร้อน (Heatwave) ดังนี้:

---

## แหล่งข้อมูลที่ 1: ERA5 Reanalysis Climate Data
**แหล่งที่มา:** Copernicus Climate Data Store (CDS)

ข้อมูลสภาพอากาศและภูมิอากาศพื้นผิว (Surface Level) ที่วิเคราะห์ย้อนหลัง ซึ่งถือเป็นข้อมูลหลักที่ใช้เป็นทั้งตัวแปรฟีเจอร์และใช้สร้างตัวแปรเป้าหมาย (Labeling)

### 📌 ข้อมูลที่ใช้งานจริง (ตัวแปร/Features)
อ้างอิงจากการโหลดข้อมูลใน `utils/data_loader.py` และการตั้งค่าใน `config/config.yaml`:
- `t2m` (2m Temperature): อุณหภูมิที่ระดับ 2 เมตร (ใช้สร้าง Label ด้วย)
- `d2m` (2m Dewpoint Temperature): อุณหภูมิจุดน้ำค้างที่ระดับ 2 เมตร
- `sp` (Surface Pressure): ความกดอากาศที่พื้นผิว
- `u10` (10m U-wind Component): ความเร็วลมแกน U ที่ระดับ 10 เมตร
- `v10` (10m V-wind Component): ความเร็วลมแกน V ที่ระดับ 10 เมตร

### ⚙️ สคริปต์ที่ใช้ดึงและโหลดข้อมูล (Code Evidence)
1. **การดาวน์โหลด (Download):**
   - ไฟล์: `download_extension_data.py` (คลาส `ERA5ExtensionDownloader`)
   - ใช้ไลบรารี: `cdsapi` (Copernicus Climate Data Store API)
   - สคริปต์เรียกใช้งาน `client.retrieve("reanalysis-era5-single-levels", {...})` เพื่อดาวน์โหลดข้อมูลเป็นไฟล์ NetCDF (`.nc`) ของพื้นที่ประเทศไทย (`THAILAND_AREA`) ครอบคลุมหลายปี
2. **การโหลดข้อมูลเข้าโมเดล (Ingestion):**
   - ไฟล์: `utils/data_loader.py` (คลาส `ERA5DataLoader`)
   - ใช้ไลบรารี: `xarray` และ `pandas`
   - สคริปต์ใช้ `xr.open_dataset(fname, engine="netcdf4")` โหลดไฟล์ที่ดาวน์โหลดมา แล้วแปลงเป็นตาราง (DataFrame)

---

## แหล่งข้อมูลที่ 2: Satellite NDVI (Normalized Difference Vegetation Index)
**แหล่งที่มา:** Google Earth Engine (GEE)

ข้อมูลดัชนีพืชพรรณจากดาวเทียม ซึ่งถูกนำมาเสริมเป็นฟีเจอร์เพื่อให้โมเดลเรียนรู้ความสัมพันธ์ระหว่างพื้นที่สีเขียวและการเกิดคลื่นความร้อน

### 📌 ข้อมูลที่ใช้งานจริง (ตัวแปร/Features)
- `ndvi`: ดัชนีพืชพรรณรายเดือน (Monthly Composite)
- `ndvi_lag1` / `ndvi_lag2`: ข้อมูล NDVI ย้อนหลัง 1 และ 2 เดือน (สร้างขึ้นผ่าน `utils/ndvi_processor.py`)
- โปรดักต์ดาวเทียม: **MODIS MOD13A3 v061** ความละเอียด 1 กิโลเมตร

### ⚙️ สคริปต์ที่ใช้ดึงและโหลดข้อมูล (Code Evidence)
1. **การดาวน์โหลด (Download):**
   - ไฟล์: `utils/ndvi_downloader.py` (คลาส `NDVIDownloader`) และ `download_extension_data.py` (คลาส `NDVIExtensionDownloader`)
   - ใช้ไลบรารี: `earthengine-api` (ไลบรารี `ee`)
   - สคริปต์ยืนยันตัวตนกับ Google Cloud Project (`ee.Initialize(project=...)`) และดึงข้อมูลจาก ImageCollection รหัส `MODIS/061/MOD13A3`
   - มีการสั่ง Export ผ่าน `ee.batch.Export.image.toDrive(...)` เพื่อส่งไฟล์ GeoTIFF ออกไปยัง Google Drive
2. **การประมวลผลและการผสานข้อมูล (Processing & Merging):**
   - ไฟล์: `utils/ndvi_processor.py` และ `utils/preprocessing.py`
   - ข้อมูล `.tif` ที่ดาวน์โหลดมา จะถูกอ่านและจัดรูปแบบ (Resample) ให้มีความละเอียดกริด (Grid) ตรงกับข้อมูล ERA5 (0.25 องศา) ก่อนจะถูก Merge เข้ากับฟีเจอร์หลักเพื่อเข้าสู่กระบวนการเทรน

---

## 📋 สรุป (Summary)
โปรเจกต์นี้เขียนสคริปต์ไปดึงข้อมูลจาก APIs ภายนอก 2 แห่งจริงๆ ได้แก่:
1. **API ของ Copernicus (CDS API):** ดึงข้อมูลสภาพอากาศตัวแปรพื้นผิว 5 ตัวแปร
2. **API ของ Google Earth Engine (GEE Python API):** สั่งรัน Task บนคลาวด์เพื่อดึงภาพถ่ายดาวเทียม MODIS (NDVI) ออกมา

ข้อมูลทั้งสองส่วนจะถูกดาวน์โหลดมาเก็บที่เครื่อง (Local) ก่อนจะใช้สคริปต์ Python ในแฟ้ม `utils/` แปลงข้อมูลดิบ (`.nc` และ `.tif`) รวมกันเป็น DataFrame เดียว เพื่อป้อนให้โมเดล AI ทั้ง 5 ตัวครับ
