/**
 * ProvinceForecastPanel
 *
 * Renders the 7-day per-province heatwave outlook returned by
 * `/api/forecast/province/:id` (via `useProvinceForecast`), with the model's
 * "as of" (`generated_at`) timestamp. Handles loading / empty / error states
 * so it degrades gracefully when the backend is asleep or offline.
 *
 * Reused by the Map screen and the /liff (LINE) route so web and in-LINE views
 * show identical data.
 */

import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity } from 'react-native';
import { Colors, DesignTokens } from '@/constants/theme';
import { useSettings } from '@/hooks/useSettings';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { useProvinceForecast } from '@/hooks/useProvinceForecast';
import {
  getRiskColor,
  riskLevelToSeverity,
  formatGeneratedAt,
  formatForecastDate,
} from '@/services/forecastService';
import type { Province } from '@/services/provincesService';

interface Props {
  province: Province | null;
  days?: number;
}

export function ProvinceForecastPanel({ province, days = 7 }: Props) {
  const { isDarkMode, language, t } = useSettings();
  const theme = Colors[isDarkMode ? 'dark' : 'light'];

  const { days: forecast, generatedAt, loading, error, refresh } = useProvinceForecast(
    province?.id ?? null,
    days,
  );

  if (!province) return null;

  const provinceName = language === 'th' ? province.name_th : province.name_en;
  const asOf = formatGeneratedAt(generatedAt);

  return (
    <View style={[styles.card, { backgroundColor: theme.surface, borderColor: theme.border }]}>
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={[styles.title, { color: theme.text }]}>{provinceName}</Text>
          <Text style={[styles.subtitle, { color: theme.textMuted }]}>{t('sevenDayForecast')}</Text>
        </View>
        {!!asOf && (
          <View style={styles.asOfRow}>
            <IconSymbol size={13} name="clock" color={theme.textMuted} />
            <Text style={[styles.asOf, { color: theme.textMuted }]}>
              {t('asOf')} {asOf}
            </Text>
          </View>
        )}
      </View>

      {loading && (
        <View style={styles.stateBox}>
          <ActivityIndicator color={theme.primary} />
          <Text style={[styles.stateText, { color: theme.textMuted }]}>{t('loading')}</Text>
        </View>
      )}

      {!loading && !!error && (
        <View style={styles.stateBox}>
          <Text style={[styles.stateText, { color: theme.textMuted }]}>{error}</Text>
          <TouchableOpacity
            style={[styles.retry, { borderColor: theme.border }]}
            onPress={refresh}
          >
            <Text style={[styles.retryText, { color: theme.primary }]}>Retry</Text>
          </TouchableOpacity>
        </View>
      )}

      {!loading && !error && forecast.length === 0 && (
        <View style={styles.stateBox}>
          <Text style={[styles.stateText, { color: theme.textMuted }]}>{t('noForecastData')}</Text>
        </View>
      )}

      {!loading && !error && forecast.length > 0 && (
        <View style={styles.daysRow}>
          {forecast.map((d) => {
            const sev = riskLevelToSeverity(d.risk_level);
            const color = getRiskColor(sev);
            return (
              <View
                key={d.target_date}
                style={[styles.dayCell, { backgroundColor: `${color}1A`, borderColor: `${color}55` }]}
              >
                <Text style={[styles.dayDate, { color: theme.textMuted }]} numberOfLines={1}>
                  {formatForecastDate(d.target_date).replace(/, \d{4}$/, '')}
                </Text>
                <View style={[styles.dayDot, { backgroundColor: color }]} />
                <Text style={[styles.dayProb, { color }]}>
                  {Math.round((d.probability ?? 0) * 100)}%
                </Text>
              </View>
            );
          })}
        </View>
      )}
    </View>
  );
}

export default ProvinceForecastPanel;

const styles = StyleSheet.create({
  card: {
    borderRadius: DesignTokens.borderRadius.lg,
    borderWidth: 1,
    padding: DesignTokens.spacing.md,
    gap: DesignTokens.spacing.sm,
  },
  header: { flexDirection: 'row', alignItems: 'flex-start', gap: DesignTokens.spacing.sm },
  title: { fontSize: 16, fontWeight: '700' },
  subtitle: { fontSize: 12, marginTop: 2 },
  asOfRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  asOf: { fontSize: 11, fontWeight: '500' },
  stateBox: { paddingVertical: 16, alignItems: 'center', gap: 8 },
  stateText: { fontSize: 13, textAlign: 'center' },
  retry: {
    paddingVertical: 6,
    paddingHorizontal: 16,
    borderRadius: DesignTokens.borderRadius.full,
    borderWidth: 1,
  },
  retryText: { fontSize: 13, fontWeight: '600' },
  daysRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  dayCell: {
    flexGrow: 1,
    flexBasis: 40,
    minWidth: 40,
    alignItems: 'center',
    gap: 4,
    paddingVertical: 8,
    borderRadius: DesignTokens.borderRadius.md,
    borderWidth: 1,
  },
  dayDate: { fontSize: 10, fontWeight: '600' },
  dayDot: { width: 8, height: 8, borderRadius: 4 },
  dayProb: { fontSize: 12, fontWeight: '700' },
});
