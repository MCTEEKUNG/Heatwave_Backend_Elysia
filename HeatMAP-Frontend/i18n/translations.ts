/**
 * Internationalization (i18n) translations for Heatwave App
 * Supports English (en) and Thai (th)
 */

export type Language = 'en' | 'th';

export interface Translations {
  // App
  appName: string;
  
  // Navigation
  navMap: string;
  navAlerts: string;
  navSafety: string;
  navProfile: string;
  
  // Settings Page
  settingsTitle: string;
  profile: string;
  editProfile: string;
  appearance: string;
  darkMode: string;
  darkModeOn: string;
  darkModeOff: string;
  language: string;
  notifications: string;
  pushNotifications: string;
  hapticFeedback: string;
  fontSize: string;
  heatAlerts: string;
  heatAlertsInfo: string;
  securityPrivacy: string;
  signOut: string;
  
  // Map Page
  dangerZoneDetected: string;
  mediumRiskArea: string;
  heatRiskLevelMedium: string;
  riskLevelExtremeHeat: string;
  lowRisk: string;
  currentlyTemp: string;
  extremeHeat: string;
  locationActive: string;
  gettingLocation: string;
  
  // Alerts Page
  forecastDetails: string;
  forecastLabel: string;
  peakIntensityWarning: string;
  augustForecast: string;
  safetyActions: string;
  
  // Safety/Checklist Page
  safetyChecklist: string;
  currentProgress: string;
  completed: string;
  nearestCare: string;
  hospitalName: string;
  hospitalOpen: string;
  navigate: string;
  emergency: string;
  
  // Checklist items
  hydrate: string;
  hydrateDesc: string;
  blockHeat: string;
  blockHeatDesc: string;
  dressAppropriately: string;
  dressAppropriatelyDesc: string;
  findCool: string;
  findCoolDesc: string;
  
  // Metrics
  wetBulb: string;
  aqi: string;
  uvIndex: string;
  humidity: string;
  moderateRisk: string;
  goodQuality: string;
  moderate: string;
  stable: string;
  
  // Common
  now: string;
  today: string;
  loading: string;
  error: string;
}

// Flat translation keys for easy access
export type TranslationKey = keyof Translations;

const en: Record<TranslationKey, string> = {
  // App
  appName: 'Heatwave',
  
  // Navigation
  navMap: 'MAP',
  navAlerts: 'ALERTS',
  navSafety: 'SAFETY',
  navProfile: 'PROFILE',
  
  // Settings Page
  settingsTitle: 'Settings & Profile',
  profile: 'Profile',
  editProfile: 'EDIT PROFILE',
  appearance: 'APPEARANCE',
  darkMode: 'Dark Mode',
  darkModeOn: 'Currently using dark theme',
  darkModeOff: 'Currently using light theme',
  language: 'Language',
  notifications: 'NOTIFICATIONS',
  pushNotifications: 'Push Notifications',
  hapticFeedback: 'Haptic Feedback',
  fontSize: 'Font Size',
  heatAlerts: 'HEAT ALERTS',
  heatAlertsInfo: 'Get notified when heatwave conditions are detected in your area.',
  securityPrivacy: 'Security & Privacy',
  signOut: 'Sign Out',
  
  // Map Page
  dangerZoneDetected: 'Danger Zone Detected',
  mediumRiskArea: 'Medium Risk Area',
  heatRiskLevelMedium: 'Heat risk level: Medium',
  riskLevelExtremeHeat: 'Risk Level: Extreme Heat',
  lowRisk: 'Low Risk',
  currentlyTemp: 'Currently Temp',
  extremeHeat: 'EXTREME HEAT',
  locationActive: 'Location active',
  gettingLocation: 'Getting location...',
  
  // Alerts Page
  forecastDetails: 'Forecast Details',
  forecastLabel: '+2h Forecast',
  peakIntensityWarning: 'Peak intensity expected. Stay hydrated and avoid direct sunlight.',
  augustForecast: 'AUGUST 2024 FORECAST',
  safetyActions: 'VIEW SAFETY ACTIONS',
  
  // Safety/Checklist Page
  safetyChecklist: 'Safety Checklist',
  currentProgress: 'Current Progress',
  completed: 'completed',
  nearestCare: 'Nearest Care',
  hospitalName: "St. Mary's General",
  hospitalOpen: 'Estimated 8 min drive • Open 24/7',
  navigate: 'NAVIGATE',
  emergency: 'EMERGENCY 911',
  
  // Checklist items
  hydrate: 'Hydrate',
  hydrateDesc: 'Drink 500ml of water immediately.',
  blockHeat: 'Block Heat',
  blockHeatDesc: 'Move to a shaded area.',
  dressAppropriately: 'Dress appropriately',
  dressAppropriatelyDesc: 'Wear light-colored, breathable clothing.',
  findCool: 'Find Cool',
  findCoolDesc: 'Locate nearest cooling station.',
  
  // Metrics
  wetBulb: 'Wet Bulb',
  aqi: 'AQI',
  uvIndex: 'UV Index',
  humidity: 'Humidity',
  moderateRisk: 'Moderate Risk',
  goodQuality: 'Good Quality',
  moderate: 'Moderate',
  stable: 'Stable',
  
  // Common
  now: 'Now',
  today: 'Today',
  loading: 'Loading...',
  error: 'Error',
};

const th: Record<TranslationKey, string> = {
  // App
  appName: 'คลื่นความร้อน',
  
  // Navigation
  navMap: 'แผนที่',
  navAlerts: 'แจ้งเตือน',
  navSafety: 'ความปลอดภัย',
  navProfile: 'โปรไฟล์',
  
  // Settings Page
  settingsTitle: 'การตั้งค่าและโปรไฟล์',
  profile: 'โปรไฟล์',
  editProfile: 'แก้ไขโปรไฟล์',
  appearance: 'รูปลักษณ์',
  darkMode: 'โหมดมืด',
  darkModeOn: 'กำลังใช้ธีมมืด',
  darkModeOff: 'กำลังใช้ธีมสว่าง',
  language: 'ภาษา',
  notifications: 'การแจ้งเตือน',
  pushNotifications: 'การแจ้งเตือน Push',
  hapticFeedback: 'การสั่นสะเทือน',
  fontSize: 'ขนาดตัวอักษร',
  heatAlerts: 'การแจ้งเตือนความร้อน',
  heatAlertsInfo: 'รับการแจ้งเตือนเมื่อตรวจพบสภาพคลื่นความร้อนในพื้นที่ของคุณ',
  securityPrivacy: 'ความปลอดภัยและความเป็นส่วนตัว',
  signOut: 'ออกจากระบบ',
  
  // Map Page
  dangerZoneDetected: 'ตรวจพบโซนอันตราย',
  mediumRiskArea: 'พื้นที่เสี่ยงระดับปานกลาง',
  heatRiskLevelMedium: 'ระดับความเสี่ยงความร้อน: ปานกลาง',
  riskLevelExtremeHeat: 'ระดับความเสี่ยง: ความร้อนสูงสุด',
  lowRisk: 'ความเสี่ยงต่ำ',
  currentlyTemp: 'อุณหภูมิปัจจุบัน',
  extremeHeat: 'ความร้อนสูงสุด',
  locationActive: 'ตำแหน่งที่ตั้งทำงาน',
  gettingLocation: 'กำลังรับตำแหน่ง...',
  
  // Alerts Page
  forecastDetails: 'รายละเอียดการพยากรณ์',
  forecastLabel: 'พยากรณ์ +2 ชม.',
  peakIntensityWarning: 'คาดว่าจะมีความเข้มข้นสูงสุด ดื่มน้ำให้เพียงพอและหลีกเลี่ยงแสงแดดโดยตรง',
  augustForecast: 'การพยากรณ์ สิงหาคม 2024',
  safetyActions: 'ดูมาตรการความปลอดภัย',
  
  // Safety/Checklist Page
  safetyChecklist: 'รายการตรวจสอบความปลอดภัย',
  currentProgress: 'ความก้าวหน้าปัจจุบัน',
  completed: 'เสร็จสิ้น',
  nearestCare: 'สถานพยาบาลใกล้ที่สุด',
  hospitalName: 'โรงพยาบาลสมุทรสงคราม',
  hospitalOpen: 'ขับขี่ ~8 นาที • เปิด 24 ชม.',
  navigate: 'นำทาง',
  emergency: 'ฉุกเฉิน 1669',
  
  // Checklist items
  hydrate: 'ดื่มน้ำ',
  hydrateDesc: 'ดื่มน้ำ 500 มล. ทันที',
  blockHeat: 'กันความร้อน',
  blockHeatDesc: 'ย้ายไปที่ร่มเงา',
  dressAppropriately: 'แต่งกายเหมาะสม',
  dressAppropriatelyDesc: 'สวมเสื้อผ้าสีอ่อน ระบายอากาศได้ดี',
  findCool: 'หาที่เย็น',
  findCoolDesc: 'ค้นหาศูนย์ความเย็นใกล้ที่สุด',
  
  // Metrics
  wetBulb: 'เทอร์โมมิเตอร์เปียก',
  aqi: 'AQI',
  uvIndex: 'ดัชนี UV',
  humidity: 'ความชื้น',
  moderateRisk: 'ความเสี่ยงปานกลาง',
  goodQuality: 'คุณภาพดี',
  moderate: 'ปานกลาง',
  stable: 'คงที่',
  
  // Common
  now: 'ตอนนี้',
  today: 'วันนี้',
  loading: 'กำลังโหลด...',
  error: 'ข้อผิดพลาด',
};

export const translations: Record<Language, Record<TranslationKey, string>> = {
  en,
  th,
};
