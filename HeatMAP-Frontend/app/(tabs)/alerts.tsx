import { View, StyleSheet, TouchableOpacity, ScrollView, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { Colors, DesignTokens, GlassStyle, BottomNavStyle } from '@/constants/theme';
import { useSettings } from '@/hooks/useSettings';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { ScaledText } from '@/components/ui/ScaledText';
import { useForecast, type CalendarDay, type RiskLevel } from '@/hooks/useForecast';
import { useWeather } from '@/hooks/useWeather';

// ─── 3-tier risk colour helpers ───────────────────────────────────────────────
// safe    = 🟢 Green  — no heatwave predicted
// caution = 🟡 Yellow — heatwave predicted, probability < 70%
// danger  = 🔴 Red    — heatwave predicted, probability ≥ 70%

const RISK_COLORS = {
  safe:    { bg: 'rgba(34,197,94,0.18)',  border: '#22C55E', text: { dark: '#4ADE80', light: '#16A34A' } },
  caution: { bg: 'rgba(234,179,8,0.20)',  border: '#EAB308', text: { dark: '#FDE047', light: '#CA8A04' } },
  danger:  { bg: 'rgba(239,68,68,0.22)',  border: '#EF4444', text: { dark: '#F87171', light: '#DC2626' } },
};

function riskBg(risk: RiskLevel): string {
  return RISK_COLORS[risk]?.bg ?? 'transparent';
}

function riskBorder(risk: RiskLevel): string {
  return RISK_COLORS[risk]?.border ?? 'transparent';
}

function riskTextColor(risk: RiskLevel, isDark: boolean): string {
  return RISK_COLORS[risk]?.text[isDark ? 'dark' : 'light'] ?? (isDark ? '#A1A1AA' : '#6B7280');
}

// ─── Calendar builder ─────────────────────────────────────────────────────────

/**
 * Builds a month grid matching the forecast calendar.
 * We show the current month and colour each day using AI risk data.
 */
function buildMonthGrid(calendarDays: CalendarDay[]): {
  year: number;
  month: number;
  startWeekday: number;
  daysInMonth: number;
  riskMap: Map<number, CalendarDay>;
} {
  const now = new Date();
  const year  = now.getFullYear();
  const month = now.getMonth(); // 0-indexed
  const daysInMonth    = new Date(year, month + 1, 0).getDate();
  const startWeekday   = new Date(year, month, 1).getDay(); // 0 = Sunday

  // Map day-of-month → CalendarDay for fast lookup
  const riskMap = new Map<number, CalendarDay>();
  calendarDays.forEach((c) => {
    const d = new Date(c.date);
    if (d.getFullYear() === year && d.getMonth() === month) {
      riskMap.set(d.getDate(), c);
    }
  });

  return { year, month, startWeekday, daysInMonth, riskMap };
}

const MONTH_NAMES = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December',
];

// ─── Component ────────────────────────────────────────────────────────────────

export default function AlertsScreen() {
  const { isDarkMode, t } = useSettings();
  const theme = Colors[isDarkMode ? 'dark' : 'light'];

  // Real AI forecast data from the backend
  const { calendar, summary, loading: forecastLoading, error: forecastError, refresh } = useForecast(1);

  // Real weather data from Open-Meteo (Bangkok default, no GPS needed)
  const { temperature, wetBulb, uvIndex, humidity, aqi, aqiLabel, daily, loading: weatherLoading } = useWeather();

  const loading = forecastLoading || weatherLoading;

  // Build dynamic calendar grid for the current month
  const { year, month, startWeekday, daysInMonth, riskMap } = buildMonthGrid(calendar);

  // Derive today's forecast headline
  const todayForecast = summary.today;
  const todayTemp     = todayForecast ? Math.round(todayForecast.temperature_c) : Math.round(temperature);
  const todayRisk: RiskLevel = todayForecast
    ? (todayForecast.predicted_heatwave !== 1
        ? 'safe'
        : todayForecast.heatwave_probability >= 0.70 ? 'danger' : 'caution')
    : 'safe';

  const todayLabel =
    todayRisk === 'danger'  ? '🔴 DANGER — Check Safety Guide Now' :
    todayRisk === 'caution' ? '🟡 Caution — Prepare Yourself' :
                              '🟢 Safe — No Heatwave';

  // Survival metrics derived from real data
  const METRICS = [
    {
      label:       t('wetBulb'),
      value:       `${wetBulb}°C`,
      status:      wetBulb >= 28 ? 'Danger Zone' : wetBulb >= 24 ? t('moderateRisk') : 'Safe',
      statusColor: wetBulb >= 28
        ? (isDarkMode ? '#F87171' : '#EF4444')
        : wetBulb >= 24
          ? (isDarkMode ? '#FB923C' : '#F97316')
          : (isDarkMode ? '#4ADE80' : '#34C759'),
    },
    {
      label:       t('aqi'),
      value:       String(aqi),
      status:      aqiLabel,
      statusColor: aqi <= 20
        ? (isDarkMode ? '#4ADE80' : '#34C759')
        : aqi <= 40
          ? (isDarkMode ? '#60A5FA' : '#007AFF')
          : (isDarkMode ? '#FB923C' : '#F97316'),
    },
    {
      label:       t('uvIndex'),
      value:       uvIndex.toFixed(1),
      status:      uvIndex >= 8 ? 'Very High' : uvIndex >= 6 ? t('high') : t('moderate'),
      statusColor: uvIndex >= 8
        ? (isDarkMode ? '#F87171' : '#EF4444')
        : isDarkMode ? '#FB923C' : '#F97316',
    },
    {
      label:       t('humidity'),
      value:       `${Math.round(humidity)}%`,
      status:      humidity >= 80 ? 'Very Humid' : humidity >= 60 ? t('stable') : 'Low',
      statusColor: isDarkMode ? '#A1A1AA' : '#8E8E93',
    },
  ];

  // ── Normal render ──
  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]} edges={['top']}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: isDarkMode ? 'rgba(26,21,18,0.85)' : 'rgba(255,255,255,0.85)' }]}>
        <TouchableOpacity
          style={[styles.backButton, { backgroundColor: isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)' }]}
          onPress={() => router.back()}
        >
          <IconSymbol size={20} name="arrow_back_ios_new" color={theme.icon} />
        </TouchableOpacity>
        <ScaledText variant="h3" style={[styles.headerTitle, { color: theme.text }]}>{t('forecastDetails')}</ScaledText>
        <TouchableOpacity onPress={refresh} disabled={forecastLoading}>
          {forecastLoading
            ? <ActivityIndicator size="small" color={theme.primary} />
            : <IconSymbol size={20} name="refresh" color={theme.textSecondary} />}
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ── Forecast unavailable banner (non-blocking) ── */}
        {forecastError && calendar.length === 0 && (
          <View style={[styles.forecastBanner, { backgroundColor: isDarkMode ? 'rgba(239,68,68,0.12)' : 'rgba(239,68,68,0.08)', borderColor: isDarkMode ? '#F87171' : '#EF4444' }]}>
            <IconSymbol size={16} name="error_outline" color={isDarkMode ? '#F87171' : '#EF4444'} />
            <ScaledText variant="bodySmall" style={{ color: isDarkMode ? '#F87171' : '#EF4444', flex: 1, marginLeft: 8 }}>
              AI forecast unavailable — backend is waking up. Weather data below is live.
            </ScaledText>
            <TouchableOpacity onPress={refresh} disabled={forecastLoading}>
              {forecastLoading
                ? <ActivityIndicator size="small" color={isDarkMode ? '#F87171' : '#EF4444'} />
                : <ScaledText variant="labelSmall" style={{ color: isDarkMode ? '#F87171' : '#EF4444', fontWeight: '700' }}>Retry</ScaledText>}
            </TouchableOpacity>
          </View>
        )}

        {/* ── Hero Forecast Card ── */}
        <View style={[styles.heroCard, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
          <ScaledText variant="labelMedium" style={[styles.forecastLabel, { color: theme.primary }]}>
            {t('forecastLabel')}
          </ScaledText>

          <View style={styles.weatherIcon}>
            <View style={styles.sunGlow} />
            <ScaledText variant="displayLarge" style={styles.sunIcon}>
              {todayRisk === 'danger' ? '🔥' : todayRisk === 'caution' ? '☀️' : '🌤️'}
            </ScaledText>
          </View>

          <ScaledText variant="displayLarge" style={[styles.tempValue, { color: theme.text }]}>
            {todayTemp}°C
          </ScaledText>

          <ScaledText
            variant="h4"
            style={[styles.heatStatus, { color: riskTextColor(todayRisk, isDarkMode) }]}
          >
            {todayLabel}
          </ScaledText>

          {todayForecast && (
            <ScaledText variant="bodyMedium" style={[styles.forecastDesc, { color: theme.textSecondary }]}>
              {`${Math.round(summary.heatwaveDays)} heatwave days predicted in the next ${summary.totalDays} days — ${(summary.avgProbability * 100).toFixed(0)}% average risk`}
            </ScaledText>
          )}
        </View>

        {/* ── AI-powered Calendar ── */}
        <View style={styles.calendarSection}>
          <ScaledText variant="labelMedium" style={[styles.sectionTitle, { color: theme.textSecondary }]}>
            {`${MONTH_NAMES[month]} ${year} — AI Heatwave Forecast`}
          </ScaledText>

          <View style={[styles.calendarCard, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
            {/* Week-day headers */}
            <View style={styles.weekHeader}>
              {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
                <ScaledText key={i} variant="labelSmall" style={[styles.weekDay, { color: theme.textSecondary }]}>
                  {d}
                </ScaledText>
              ))}
            </View>

            {/* Calendar grid */}
            <View style={styles.calendarGrid}>
              {/* Leading empty cells */}
              {Array.from({ length: startWeekday }).map((_, i) => (
                <View key={`empty-${i}`} style={styles.calendarCell} />
              ))}

              {/* Day cells */}
              {Array.from({ length: daysInMonth }, (_, i) => i + 1).map((day) => {
                const cell    = riskMap.get(day);
                const risk    = cell?.riskLevel ?? 'safe';
                const isToday = cell?.isToday ?? (day === new Date().getDate());

                return (
                  <View
                    key={day}
                    style={[
                      styles.calendarCell,
                      {
                        backgroundColor: isToday
                          ? (isDarkMode ? '#3B82F6' : '#007AFF')
                          : riskBg(risk),
                        borderColor:     isToday ? 'transparent' : riskBorder(risk),
                        borderWidth:     risk !== 'safe' && !isToday ? 1 : 0,
                      },
                    ]}
                  >
                    <ScaledText
                      variant="labelSmall"
                      style={[
                        styles.calendarDay,
                        isToday
                          ? { color: '#fff', fontWeight: '900' }
                          : { color: riskTextColor(risk, isDarkMode), fontWeight: risk !== 'safe' ? '700' : '400' },
                      ]}
                    >
                      {day}
                    </ScaledText>
                  </View>
                );
              })}
            </View>

            {/* Legend */}
            <View style={styles.calendarLegend}>
              {([
                { label: '🟢 Safe',    color: isDarkMode ? '#4ADE80' : '#16A34A' },
                { label: '🟡 Caution', color: isDarkMode ? '#FDE047' : '#CA8A04' },
                { label: '🔴 Danger',  color: isDarkMode ? '#F87171' : '#DC2626' },
              ] as const).map((item) => (
                <View key={item.label} style={styles.legendItem}>
                  <View style={[styles.legendDot, { backgroundColor: item.color }]} />
                  <ScaledText variant="labelSmall" style={{ color: theme.textSecondary, fontSize: 9 }}>
                    {item.label}
                  </ScaledText>
                </View>
              ))}
            </View>
          </View>
        </View>

        {/* ── Live Conditions Grid ── */}
        <View style={styles.metricsSection}>
          <View style={styles.metricsGrid}>
            {METRICS.map((metric, index) => (
              <View key={index} style={[styles.metricCard, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
                <View style={styles.metricHeader}>
                  <IconSymbol size={18} name="wb_sunny" color={theme.primary} />
                  <ScaledText variant="bodySmall" style={[styles.metricLabel, { color: theme.textSecondary }]}>
                    {metric.label}
                  </ScaledText>
                </View>
                <ScaledText variant="labelLarge" style={[styles.metricValue, { color: theme.text }]}>
                  {metric.value}
                </ScaledText>
                <ScaledText variant="labelSmall" style={[styles.metricStatus, { color: metric.statusColor }]}>
                  {metric.status}
                </ScaledText>
              </View>
            ))}
          </View>
        </View>

        {/* ── 7-Day Weather Forecast (Open-Meteo) ── */}
        {daily.length > 0 && (
          <View style={styles.dailySection}>
            <ScaledText variant="labelMedium" style={[styles.sectionTitle, { color: theme.textSecondary }]}>
              7-DAY WEATHER FORECAST
            </ScaledText>
            <View style={[styles.dailyCard, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
              {daily.map((day, i) => (
                <View
                  key={day.date}
                  style={[
                    styles.dailyRow,
                    i < daily.length - 1 && { borderBottomWidth: 1, borderBottomColor: isDarkMode ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)' }
                  ]}
                >
                  <ScaledText variant="labelMedium" style={[styles.dailyDay, { color: theme.text }]}>
                    {day.dayLabel}
                  </ScaledText>
                  <View style={styles.dailyMiddle}>
                    <ScaledText style={{ fontSize: 20 }}>{
                      day.icon === 'sunny' ? '☀️' :
                      day.icon === 'partly_cloudy_day' ? '⛅' :
                      day.icon === 'cloud' ? '☁️' :
                      day.icon === 'rainy' ? '🌧️' :
                      day.icon === 'thunderstorm' ? '⛈️' :
                      day.icon === 'foggy' ? '🌫️' : '🌤️'
                    }</ScaledText>
                    {day.precipProb > 20 && (
                      <ScaledText variant="labelSmall" style={{ color: '#60A5FA', marginLeft: 6 }}>
                        {day.precipProb}%
                      </ScaledText>
                    )}
                  </View>
                  <View style={styles.dailyTemps}>
                    <ScaledText variant="labelMedium" style={{ color: theme.text, fontWeight: '700', minWidth: 36, textAlign: 'right' }}>
                      {day.tempMax}°
                    </ScaledText>
                    <ScaledText variant="labelSmall" style={{ color: theme.textSecondary, minWidth: 32, textAlign: 'right' }}>
                      {day.tempMin}°
                    </ScaledText>
                  </View>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* ── Safety Button ── */}
        <TouchableOpacity
          style={[styles.safetyButton, { backgroundColor: theme.primary }]}
          onPress={() => router.push('/checklist')}
        >
          <IconSymbol size={24} name="shield_check" color="#fff" />
          <ScaledText variant="labelLarge" style={styles.safetyButtonText}>
            {t('safetyActions')}
          </ScaledText>
        </TouchableOpacity>
      </ScrollView>

      {/* Bottom Navigation */}
      <View style={[styles.bottomNav, BottomNavStyle.container, isDarkMode ? BottomNavStyle.dark : {}]}>
        <TouchableOpacity style={styles.navItem} onPress={() => router.push('/(tabs)/map')}>
          <IconSymbol size={28} name="map.fill" color={theme.tabIconDefault} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.tabIconDefault }]}>{t('navMap')}</ScaledText>
        </TouchableOpacity>

        <TouchableOpacity style={styles.navItem}>
          <IconSymbol size={28} name="notifications" color={theme.primary} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.primary }]}>{t('navAlerts')}</ScaledText>
          <View style={[styles.activeDot, { backgroundColor: theme.primary }]} />
        </TouchableOpacity>

        <TouchableOpacity style={styles.navItem} onPress={() => router.push('/checklist')}>
          <IconSymbol size={28} name="shield.fill" color={theme.tabIconDefault} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.tabIconDefault }]}>{t('navSafety')}</ScaledText>
        </TouchableOpacity>

        <TouchableOpacity style={styles.navItem} onPress={() => router.push('/(tabs)/settings')}>
          <IconSymbol size={28} name="person.fill" color={theme.tabIconDefault} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.tabIconDefault }]}>{t('navProfile')}</ScaledText>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container:      { flex: 1 },
  centeredContent:{ flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    flexDirection:  'row',
    alignItems:     'center',
    justifyContent: 'space-between',
    paddingHorizontal: DesignTokens.spacing.lg,
    paddingVertical:   DesignTokens.spacing.md,
  },
  backButton: {
    width: 40, height: 40, borderRadius: 20,
    justifyContent: 'center', alignItems: 'center',
  },
  headerTitle: { fontSize: 18, fontWeight: '600', letterSpacing: -0.5 },
  headerSpacer: { width: 40 },
  retryButton: {
    paddingVertical: DesignTokens.spacing.md,
    paddingHorizontal: DesignTokens.spacing.lg,
    borderRadius: DesignTokens.borderRadius.xl,
  },
  scrollView:   { flex: 1 },
  scrollContent:{ padding: DesignTokens.spacing.lg, paddingBottom: 120 },

  // Forecast banner
  forecastBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.lg,
    borderWidth: 1,
    marginBottom: DesignTokens.spacing.md,
  },

  // Hero
  heroCard: {
    alignItems:   'center',
    padding:       DesignTokens.spacing.lg,
    borderRadius:  DesignTokens.borderRadius.xl,
    marginBottom:  DesignTokens.spacing.lg,
  },
  forecastLabel: {
    fontSize: 12, fontWeight: '700',
    textTransform: 'uppercase', letterSpacing: 1,
    marginBottom: DesignTokens.spacing.sm,
  },
  weatherIcon: { position: 'relative', marginBottom: DesignTokens.spacing.lg },
  sunGlow: {
    position: 'absolute', top: -10, left: -10, right: -10, bottom: -10,
    backgroundColor: 'rgba(250,204,21,0.2)', borderRadius: 50,
  },
  sunIcon:    { fontSize: 64 },
  tempValue:  { fontSize: 72, fontWeight: '900', marginBottom: DesignTokens.spacing.sm },
  heatStatus: {
    fontSize: 14, fontWeight: '700',
    textTransform: 'uppercase', letterSpacing: 1,
    marginBottom: DesignTokens.spacing.xl,
  },
  forecastDesc: { fontSize: 12, textAlign: 'center', maxWidth: 260 },

  // Calendar
  calendarSection: { marginBottom: DesignTokens.spacing.lg },
  sectionTitle: {
    fontSize: 12, fontWeight: '700',
    textTransform: 'uppercase', letterSpacing: 1,
    marginBottom: DesignTokens.spacing.md,
  },
  calendarCard: {
    padding:      DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.xl,
  },
  weekHeader:   { flexDirection: 'row', marginBottom: DesignTokens.spacing.sm },
  weekDay:      { flex: 1, textAlign: 'center', fontSize: 12, fontWeight: '700' },
  calendarGrid: { flexDirection: 'row', flexWrap: 'wrap' },
  calendarCell: {
    width: `${100 / 7}%`,
    aspectRatio: 1,
    justifyContent: 'center',
    alignItems:     'center',
    borderRadius:   DesignTokens.borderRadius.md,
  },
  calendarDay:  { fontSize: 12 },
  calendarLegend: {
    flexDirection:  'row',
    justifyContent: 'center',
    gap:  DesignTokens.spacing.lg,
    marginTop: DesignTokens.spacing.sm,
    paddingTop: DesignTokens.spacing.sm,
  },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendDot:  { width: 8, height: 8, borderRadius: 4 },

  // Metrics
  metricsSection: { marginBottom: DesignTokens.spacing.lg },
  metricsGrid:    { flexDirection: 'row', flexWrap: 'wrap', gap: DesignTokens.spacing.md },
  metricCard: {
    width: '47%', padding: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.xl,
  },
  metricHeader: {
    flexDirection: 'row', alignItems: 'center',
    gap: DesignTokens.spacing.sm, marginBottom: DesignTokens.spacing.sm,
  },
  metricLabel:  { fontSize: 10, fontWeight: '700', textTransform: 'uppercase' },
  metricValue:  { fontSize: 24, fontWeight: '700' },
  metricStatus: { fontSize: 10, fontWeight: '700', textTransform: 'uppercase', marginTop: 4 },

  // 7-day weather
  dailySection: { marginBottom: DesignTokens.spacing.lg },
  dailyCard: {
    borderRadius: DesignTokens.borderRadius.xl,
    overflow: 'hidden',
  },
  dailyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: DesignTokens.spacing.md,
    paddingHorizontal: DesignTokens.spacing.lg,
  },
  dailyDay: { width: 52, fontWeight: '600' },
  dailyMiddle: { flex: 1, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8 },
  dailyTemps: { flexDirection: 'row', alignItems: 'center', gap: 8 },

  // Safety button
  safetyButton: {
    flexDirection:  'row',
    alignItems:     'center',
    justifyContent: 'center',
    gap:            DesignTokens.spacing.sm,
    paddingVertical: DesignTokens.spacing.lg,
    borderRadius:   DesignTokens.borderRadius.xl,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2, shadowRadius: 8, elevation: 4,
  },
  safetyButtonText: { color: '#fff', fontSize: 16, fontWeight: '700', letterSpacing: 1 },

  // Bottom nav
  bottomNav: {
    flexDirection:  'row',
    justifyContent: 'space-around',
    alignItems:     'center',
    paddingHorizontal: DesignTokens.spacing.md,
  },
  navItem: {
    alignItems: 'center', justifyContent: 'center',
    width: 64, position: 'relative',
  },
  navLabel: {
    fontSize: 10, fontWeight: '700',
    textTransform: 'uppercase', letterSpacing: 1, marginTop: 4,
  },
  activeDot: {
    position: 'absolute', bottom: -8,
    width: 4, height: 4, borderRadius: 2,
  },
});
