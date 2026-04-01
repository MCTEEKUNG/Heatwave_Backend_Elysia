import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { Colors, DesignTokens, GlassStyle, BottomNavStyle } from '@/constants/theme';
import { useSettings } from '@/hooks/useSettings';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { ScaledText } from '@/components/ui/ScaledText';

// Calendar data - August 2024
const CALENDAR_DAYS = Array.from({ length: 31 }, (_, i) => i + 1);
const START_DAY = 4; // Thursday (Aug 1, 2024)

// Risk levels for each day
const RISK_LEVELS: { [key: number]: string } = {
  1: 'low', 2: 'low', 3: 'low', 4: 'low', 5: 'low', 6: 'low', 7: 'low',
  8: 'extreme', 9: 'extreme',
  10: 'low', 11: 'low', 12: 'low', 13: 'low',
  14: 'today', // Today
  15: 'medium', 16: 'medium',
};

// Survival metrics data
const getMetrics = (t: (key: any) => string, isDarkMode: boolean) => [
  { label: t('wetBulb'), value: '22°C', status: t('moderateRisk'), statusColor: isDarkMode ? '#60A5FA' : '#007AFF' },
  { label: t('aqi'), value: '42', status: t('goodQuality'), statusColor: isDarkMode ? '#4ADE80' : '#34C759' },
  { label: t('uvIndex'), value: '3.4', status: t('moderate'), statusColor: isDarkMode ? '#FB923C' : '#F97316' },
  { label: t('humidity'), value: '65%', status: t('stable'), statusColor: isDarkMode ? '#A1A1AA' : '#8E8E93' },
];

const getRiskColor = (risk: string, theme: any): string => {
  switch (risk) {
    case 'extreme':
      return `${theme.extreme}15`;
    case 'medium':
      return `${theme.medium}20`;
    case 'low':
      return `${theme.low}15`;
    case 'today':
      return theme.primary;
    default:
      return 'transparent';
  }
};

const getRiskBorder = (risk: string, theme: any): string => {
  switch (risk) {
    case 'extreme':
      return theme.extreme;
    case 'medium':
      return theme.medium;
    default:
      return 'transparent';
  }
};

export default function AlertsScreen() {
  const { isDarkMode, t } = useSettings();
  const theme = Colors[isDarkMode ? 'dark' : 'light'];
  const METRICS = getMetrics(t, isDarkMode);

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]} edges={['top']}>
      {/* Header - matching design */}
      <View style={[styles.header, { backgroundColor: isDarkMode ? 'rgba(26, 21, 18, 0.85)' : 'rgba(255, 255, 255, 0.85)', backdropFilter: 'blur(12px)' }]}>
        <TouchableOpacity 
          style={[styles.backButton, { backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)' }]}
          onPress={() => router.back()}
        >
          <IconSymbol size={20} name="arrow_back_ios_new" color={theme.icon} />
        </TouchableOpacity>
        <ScaledText variant="h3" style={[styles.headerTitle, { color: theme.text }]}>{t('forecastDetails')}</ScaledText>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Hero Forecast Card - matching design */}
        <View style={[styles.heroCard, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
          <ScaledText variant="labelMedium" style={[styles.forecastLabel, { color: theme.primary }]}>{t('forecastLabel')}</ScaledText>
          
          <View style={styles.weatherIcon}>
            <View style={styles.sunGlow} />
            <ScaledText variant="displayLarge" style={styles.sunIcon}>☀️</ScaledText>
          </View>
          
          <ScaledText variant="displayLarge" style={[styles.tempValue, { color: theme.text }]}>40°C</ScaledText>
          
          <ScaledText variant="h4" style={[styles.heatStatus, { color: theme.extreme }]}>{t('extremeHeat')}</ScaledText>
          
          <ScaledText variant="bodyMedium" style={[styles.forecastDesc, { color: theme.textSecondary }]}>
            {t('peakIntensityWarning')}
          </ScaledText>
        </View>

        {/* Calendar Section - matching design */}
        <View style={styles.calendarSection}>
          <ScaledText variant="labelMedium" style={[styles.sectionTitle, { color: theme.textSecondary }]}>{t('augustForecast')}</ScaledText>
          
          <View style={[styles.calendarCard, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
            {/* Week headers */}
            <View style={styles.weekHeader}>
              {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, i) => (
                <ScaledText variant="labelSmall" key={i} style={[styles.weekDay, { color: theme.textSecondary }]}>{day}</ScaledText>
              ))}
            </View>
            
            {/* Calendar grid */}
            <View style={styles.calendarGrid}>
              {/* Empty cells for Aug 2024 start */}
              {[...Array(START_DAY)].map((_, i) => (
                <View key={`empty-${i}`} style={styles.calendarCell} />
              ))}
              
              {/* Days */}
              {CALENDAR_DAYS.map((day) => {
                const risk = RISK_LEVELS[day] || 'default';
                return (
                  <View
                    key={day}
                    style={[
                      styles.calendarCell,
                      {
                        backgroundColor: getRiskColor(risk, theme),
                        borderColor: getRiskBorder(risk, theme),
                        borderWidth: risk === 'extreme' || risk === 'medium' ? 1 : 0,
                      },
                      risk === 'today' && { backgroundColor: isDarkMode ? '#3B82F6' : '#007AFF' }
                    ]}
                  >
                    <Text
                      style={[
                        styles.calendarDay,
                        risk === 'today' && { color: '#fff', fontWeight: '900' },
                        risk === 'low' && { color: isDarkMode ? '#4ADE80' : '#34C759' },
                        risk === 'medium' && { color: isDarkMode ? '#FBBF24' : '#D97706', fontWeight: '700' },
                        risk === 'extreme' && { color: isDarkMode ? '#F87171' : '#EF4444', fontWeight: '700' },
                        !risk && { color: theme.textSecondary },
                      ]}
                    >
                      {day}
                    </Text>
                  </View>
                );
              })}
            </View>
          </View>
        </View>

        {/* Survival Metrics Grid - matching design */}
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

        {/* Safety Action Button - matching design */}
        <TouchableOpacity 
          style={[styles.safetyButton, { backgroundColor: theme.primary }]}
          onPress={() => router.push('/checklist')}
        >
          <IconSymbol size={24} name="shield_check" color="#fff" />
          <ScaledText variant="labelLarge" style={styles.safetyButtonText}>{t('safetyActions')}</ScaledText>
        </TouchableOpacity>
      </ScrollView>

      {/* Bottom Navigation - matching design */}
      <View style={[styles.bottomNav, BottomNavStyle.container, isDarkMode ? BottomNavStyle.dark : {}]}>
        <TouchableOpacity 
          style={styles.navItem}
          onPress={() => router.push('/(tabs)/map')}
        >
          <IconSymbol size={28} name="map.fill" color={theme.tabIconDefault} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.tabIconDefault }]}>{t('navMap')}</ScaledText>
        </TouchableOpacity>
        
        <TouchableOpacity style={styles.navItem}>
          <IconSymbol size={28} name="notifications" color={theme.primary} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.primary }]}>{t('navAlerts')}</ScaledText>
          <View style={[styles.activeDot, { backgroundColor: theme.primary }]} />
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={styles.navItem}
          onPress={() => router.push('/checklist')}
        >
          <IconSymbol size={28} name="shield.fill" color={theme.tabIconDefault} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.tabIconDefault }]}>{t('navSafety')}</ScaledText>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={styles.navItem}
          onPress={() => router.push('/(tabs)/settings')}
        >
          <IconSymbol size={28} name="person.fill" color={theme.tabIconDefault} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.tabIconDefault }]}>{t('navProfile')}</ScaledText>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: DesignTokens.spacing.lg,
    paddingVertical: DesignTokens.spacing.md,
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    letterSpacing: -0.5,
  },
  headerSpacer: {
    width: 40,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: DesignTokens.spacing.lg,
    paddingBottom: 120,
  },
  heroCard: {
    alignItems: 'center',
    padding: DesignTokens.spacing.lg,
    borderRadius: DesignTokens.borderRadius.xl,
    marginBottom: DesignTokens.spacing.lg,
  },
  forecastLabel: {
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: DesignTokens.spacing.sm,
  },
  weatherIcon: {
    position: 'relative',
    marginBottom: DesignTokens.spacing.lg,
  },
  sunGlow: {
    position: 'absolute',
    top: -10,
    left: -10,
    right: -10,
    bottom: -10,
    backgroundColor: 'rgba(250, 204, 21, 0.2)',
    borderRadius: 50,
  },
  sunIcon: {
    fontSize: 64,
  },
  tempValue: {
    fontSize: 72,
    fontWeight: '900',
    marginBottom: DesignTokens.spacing.sm,
  },
  heatStatus: {
    fontSize: 14,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: DesignTokens.spacing.xl,
  },
  forecastDesc: {
    fontSize: 12,
    textAlign: 'center',
    maxWidth: 240,
  },
  calendarSection: {
    marginBottom: DesignTokens.spacing.lg,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: DesignTokens.spacing.md,
  },
  calendarCard: {
    padding: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.xl,
  },
  weekHeader: {
    flexDirection: 'row',
    marginBottom: DesignTokens.spacing.sm,
  },
  weekDay: {
    flex: 1,
    textAlign: 'center',
    fontSize: 12,
    fontWeight: '700',
  },
  calendarGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  calendarCell: {
    width: `${100 / 7}%`,
    aspectRatio: 1,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: DesignTokens.borderRadius.md,
  },
  calendarDay: {
    fontSize: 12,
    fontWeight: '600',
  },
  metricsSection: {
    marginBottom: DesignTokens.spacing.lg,
  },
  metricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: DesignTokens.spacing.md,
  },
  metricCard: {
    width: '47%',
    padding: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.xl,
  },
  metricHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: DesignTokens.spacing.sm,
    marginBottom: DesignTokens.spacing.sm,
  },
  metricLabel: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  metricValue: {
    fontSize: 24,
    fontWeight: '700',
  },
  metricStatus: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    marginTop: 4,
  },
  safetyButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: DesignTokens.spacing.sm,
    paddingVertical: DesignTokens.spacing.lg,
    borderRadius: DesignTokens.borderRadius.xl,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 4,
  },
  safetyButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: 1,
  },
  bottomNav: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    paddingHorizontal: DesignTokens.spacing.md,
  },
  navItem: {
    alignItems: 'center',
    justifyContent: 'center',
    width: 64,
    position: 'relative',
  },
  navLabel: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginTop: 4,
  },
  activeDot: {
    position: 'absolute',
    bottom: -8,
    width: 4,
    height: 4,
    borderRadius: 2,
  },
});
