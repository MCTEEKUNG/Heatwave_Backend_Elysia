import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Linking } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, DesignTokens, GlassStyle } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';

const PRD_CONTENT = {
  title: 'Heatwave Forecast',
  version: '1.0.0',
  description: 'AI-powered heatwave forecasting application to help users stay safe during extreme heat events.',
  features: [
    {
      icon: '📅',
      title: 'Calendar Forecast',
      description: 'Monthly calendar view with severity-based color classification',
    },
    {
      icon: '🗺️',
      title: 'Grid Map',
      description: 'Latitude-longitude grid visualization for localized predictions',
    },
    {
      icon: '🔔',
      title: 'Push Alerts',
      description: 'Real-time notifications for heatwave conditions',
    },
    {
      icon: '🛡️',
      title: 'Safety Checklist',
      description: 'Protective measures guide during heatwave events',
    },
  ],
  severity: [
    { color: '#E53935', label: 'Extreme', description: 'Temperature > 40°C - Avoid outdoor activities' },
    { color: '#FDD835', label: 'Medium', description: 'Temperature 35-40°C - Take precautions' },
    { color: '#43A047', label: 'Low', description: 'Temperature < 35°C - Normal conditions' },
  ],
};

export default function PRDScreen() {
  const colorScheme = useColorScheme();
  const theme = Colors[colorScheme ?? 'light'];

  const callEmergency = () => {
    Linking.openURL('tel:911');
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]} edges={['top']}>
      {/* Header */}
      <View style={[styles.header, GlassStyle[colorScheme ?? 'light']]}>
        <Text style={[styles.headerTitle, { color: theme.text }]}>Product Requirements</Text>
        <Text style={[styles.version, { color: theme.textSecondary }]}>v{PRD_CONTENT.version}</Text>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* App Title */}
        <View style={[styles.titleCard, { backgroundColor: theme.primary }]}>
          <Text style={styles.titleIcon}>🌡️</Text>
          <Text style={styles.titleText}>{PRD_CONTENT.title}</Text>
          <Text style={styles.descriptionText}>{PRD_CONTENT.description}</Text>
        </View>

        {/* Emergency CTA */}
        <TouchableOpacity
          style={[styles.emergencyCard, { backgroundColor: theme.extreme }]}
          onPress={callEmergency}
        >
          <Text style={styles.emergencyIcon}>🚨</Text>
          <View style={styles.emergencyContent}>
            <Text style={styles.emergencyTitle}>Emergency: Call 911</Text>
            <Text style={styles.emergencyText}>
              For heat stroke emergencies, call emergency services immediately
            </Text>
          </View>
        </TouchableOpacity>

        {/* Features */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.text }]}>Core Features</Text>
          {PRD_CONTENT.features.map((feature, index) => (
            <View
              key={index}
              style={[styles.featureCard, GlassStyle[colorScheme ?? 'light']]}
            >
              <View style={[styles.featureIcon, { backgroundColor: theme.primary + '20' }]}>
                <Text style={styles.featureIconText}>{feature.icon}</Text>
              </View>
              <View style={styles.featureContent}>
                <Text style={[styles.featureTitle, { color: theme.text }]}>{feature.title}</Text>
                <Text style={[styles.featureDescription, { color: theme.textSecondary }]}>
                  {feature.description}
                </Text>
              </View>
            </View>
          ))}
        </View>

        {/* Severity Classification */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.text }]}>Severity Classification</Text>
          <View style={[styles.severityCard, GlassStyle[colorScheme ?? 'light']]}>
            {PRD_CONTENT.severity.map((item, index) => (
              <View
                key={index}
                style={[
                  styles.severityItem,
                  index < PRD_CONTENT.severity.length - 1 && { borderBottomWidth: 1, borderBottomColor: theme.border },
                ]}
              >
                <View style={[styles.severityDot, { backgroundColor: item.color }]} />
                <View style={styles.severityContent}>
                  <Text style={[styles.severityLabel, { color: theme.text }]}>{item.label}</Text>
                  <Text style={[styles.severityDesc, { color: theme.textSecondary }]}>{item.description}</Text>
                </View>
              </View>
            ))}
          </View>
        </View>

        {/* Technical Info */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.text }]}>Technical Information</Text>
          <View style={[styles.infoCard, GlassStyle[colorScheme ?? 'light']]}>
            <View style={styles.infoRow}>
              <Text style={[styles.infoLabel, { color: theme.textSecondary }]}>Platform:</Text>
              <Text style={[styles.infoValue, { color: theme.text }]}>iOS, Android, Web</Text>
            </View>
            <View style={[styles.infoRow, { borderTopWidth: 1, borderTopColor: theme.border }]}>
              <Text style={[styles.infoLabel, { color: theme.textSecondary }]}>Framework:</Text>
              <Text style={[styles.infoValue, { color: theme.text }]}>React Native / Expo</Text>
            </View>
            <View style={[styles.infoRow, { borderTopWidth: 1, borderTopColor: theme.border }]}>
              <Text style={[styles.infoLabel, { color: theme.textSecondary }]}>Design:</Text>
              <Text style={[styles.infoValue, { color: theme.text }]}>Glassmorphism + Inter Font</Text>
            </View>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: DesignTokens.spacing.lg,
    paddingVertical: DesignTokens.spacing.md,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
  },
  version: {
    fontSize: 14,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: DesignTokens.spacing.lg,
    paddingBottom: DesignTokens.spacing.xxl,
  },
  titleCard: {
    padding: DesignTokens.spacing.xl,
    borderRadius: DesignTokens.borderRadius.xl,
    alignItems: 'center',
    marginBottom: DesignTokens.spacing.lg,
  },
  titleIcon: {
    fontSize: 48,
    marginBottom: DesignTokens.spacing.md,
  },
  titleText: {
    fontSize: 28,
    fontWeight: '700',
    color: '#fff',
    marginBottom: DesignTokens.spacing.sm,
  },
  descriptionText: {
    fontSize: 14,
    color: '#fff',
    textAlign: 'center',
    opacity: 0.9,
  },
  emergencyCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: DesignTokens.spacing.lg,
    borderRadius: DesignTokens.borderRadius.lg,
    marginBottom: DesignTokens.spacing.lg,
  },
  emergencyIcon: {
    fontSize: 32,
    marginRight: DesignTokens.spacing.md,
  },
  emergencyContent: {
    flex: 1,
  },
  emergencyTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#fff',
  },
  emergencyText: {
    fontSize: 12,
    color: '#fff',
    opacity: 0.9,
    marginTop: 4,
  },
  section: {
    marginBottom: DesignTokens.spacing.lg,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: DesignTokens.spacing.md,
  },
  featureCard: {
    flexDirection: 'row',
    padding: DesignTokens.spacing.md,
    marginBottom: DesignTokens.spacing.sm,
  },
  featureIcon: {
    width: 48,
    height: 48,
    borderRadius: DesignTokens.borderRadius.md,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: DesignTokens.spacing.md,
  },
  featureIconText: {
    fontSize: 24,
  },
  featureContent: {
    flex: 1,
  },
  featureTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  featureDescription: {
    fontSize: 14,
  },
  severityCard: {
    borderRadius: DesignTokens.borderRadius.lg,
    overflow: 'hidden',
  },
  severityItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: DesignTokens.spacing.md,
  },
  severityDot: {
    width: 16,
    height: 16,
    borderRadius: 8,
    marginRight: DesignTokens.spacing.md,
  },
  severityContent: {
    flex: 1,
  },
  severityLabel: {
    fontSize: 16,
    fontWeight: '600',
  },
  severityDesc: {
    fontSize: 12,
    marginTop: 2,
  },
  infoCard: {
    borderRadius: DesignTokens.borderRadius.lg,
    overflow: 'hidden',
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: DesignTokens.spacing.md,
  },
  infoLabel: {
    fontSize: 14,
  },
  infoValue: {
    fontSize: 14,
    fontWeight: '500',
  },
});
