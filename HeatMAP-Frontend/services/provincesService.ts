/**
 * Provinces Service
 *
 * Fetches the list of 77 Thai provinces (id, code, names, region, centroid)
 * from the backend `GET /api/provinces`. Falls back to a bundled static list
 * when the backend is unreachable, so the province selector always works.
 *
 * API contract (spec §7):
 *   GET /api/provinces -> [{ id, code, name_th, name_en, region, lat, lon }]
 */

import { api } from './apiService';

export interface Province {
  id: number;
  code: string;
  name_th: string;
  name_en: string;
  region: string;
  lat: number;
  lon: number;
}

/**
 * Bundled fallback list of all 77 Thai provinces with approximate centroids.
 * Used when `/api/provinces` is unreachable (backend asleep / offline) so the
 * selector and nearest-province map logic still work. Backend data — when
 * available — always takes precedence (see `getProvinces`).
 */
export const FALLBACK_PROVINCES: Province[] = [
  { id: 1,  code: 'TH-10', name_th: 'กรุงเทพมหานคร', name_en: 'Bangkok',            region: 'Central',      lat: 13.7563, lon: 100.5018 },
  { id: 2,  code: 'TH-11', name_th: 'สมุทรปราการ',     name_en: 'Samut Prakan',       region: 'Central',      lat: 13.5991, lon: 100.5998 },
  { id: 3,  code: 'TH-12', name_th: 'นนทบุรี',         name_en: 'Nonthaburi',         region: 'Central',      lat: 13.8591, lon: 100.5217 },
  { id: 4,  code: 'TH-13', name_th: 'ปทุมธานี',        name_en: 'Pathum Thani',       region: 'Central',      lat: 14.0208, lon: 100.5250 },
  { id: 5,  code: 'TH-14', name_th: 'พระนครศรีอยุธยา',  name_en: 'Phra Nakhon Si Ayutthaya', region: 'Central', lat: 14.3692, lon: 100.5876 },
  { id: 6,  code: 'TH-15', name_th: 'อ่างทอง',         name_en: 'Ang Thong',          region: 'Central',      lat: 14.5896, lon: 100.4550 },
  { id: 7,  code: 'TH-16', name_th: 'ลพบุรี',          name_en: 'Lopburi',            region: 'Central',      lat: 14.7995, lon: 100.6534 },
  { id: 8,  code: 'TH-17', name_th: 'สิงห์บุรี',       name_en: 'Sing Buri',          region: 'Central',      lat: 14.8907, lon: 100.3967 },
  { id: 9,  code: 'TH-18', name_th: 'ชัยนาท',          name_en: 'Chai Nat',           region: 'Central',      lat: 15.1851, lon: 100.1251 },
  { id: 10, code: 'TH-19', name_th: 'สระบุรี',         name_en: 'Saraburi',           region: 'Central',      lat: 14.5289, lon: 100.9108 },
  { id: 11, code: 'TH-20', name_th: 'ชลบุรี',          name_en: 'Chonburi',           region: 'East',         lat: 13.3611, lon: 100.9847 },
  { id: 12, code: 'TH-21', name_th: 'ระยอง',           name_en: 'Rayong',             region: 'East',         lat: 12.6814, lon: 101.2780 },
  { id: 13, code: 'TH-22', name_th: 'จันทบุรี',        name_en: 'Chanthaburi',        region: 'East',         lat: 12.6113, lon: 102.1035 },
  { id: 14, code: 'TH-23', name_th: 'ตราด',            name_en: 'Trat',               region: 'East',         lat: 12.2436, lon: 102.5150 },
  { id: 15, code: 'TH-24', name_th: 'ฉะเชิงเทรา',      name_en: 'Chachoengsao',       region: 'East',         lat: 13.6904, lon: 101.0779 },
  { id: 16, code: 'TH-25', name_th: 'ปราจีนบุรี',      name_en: 'Prachinburi',        region: 'East',         lat: 14.0509, lon: 101.3700 },
  { id: 17, code: 'TH-26', name_th: 'นครนายก',         name_en: 'Nakhon Nayok',       region: 'Central',      lat: 14.2069, lon: 101.2130 },
  { id: 18, code: 'TH-27', name_th: 'สระแก้ว',         name_en: 'Sa Kaeo',            region: 'East',         lat: 13.8240, lon: 102.0645 },
  { id: 19, code: 'TH-30', name_th: 'นครราชสีมา',      name_en: 'Nakhon Ratchasima',  region: 'Northeast',    lat: 14.9799, lon: 102.0978 },
  { id: 20, code: 'TH-31', name_th: 'บุรีรัมย์',       name_en: 'Buri Ram',           region: 'Northeast',    lat: 14.9930, lon: 103.1029 },
  { id: 21, code: 'TH-32', name_th: 'สุรินทร์',        name_en: 'Surin',              region: 'Northeast',    lat: 14.8818, lon: 103.4936 },
  { id: 22, code: 'TH-33', name_th: 'ศรีสะเกษ',        name_en: 'Si Sa Ket',          region: 'Northeast',    lat: 15.1186, lon: 104.3220 },
  { id: 23, code: 'TH-34', name_th: 'อุบลราชธานี',     name_en: 'Ubon Ratchathani',   region: 'Northeast',    lat: 15.2448, lon: 104.8473 },
  { id: 24, code: 'TH-35', name_th: 'ยโสธร',           name_en: 'Yasothon',           region: 'Northeast',    lat: 15.7921, lon: 104.1453 },
  { id: 25, code: 'TH-36', name_th: 'ชัยภูมิ',         name_en: 'Chaiyaphum',         region: 'Northeast',    lat: 15.8068, lon: 102.0316 },
  { id: 26, code: 'TH-37', name_th: 'อำนาจเจริญ',      name_en: 'Amnat Charoen',      region: 'Northeast',    lat: 15.8657, lon: 104.6256 },
  { id: 27, code: 'TH-38', name_th: 'บึงกาฬ',          name_en: 'Bueng Kan',          region: 'Northeast',    lat: 18.3609, lon: 103.6466 },
  { id: 28, code: 'TH-39', name_th: 'หนองบัวลำภู',     name_en: 'Nong Bua Lam Phu',   region: 'Northeast',    lat: 17.2218, lon: 102.4260 },
  { id: 29, code: 'TH-40', name_th: 'ขอนแก่น',         name_en: 'Khon Kaen',          region: 'Northeast',    lat: 16.4322, lon: 102.8236 },
  { id: 30, code: 'TH-41', name_th: 'อุดรธานี',        name_en: 'Udon Thani',         region: 'Northeast',    lat: 17.4138, lon: 102.7870 },
  { id: 31, code: 'TH-42', name_th: 'เลย',             name_en: 'Loei',               region: 'Northeast',    lat: 17.4860, lon: 101.7223 },
  { id: 32, code: 'TH-43', name_th: 'หนองคาย',         name_en: 'Nong Khai',          region: 'Northeast',    lat: 17.8783, lon: 102.7470 },
  { id: 33, code: 'TH-44', name_th: 'มหาสารคาม',       name_en: 'Maha Sarakham',      region: 'Northeast',    lat: 16.1850, lon: 103.3000 },
  { id: 34, code: 'TH-45', name_th: 'ร้อยเอ็ด',        name_en: 'Roi Et',             region: 'Northeast',    lat: 16.0538, lon: 103.6520 },
  { id: 35, code: 'TH-46', name_th: 'กาฬสินธุ์',       name_en: 'Kalasin',            region: 'Northeast',    lat: 16.4314, lon: 103.5059 },
  { id: 36, code: 'TH-47', name_th: 'สกลนคร',          name_en: 'Sakon Nakhon',       region: 'Northeast',    lat: 17.1545, lon: 104.1348 },
  { id: 37, code: 'TH-48', name_th: 'นครพนม',          name_en: 'Nakhon Phanom',      region: 'Northeast',    lat: 17.3920, lon: 104.7690 },
  { id: 38, code: 'TH-49', name_th: 'มุกดาหาร',        name_en: 'Mukdahan',           region: 'Northeast',    lat: 16.5420, lon: 104.7210 },
  { id: 39, code: 'TH-50', name_th: 'เชียงใหม่',       name_en: 'Chiang Mai',         region: 'North',        lat: 18.7883, lon: 98.9853 },
  { id: 40, code: 'TH-51', name_th: 'ลำพูน',           name_en: 'Lamphun',            region: 'North',        lat: 18.5743, lon: 99.0087 },
  { id: 41, code: 'TH-52', name_th: 'ลำปาง',           name_en: 'Lampang',            region: 'North',        lat: 18.2888, lon: 99.4909 },
  { id: 42, code: 'TH-53', name_th: 'อุตรดิตถ์',       name_en: 'Uttaradit',          region: 'North',        lat: 17.6200, lon: 100.0993 },
  { id: 43, code: 'TH-54', name_th: 'แพร่',            name_en: 'Phrae',              region: 'North',        lat: 18.1445, lon: 100.1405 },
  { id: 44, code: 'TH-55', name_th: 'น่าน',            name_en: 'Nan',                region: 'North',        lat: 18.7756, lon: 100.7730 },
  { id: 45, code: 'TH-56', name_th: 'พะเยา',           name_en: 'Phayao',             region: 'North',        lat: 19.1664, lon: 99.9003 },
  { id: 46, code: 'TH-57', name_th: 'เชียงราย',        name_en: 'Chiang Rai',         region: 'North',        lat: 19.9105, lon: 99.8406 },
  { id: 47, code: 'TH-58', name_th: 'แม่ฮ่องสอน',      name_en: 'Mae Hong Son',       region: 'North',        lat: 19.3020, lon: 97.9654 },
  { id: 48, code: 'TH-60', name_th: 'นครสวรรค์',       name_en: 'Nakhon Sawan',       region: 'Central',      lat: 15.7047, lon: 100.1372 },
  { id: 49, code: 'TH-61', name_th: 'อุทัยธานี',       name_en: 'Uthai Thani',        region: 'Central',      lat: 15.3835, lon: 100.0246 },
  { id: 50, code: 'TH-62', name_th: 'กำแพงเพชร',       name_en: 'Kamphaeng Phet',     region: 'Central',      lat: 16.4828, lon: 99.5226 },
  { id: 51, code: 'TH-63', name_th: 'ตาก',             name_en: 'Tak',                region: 'West',         lat: 16.8840, lon: 99.1258 },
  { id: 52, code: 'TH-64', name_th: 'สุโขทัย',         name_en: 'Sukhothai',          region: 'North',        lat: 17.0070, lon: 99.8265 },
  { id: 53, code: 'TH-65', name_th: 'พิษณุโลก',        name_en: 'Phitsanulok',        region: 'North',        lat: 16.8211, lon: 100.2659 },
  { id: 54, code: 'TH-66', name_th: 'พิจิตร',          name_en: 'Phichit',            region: 'Central',      lat: 16.4429, lon: 100.3487 },
  { id: 55, code: 'TH-67', name_th: 'เพชรบูรณ์',       name_en: 'Phetchabun',         region: 'Central',      lat: 16.4190, lon: 101.1591 },
  { id: 56, code: 'TH-70', name_th: 'ราชบุรี',         name_en: 'Ratchaburi',         region: 'West',         lat: 13.5283, lon: 99.8134 },
  { id: 57, code: 'TH-71', name_th: 'กาญจนบุรี',       name_en: 'Kanchanaburi',       region: 'West',         lat: 14.0227, lon: 99.5328 },
  { id: 58, code: 'TH-72', name_th: 'สุพรรณบุรี',      name_en: 'Suphan Buri',        region: 'Central',      lat: 14.4745, lon: 100.1177 },
  { id: 59, code: 'TH-73', name_th: 'นครปฐม',          name_en: 'Nakhon Pathom',      region: 'Central',      lat: 13.8196, lon: 100.0645 },
  { id: 60, code: 'TH-74', name_th: 'สมุทรสาคร',       name_en: 'Samut Sakhon',       region: 'Central',      lat: 13.5475, lon: 100.2745 },
  { id: 61, code: 'TH-75', name_th: 'สมุทรสงคราม',     name_en: 'Samut Songkhram',    region: 'Central',      lat: 13.4098, lon: 100.0023 },
  { id: 62, code: 'TH-76', name_th: 'เพชรบุรี',        name_en: 'Phetchaburi',        region: 'West',         lat: 13.1119, lon: 99.9399 },
  { id: 63, code: 'TH-77', name_th: 'ประจวบคีรีขันธ์',  name_en: 'Prachuap Khiri Khan', region: 'West',        lat: 11.8126, lon: 99.7957 },
  { id: 64, code: 'TH-80', name_th: 'นครศรีธรรมราช',   name_en: 'Nakhon Si Thammarat', region: 'South',       lat: 8.4304,  lon: 99.9631 },
  { id: 65, code: 'TH-81', name_th: 'กระบี่',          name_en: 'Krabi',              region: 'South',        lat: 8.0863,  lon: 98.9063 },
  { id: 66, code: 'TH-82', name_th: 'พังงา',           name_en: 'Phang Nga',          region: 'South',        lat: 8.4509,  lon: 98.5256 },
  { id: 67, code: 'TH-83', name_th: 'ภูเก็ต',          name_en: 'Phuket',             region: 'South',        lat: 7.8804,  lon: 98.3923 },
  { id: 68, code: 'TH-84', name_th: 'สุราษฎร์ธานี',     name_en: 'Surat Thani',        region: 'South',        lat: 9.1382,  lon: 99.3215 },
  { id: 69, code: 'TH-85', name_th: 'ระนอง',           name_en: 'Ranong',             region: 'South',        lat: 9.9529,  lon: 98.6085 },
  { id: 70, code: 'TH-86', name_th: 'ชุมพร',           name_en: 'Chumphon',           region: 'South',        lat: 10.4930, lon: 99.1800 },
  { id: 71, code: 'TH-90', name_th: 'สงขลา',           name_en: 'Songkhla',           region: 'South',        lat: 7.1898,  lon: 100.5951 },
  { id: 72, code: 'TH-91', name_th: 'สตูล',            name_en: 'Satun',              region: 'South',        lat: 6.6238,  lon: 100.0673 },
  { id: 73, code: 'TH-92', name_th: 'ตรัง',            name_en: 'Trang',              region: 'South',        lat: 7.5593,  lon: 99.6110 },
  { id: 74, code: 'TH-93', name_th: 'พัทลุง',          name_en: 'Phatthalung',        region: 'South',        lat: 7.6167,  lon: 100.0742 },
  { id: 75, code: 'TH-94', name_th: 'ปัตตานี',         name_en: 'Pattani',            region: 'South',        lat: 6.8694,  lon: 101.2502 },
  { id: 76, code: 'TH-95', name_th: 'ยะลา',            name_en: 'Yala',               region: 'South',        lat: 6.5410,  lon: 101.2800 },
  { id: 77, code: 'TH-96', name_th: 'นราธิวาส',        name_en: 'Narathiwat',         region: 'South',        lat: 6.4254,  lon: 101.8253 },
];

/**
 * Fetch the province list from the backend, falling back to the bundled list
 * on any failure. Resolves with `{ provinces, fromFallback }` so callers can
 * surface an offline/stale indicator if desired.
 */
export async function getProvinces(): Promise<{ provinces: Province[]; fromFallback: boolean }> {
  try {
    const data = await api.get<Province[]>('/api/provinces');
    if (Array.isArray(data) && data.length > 0) {
      return { provinces: data, fromFallback: false };
    }
    return { provinces: FALLBACK_PROVINCES, fromFallback: true };
  } catch {
    return { provinces: FALLBACK_PROVINCES, fromFallback: true };
  }
}
