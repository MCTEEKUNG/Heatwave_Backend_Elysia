# HeatAI — Model & Data Specifications (Paper Reference)

คำตอบอ้างอิงจาก source code และ experiment results จริงของโปรเจกต์

---

## Train/Test Split

**โปรเจกต์นี้ใช้ Random Stratified Split ไม่ใช่ Temporal Split**

| Subset         | สัดส่วน | รายละเอียด                                          |
| -------------- | ------- | --------------------------------------------------- |
| **Train**      | **70%** | สุ่มแบบ Stratified — ไม่ใช่ปี 2000–2012             |
| **Validation** | **15%** | สำหรับ Early Stopping (MLP, KAN, XGBoost, LightGBM) |
| **Test**       | **15%** | Benchmark สุดท้าย — ไม่แตะระหว่าง train             |

```yaml
# config/config.yaml
split:
  train: 0.70
  val: 0.15
  test: 0.15
  random_state: 42
  stratify: true # รักษาสัดส่วน class ให้เท่ากันทุก subset
```

> [!WARNING]
> สำหรับ Paper ควรระบุว่าใช้ **Random Split (stratified)** ไม่ใช่ Temporal Split
> หากต้องการ Temporal Split (train 2000–2012, test 2013–2015) ต้องแก้ `preprocessing.py`

---

## Feature List ที่เข้า Model (Input Features)

Features ที่เข้า Model จริง ๆ หลังผ่าน `_get_feature_names()` มีดังนี้

| #   | Feature      | ที่มา               | หน่วย   | หมายเหตุ                                |
| --- | ------------ | ------------------- | ------- | --------------------------------------- |
| 1   | `t2m_c`      | ERA5 `t2m`          | °C      | อุณหภูมิอากาศ 2m                        |
| 2   | `d2m_c`      | ERA5 `d2m`          | °C      | อุณหภูมิจุดน้ำค้าง 2m                   |
| 3   | `rh`         | Derived (Magnus)    | %       | ความชื้นสัมพัทธ์ — **เพิ่มใหม่**        |
| 4   | `heat_index` | Derived (Rothfusz)  | °C      | ดัชนีความร้อน — ใช้เป็น Label basis     |
| 5   | `wind_speed` | Derived จาก u10+v10 | m/s     | magnitude ของลม                         |
| 6   | `sp`         | ERA5                | Pa      | ความกดอากาศพื้นผิว                      |
| 7   | `ndvi`       | MODIS MOD13A3       | [-1, 1] | ดัชนีพืชพรรณ (**เมื่อ enabled**)        |
| 8   | `ndvi_lag1`  | MODIS MOD13A3       | [-1, 1] | NDVI เดือนที่แล้ว (**เมื่อ enabled**)   |
| 9   | `ndvi_lag2`  | MODIS MOD13A3       | [-1, 1] | NDVI 2 เดือนที่แล้ว (**เมื่อ enabled**) |

**ตัวแปรที่ไม่ได้ใช้เป็น Feature (เป็นแค่ intermediate):**

- `t2m` (Kelvin) — แปลงเป็น `t2m_c` แล้วทิ้ง
- `d2m` (Kelvin) — แปลงเป็น `d2m_c` แล้วทิ้ง
- `u10`, `v10` — รวมเป็น `wind_speed` แล้วทิ้ง

---

## คำถามเพิ่มเติม (สำคัญต่อ Paper)

---

### 1️⃣ Model Training Period — ปีไหนคือของจริง?

| ที่                  | ข้อมูล                     | ค่าจริง                                                      |
| -------------------- | -------------------------- | ------------------------------------------------------------ |
| Folder ชื่อ          | `Era5-data-2000-2026`      | ชื่อ folder เท่านั้น — **ไม่ได้หมายความว่ามีข้อมูลถึง 2026** |
| ค่า config จริง      | `config.yaml → data.years` | **2000–2015 เท่านั้น**                                       |
| ข้อมูลที่ดาวน์โหลดมา | `era5_surface_YYYY.nc`     | ครอบคลุมถึงปี 2015                                           |

**ตอบ: Training Period จริงคือ 2000–2015 (16 ปี)**

---

### 2️⃣ จำนวน Sample

ขึ้นอยู่กับ Resolution และช่วงเวลา

```
ERA5 Grid ของไทย (approx):
  Latitude:  5.5°N – 20.5°N at 0.25° → ~60 grid cells
  Longitude: 97.5°E – 105.75°E at 0.25° → ~34 grid cells
  Spatial points: ~60 × 34 = ~2,040 grid cells

Temporal:
  16 ปี × 365 วัน/ปี ≈ 5,840 time steps (hourly → สรุปเป็น snapshot per hour)
  ERA5 บันทึกเป็น Hourly → 16 × 365 × 24 = ~140,000 time steps

Total (approx) = 2,040 grid cells × จำนวน hourly snapshots
```

> [!NOTE]
> จำนวน Sample ที่แน่นอนขึ้นอยู่กับ Temporal Resolution ของ ERA5 ที่ดาวน์โหลดมา
> ต้องรัน `python main.py --mode train` ให้เสร็จแล้วดู log ที่พิมพ์ว่า `Total samples: X`

---

### 3️⃣ Balanced Random Forest Parameters

```yaml
# config/config.yaml
models:
  balanced_rf:
    n_estimators: 200 # จำนวนต้นไม้
    max_depth: 15 # ความลึกสูงสุดต่อต้น
    random_state: 42 # seed สำหรับ reproducibility
    n_jobs: -1 # ใช้ CPU ทุก core
```

| Parameter      | ค่าที่ใช้              | เหตุผล                                                                  |
| -------------- | ---------------------- | ----------------------------------------------------------------------- |
| `n_estimators` | 200                    | สมดุลระหว่าง accuracy และ computation                                   |
| `max_depth`    | 15                     | ป้องกัน overfitting                                                     |
| `random_state` | 42                     | Reproducible splits                                                     |
| `n_jobs`       | -1                     | Parallel training ทุก CPU core                                          |
| **Algorithm**  | `BalancedRandomForest` | จาก `imbalanced-learn` — handle class imbalance ด้วย balanced bootstrap |

---

### 4️⃣ Model Performance (ผลจริงจาก Experiment)

> [!IMPORTANT]
> ผลเหล่านี้เป็นผลจาก **Label แบบเก่า** (`t2m_c >= 35°C`) เนื่องจาก Retrain ยังไม่ได้รัน
> หลังเปลี่ยนเป็น Heat Index definition แล้ว ค่าเหล่านี้จะเปลี่ยนไป

| Rank | Model                      | Accuracy   | Precision  | Recall     | F1         | ROC-AUC    | เวลา Train   |
| ---- | -------------------------- | ---------- | ---------- | ---------- | ---------- | ---------- | ------------ |
| 🥇 1 | **Balanced Random Forest** | **1.0000** | **0.9927** | **1.0000** | **0.9963** | **1.0000** | 190 วินาที   |
| 🥈 2 | LightGBM                   | 0.9981     | 0.4815     | 1.0000     | 0.6500     | 0.9990     | 7.3 วินาที   |
| 🥉 3 | KAN                        | 0.9982     | 0.0000     | 0.0000     | 0.0000     | N/A        | 1,398 วินาที |
| 4    | MLP Neural Network         | 0.9982     | 0.0000     | 0.0000     | 0.0000     | N/A        | 1,527 วินาที |
| 5    | XGBoost                    | 0.9982     | 0.0000     | 0.0000     | 0.0000     | 0.8777     | 7.2 วินาที   |

> [!WARNING]
> **KAN, MLP, XGBoost ได้ F1 = 0.0** แปลว่าโมเดลเหล่านี้ **ทำนาย heatwave ไม่ได้เลย** (predict 0 ทั้งหมด)
> สาเหตุคือ Class Imbalance รุนแรง — ต้องปรับ `class_weight` หรือ threshold

---

### 5️⃣ Prediction Output

**Model Output:** ค่า **Raw Probability [0.0 – 1.0]**

```python
# จาก prediction/predictor.py
predictions = model.predict(X)          # binary: 0 หรือ 1
probabilities = model.predict_proba(X)  # float: [P(normal), P(heatwave)]
```

**การแปลงเป็น Risk Level ยังไม่มีใน codebase นี้** — ปัจจุบัน output คือ:

- `predict()` → **0 หรือ 1** (Binary)
- `predict_proba()` → **Probability float** เช่น 0.83

หากต้องการ Low / Medium / High Risk ต้องเพิ่ม threshold logic เอง เช่น:

```python
prob = model.predict_proba(X)[:, 1]
risk = pd.cut(prob, bins=[0, 0.33, 0.66, 1.0],
              labels=["Low Risk", "Medium Risk", "High Risk"])
```
