import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Dimensions
} from 'react-native';
import {
  runForecast,
  getLatestForecast,
  getHeatwaveRiskLevel,
  getRiskColor,
  formatForecastDate,
  ForecastDay
} from '../../services/forecastService';

const { width } = Dimensions.get('window');

export default function ForecastScreen() {
  const [forecast, setForecast] = useState<ForecastDay[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState('balanced_rf');
  const [selectedCycle, setSelectedCycle] = useState(1);
  const [forecastDays, setForecastDays] = useState(30);
  const [cycles, setCycles] = useState(1);

  const models = [
    { key: 'balanced_rf', label: 'Balanced RF' },
    { key: 'xgboost', label: 'XGBoost' },
    { key: 'lightgbm', label: 'LightGBM' },
    { key: 'mlp', label: 'MLP' },
    { key: 'kan', label: 'KAN' }
  ];

  useEffect(() => {
    loadLatestForecast();
  }, []);

  const loadLatestForecast = async () => {
    setLoading(true);
    try {
      console.log('[ForecastScreen] Fetching latest forecast...');
      const data = await getLatestForecast();
      console.log('[ForecastScreen] Received data:', JSON.stringify(data).slice(0, 500));
      
      if (data.forecast && data.forecast.length > 0) {
        console.log('[ForecastScreen] Setting forecast with', data.forecast.length, 'days');
        setForecast(data.forecast);
        setSelectedCycle(1);
      } else if (data.error) {
        console.log('[ForecastScreen] Error in response:', data.error);
        setError(data.error);
      } else {
        console.log('[ForecastScreen] No forecast data available');
        setError('No forecast data available. Run a forecast first.');
      }
    } catch (err: any) {
      console.error('[ForecastScreen] Error:', err);
      setError(`Connection failed: ${err.message}. Make sure backend is running on port 3000.`);
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

  const filteredForecast = forecast.filter(
    (day) => day.forecast_cycle === selectedCycle
  );

  const heatwaveDays = filteredForecast.filter(
    (day) => day.predicted_heatwave === 1
  ).length;

  const avgProbability = filteredForecast.length > 0
    ? filteredForecast.reduce((sum, day) => sum + day.heatwave_probability, 0) / filteredForecast.length
    : 0;

  const uniqueCycles = [...new Set(forecast.map((day) => day.forecast_cycle))];

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>30-Day Heatwave Forecast</Text>

      <View style={styles.modelSelector}>
        {models.map((model) => (
          <TouchableOpacity
            key={model.key}
            style={[
              styles.modelButton,
              selectedModel === model.key && styles.modelButtonActive
            ]}
            onPress={() => setSelectedModel(model.key)}
          >
            <Text
              style={[
                styles.modelButtonText,
                selectedModel === model.key && styles.modelButtonTextActive
              ]}
            >
              {model.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <View style={styles.optionsRow}>
        <View style={styles.optionGroup}>
          <Text style={styles.optionLabel}>Days</Text>
          <View style={styles.optionButtons}>
            {[7, 14, 30, 60, 90].map((d) => (
              <TouchableOpacity
                key={d}
                style={[
                  styles.optionButton,
                  forecastDays === d && styles.optionButtonActive
                ]}
                onPress={() => setForecastDays(d)}
              >
                <Text
                  style={[
                    styles.optionButtonText,
                    forecastDays === d && styles.optionButtonTextActive
                  ]}
                >
                  {d}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <View style={styles.optionGroup}>
          <Text style={styles.optionLabel}>Cycles</Text>
          <View style={styles.optionButtons}>
            {[1, 2, 3].map((c) => (
              <TouchableOpacity
                key={c}
                style={[
                  styles.optionButton,
                  cycles === c && styles.optionButtonActive
                ]}
                onPress={() => setCycles(c)}
              >
                <Text
                  style={[
                    styles.optionButtonText,
                    cycles === c && styles.optionButtonTextActive
                  ]}
                >
                  {c}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </View>

      <TouchableOpacity
        style={styles.forecastButton}
        onPress={handleRunForecast}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.forecastButtonText}>
            Generate Forecast
          </Text>
        )}
      </TouchableOpacity>

      {error && (
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.retryButton} onPress={loadLatestForecast}>
            <Text style={styles.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      )}

      {loading && forecast.length === 0 && (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#3b82f6" />
          <Text style={styles.loadingText}>Loading forecast data...</Text>
        </View>
      )}

      {forecast.length > 0 && (
        <View style={styles.resultsContainer}>
          <View style={styles.summaryRow}>
            <View style={styles.summaryCard}>
              <Text style={styles.summaryValue}>{filteredForecast.length}</Text>
              <Text style={styles.summaryLabel}>Days</Text>
            </View>
            <View style={styles.summaryCard}>
              <Text style={[styles.summaryValue, { color: '#dc2626' }]}>
                {heatwaveDays}
              </Text>
              <Text style={styles.summaryLabel}>Heatwave</Text>
            </View>
            <View style={styles.summaryCard}>
              <Text style={[styles.summaryValue, { color: '#2563eb' }]}>
                {(avgProbability * 100).toFixed(1)}%
              </Text>
              <Text style={styles.summaryLabel}>Avg Risk</Text>
            </View>
          </View>

          {uniqueCycles.length > 1 && (
            <View style={styles.cycleSelector}>
              {uniqueCycles.map((cycle) => (
                <TouchableOpacity
                  key={cycle}
                  style={[
                    styles.cycleButton,
                    selectedCycle === cycle && styles.cycleButtonActive
                  ]}
                  onPress={() => setSelectedCycle(cycle)}
                >
                  <Text
                    style={[
                      styles.cycleButtonText,
                      selectedCycle === cycle && styles.cycleButtonTextActive
                    ]}
                  >
                    Cycle {cycle}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          )}

          <View style={styles.calendarGrid}>
            {filteredForecast.map((day, index) => {
              const risk = getHeatwaveRiskLevel(day.heatwave_probability);
              const riskColor = getRiskColor(risk);

              return (
                <TouchableOpacity
                  key={index}
                  style={[
                    styles.dayCell,
                    {
                      borderColor: riskColor,
                      backgroundColor:
                        day.predicted_heatwave === 1
                          ? `${riskColor}15`
                          : '#f8fafc'
                    }
                  ]}
                >
                  <Text style={styles.dayDate}>
                    {formatForecastDate(day.date).split(' ')[0]}{' '}
                    {formatForecastDate(day.date).split(' ')[1]}
                  </Text>
                  <View
                    style={[
                      styles.riskIndicator,
                      { backgroundColor: riskColor }
                    ]}
                  />
                  <Text style={styles.dayProbability}>
                    {(day.heatwave_probability * 100).toFixed(0)}%
                  </Text>
                  <Text style={styles.dayTemp}>
                    {day.temperature_c.toFixed(1)}°C
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <View style={styles.legend}>
            <Text style={styles.legendTitle}>Risk Level</Text>
            <View style={styles.legendItems}>
              {[
                { label: 'Low', color: '#16a34a' },
                { label: 'Moderate', color: '#ca8a04' },
                { label: 'High', color: '#ea580c' },
                { label: 'Extreme', color: '#dc2626' }
              ].map((item) => (
                <View key={item.label} style={styles.legendItem}>
                  <View
                    style={[styles.legendDot, { backgroundColor: item.color }]}
                  />
                  <Text style={styles.legendLabel}>{item.label}</Text>
                </View>
              ))}
            </View>
          </View>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    padding: 16
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 20,
    color: '#1e293b'
  },
  modelSelector: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 16
  },
  modelButton: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: '#e2e8f0',
    borderWidth: 2,
    borderColor: 'transparent'
  },
  modelButtonActive: {
    borderColor: '#3b82f6',
    backgroundColor: '#dbeafe'
  },
  modelButtonText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#64748b'
  },
  modelButtonTextActive: {
    color: '#2563eb'
  },
  optionsRow: {
    flexDirection: 'row',
    gap: 16,
    marginBottom: 16
  },
  optionGroup: {
    flex: 1
  },
  optionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#475569',
    marginBottom: 8
  },
  optionButtons: {
    flexDirection: 'row',
    gap: 6
  },
  optionButton: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 6,
    backgroundColor: '#e2e8f0'
  },
  optionButtonActive: {
    backgroundColor: '#3b82f6'
  },
  optionButtonText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#64748b'
  },
  optionButtonTextActive: {
    color: '#fff'
  },
  forecastButton: {
    backgroundColor: '#3b82f6',
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginBottom: 16
  },
  forecastButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold'
  },
  errorContainer: {
    backgroundColor: '#fee2e2',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16
  },
  errorText: {
    color: '#dc2626',
    fontSize: 14
  },
  retryButton: {
    marginTop: 8,
    paddingVertical: 6,
    paddingHorizontal: 16,
    backgroundColor: '#dc2626',
    borderRadius: 6,
    alignSelf: 'flex-start'
  },
  retryText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600'
  },
  loadingContainer: {
    padding: 32,
    alignItems: 'center'
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: '#64748b'
  },
  resultsContainer: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginBottom: 16,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0'
  },
  summaryCard: {
    alignItems: 'center'
  },
  summaryValue: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#1e293b'
  },
  summaryLabel: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 4
  },
  cycleSelector: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16
  },
  cycleButton: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
    backgroundColor: '#e2e8f0'
  },
  cycleButtonActive: {
    backgroundColor: '#3b82f6'
  },
  cycleButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#64748b'
  },
  cycleButtonTextActive: {
    color: '#fff'
  },
  calendarGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 16
  },
  dayCell: {
    width: (width - 64) / 4,
    padding: 8,
    borderRadius: 8,
    borderWidth: 2,
    alignItems: 'center'
  },
  dayDate: {
    fontSize: 10,
    color: '#64748b',
    marginBottom: 4
  },
  riskIndicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginBottom: 4
  },
  dayProbability: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#1e293b'
  },
  dayTemp: {
    fontSize: 10,
    color: '#64748b',
    marginTop: 2
  },
  legend: {
    borderTopWidth: 1,
    borderTopColor: '#e2e8f0',
    paddingTop: 16
  },
  legendTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#475569',
    marginBottom: 8
  },
  legendItems: {
    flexDirection: 'row',
    justifyContent: 'space-around'
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4
  },
  legendDot: {
    width: 10,
    height: 10,
    borderRadius: 5
  },
  legendLabel: {
    fontSize: 12,
    color: '#64748b'
  }
});
