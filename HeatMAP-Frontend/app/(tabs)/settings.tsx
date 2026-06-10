import { View, StyleSheet, TouchableOpacity, ScrollView, Alert } from 'react-native';
import { CustomSwitch } from '@/components/ui/CustomSwitch';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, FontFamily, SoftShadow } from '@/constants/theme';
import { GlassTabBar } from '@/components/ui/GlassTabBar';
import { useSettings, Language, FontSize } from '@/hooks/useSettings';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { ScaledText } from '@/components/ui/ScaledText';
import { scheduleLocalNotification } from '@/services/NotificationService';

// Keep in sync with models/model_card.json (served model) — judges read this.
const MODEL_INFO = {
  model: 'LightGBM · lgbm-v1',
  coverage: '77 จังหวัด · พยากรณ์ 7 วัน',
  source: 'Open-Meteo / ERA5 (1991–2025)',
};

/**
 * SETTINGS — "ตั้งค่า" (Calm Authority). Deliberately NOT a profile screen:
 * this app has no login — everyone receives the same public information.
 * What lives here instead: notification + display preferences, and the
 * "เกี่ยวกับระบบพยากรณ์" transparency card (model, data sources, heatwave
 * definition) so anyone — including science-fair judges — can see exactly
 * how the forecast is made.
 */
export default function SettingsScreen() {
  const {
    isDarkMode,
    setThemeMode,
    language,
    setLanguage,
    fontSize,
    setFontSize,
    pushNotifications,
    setPushNotifications,
    hapticFeedback,
    setHapticFeedback,
  } = useSettings();
  const theme = Colors[isDarkMode ? 'dark' : 'light'];

  const card = [styles.card, { backgroundColor: theme.surface, borderColor: theme.border }, SoftShadow.light];

  const SectionH = ({ children }: { children: string }) => (
    <ScaledText style={[styles.sectionH, { color: theme.textMuted }]}>{children}</ScaledText>
  );

  const Row = ({ icon, label, sub, right, last }: {
    icon: string; label: string; sub?: string; right: React.ReactNode; last?: boolean;
  }) => (
    <View style={[styles.row, !last && { borderBottomWidth: 1, borderBottomColor: theme.border }]}>
      <View style={styles.rowLeft}>
        <IconSymbol size={20} name={icon as never} color={theme.icon} />
        <View style={styles.rowText}>
          <ScaledText style={[styles.rowLabel, { color: theme.text }]}>{label}</ScaledText>
          {sub ? <ScaledText style={[styles.rowSub, { color: theme.textMuted }]}>{sub}</ScaledText> : null}
        </View>
      </View>
      {right}
    </View>
  );

  const Segmented = <T extends string>({ value, options, onChange }: {
    value: T; options: { v: T; label: string }[]; onChange: (v: T) => void;
  }) => (
    <View style={[styles.segmented, { backgroundColor: theme.background, borderColor: theme.border }]}>
      {options.map((opt) => (
        <TouchableOpacity
          key={opt.v}
          style={[styles.segment, value === opt.v && { backgroundColor: theme.primary }]}
          onPress={() => onChange(opt.v)}
          accessibilityRole="button"
          accessibilityState={{ selected: value === opt.v }}
        >
          <ScaledText style={[styles.segmentText, { color: value === opt.v ? '#FFFFFF' : theme.textMuted }]}>
            {opt.label}
          </ScaledText>
        </TouchableOpacity>
      ))}
    </View>
  );

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]} edges={['top']}>
      <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* App bar */}
        <View style={styles.appbar}>
          <ScaledText style={[styles.appbarTitle, { color: theme.primary }]}>ตั้งค่า</ScaledText>
        </View>

        <SectionH>การแจ้งเตือน</SectionH>
        <View style={card}>
          <Row
            icon="notifications_active"
            label="แจ้งเตือนความเสี่ยง"
            sub="เตือนเมื่อพื้นที่ของคุณเข้าเกณฑ์เฝ้าระวัง/เตือนภัย"
            right={<CustomSwitch value={pushNotifications} onValueChange={setPushNotifications} />}
          />
          <Row
            icon="vibration"
            label="สั่นตอบสนอง"
            right={<CustomSwitch value={hapticFeedback} onValueChange={setHapticFeedback} />}
          />
          <Row
            last
            icon="send"
            label="ทดสอบการแจ้งเตือน"
            right={
              <TouchableOpacity
                style={[styles.testBtn, { borderColor: theme.primary }]}
                onPress={async () => {
                  if (!pushNotifications) {
                    Alert.alert('ปิดอยู่', 'เปิด "แจ้งเตือนความเสี่ยง" ก่อนทดสอบ');
                    return;
                  }
                  await scheduleLocalNotification(
                    'ทดสอบการแจ้งเตือนความร้อน',
                    'นี่คือข้อความทดสอบจากหน้าตั้งค่า',
                    { url: '/(tabs)/alerts' },
                  );
                }}
              >
                <ScaledText style={[styles.testBtnText, { color: theme.primary }]}>ส่งทดสอบ</ScaledText>
              </TouchableOpacity>
            }
          />
        </View>

        <SectionH>การแสดงผล</SectionH>
        <View style={card}>
          <Row
            icon="language"
            label="ภาษา"
            right={
              <Segmented<Language>
                value={language}
                options={[{ v: 'th', label: 'ไทย' }, { v: 'en', label: 'EN' }]}
                onChange={setLanguage}
              />
            }
          />
          <Row
            icon="format_size"
            label="ขนาดตัวอักษร"
            right={
              <Segmented<FontSize>
                value={fontSize}
                options={[{ v: 'small', label: 'เล็ก' }, { v: 'default', label: 'กลาง' }, { v: 'large', label: 'ใหญ่' }]}
                onChange={setFontSize}
              />
            }
          />
          <Row
            last
            icon={isDarkMode ? 'dark_mode' : 'light_mode'}
            label="ธีมมืด"
            right={<CustomSwitch value={isDarkMode} onValueChange={(v) => setThemeMode(v ? 'dark' : 'light')} />}
          />
        </View>

        <SectionH>เกี่ยวกับระบบพยากรณ์</SectionH>
        <View style={[...card, styles.aboutCard]}>
          {([
            ['โมเดล', MODEL_INFO.model],
            ['ครอบคลุม', MODEL_INFO.coverage],
            ['แหล่งข้อมูล', MODEL_INFO.source],
          ] as const).map(([k, v], i, arr) => (
            <View key={k} style={[styles.aboutRow, i < arr.length - 1 && { borderBottomWidth: 1, borderBottomColor: theme.border, borderStyle: 'dashed' as never }]}>
              <ScaledText style={[styles.aboutKey, { color: theme.textMuted }]}>{k}</ScaledText>
              <ScaledText style={[styles.aboutVal, { color: theme.text }]}>{v}</ScaledText>
            </View>
          ))}
          <ScaledText style={[styles.aboutNote, { color: theme.textMuted }]}>
            {'"คลื่นความร้อน" ในระบบนี้ = วันที่ดัชนีความร้อน (รวมความชื้น) สูงกว่า 95% ของวันเดียวกันในรอบ 30 ปี และร้อนติดต่อกันอย่างน้อย 2 วัน — เกณฑ์เฉพาะพื้นที่ของแต่ละจังหวัด'}
          </ScaledText>
        </View>

        <ScaledText style={[styles.footerNote, { color: theme.textMuted }]}>
          แอปนี้ไม่ต้องสมัครสมาชิก — ทุกคนเข้าถึงข้อมูลพยากรณ์ชุดเดียวกันได้อย่างทั่วถึง
        </ScaledText>
      </ScrollView>

      {/* Floating liquid-glass tab bar (shared) */}
      <GlassTabBar active="profile" />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scrollView: { flex: 1 },
  scrollContent: { paddingBottom: 104, paddingHorizontal: 16 },
  appbar: { paddingTop: 14, paddingBottom: 6 },
  appbarTitle: { fontSize: 20, fontFamily: FontFamily.display, fontWeight: '700' },
  sectionH: {
    fontSize: 12.5,
    fontFamily: FontFamily.displaySemi,
    fontWeight: '600',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    marginTop: 18,
    marginBottom: 8,
    marginLeft: 4,
  },
  card: {
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 16,
    marginBottom: 4,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    paddingVertical: 13,
    minHeight: 52,
  },
  rowLeft: { flexDirection: 'row', alignItems: 'center', gap: 12, flexShrink: 1 },
  rowText: { flexShrink: 1 },
  rowLabel: { fontSize: 14, fontFamily: FontFamily.bodyMedium },
  rowSub: { fontSize: 11.5, fontFamily: FontFamily.body, marginTop: 1 },
  segmented: {
    flexDirection: 'row',
    borderWidth: 1,
    borderRadius: 9,
    padding: 2,
    gap: 2,
  },
  segment: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 7,
    minHeight: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  segmentText: { fontSize: 12, fontFamily: FontFamily.bodySemi, fontWeight: '600' },
  testBtn: {
    borderWidth: 1.5,
    borderRadius: 9,
    paddingVertical: 7,
    paddingHorizontal: 14,
    minHeight: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  testBtnText: { fontSize: 12.5, fontFamily: FontFamily.bodySemi, fontWeight: '600' },
  aboutCard: { paddingVertical: 6 },
  aboutRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    gap: 12,
    paddingVertical: 9,
  },
  aboutKey: { fontSize: 12.5, fontFamily: FontFamily.body },
  aboutVal: { fontSize: 12.5, fontFamily: FontFamily.bodySemi, fontWeight: '600', textAlign: 'right', flexShrink: 1 },
  aboutNote: { fontSize: 12, fontFamily: FontFamily.body, lineHeight: 20, paddingVertical: 10 },
  footerNote: {
    fontSize: 11.5,
    fontFamily: FontFamily.body,
    textAlign: 'center',
    marginTop: 18,
    paddingHorizontal: 12,
    lineHeight: 18,
  },
});
