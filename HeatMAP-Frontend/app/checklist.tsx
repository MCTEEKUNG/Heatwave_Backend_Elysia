import { useState, useEffect, useCallback } from 'react';
import { View, StyleSheet, TouchableOpacity, ScrollView, Linking, Platform, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { Colors, FontFamily, RiskBg, RiskColors, SoftShadow } from '@/constants/theme';
import { GlassTabBar } from '@/components/ui/GlassTabBar';
import { useSettings } from '@/hooks/useSettings';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { ScaledText } from '@/components/ui/ScaledText';
import { useLocation } from '@/hooks/useLocation';
import { getNearestCoolingPlaces, estimateTravelTime, type Place } from '@/services/nearbyPlaces';

// Get icon for place type
const getPlaceIcon = (type: Place['type']): string => {
  switch (type) {
    case 'shopping_mall': return 'local_mall';
    case 'hospital': return 'local_hospital';
    case 'supermarket': return 'local_grocery_store';
    case 'convenience_store': return 'storefront';
    case 'library': return 'local_library';
    case 'government_building': return 'account_balance';
    case 'transit_station': return 'directions_transit';
    case 'cooling_center': return 'ac_unit';
    default: return 'place';
  }
};

/**
 * SAFETY — "ดูแลตัวเอง" (Calm Authority, per docs/calm-authority-mockup.html).
 * Plain-language heat advice grouped by time of day, the heat-stroke danger
 * card with the Thai EMS number (1669), and real nearby cooling places (OSM).
 * No checkboxes/progress gamification — calm guidance, not homework.
 */
export default function ChecklistScreen() {
  const { isDarkMode } = useSettings();
  const theme = Colors[isDarkMode ? 'dark' : 'light'];

  // Location and nearby places
  const {
    location: userLocation,
    status: locationStatus,
    requestPermission,
    getCurrentLocation,
  } = useLocation();

  const [nearbyPlaces, setNearbyPlaces] = useState<Place[]>([]);
  const [isLoadingPlaces, setIsLoadingPlaces] = useState(false);
  const [placesError, setPlacesError] = useState<string | null>(null);

  const fetchNearbyPlaces = useCallback(async () => {
    if (!userLocation) return;
    setIsLoadingPlaces(true);
    setPlacesError(null);
    try {
      const places = await getNearestCoolingPlaces(userLocation.latitude, userLocation.longitude);
      setNearbyPlaces(places);
    } catch {
      setPlacesError('ไม่พบสถานที่ใกล้เคียง ลองอีกครั้ง');
    } finally {
      setIsLoadingPlaces(false);
    }
  }, [userLocation]);

  useEffect(() => {
    if (locationStatus === 'idle') {
      getCurrentLocation();
    }
    // getCurrentLocation is stable from the hook; depend only on locationStatus.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locationStatus]);

  useEffect(() => {
    if (userLocation) {
      fetchNearbyPlaces();
    }
  }, [userLocation, fetchNearbyPlaces]);

  const handleFindCoolingLocation = async () => {
    if (locationStatus !== 'granted') {
      const hasPermission = await requestPermission();
      if (!hasPermission) return;
    }
    if (!userLocation) {
      await getCurrentLocation();
    }
    await fetchNearbyPlaces();
  };

  // Thai EMS (การแพทย์ฉุกเฉิน) — NOT 911
  const callEmergency = () => {
    Linking.openURL('tel:1669');
  };

  const navigateToPlace = (place: Place) => {
    const { latitude, longitude } = place;
    const url = Platform.OS === 'ios'
      ? `http://maps.apple.com/?daddr=${latitude},${longitude}`
      : `https://www.google.com/maps/dir/?api=1&destination=${latitude},${longitude}`;
    Linking.openURL(url);
  };

  const card = [styles.card, { backgroundColor: theme.surface, borderColor: theme.border }, SoftShadow.light];

  const Advice = ({ icon, title, desc, warn }: { icon: string; title: string; desc: React.ReactNode; warn?: boolean }) => (
    <View style={[...card, warn && styles.warnCard]}>
      <View style={[styles.adviceIcon, { backgroundColor: warn ? RiskBg.warning : theme.background, borderColor: theme.border }]}>
        <IconSymbol size={22} name={icon as never} color={warn ? RiskColors.warning : theme.icon} />
      </View>
      <View style={styles.adviceBody}>
        <ScaledText style={[styles.adviceTitle, { color: theme.text }]}>{title}</ScaledText>
        <ScaledText style={[styles.adviceDesc, { color: theme.textMuted }]}>{desc}</ScaledText>
      </View>
    </View>
  );

  const SectionH = ({ children }: { children: string }) => (
    <ScaledText style={[styles.sectionH, { color: theme.textMuted }]}>{children}</ScaledText>
  );

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]} edges={['top']}>
      <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* App bar */}
        <View style={styles.appbar}>
          <TouchableOpacity style={styles.backButton} onPress={() => router.back()} accessibilityLabel="ย้อนกลับ">
            <IconSymbol size={18} name="arrow_back_ios_new" color={theme.icon} />
          </TouchableOpacity>
          <View style={styles.appbarText}>
            <ScaledText style={[styles.appbarTitle, { color: theme.primary }]}>ดูแลตัวเอง</ScaledText>
            <ScaledText style={[styles.appbarSub, { color: theme.textMuted }]}>คำแนะนำวันอากาศร้อน</ScaledText>
          </View>
        </View>

        <SectionH>ก่อนออกจากบ้าน</SectionH>
        <Advice
          icon="water_drop"
          title="เตรียมน้ำดื่มติดตัว"
          desc="อย่างน้อย 1 ลิตรต่อการออกนอกบ้าน 3 ชั่วโมง เลี่ยงเครื่องดื่มแอลกอฮอล์และกาแฟ"
        />
        <Advice
          icon="checkroom"
          title="เสื้อผ้าสีอ่อน ระบายอากาศ"
          desc="ผ้าฝ้ายหลวม ๆ สีอ่อน หมวกปีกกว้าง ช่วยลดอุณหภูมิร่างกายได้จริง"
        />

        <SectionH>ช่วงกลางวัน 11:00–15:00</SectionH>
        <Advice
          icon="home"
          title="เลี่ยงกลางแจ้งช่วงแดดแรง"
          desc="ถ้าจำเป็นต้องทำงานกลางแจ้ง พัก 10–15 นาทีในที่ร่มทุกชั่วโมง"
        />
        <Advice
          icon="groups"
          title="ดูแลกลุ่มเสี่ยงใกล้ตัว"
          desc="ผู้สูงอายุ เด็กเล็ก ผู้ป่วยโรคหัวใจ — โทรเช็คอาการช่วงบ่ายวันร้อนจัด"
        />

        <SectionH>สัญญาณอันตราย</SectionH>
        <Advice
          warn
          icon="warning"
          title="โรคลมแดด (Heat Stroke)"
          desc={
            <>
              ตัวร้อนจัดแต่ไม่มีเหงื่อ สับสน หมดสติ — ระหว่างรอ: ย้ายเข้าร่ม เช็ดตัวด้วยน้ำเย็น
            </>
          }
        />
        <TouchableOpacity
          style={[styles.emergencyBtn, { backgroundColor: RiskColors.warning }]}
          onPress={callEmergency}
          accessibilityRole="button"
          accessibilityLabel="โทรสายด่วนการแพทย์ฉุกเฉิน 1669"
        >
          <IconSymbol size={20} name="call" color="#FFFFFF" />
          <ScaledText style={styles.emergencyText}>โทร 1669 — การแพทย์ฉุกเฉิน</ScaledText>
        </TouchableOpacity>

        <SectionH>จุดหลบร้อนใกล้คุณ</SectionH>
        {isLoadingPlaces && (
          <View style={[...card, styles.placesStatus]}>
            <ActivityIndicator size="small" color={theme.primary} />
            <ScaledText style={[styles.adviceDesc, { color: theme.textMuted }]}>กำลังค้นหาสถานที่เย็นใกล้เคียง…</ScaledText>
          </View>
        )}
        {!isLoadingPlaces && placesError && (
          <TouchableOpacity style={[...card, styles.placesStatus]} onPress={handleFindCoolingLocation}>
            <IconSymbol size={18} name="refresh" color={theme.primary} />
            <ScaledText style={[styles.adviceDesc, { color: theme.textMuted }]}>{placesError} · แตะเพื่อลองใหม่</ScaledText>
          </TouchableOpacity>
        )}
        {!isLoadingPlaces && !placesError && nearbyPlaces.length === 0 && (
          <TouchableOpacity style={[...card, styles.placesStatus]} onPress={handleFindCoolingLocation}>
            <IconSymbol size={18} name="my_location" color={theme.primary} />
            <ScaledText style={[styles.adviceDesc, { color: theme.textMuted }]}>
              แตะเพื่อค้นหาห้าง ร้านสะดวกซื้อ หรือที่เย็น ๆ ใกล้คุณ
            </ScaledText>
          </TouchableOpacity>
        )}
        {nearbyPlaces.map((place) => (
          <TouchableOpacity key={`${place.name}-${place.latitude}`} style={[...card, styles.placeRow]} onPress={() => navigateToPlace(place)}>
            <View style={[styles.adviceIcon, { backgroundColor: theme.background, borderColor: theme.border }]}>
              <IconSymbol size={20} name={getPlaceIcon(place.type) as never} color={theme.icon} />
            </View>
            <View style={styles.adviceBody}>
              <ScaledText numberOfLines={1} style={[styles.adviceTitle, { color: theme.text }]}>{place.name}</ScaledText>
              <ScaledText style={[styles.adviceDesc, { color: theme.textMuted }]}>
                {estimateTravelTime(place.distance)} · {place.distance.toFixed(1)} กม.
              </ScaledText>
            </View>
            <IconSymbol size={18} name="directions" color={theme.primary} />
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Floating liquid-glass tab bar (shared) */}
      <GlassTabBar active="safety" />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scrollView: { flex: 1 },
  scrollContent: { paddingBottom: 104, paddingHorizontal: 16 },
  appbar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingTop: 14,
    paddingBottom: 6,
  },
  backButton: { minWidth: 44, minHeight: 44, alignItems: 'flex-start', justifyContent: 'center' },
  appbarText: { flex: 1 },
  appbarTitle: { fontSize: 20, fontFamily: FontFamily.display, fontWeight: '700' },
  appbarSub: { fontSize: 12, fontFamily: FontFamily.body },
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
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 14,
    borderWidth: 1,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  warnCard: { borderLeftWidth: 3, borderLeftColor: RiskColors.warning },
  adviceIcon: {
    width: 42,
    height: 42,
    borderRadius: 11,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  adviceBody: { flex: 1 },
  adviceTitle: { fontSize: 14.5, fontFamily: FontFamily.displaySemi, fontWeight: '600' },
  adviceDesc: { fontSize: 12.5, fontFamily: FontFamily.body, lineHeight: 20, marginTop: 2 },
  emergencyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    borderRadius: 12,
    paddingVertical: 14,
    marginBottom: 12,
    minHeight: 48,
  },
  emergencyText: { color: '#FFFFFF', fontSize: 14.5, fontFamily: FontFamily.bodySemi, fontWeight: '600' },
  placesStatus: { alignItems: 'center' },
  placeRow: { alignItems: 'center' },
});
