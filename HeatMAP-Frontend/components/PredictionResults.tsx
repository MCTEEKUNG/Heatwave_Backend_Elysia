import { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';

const API_URL = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:3000') + '/api';

interface PredictionData {
  success: boolean;
  model: string;
  predictions: { predicted_heatwave: string; heatwave_probability?: string }[];
  log?: string;
}

export default function PredictionResults() {
  const [predictions, setPredictions] = useState<PredictionData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState('balanced_rf');
  const models = ['balanced_rf'];

  const fetchPrediction = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: selectedModel,
          inputData: 'temperature,humidity,pressure,wind_speed\n35.2,45,1013,12.5\n38.1,40,1010,10.2',
          includeProba: true
        })
      });

      const data = await response.json();

      if (data.success) {
        setPredictions(data);
      } else {
        setError(data.error || 'Prediction failed');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (prediction: { predicted_heatwave: string }) => {
    return prediction?.predicted_heatwave === '1' ? '#e74c3c' : '#27ae60';
  };

  const getStatusText = (prediction: { predicted_heatwave: string }) => {
    return prediction?.predicted_heatwave === '1' ? 'Heatwave Detected' : 'No Heatwave';
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Heatwave AI Predictions</Text>

      <View style={styles.modelSelector}>
        {models.map((model) => (
          <TouchableOpacity
            key={model}
            style={[
              styles.modelButton,
              selectedModel === model && styles.modelButtonActive
            ]}
            onPress={() => setSelectedModel(model)}
          >
            <Text style={[
              styles.modelButtonText,
              selectedModel === model && styles.modelButtonTextActive
            ]}>
              {model.toUpperCase()}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity
        style={styles.predictButton}
        onPress={fetchPrediction}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.predictButtonText}>Run Prediction</Text>
        )}
      </TouchableOpacity>

      {error && (
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {predictions && (
        <View style={styles.resultsContainer}>
          <Text style={styles.resultsTitle}>Prediction Results</Text>
          <Text style={styles.modelInfo}>Model: {predictions.model}</Text>

          {predictions.predictions.map((pred, index) => (
            <View key={index} style={styles.predictionCard}>
              <View style={[
                styles.statusIndicator,
                { backgroundColor: getStatusColor(pred) }
              ]} />
              <View style={styles.predictionContent}>
                <Text style={styles.predictionStatus}>
                  {getStatusText(pred)}
                </Text>
                {pred.heatwave_probability && (
                  <Text style={styles.probabilityText}>
                    Confidence: {(parseFloat(pred.heatwave_probability) * 100).toFixed(1)}%
                  </Text>
                )}
              </View>
            </View>
          ))}

          <Text style={styles.logText}>Prediction Log:</Text>
          <ScrollView style={styles.logContainer}>
            <Text style={styles.logContent}>{predictions.log}</Text>
          </ScrollView>
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
    color: '#2c3e50'
  },
  modelSelector: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginBottom: 16,
    gap: 8
  },
  modelButton: {
    padding: 10,
    borderRadius: 8,
    backgroundColor: '#ecf0f1',
    borderWidth: 2,
    borderColor: 'transparent'
  },
  modelButtonActive: {
    borderColor: '#3498db',
    backgroundColor: '#ebf5fb'
  },
  modelButtonText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#7f8c8d'
  },
  modelButtonTextActive: {
    color: '#2980b9'
  },
  predictButton: {
    backgroundColor: '#3498db',
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 16
  },
  predictButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold'
  },
  errorContainer: {
    backgroundColor: '#fadbd8',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16
  },
  errorText: {
    color: '#e74c3c',
    fontSize: 14
  },
  resultsContainer: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3
  },
  resultsTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 8,
    color: '#2c3e50'
  },
  modelInfo: {
    fontSize: 14,
    color: '#7f8c8d',
    marginBottom: 16
  },
  predictionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: '#f8f9fa',
    borderRadius: 8,
    marginBottom: 8
  },
  statusIndicator: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: 12
  },
  predictionContent: {
    flex: 1
  },
  predictionStatus: {
    fontSize: 16,
    fontWeight: '600',
    color: '#2c3e50'
  },
  probabilityText: {
    fontSize: 14,
    color: '#7f8c8d',
    marginTop: 4
  },
  logText: {
    fontSize: 14,
    fontWeight: '600',
    marginTop: 16,
    marginBottom: 8,
    color: '#2c3e50'
  },
  logContainer: {
    backgroundColor: '#2c3e50',
    borderRadius: 8,
    padding: 12,
    maxHeight: 200
  },
  logContent: {
    color: '#ecf0f1',
    fontSize: 12,
    fontFamily: 'monospace'
  }
});
