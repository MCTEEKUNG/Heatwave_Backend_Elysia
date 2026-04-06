import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Dimensions,
  useColorScheme
} from 'react-native';
import {
  runForecast,
  getLatestForecast,
  getHeatwaveRiskLevel,
  ForecastDay
} from '../../services/forecastService';

const { width } = Dimensions.get('window');
const CELL_W = Math.floor((width - 72) / 7); // 7-col calendar, 20px padding each side + 12px card padding each side

const RISK_COLORS = {
  low:      '#22C55E',
  moderate: '#EAB308',
  high:     '#F97316',
  extreme:  '#EF4444',
};

const RISK_BG_LIGHT = {
  low:      'rgba(34, 197, 94, 0.12)',
  moderate: 'rgba(234, 179, 8, 0.14)',
  high:     'rgba(249, 115, 22, 0.14)',
  extreme:  'rgba(239, 68, 68, 0.14)',
};

const RISK_BG_DARK = {
  low:      'rgba(34, 197, 94, 0.22)',
  moderate: 'rgba(234, 179, 8, 0.22)',
  high:     'rgba(249, 115, 22, 0.22)',
  extreme:  'rgba(239, 68, 68, 0.22)',
};

const THEME = {
  light: {
    background: '#F2F2F7',
    text: '#1A1A1A',
    textMuted: '#6B7280',
    cardBg: 'rgba(255,255,255,0.82)',
    cardBorder: 'rgba(0,0,0,0.06)',
    chipBg: 'rgba(0,0,0,0.06)',
  },
  dark: {
    background: '#0D0D12',
    text: '#F5F5F5',
    textMuted: '#8E8E93',
    cardBg: 'rgba(28,30,38,0.80)',
    cardBorder: 'rgba(255,255,255,0.10)',
    chipBg: 'rgba(255,255,255,0.08)',
  },
};

function groupByMonth(days: ForecastDay[]): [string, ForecastDay[]][] {
  const map: Map<string, ForecastDay[]> = new Map();
  for (const day of days) {
    const d = new Date(day.date);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(day);
  }
  return Array.from(map.entries());
}

function getMonthLabel(key: string): string {
  const [year, month] = key.split('-');
  return new Date(parseInt(year), parseInt(month) - 1, 1)
    .toLocaleString('default', { month: 'long', year: 'numeric' });
}

function getFirstDayOffset(key: string): number {
  const [year, month] = key.split('-');
  return new Date(parseInt(year), parseInt(month) - 1, 1).getDay();
}

function getDaysInMonth(key: string): number {
  const [year, month] = key.split('-');
  return new Date(parseInt(year), parseInt(month), 0).getDate();
}

export default function ForecastScreen() {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  const t = isDark ? THEME.dark : THEME.light;

  const [forecast, setForecast] = useState<ForecastDay[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState('balanced_rf');
  const [selectedCycle, setSelectedCycle] = useState(1);
  const [forecastDays, setForecastDays] = useState(30);
  const [cycles, setCycles] = useState(1);

  const models = [
    { key: 'balanced_rf', label: 'Balanced RF' },
    { key: 'xgboost',     label: 'XGBoost' },
    { key: 'lightgbm',    label: 'LightGBM' },
    { key: 'mlp',         label: 'MLP' },
    { key: 'kan',         label: 'KAN' },
  ];

  useEffect(() => { loadLatestForecast(); }, []);

  const loadLatestForecast = async () => {
    setLoading(true);
    try {
      const data = await getLatestForecast();
      if (data.forecast && data.forecast.length > 0) {
        setForecast(data.forecast);
        setSelectedCycle(1);
      } else {
        setError(data.error || 'No forecast data available. Run a forecast first.');
      }
    } catch (err: any) {
      setError('Unable to connect to the forecast service. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleRunForecast = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await runForecast(selectedModel, forecastDays, cycles);
      if (result.success && result.forecast) {
        setForecast(result.forecast);
      } else {
        setError(result.error || 'Forecast generation failed');
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const filteredForecast = forecast.filter(d => d.forecast_cycle === selectedCycle);
  const heatwaveDays = filteredForecast.filter(d => d.predicted_heatwave === 1).length;
  const avgProbability = filteredForecast.length > 0
    ? filteredForecast.reduce((s, d) => s + d.heatwave_probability, 0) / filteredForecast.length
    : 0;
  const maxRiskDay = filteredForecast.reduce<ForecastDay | null>(
    (max, d) => (!max || d.heatwave_probability > max.heatwave_probability) ? d : max,
    null
  );
  const uniqueCycles = [...new Set(forecast.map(d => d.forecast_cycle))];
  const monthGroups = groupByMonth(filteredForecast);

  const dateMap = new Map<string, ForecastDay>();
  filteredForecast.forEach(d => {
    const parsed = new Date(d.date);
    const key = `${parsed.getFullYear()}-${String(parsed.getMonth()+1).padStart(2,'0')}-${String(parsed.getDate()).padStart(2,'0')}`;
    dateMap.set(key, d);
  });

  const overallRisk = (maxRiskDay
    ? getHeatwaveRiskLevel(maxRiskDay.heatwave_probability)
    : 'low') as keyof typeof RISK_COLORS;
  const overallColor = RISK_COLORS[overallRisk];

  const cardStyle = [
    styles.card,
    { backgroundColor: t.cardBg, borderColor: t.cardBorder },
    isDark ? styles.cardShadowDark : styles.cardShadowLight,
  ];

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: t.background }]}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* ── Header ── */}
      <View style={styles.header}>
        <Text style={[styles.pageTitle, { color: t.text }]}>Heatwave Forecast</Text>
        <Text style={[styles.pageSubtitle, { color: t.textMuted }]}>AI-powered predictions</Text>
      </View>

      {/* ── Controls Panel ── */}
      <View style={cardStyle}>
        <Text style={[styles.label, { color: t.textMuted }]}>AI MODEL</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View style={styles.chipRow}>
            {models.map(m => (
              <TouchableOpacity
                key={m.key}
                style={[styles.chip, { backgroundColor: t.chipBg },
                  selectedModel === m.key && styles.chipActive]}
                onPress={() => setSelectedModel(m.key)}
              >
                <Text style={[styles.chipText, { color: t.textMuted },
                  selectedModel === m.key && styles.chipTextActive]}>
                  {m.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>

        <View style={styles.optionRow}>
          <View style={styles.optionGroup}>
            <Text style={[styles.label, { color: t.textMuted }]}>DAYS</Text>
            <View style={styles.chipRow}>
              {[7, 14, 30, 60, 90].map(d => (
                <TouchableOpacity
                  key={d}
                  style={[styles.chip, { backgroundColor: t.chipBg },
                    forecastDays === d && styles.chipActive]}
                  onPress={() => setForecastDays(d)}
                >
                  <Text style={[styles.chipText, { color: t.textMuted },
                    forecastDays === d && styles.chipTextActive]}>{d}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
          <View style={styles.optionGroup}>
            <Text style={[styles.label, { color: t.textMuted }]}>CYCLES</Text>
            <View style={styles.chipRow}>
              {[1, 2, 3].map(n => (
                <TouchableOpacity
                  key={n}
                  style={[styles.chip, { backgroundColor: t.chipBg },
                    cycles === n && styles.chipActive]}
                  onPress={() => setCycles(n)}
                >
                  <Text style={[styles.chipText, { color: t.textMuted },
                    cycles === n && styles.chipTextActive]}>{n}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        </View>

        <TouchableOpacity
          style={[styles.generateBtn, loading && { opacity: 0.6 }]}
          onPress={handleRunForecast}
          disabled={loading}
          activeOpacity={0.8}
        >
          {loading
            ? <ActivityIndicator color="#fff" size="small" />
            : <Text style={styles.generateBtnText}>Generate Forecast</Text>
          }
        </TouchableOpacity>
      </View>

      {/* ── Error ── */}
      {error && (
        <View style={styles.errorCard}>
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={loadLatestForecast}>
            <Text style={styles.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* ── Loading state ── */}
      {loading && forecast.length === 0 && (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="large" color="#E67E22" />
          <Text style={[styles.loadingText, { color: t.textMuted }]}>Running AI model…</Text>
        </View>
      )}

      {/* ── Results ── */}
      {filteredForecast.length > 0 && (
        <>
          {/* Hero Risk Card */}
          <View style={[
            styles.heroCard,
            { borderColor: `${overallColor}50`,
              backgroundColor: isDark ? `${overallColor}18` : `${overallColor}0E` }
          ]}>
            <View style={styles.heroLeft}>
              <View style={[styles.riskBadge, { backgroundColor: overallColor }]}>
                <Text style={styles.riskBadgeText}>{overallRisk.toUpperCase()}</Text>
              </View>
              <Text style={[styles.heroTitle, { color: t.text }]}>Risk Overview</Text>
              <Text style={[styles.heroSub, { color: t.textMuted }]}>
                {heatwaveDays} heatwave day{heatwaveDays !== 1 ? 's' : ''} detected
              </Text>
            </View>
            <View style={styles.heroRight}>
              <Text style={[styles.heroPercent, { color: overallColor }]}>
                {(avgProbability * 100).toFixed(0)}%
              </Text>
              <Text style={[styles.heroPercentLabel, { color: t.textMuted }]}>avg risk</Text>
            </View>
          </View>

          {/* Summary 2×2 grid */}
          <View style={styles.metricsGrid}>
            {[
              { label: 'Total Days',    value: `${filteredForecast.length}`, color: t.text },
              { label: 'Heatwave Days', value: `${heatwaveDays}`,            color: RISK_COLORS.extreme },
              { label: 'Avg Risk',      value: `${(avgProbability * 100).toFixed(1)}%`, color: '#E67E22' },
              { label: 'Peak Temp',
                value: maxRiskDay ? `${maxRiskDay.temperature_c.toFixed(1)}°C` : '—',
                color: RISK_COLORS.high },
            ].map((m, i) => (
              <View key={i} style={[styles.metricCard, cardStyle]}>
                <Text style={[styles.metricValue, { color: m.color }]}>{m.value}</Text>
                <Text style={[styles.metricLabel, { color: t.textMuted }]}>{m.label}</Text>
              </View>
            ))}
          </View>

          {/* Cycle selector */}
          {uniqueCycles.length > 1 && (
            <View style={styles.chipRow}>
              {uniqueCycles.map(cyc => (
                <TouchableOpacity
                  key={cyc}
                  style={[styles.chip, { backgroundColor: t.chipBg },
                    selectedCycle === cyc && styles.chipActive]}
                  onPress={() => setSelectedCycle(cyc)}
                >
                  <Text style={[styles.chipText, { color: t.textMuted },
                    selectedCycle === cyc && styles.chipTextActive]}>
                    Cycle {cyc}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          )}

          {/* Monthly calendar grids */}
          {monthGroups.map(([monthKey, _days]) => {
            const offset = getFirstDayOffset(monthKey);
            const totalDays = getDaysInMonth(monthKey);
            const [yr, mo] = monthKey.split('-');

            const cells: (ForecastDay | null)[] = [];
            for (let i = 0; i < offset; i++) cells.push(null);
            for (let d = 1; d <= totalDays; d++) {
              const key = `${yr}-${mo}-${String(d).padStart(2, '0')}`;
              cells.push(dateMap.get(key) ?? null);
            }

            return (
              <View key={monthKey} style={cardStyle}>
                <Text style={[styles.monthTitle, { color: t.text }]}>
                  {getMonthLabel(monthKey)}
                </Text>

                {/* Day-of-week headers */}
                <View style={styles.calHeaders}>
                  {['S','M','T','W','T','F','S'].map((d, i) => (
                    <Text key={i} style={[styles.calHeaderCell, { color: t.textMuted }]}>{d}</Text>
                  ))}
                </View>

                {/* Day cells */}
                <View style={styles.calGrid}>
                  {cells.map((day, idx) => {
                    if (!day) return <View key={idx} style={styles.calEmpty} />;

                    const risk = getHeatwaveRiskLevel(day.heatwave_probability) as keyof typeof RISK_COLORS;
                    const riskColor = RISK_COLORS[risk];
                    const bg = isDark ? RISK_BG_DARK[risk] : RISK_BG_LIGHT[risk];
                    const isHW = day.predicted_heatwave === 1;
                    const dayNum = new Date(day.date).getDate();

                    return (
                      <View
                        key={idx}
                        style={[
                          styles.calCell,
                          { backgroundColor: bg },
                          isHW && { borderWidth: 1.5, borderColor: `${riskColor}55` }
                        ]}
                      >
                        <Text style={[styles.calCellDay, { color: isHW ? riskColor : t.text }]}>
                          {dayNum}
                        </Text>
                        <Text style={[styles.calCellProb, { color: riskColor }]}>
                          {(day.heatwave_probability * 100).toFixed(0)}%
                        </Text>
                      </View>
                    );
                  })}
                </View>
              </View>
            );
          })}

          {/* Legend */}
          <View style={[styles.legend, cardStyle]}>
            <Text style={[styles.label, { color: t.textMuted }]}>RISK LEVEL</Text>
            <View style={styles.legendRow}>
              {(['low','moderate','high','extreme'] as const).map(r => (
                <View key={r} style={styles.legendItem}>
                  <View style={[styles.legendDot, { backgroundColor: RISK_COLORS[r] }]} />
                  <Text style={[styles.legendLabel, { color: t.textMuted }]}>
                    {r.charAt(0).toUpperCase() + r.slice(1)}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: 20, gap: 16, paddingBottom: 40 },

  header: { paddingVertical: 4 },
  pageTitle: { fontSize: 28, fontWeight: '700', letterSpacing: -0.5 },
  pageSubtitle: { fontSize: 14, marginTop: 2 },

  card: {
    borderRadius: 20,
    padding: 16,
    gap: 12,
    borderWidth: 1,
  },
  cardShadowLight: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.07,
    shadowRadius: 16,
    elevation: 3,
  },
  cardShadowDark: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.45,
    shadowRadius: 20,
    elevation: 8,
  },

  label: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2 },

  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { paddingVertical: 7, paddingHorizontal: 14, borderRadius: 100 },
  chipActive: { backgroundColor: '#E67E22' },
  chipText: { fontSize: 12, fontWeight: '600' },
  chipTextActive: { color: '#fff' },

  optionRow: { flexDirection: 'row', gap: 16 },
  optionGroup: { flex: 1, gap: 8 },

  generateBtn: {
    backgroundColor: '#E67E22',
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: 'center',
    shadowColor: '#E67E22',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.40,
    shadowRadius: 10,
    elevation: 6,
  },
  generateBtnText: { color: '#fff', fontSize: 15, fontWeight: '700', letterSpacing: 0.3 },

  errorCard: {
    borderRadius: 16,
    padding: 14,
    gap: 8,
    backgroundColor: 'rgba(239,68,68,0.10)',
    borderWidth: 1,
    borderColor: 'rgba(239,68,68,0.28)',
  },
  errorText: { color: '#EF4444', fontSize: 13 },
  retryBtn: {
    alignSelf: 'flex-start',
    paddingVertical: 6,
    paddingHorizontal: 16,
    backgroundColor: '#EF4444',
    borderRadius: 8,
  },
  retryText: { color: '#fff', fontSize: 13, fontWeight: '600' },

  loadingBox: { paddingVertical: 48, alignItems: 'center', gap: 12 },
  loadingText: { fontSize: 14 },

  // Hero card
  heroCard: {
    borderRadius: 20,
    padding: 20,
    borderWidth: 1.5,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  heroLeft: { gap: 6, flex: 1 },
  heroRight: { alignItems: 'flex-end' },
  riskBadge: { paddingVertical: 4, paddingHorizontal: 10, borderRadius: 100, alignSelf: 'flex-start' },
  riskBadgeText: { color: '#fff', fontSize: 10, fontWeight: '800', letterSpacing: 1 },
  heroTitle: { fontSize: 20, fontWeight: '700' },
  heroSub: { fontSize: 13 },
  heroPercent: { fontSize: 42, fontWeight: '800', letterSpacing: -1 },
  heroPercentLabel: { fontSize: 12, marginTop: -4 },

  // Metrics grid
  metricsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  metricCard: { width: (width - 52) / 2, gap: 4 },
  metricValue: { fontSize: 26, fontWeight: '700', letterSpacing: -0.5 },
  metricLabel: { fontSize: 12, fontWeight: '500' },

  // Calendar
  monthTitle: { fontSize: 16, fontWeight: '700' },
  calHeaders: { flexDirection: 'row', justifyContent: 'space-around' },
  calHeaderCell: { width: CELL_W, textAlign: 'center', fontSize: 11, fontWeight: '700', letterSpacing: 0.4 },
  calGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 3 },
  calEmpty: { width: CELL_W, height: CELL_W },
  calCell: {
    width: CELL_W,
    height: CELL_W,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 1,
  },
  calCellDay: { fontSize: 12, fontWeight: '700' },
  calCellProb: { fontSize: 9, fontWeight: '600' },

  // Legend
  legend: {},
  legendRow: { flexDirection: 'row', justifyContent: 'space-between' },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  legendDot: { width: 8, height: 8, borderRadius: 4 },
  legendLabel: { fontSize: 12, fontWeight: '500' },
});
