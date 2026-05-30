# Heatwave-AI — รีวิวเชิงวิชาการ: นิยาม Heatwave, การพยากรณ์ด้วย ML/DL และจุดที่ต้องปรับ

> วันที่: 30 พฤษภาคม 2026
> ผู้จัดทำ: อ่านโค้ดที่ deploy จริง (root repo) ตรง + อ้างอิงงานวิจัย peer-reviewed
> ขอบเขต: ตรวจ **โค้ดที่ tracked อยู่ที่ root** (`config.yaml`, `src/`, `prediction/`, `models/`) ซึ่งเป็น backend ที่ deploy จริง
>
> **หมายเหตุสำคัญ 2 ข้อ:**
> 1. รายงานนี้ **แก้ไขข้อสรุปหลักของ `PROJECT_REVIEW.md` (9 พ.ค.)** ซึ่งระบุว่าปัญหาใหญ่สุดคือ "class imbalance ทำให้ F1 = 0" — จริง ๆ แล้วปัญหาที่ลึกกว่าคือ **target leakage + กรอบงานเป็น diagnosis ไม่ใช่ forecasting** การไปแก้ class weight เพื่อดัน F1 ให้สูงขึ้นจะทำให้ "ตัวเลขสวยขึ้นแต่ทักษะจริงยังเป็นศูนย์"
> 2. โฟลเดอร์ `Heatwave-AI-TRAIN/` บนเครื่องนี้เหลือแต่ `__pycache__` (ไม่มี source `.py`) — จึง **ยืนยันไม่ได้** ว่าการแก้ temporal-split ที่บันทึกไว้ใน memory ทำในฝั่ง TRAIN จริงหรือไม่ แต่ **config ที่ deploy จริงยังเป็น random split** (รายละเอียดข้อ B4)

---

## ส่วน A — สรุปงานวิจัย (Research Synthesis)

### A1. นิยาม "คลื่นความร้อน" (Heatwave) — งานวิจัยพูดตรงกันใน 3 ประเด็น

**(1) Persistence / ระยะเวลาต่อเนื่อง เป็นส่วนหนึ่งของนิยาม — ไม่ใช่ทางเลือก**
ทุกนิยามมาตรฐานต้องการความ "ต่อเนื่องหลายวัน" เสมอ งานทบทวนเชิงระบบของ Perkins & Alexander นิยาม heatwave ว่า **อุณหภูมิเกิน percentile-90 ติดต่อกัน ≥ 3 วัน** (หรือค่า Excess Heat Factor เป็นบวก) [[1]](https://consensus.app/papers/details/4c2812a9e2a0553fbe8db350ebd8af9d/?utm_source=claude_desktop) งาน meta-analysis 556 อ้างอิงสรุปว่า "ไม่มีนิยามสากลเดียว" แต่ที่ใช้กันคือ **อุณหภูมิ ≥ percentile-95–99 ติดต่อกัน ≥ 2 วัน** และพบว่า *ความรุนแรง (intensity) สำคัญกว่าระยะเวลาเล็กน้อย* แต่ทั้งคู่เป็นเงื่อนไขร่วม [[2]](https://consensus.app/papers/details/ca96ce8f0a0f5963a2b662061bd34af5/?utm_source=claude_desktop) งานในเอเชียตะวันออกเฉียงใต้ (ตรงบริบทไทย) ใช้ **Tmax > percentile-90 ติดต่อกัน ≥ 3 วัน** [[3]](https://consensus.app/papers/details/0514bde70f26593384534ec1a7d13376/?utm_source=claude_desktop) และงานอินเดียหลายเมืองใช้ **> percentile-97 ติดต่อกัน 2 วัน** [[7]](https://consensus.app/papers/details/8e4f57bd03f45cab96659fd176b6f313/?utm_source=claude_desktop)

**(2) Threshold ควรเป็น "relative/percentile เฉพาะพื้นที่" มากกว่า "ค่าคงที่สากล"**
งานภาระโรคระดับโลกนิยาม heatwave แบบ **location-specific: อุณหภูมิเฉลี่ยรายวัน ≥ percentile-95 ของช่วงทั้งปี ต่อเนื่อง ≥ 2 วัน** [[8]](https://consensus.app/papers/details/73df4709bb5f53cb8a04a3628773295b/?utm_source=claude_desktop) งานล่าสุดที่ครอบคลุม **ประเทศไทยโดยตรง** เสนอ Health-based Excess Heat Factor (HEHF) ซึ่งกำหนด threshold จาก *ความสัมพันธ์อุณหภูมิ–การตาย* เฉพาะภูมิภาค และเพิ่ม **acclimatization index** = ผลต่างระหว่างอุณหภูมิเฉลี่ย 3 วันล่าสุด กับ 30 วันก่อนหน้า (จับ "ร้อนผิดปกติเมื่อเทียบกับที่ร่างกายชิน") — พบว่า HEHF อธิบายการตายได้ดีกว่านิยาม percentile และนิยามทางการของประเทศ และในไทยมีสัดส่วนการตายที่เกิดจาก heatwave ~4.50% [[5]](https://consensus.app/papers/details/25a12eb62f335c22865f754fa7b15733/?utm_source=claude_desktop)

**(3) ในเขตร้อนชื้น ต้องใส่ความชื้น — WBGT / Heat Index ดีกว่าอุณหภูมิแห้งล้วน**
WBGT ระบุ heatwave ได้สัมพันธ์กับการเข้าโรงพยาบาลด้วยโรคจากความร้อนดีกว่าอุณหภูมิอากาศ (RR สูงสุด 2.96) และจับ heatwave ได้ยาวกว่า 1.15 เท่า [[4]](https://consensus.app/papers/details/f64832bc262b598386b25f2d6c04c39e/?utm_source=claude_desktop) งานของ Bureau of Meteorology ออสเตรเลียพบว่า **เขตร้อน** ต้องใช้ EHF เวอร์ชันที่รวม Heat Index ควบคู่อุณหภูมิแห้ง จึงจะเตือนภัย heatwave ชื้นได้แม่นยำ [[6]](https://consensus.app/papers/details/02e30413e5625879a6913a39f32ad40c/?utm_source=claude_desktop)

> **บทสรุป A1:** นิยามที่ "ถูกต้องตามงานวิจัย" สำหรับไทย = **ดัชนีที่รวมความชื้น (WBGT/HI หรือ EHF-HI) ที่เกิน percentile เฉพาะพื้นที่ ต่อเนื่อง ≥ 2–3 วัน** โดยควรเทียบกับ baseline/acclimatization

### A2. การพยากรณ์ heatwave ด้วย ML/DL — งานวิจัยมองเป็น "forecast ที่ lead time" เสมอ

หัวใจคือ: **ทำนายโอกาสเกิด heatwave ที่เวลา t+k จากตัวแปรที่รู้ได้ ณ เวลา ≤ t** ไม่ใช่คำนวณว่าวันนี้ร้อนเกิน threshold ไหม

- **Lead time มีตั้งแต่ราย 1–7 วัน ถึงราย 1–5 เดือน** เช่น seasonal forecast ของ heatwave ด้วย ML 5 แบบ ใช้ฟีเจอร์ 13 ตัว (atmospheric + landscape) ลีดถึง 5 เดือน โดย **Balanced Random Forest ให้ผลเสถียรที่สุด** (balanced accuracy ~0.77) [[10]](https://consensus.app/papers/details/164da53c789559ee990020f65a06fd18/?utm_source=claude_desktop)
- **Predictors ที่ใช้จริงในงานวิจัย** ไม่ใช่แค่ T/RH วันเดียว แต่เป็นตัวขับเชิงพลวัตและพื้นผิว: **geopotential height 500 hPa (รูปแบบการไหลเวียน), sea-level pressure, soil moisture/soil water, runoff, evaporation, SST** — โดย CNN ทำนาย heatwave ยาวนานได้ล่วงหน้า 15 วันจากสนาม surface temp + 500 hPa geopotential [[11]](https://consensus.app/papers/details/e1729ec3e94e595e92976917de91753a/?utm_source=claude_desktop) งานเชิงความน่าจะเป็นแยก "fast drivers (geopotential)" กับ "slow drivers (soil moisture)" ชัดเจน [[12]](https://consensus.app/papers/details/5421c38eca3e55d984411191d16d202a/?utm_source=claude_desktop)
- **Land–atmosphere coupling สำคัญ**: การเพิ่ม soil moisture หลายชั้น + multi-step loss ยกความแม่นพยากรณ์ heatwave ขึ้น 5.9–11.2% เทียบกับโมเดลที่ใช้บรรยากาศอย่างเดียว [[13]](https://consensus.app/papers/details/bbd22d647966519dbe039282ad9ca124/?utm_source=claude_desktop) — นี่คือเหตุผลเชิงฟิสิกส์ที่ทำให้ **NDVI/ความชื้นดิน** ของโปรเจกต์นี้มีคุณค่า (ถ้าใช้แบบ real-time ไม่ใช่ climatology)
- **โมเดลเชิงเวลา (LSTM/CNN/hybrid) เป็นมาตรฐาน**: LSTM ทำนาย extreme heat ราย 1–3 วันได้แม่น และ SHAP ชี้ว่า **ความชื้นและอุณหภูมิสูงสุดเป็นตัวแปรเด่น** [[14]](https://consensus.app/papers/details/1a504aa0502a5d029caff349c4d2b04d/?utm_source=claude_desktop); hybrid STL-ARIMA-LSTM ที่แยกฤดูกาลออกก่อน ชนะโมเดลเดี่ยว [[15]](https://consensus.app/papers/details/5a360ccc7ecf5f89ad629f9558655c68/?utm_source=claude_desktop); งาน marine heatwave ใช้ RF/LSTM/CNN เทียบกันที่หลาย lead time [[16]](https://consensus.app/papers/details/7b45696075e55022892a6f1003262a6c/?utm_source=claude_desktop)
- **Explainability (SHAP/LIME) เป็น norm** ของสายงานนี้ เพื่อยืนยันว่าโมเดลเรียนรู้ตัวขับเชิงฟิสิกส์จริง ไม่ใช่ leak [[10]](https://consensus.app/papers/details/164da53c789559ee990020f65a06fd18/?utm_source=claude_desktop)[[14]](https://consensus.app/papers/details/1a504aa0502a5d029caff349c4d2b04d/?utm_source=claude_desktop)

> **บทสรุป A2:** งานพยากรณ์ heatwave จริง = **predict occurrence/probability ที่ lead time จาก antecedent + synoptic + land-surface predictors** มีการแยกเวลา features (≤ t) ออกจาก target (t+k) อย่างเคร่งครัด

### A3. การประเมินผลกับเหตุการณ์หายาก (Rare-event evaluation)

- **Accuracy หลอกตาเมื่อ imbalance รุนแรง**: เมื่อ positive ~0.2% โมเดลที่ทำนาย "ไม่เกิด" ตลอดได้ accuracy ~99.8% โดยไร้ทักษะ — งานจำลองแสดงว่ายิ่ง imbalance มาก accuracy ยิ่งสูงปลอม ๆ ขณะที่ PPV/precision พังลง [[19]](https://consensus.app/papers/details/82307269120d59f4ae9620099a07085a/?utm_source=claude_desktop) ตรงกับ leaderboard ของโปรเจกต์ที่ accuracy 0.998 แต่ precision = 0
- **ใช้หลายเมตริก อย่าพึ่ง ROC-AUC อย่างเดียว**: AUPRC เผยจุดอ่อนที่ ROC-AUC ซ่อนไว้ในข้อมูล imbalance หนัก [[17]](https://consensus.app/papers/details/56edd00b52fc5610a0fc142b8ec64b3f/?utm_source=claude_desktop)[[18]](https://consensus.app/papers/details/1656e0169a535328b622d4ec904f9e74/?utm_source=claude_desktop) สำหรับ positive < 3% แนะนำ **MCC และ F2 เป็นเมตริกหลัก เสริมด้วย PR-AUC** [[20]](https://consensus.app/papers/details/837910e747235e7ca572e8b9d1a974bb/?utm_source=claude_desktop)
  - *ข้อควรระวัง (nuance):* มีงานโต้แย้งว่า PR-AUC ไม่ได้เหนือกว่า ROC เสมอ และ ROC ทนต่อ imbalance ได้ดี — ประเด็นคือ **ต้องดูหลายเมตริกพร้อม calibration ไม่ใช่ accuracy เดี่ยว ๆ** [[21]](https://consensus.app/papers/details/3e2a7a07b42a50a3af833b234812395d/?utm_source=claude_desktop)
- **Resampling (SMOTE/undersample) แก้ตัวเลขแต่ทำลาย calibration**: โมเดลที่เทรนบนข้อมูลที่ปรับ balance แล้วมัก calibrate แย่ ความน่าจะเป็นที่ออกมาเชื่อถือไม่ได้ ต้องมี plug-in correction [[22]](https://consensus.app/papers/details/145c928d87ac5481b38fc24cb8e529f9/?utm_source=claude_desktop) — สำคัญมากเพราะแอปนี้แสดง "heatwave_probability" ให้ผู้ใช้

> **บทสรุป A3:** รายงาน **PR-AUC + MCC + F2 + ROC-AUC + reliability/calibration curve** และ **จูน decision threshold** (Youden's J / Fβ) แทนการใช้ 0.5 — และระวัง resampling ทำ probability เพี้ยน

---

## ส่วน B — ตรวจโปรเจกต์เทียบงานวิจัย (Gap Analysis)

### B0. ปัญหาแกนกลางที่ร้อยทุกอย่างเข้าด้วยกัน: ระบบนี้ "วินิจฉัย" ไม่ได้ "พยากรณ์"

มีกรอบงาน 3 ระดับที่สับสนกัน:
1. **คำนวณ** ว่าสภาพ *ที่วัดได้วันนี้* เกิน threshold ไหม = **การใช้สูตรนิยาม (diagnosis)** ไม่ใช่ AI
2. **"ทำนาย"** โดยป้อน *ตัวแปรที่นิยาม label เอง* ให้โมเดล = **target leakage**
3. **"พยากรณ์"** โดยป้อน *สภาพอากาศที่สุ่มขึ้นมา* (`np.random`) = ไม่ใช่การพยากรณ์

ทั้ง 3 อย่างไม่มีอันไหน "พยากรณ์ heatwave ในอนาคตจากข้อมูลที่รู้ ณ ปัจจุบัน" ตามที่งานวิจัยทำ [[10]](https://consensus.app/papers/details/164da53c789559ee990020f65a06fd18/?utm_source=claude_desktop)[[11]](https://consensus.app/papers/details/e1729ec3e94e595e92976917de91753a/?utm_source=claude_desktop)[[12]](https://consensus.app/papers/details/5421c38eca3e55d984411191d16d202a/?utm_source=claude_desktop) ข้อ B1–B5 ด้านล่างคืออาการของช่องว่างกรอบงานเดียวกันนี้

### B1. 🔴 Target Leakage — ปัญหาที่ใหญ่ที่สุด

ใน `src/preprocessing.py`:
- `_generate_labels()` ตั้ง `heatwave = (heat_index >= 41).astype(int)` (บรรทัด ~342)
- `_get_feature_names()` คืน `heat_index` เป็น **ฟีเจอร์** ด้วย (บรรทัด ~377–385) และ `fit_transform()` ใช้ลิสต์นี้ (ไม่ใช่ `config.data.features` — ลิสต์ใน config เป็น dead code, `self.features` ไม่เคยถูกอ้างถึง)

→ โมเดลได้รับ **ปริมาณที่นิยาม label ของตัวเอง** เป็น input ผลคือ Balanced RF ได้ F1 = 0.9999 / accuracy = 1.0 (`leaderboard.json`, 2026-04-01) ซึ่งเป็นผล **เชิงกลไก ไม่ใช่ทักษะ**

⚠️ **การแก้ที่ผิด:** "ลบคอลัมน์ `heat_index` ออกจากฟีเจอร์" ไม่พอ เพราะ `rh` เป็นฟังก์ชันของ `t2m_c, d2m_c` และ `heat_index` เป็นฟังก์ชันของ `t2m_c, rh` ดังนั้น **`t2m_c` + `d2m_c` (ซึ่งยังเป็นฟีเจอร์อยู่) ก็ reproduce label ได้สมบูรณ์** การรั่วเป็นเชิงโครงสร้าง ไม่ใช่คอลัมน์เดียว → ต้องเปลี่ยน *กรอบปัญหา* (ดู C1)

### B2. 🔴 Label ไม่มี Persistence — ไม่ได้กำลังติดป้าย "heatwave"

`_generate_labels()` ติดป้ายแต่ละแถวอิสระ (`heat_index >= 41`) **ไม่มีเงื่อนไขต่อเนื่องหลายวันเลย** จึงเป็นการติดป้าย "ชั่วโมง/วันที่ร้อน" ไม่ใช่ "คลื่นความร้อน" ขัดกับทุกนิยามในงานวิจัยที่ต้องการ ≥ 2–3 วันต่อเนื่อง [[1]](https://consensus.app/papers/details/4c2812a9e2a0553fbe8db350ebd8af9d/?utm_source=claude_desktop)[[2]](https://consensus.app/papers/details/ca96ce8f0a0f5963a2b662061bd34af5/?utm_source=claude_desktop)[[3]](https://consensus.app/papers/details/0514bde70f26593384534ec1a7d13376/?utm_source=claude_desktop)[[8]](https://consensus.app/papers/details/73df4709bb5f53cb8a04a3628773295b/?utm_source=claude_desktop) (memory ระบุว่าตั้งใจใช้ "WBGT ≥ 32°C ติดต่อ ≥ 2 วัน" แต่โค้ดที่ deploy จริงไม่มี logic ต่อเนื่อง และใช้ heat_index ≥ 41 ไม่ใช่ WBGT)

### B3. 🟠 Threshold/Index ไม่เหมาะกับไทย

`config.yaml` ใช้ `labeling_method: heat_index`, `heatwave_heat_index_threshold: 41.0` — **41°C คือเกณฑ์ "Danger" ของ US NWS** ซึ่ง calibrate กับประชากรอเมริกา เป็นค่าคงที่สากล ไม่ใช่ percentile เฉพาะพื้นที่ งานวิจัยชี้ว่าควรเป็น **(ก) ดัชนีรวมความชื้นแบบ WBGT/EHF-HI** [[4]](https://consensus.app/papers/details/f64832bc262b598386b25f2d6c04c39e/?utm_source=claude_desktop)[[6]](https://consensus.app/papers/details/02e30413e5625879a6913a39f32ad40c/?utm_source=claude_desktop) **(ข) percentile เฉพาะพื้นที่** [[2]](https://consensus.app/papers/details/ca96ce8f0a0f5963a2b662061bd34af5/?utm_source=claude_desktop)[[8]](https://consensus.app/papers/details/73df4709bb5f53cb8a04a3628773295b/?utm_source=claude_desktop) และ **(ค) เทียบ acclimatization/anomaly** [[5]](https://consensus.app/papers/details/25a12eb62f335c22865f754fa7b15733/?utm_source=claude_desktop) — โครงการมี WBGT เป็น option อยู่แล้ว ควรสลับมาใช้

### B4. 🔴 Random Split = Temporal Leakage (ในโค้ด deploy)

`config.yaml` ยังตั้ง `split: {train: 0.7, val: 0.15, test: 0.15, random_state: 42, stratify: true}` และ `preprocessing.fit_transform()` ใช้ `train_test_split(...)` แบบสุ่ม → แถวจากวันเดียวกัน/ช่วงเวลาใกล้กันกระจายข้าม train/val/test ทำให้ผลดูดีเกินจริง (temporal leakage) memory ระบุว่าแก้เป็น year-based split (train 2020–2024 / val 2025) แล้ว แต่ **โค้ดที่ tracked อยู่ที่ root ยังเป็น random split** (ยืนยันฝั่ง TRAIN ไม่ได้เพราะไม่มี source) — leakage นี้ซ้อนทับกับ target leakage ใน B1

### B5. 🔴 `forecast.py` พยากรณ์จาก "อากาศที่สุ่มขึ้นมา"

`prediction/forecast.py::_generate_forecast_input()` สร้างอุณหภูมิ/น้ำค้าง/ลม/ความกดด้วย `np.random.normal(...)` แล้วป้อนเข้าโมเดล → ค่า `heatwave_probability` ที่ endpoint `/api/forecast` ส่งให้แอป **มาจากตัวเลขสุ่ม ไม่ใช่พยากรณ์อากาศจริง** (ไม่มีการดึง ERA5/Open-Meteo/พยากรณ์เชิงตัวเลข) ขัดกับ A2 ทั้งหมด นอกจากนี้:
- `np.random.seed(42)` ถูกตั้ง *หลัง* สุ่ม `temps_c` แล้ว (บรรทัด 51 ก่อน 54) → reproducibility ครึ่ง ๆ กลาง ๆ
- จุดเดียว lat=13.75 lon=100.50 (กรุงเทพ) เท่านั้น (one point fits all)
- `humidity_est = (t2m − d2m)` (index.ts/forecast) จริง ๆ คือ **dewpoint depression** (ยิ่งมากยิ่ง *แห้ง*) ติดป้ายผิดเป็น "ความชื้น" — แสดงผลกลับด้านได้

### B6. 🟠 Features บางเกินไปเทียบงานวิจัย

ใช้ ~9 ฟีเจอร์ (`t2m_c, d2m_c, rh, heat_index, wind_speed, sp, ndvi, ndvi_lag0/1/2`) งานวิจัยใช้ตัวขับที่โครงการนี้ยังไม่มี:
- **Synoptic/circulation**: geopotential height 500 hPa, SLP/pressure anomaly, ridge index [[11]](https://consensus.app/papers/details/e1729ec3e94e595e92976917de91753a/?utm_source=claude_desktop)[[12]](https://consensus.app/papers/details/5421c38eca3e55d984411191d16d202a/?utm_source=claude_desktop) (มีไฟล์ ERA5 upper-level อยู่แล้วใน config `upper_prefix`)
- **Land-surface**: soil moisture, evaporation, runoff (slow drivers ที่ยกความแม่นได้ 6–11%) [[13]](https://consensus.app/papers/details/bbd22d647966519dbe039282ad9ca124/?utm_source=claude_desktop)
- **Temporal**: rolling mean/max 3/7/14/30 วัน, anomaly เทียบ climatology, sin/cos day-of-year [[15]](https://consensus.app/papers/details/5a360ccc7ecf5f89ad629f9558655c68/?utm_source=claude_desktop)
- NDVI ตอน inference ใช้ seasonal climatology ไม่ใช่ real-time (สูญเสียคุณค่า land-atmosphere coupling)

### B7. 🟠 Imbalance & Metrics

- XGBoost/MLP/KAN ได้ F1 = 0 (collapse ไป majority class) — ขาด `scale_pos_weight`/`class_weight`/`pos_weight`/focal loss
- leaderboard รายงาน **accuracy** เด่น ซึ่งหลอกตาที่ positive ~0.2% [[19]](https://consensus.app/papers/details/82307269120d59f4ae9620099a07085a/?utm_source=claude_desktop) ควรเพิ่ม **PR-AUC, MCC, F2 + calibration** [[17]](https://consensus.app/papers/details/56edd00b52fc5610a0fc142b8ec64b3f/?utm_source=claude_desktop)[[20]](https://consensus.app/papers/details/837910e747235e7ca572e8b9d1a974bb/?utm_source=claude_desktop)
- ⚠️ แต่ **ต้องแก้ B1/B4 ก่อน** มิฉะนั้นการดัน F1 = แต่งตัวเลขปลอม (จุดที่ PROJECT_REVIEW เดิมพลาด) และ Balanced RF ใช้ undersampling ในตัว ระวัง calibration เพี้ยน [[22]](https://consensus.app/papers/details/145c928d87ac5481b38fc24cb8e529f9/?utm_source=claude_desktop)

### B8. 🟡 บั๊ก/หนี้ทางวิศวกรรมที่เจอตอนอ่านโค้ด

- **Config path พัง (ยืนยันแล้ว):** `predict.py`/`forecast.py` ใช้ default `config/config.yaml` และ `src/index.ts` ส่ง `--config .../config/config.yaml` แต่ `Dockerfile.render` บรรทัด 30 `COPY config.yaml ./` วางไว้ที่ `/app/config.yaml` เท่านั้น **ไม่เคยสร้างโฟลเดอร์ `config/`** → endpoint `/api/predict` และ `/api/forecast` **crash** ด้วย FileNotFoundError ตอนโหลด config (ซ้ำร้าย `prediction/predictor.py` โหลดโมเดลจาก `experiments/models/` แต่ Dockerfile ดาวน์โหลด `.pkl` ไปไว้ที่ `models/`)
- **Model registry ไม่ตรงกัน**: `prediction/predictor.py` มีแค่ `balanced_rf`; `src/predictor.py` มี 5 โมเดล แต่ `/api/predict/models` hardcode `["balanced_rf"]` และ LightGBM (F1 ดีสุด) ไม่ถูก deploy
- **Models dir ไม่ตรงกัน**: `prediction/predictor.py` โหลดจาก `experiments/models/`; `src/predictor.py` โหลดจาก `../models/` → เสี่ยงโหลดคนละไฟล์
- **Silent fallback อันตราย**: ถ้าไม่พบ `scaler.pkl` หรือ `scaler.transform` ล้มเหลว จะ log warning แล้ว **ใช้ raw features ต่อ** → output ผิดเงียบ ๆ (ควร raise)
- **CORS เปิดทุก origin** (`.use(cors())`) ใน production

---

## ส่วน C — สิ่งที่ควรปรับ (เรียงตามความสำคัญ)

### 🔴 C1 — เปลี่ยนกรอบจาก "diagnosis" เป็น "forecasting at lead time" (สำคัญสุด)
นิยามงานใหม่ให้ชัด: **ทำนาย P(heatwave ที่วัน t+k) จาก predictors ที่รู้ ณ ≤ t**
- target = label heatwave (มี persistence, ดู C2) ที่ **เลื่อนไปข้างหน้า k วัน**
- features = สภาพอากาศ/anomaly **ก่อนหน้า** (lagged) — **ห้ามใส่ index ของวันเป้าหมายเอง** ตัดวงจร leakage เชิงโครงสร้าง (B1)
- ถ้าต้องการเลเยอร์ "เตือนวันนี้ร้อนไหม" ให้แยกเป็น **diagnostic layer** (คำนวณสูตรตรง ๆ ไม่ต้องมีโมเดล) คนละทางกับ forecasting layer

### 🔴 C2 — แก้ label ให้เป็น heatwave จริง
ใช้ **percentile เฉพาะพื้นที่ (เช่น WBGT/Tmax > p90–p95) ต่อเนื่อง ≥ 2–3 วัน** [[2]](https://consensus.app/papers/details/ca96ce8f0a0f5963a2b662061bd34af5/?utm_source=claude_desktop)[[3]](https://consensus.app/papers/details/0514bde70f26593384534ec1a7d13376/?utm_source=claude_desktop)[[8]](https://consensus.app/papers/details/73df4709bb5f53cb8a04a3628773295b/?utm_source=claude_desktop) พิจารณา EHF/HEHF ที่มี acclimatization (3-day vs 30-day) สำหรับบริบทไทย [[5]](https://consensus.app/papers/details/25a12eb62f335c22865f754fa7b15733/?utm_source=claude_desktop) — สลับ config มาใช้ WBGT + เพิ่ม logic นับวันต่อเนื่อง

### 🔴 C3 — ใช้ temporal split + ปิด random split
เปลี่ยน `config.yaml` เป็น year-based (train 2020–2024 / val 2025) ให้ตรงกับที่ memory อ้างว่าทำแล้ว และ **คำนวณ percentile climatology จากปี train เท่านั้น** (กัน leakage)

### 🔴 C4 — ทำ forecast ให้ใช้ข้อมูลจริง
แทน `np.random` ด้วย **พยากรณ์เชิงตัวเลขจริง** (Open-Meteo/ECMWF/GFS) หรือ ERA5 ล่าสุด แล้วป้อน lagged features; ลบ `--cycles` ที่ ignored; แก้ `humidity_est` ให้เป็น RH จริง

### 🟠 C5 — เพิ่ม predictors ตามงานวิจัย
geopotential 500 hPa + SLP anomaly (มี ERA5 upper อยู่แล้ว) [[11]](https://consensus.app/papers/details/e1729ec3e94e595e92976917de91753a/?utm_source=claude_desktop)[[12]](https://consensus.app/papers/details/5421c38eca3e55d984411191d16d202a/?utm_source=claude_desktop), soil moisture/evaporation [[13]](https://consensus.app/papers/details/bbd22d647966519dbe039282ad9ca124/?utm_source=claude_desktop), rolling/anomaly/seasonal features [[15]](https://consensus.app/papers/details/5a360ccc7ecf5f89ad629f9558655c68/?utm_source=claude_desktop), NDVI แบบ real-time

### 🟠 C6 — เมตริก + threshold + calibration
หลังแก้ leakage แล้วค่อยจัดการ imbalance: ใส่ class weight/focal ให้ XGB/MLP/KAN, จูน threshold ด้วย PR-curve/Youden, รายงาน **PR-AUC + MCC + F2 + reliability curve** [[17]](https://consensus.app/papers/details/56edd00b52fc5610a0fc142b8ec64b3f/?utm_source=claude_desktop)[[20]](https://consensus.app/papers/details/837910e747235e7ca572e8b9d1a974bb/?utm_source=claude_desktop), ตรวจ calibration หลัง resampling [[22]](https://consensus.app/papers/details/145c928d87ac5481b38fc24cb8e529f9/?utm_source=claude_desktop) — และคาดหวังว่า **F1 จะตกลงจาก 0.99 มาเป็นเลขที่สมจริง** นั่นคือสัญญาณที่ดี

### 🟠 C7 — โมเดลเชิงเวลา (ระยะถัดไป)
ลอง LSTM/CNN/Temporal บนลำดับ 30 วันย้อนหลัง + probabilistic output (ให้ผู้ใช้เห็น uncertainty) [[11]](https://consensus.app/papers/details/e1729ec3e94e595e92976917de91753a/?utm_source=claude_desktop)[[14]](https://consensus.app/papers/details/1a504aa0502a5d029caff349c4d2b04d/?utm_source=claude_desktop)[[15]](https://consensus.app/papers/details/5a360ccc7ecf5f89ad629f9558655c68/?utm_source=claude_desktop) และเพิ่ม SHAP เพื่อยืนยันว่าเรียนรู้ตัวขับฟิสิกส์จริง ไม่ใช่ leak [[10]](https://consensus.app/papers/details/164da53c789559ee990020f65a06fd18/?utm_source=claude_desktop)

### 🟡 C8 — แก้บั๊กวิศวกรรม
แก้ config path (`config/` ↔ root), รวม model registry/​models dir ให้ตรงกัน, deploy LightGBM, เปลี่ยน silent fallback เป็น raise, ปิด CORS แบบ whitelist

---

## ลำดับลงมือ
1. **C3 + C1** (temporal split + แยก feature/target ตามเวลา) — ตัด leakage ทั้งสองชั้น แล้ว rerun ดู baseline จริง
2. **C2** (label heatwave มี persistence + percentile/WBGT)
3. **C6** (imbalance + เมตริกถูกต้อง) — *หลัง* 1–2 เท่านั้น
4. **C4 + C8** (forecast จริง + แก้บั๊ก) ให้ end-product ใช้ได้
5. **C5 → C7** (features + temporal models) ยกระดับทักษะ

> สรุปสั้น: วิศวกรรม (โครงสร้าง, security, UI, DevOps) ของโปรเจกต์นี้แข็งแรงตามที่ `PROJECT_REVIEW.md` ชม แต่ **แกน ML ยังวัด "ทักษะการพยากรณ์" ไม่ได้เลย** เพราะ target leakage + label ไม่มี persistence + split สุ่ม + forecast สุ่ม เมื่อแก้ 4 อย่างนี้ตามงานวิจัย ตัวเลขจะ "ดูแย่ลง" ชั่วคราว แต่จะเป็นครั้งแรกที่ตัวเลข *มีความหมาย*

---

## ส่วน D — งานวิจัย/แหล่งข้อมูลเพิ่มเติม (ใช้ WebSearch + WebFetch ข้ามขีดจำกัด Consensus)

### D1. นิยามทางการ / operational (grey literature ที่ Consensus ไม่ครอบคลุม)
- **WMO:** heatwave = อุณหภูมิสูงสุดสูงกว่าค่าปกติ (ฐาน 1961–1990) **≥ 5°C ต่อเนื่อง > 5 วัน** — เป็นนิยามแบบ **anomaly + persistence** ไม่ใช่ค่าสัมบูรณ์ [[W1]](https://wmo.int/topics/heatwave)[[W2]](https://rcc.dwd.de/DWD-RCC/EN/overview/documents/01_wmo_guidelines.pdf?__blob=publicationFile&v=3)
- **กรมอุตุนิยมวิทยา (TMD):** คลื่นความร้อนในไทย = อุณหภูมิสูงสุด **สูงกว่าค่าเฉลี่ยต่อเนื่องเกิน 5 วัน**; ไทยเคยวัดสูงสุด 45.4°C ที่ตาก (18 เม.ย. 2566) — สังเกตว่า "เกณฑ์อากาศร้อน" ของ TMD (อากาศร้อน 35.0–39.9°C, ร้อนจัด ≥ 40°C) เป็น **ค่าสัมบูรณ์เพื่อสื่อสารรายวัน คนละอย่างกับนิยาม heatwave** [[W3]](https://tmd.go.th/info/%E0%B8%AD%E0%B8%93%E0%B8%AB%E0%B8%A0%E0%B8%A1)
- **มาตรฐาน WBGT ตามกฎหมายไทย** (กฎกระทรวงฯ ความร้อน แสงสว่าง เสียง พ.ศ. 2559): นิยาม "ระดับความร้อน" = **WBGT** (ค่าเฉลี่ย 2 ชม.ที่สูงสุด) ตาม **ISO 7243**; กลางแจ้งไร้แดด/ในอาคาร WBGT = 0.7·T_nwb + 0.3·T_g → **WBGT มีสถานะทางกฎหมายในไทย** จึงเหมาะเป็น label มากกว่า heat_index ของ US NWS [[W4]](https://www.safetechthailand.net/articledetail.asp?id=35315)[[W5]](https://he01.tci-thaijo.org/index.php/JSH/article/download/187302/159131/785911)

> ตอกย้ำ B2/B3: ทั้ง WMO และ TMD นิยาม heatwave เป็น **anomaly เทียบค่าปกติ + ต่อเนื่อง > 5 วัน** — ตรงข้ามกับโค้ดที่ใช้ `heat_index ≥ 41` รายแถวแบบสัมบูรณ์ ไร้ persistence

### D2. งาน Deep Learning ล่าสุด 2024–2025 (เสริม A2)
- 🔑 **ML/DL มักประเมินความรุนแรงของ extreme ต่ำกว่าจริง:** งานตรวจสอบ GraphCast/Pangu-Weather บนเหตุการณ์สุดขั้วจริงพบว่าโมเดล DL **underestimate** ความรุนแรง โดยเฉพาะ **humid heatwave** (เอเชียใต้ 2023 — ประเมินระดับอันตรายของบังกลาเทศต่ำไป) และ **โมเดลพยากรณ์ความชื้นผิวพื้นได้ไม่ดี** ทำให้ heat index ต่ำกว่าค่าจริง; ที่ lead > 1 สัปดาห์ แย่ลง ~3 เท่า [[W6]](https://arxiv.org/html/2404.17652v2) → **สำคัญต่อไทยมาก** เพราะเป็น humid heatwave: ยิ่งต้องโฟกัส short lead, ใส่ความชื้น/WBGT ให้ดี และประเมินแบบ impact-centric
- subseasonal heatwave prediction ในจีนด้วย DL ที่ใส่ scale interaction (Xie, 2024, GRL) [[W7]](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2024GL111076)
- **MHWUNet** (U-Net + attention) พยากรณ์ heatwave 14 วัน เพิ่ม **F1 +8.3% และ MCC +10.2%** — ใช้ **MCC** เป็นเมตริก ตรงกับข้อแนะนำ A3 [[W8]](https://arxiv.org/pdf/2412.04475)
- ขีดจำกัด predictability ของ heatwave ~23 วัน แต่โมเดลยังพลาด magnitude ที่ lead 10 วัน [[W9]](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2024GL110651)

### D3. แหล่งข้อมูลพยากรณ์จริง แทน `np.random` (actionable ตรงกับ C4 + C5)
**Open-Meteo** — ฟรี ไม่ต้องใช้ API key ครอบคลุมตัวแปรที่งานวิจัยแนะนำ **ครบในแหล่งเดียว** [[W10]](https://open-meteo.com/en/docs/historical-forecast-api)[[W11]](https://open-meteo.com/en/docs/historical-weather-api):
- **Heat:** temp 2m/max/min, apparent temperature, **wet-bulb temperature (2m)**, dewpoint, RH
- **Synoptic:** surface pressure + pressure-level 1000–30 hPa รวม **geopotential height** (ได้ 500 hPa ตาม [[11]](https://consensus.app/papers/details/e1729ec3e94e595e92976917de91753a/?utm_source=claude_desktop)[[12]](https://consensus.app/papers/details/5421c38eca3e55d984411191d16d202a/?utm_source=claude_desktop))
- **Land-surface:** **soil moisture 5 ชั้น + soil temperature** (slow drivers ตาม [[13]](https://consensus.app/papers/details/bbd22d647966519dbe039282ad9ca124/?utm_source=claude_desktop))
- **ครอบคลุมเวลา:** Historical Weather (ERA5 ตั้งแต่ 1940, ERA5-Land 0.1°) สำหรับ **เทรน**, Historical Forecast (2022+), Seasonal Forecast API, Ensemble API สำหรับ **inference** — ฟรีสำหรับงานไม่เชิงพาณิชย์, ข้อมูลภายใต้ CC-BY 4.0 (เชิงพาณิชย์ควรตรวจ terms)

> เปลี่ยน `forecast.py` ให้ดึง Open-Meteo เป็น **lagged real features** จะแก้ทั้ง B5 (forecast สุ่ม) และ B6 (features บาง) พร้อมกัน และทำให้ inference ใช้ predictors ชุดเดียวกับตอนเทรน (ERA5)

### Web sources
- [W1] [WMO — Heatwave](https://wmo.int/topics/heatwave)
- [W2] [WMO — Guidelines on the Definition and Characterization of Extreme Weather and Climate Events (PDF)](https://rcc.dwd.de/DWD-RCC/EN/overview/documents/01_wmo_guidelines.pdf?__blob=publicationFile&v=3)
- [W3] [กรมอุตุนิยมวิทยา (TMD) — ข้อมูลอุณหภูมิ/เกณฑ์อากาศ](https://tmd.go.th/info/%E0%B8%AD%E0%B8%93%E0%B8%AB%E0%B8%A0%E0%B8%A1)
- [W4] [กฎกระทรวงฯ มาตรฐานความร้อน แสงสว่าง และเสียง พ.ศ. 2559](https://www.safetechthailand.net/articledetail.asp?id=35315)
- [W5] [ความร้อน: ผลกระทบต่อสุขภาพ การตรวจวัด ค่ามาตรฐาน (วารสาร JSH)](https://he01.tci-thaijo.org/index.php/JSH/article/download/187302/159131/785911)
- [W6] [Validating Deep-Learning Weather Forecast Models on Recent High-Impact Extreme Events (arXiv 2404.17652)](https://arxiv.org/html/2404.17652v2)
- [W7] [Advancing Subseasonal Surface Air Temperature and Heat Wave Prediction Skill in China by Incorporating Scale Interaction in a Deep Learning Model (Xie et al., 2024, GRL)](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2024GL111076)
- [W8] [Advancing Marine Heatwave Forecasts: An Integrated Deep Learning Approach — MHWUNet (arXiv 2412.04475)](https://arxiv.org/pdf/2412.04475)
- [W9] [Predictability Limit of the 2021 Pacific Northwest Heatwave From Deep-Learning Sensitivity Analysis (Vonich et al., 2024, GRL)](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2024GL110651)
- [W10] [Open-Meteo — Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api)
- [W11] [Open-Meteo — Historical Weather API (ERA5)](https://open-meteo.com/en/docs/historical-weather-api)

---

## References

[1] [On the Measurement of Heat Waves](https://consensus.app/papers/details/4c2812a9e2a0553fbe8db350ebd8af9d/?utm_source=claude_desktop) (Perkins & Alexander, 2013, Journal of Climate, 1073 citations)
[2] [Impact of heatwave on mortality under different heatwave definitions: A systematic review and meta-analysis](https://consensus.app/papers/details/ca96ce8f0a0f5963a2b662061bd34af5/?utm_source=claude_desktop) (Xu et al., 2016, Environment International, 556 citations)
[3] [Heatwaves in Southeast Asia and Their Changes in a Warmer World](https://consensus.app/papers/details/0514bde70f26593384534ec1a7d13376/?utm_source=claude_desktop) (Dong et al., 2021, Earth's Future, 107 citations)
[4] [Comparison of health risks by heat wave definition: Applicability of wet-bulb globe temperature for heat wave criteria](https://consensus.app/papers/details/f64832bc262b598386b25f2d6c04c39e/?utm_source=claude_desktop) (Heo et al., 2019, Environmental Research, 131 citations)
[5] [Quantifying localized heatwave impact on mortality: a multi-country modeling study in the Asia–Pacific region](https://consensus.app/papers/details/25a12eb62f335c22865f754fa7b15733/?utm_source=claude_desktop) (Tao et al., 2025, The Lancet Regional Health: Western Pacific, 3 citations)
[6] [The impact of humidity on Australia's operational heatwave services](https://consensus.app/papers/details/02e30413e5625879a6913a39f32ad40c/?utm_source=claude_desktop) (Nairn et al., 2022, Climate Services, 14 citations)
[7] [Impact of heatwaves on all-cause mortality in India: A comprehensive multi-city study](https://consensus.app/papers/details/8e4f57bd03f45cab96659fd176b6f313/?utm_source=claude_desktop) (de Bont et al., 2024, Environment International, 60 citations)
[8] [Global, regional, and national burden of heatwave-related mortality from 1990 to 2019](https://consensus.app/papers/details/73df4709bb5f53cb8a04a3628773295b/?utm_source=claude_desktop) (Zhao et al., 2024, PLOS Medicine, 69 citations)
[9] [Heatwave and health events: A systematic evaluation of different temperature indicators, heatwave intensities and durations](https://consensus.app/papers/details/c8a3e8ff62185a81b2d766dd70761905/?utm_source=claude_desktop) (Xu et al., 2018, Science of the Total Environment, 89 citations)
[10] [Seasonal heatwave forecasting with explainable machine learning and remote sensing data](https://consensus.app/papers/details/164da53c789559ee990020f65a06fd18/?utm_source=claude_desktop) (Kan et al., 2025, Stochastic Environmental Research and Risk Assessment, 3 citations)
[11] [Deep Learning-Based Extreme Heatwave Forecast](https://consensus.app/papers/details/e1729ec3e94e595e92976917de91753a/?utm_source=claude_desktop) (Jacques-Dumas et al., 2021, 70 citations)
[12] [Probabilistic forecasts of extreme heatwaves using convolutional neural networks in a regime of lack of data](https://consensus.app/papers/details/5421c38eca3e55d984411191d16d202a/?utm_source=claude_desktop) (Miloshevich et al., 2022, ArXiv, 41 citations)
[13] [A deep learning-based land-atmosphere coupled model for heatwave prediction](https://consensus.app/papers/details/bbd22d647966519dbe039282ad9ca124/?utm_source=claude_desktop) (Cho et al., 2026, npj Climate and Atmospheric Science)
[14] [Extreme heat prediction through deep learning and explainable AI](https://consensus.app/papers/details/1a504aa0502a5d029caff349c4d2b04d/?utm_source=claude_desktop) (Shafiq et al., 2025, PLOS One, 2 citations)
[15] [Developing a seasonal-adjusted machine-learning-based hybrid time-series model to forecast heatwave warning](https://consensus.app/papers/details/5a360ccc7ecf5f89ad629f9558655c68/?utm_source=claude_desktop) (Qureshi et al., 2025, Scientific Reports, 15 citations)
[16] [Machine learning methods to predict sea surface temperature and marine heatwave occurrence: Mediterranean Sea](https://consensus.app/papers/details/7b45696075e55022892a6f1003262a6c/?utm_source=claude_desktop) (Bonino et al., 2024, Ocean Science, 36 citations)
[17] [Evaluating classifier performance with highly imbalanced Big Data](https://consensus.app/papers/details/56edd00b52fc5610a0fc142b8ec64b3f/?utm_source=claude_desktop) (Hancock et al., 2023, Journal of Big Data, 90 citations)
[18] [Limitation of ROC in Evaluation of Classifiers for Imbalanced Data](https://consensus.app/papers/details/1656e0169a535328b622d4ec904f9e74/?utm_source=claude_desktop) (Movahedi et al., 2021, Journal of Heart and Lung Transplantation, 8 citations)
[19] [Outcome class imbalance and rare events: An underappreciated complication for overdose risk prediction modeling](https://consensus.app/papers/details/82307269120d59f4ae9620099a07085a/?utm_source=claude_desktop) (Cartus et al., 2023, Addiction, 16 citations)
[20] [Why ROC-AUC Is Misleading for Highly Imbalanced Data: MCC, F2-Score, H-Measure, and AUC-Based Metrics](https://consensus.app/papers/details/837910e747235e7ca572e8b9d1a974bb/?utm_source=claude_desktop) (Imani et al., 2026, Technologies, 3 citations)
[21] [A Closer Look at AUROC and AUPRC under Class Imbalance](https://consensus.app/papers/details/3e2a7a07b42a50a3af833b234812395d/?utm_source=claude_desktop) (McDermott et al., 2024, ArXiv, 124 citations)
[22] [Understanding random resampling techniques for class imbalance correction and their consequences on calibration and discrimination](https://consensus.app/papers/details/145c928d87ac5481b38fc24cb8e529f9/?utm_source=claude_desktop) (Piccininni et al., 2024, Journal of Biomedical Informatics, 25 citations)

---

*Upgrade to Consensus Pro to return 20 results per search instead of 10, and include more data like study design and key takeaways for every result.: https://consensus.app/pricing/?utm_source=claude_desktop*
