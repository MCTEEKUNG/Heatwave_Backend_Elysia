import { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Linking, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { Colors, DesignTokens, GlassStyle, BottomNavStyle } from '@/constants/theme';
import { useSettings } from '@/hooks/useSettings';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { ScaledText } from '@/components/ui/ScaledText';

// Checklist items matching design - will use translations
const getChecklistItems = (t: (key: any) => string) => [
  {
    id: 'hydrate',
    title: t('hydrate'),
    description: t('hydrateDesc'),
    icon: 'water_drop',
    completed: false,
  },
  {
    id: 'block-heat',
    title: t('blockHeat'),
    description: t('blockHeatDesc'),
    icon: 'wb_sunny',
    completed: false,
  },
  {
    id: 'dress',
    title: t('dressAppropriately'),
    description: t('dressAppropriatelyDesc'),
    icon: 'check',
    completed: false,
  },
  {
    id: 'find-cool',
    title: t('findCool'),
    description: t('findCoolDesc'),
    icon: 'ac_unit',
    completed: false,
  },
];

export default function SafetyScreen() {
  const { isDarkMode, language, fontScale, typography, t } = useSettings();
  const theme = Colors[isDarkMode ? 'dark' : 'light'];
  const checklistItems = getChecklistItems(t);
  const [checklist, setChecklist] = useState(checklistItems);

  const completedCount = checklist.filter(item => item.completed).length;
  const totalCount = checklist.length;
  const progressPercent = (completedCount / totalCount) * 100;

  const handleToggleItem = (itemId: string) => {
    setChecklist(prev =>
      prev.map(item =>
        item.id === itemId ? { ...item, completed: !item.completed } : item
      )
    );
  };

  const callEmergency = () => {
    Linking.openURL('tel:1669');
  };

  const navigateToHospital = () => {
    const address = encodeURIComponent("St. Mary's General Hospital");
    const url = Platform.OS === 'ios' 
      ? `http://maps.apple.com/?daddr=${address}`
      : `https://www.google.com/maps/search/?api=1&query=${address}`;
    Linking.openURL(url);
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]} edges={['top']}>
      {/* Header - matching design */}
      <View style={[styles.header, { backgroundColor: isDarkMode ? 'rgba(26, 21, 18, 0.85)' : 'rgba(255, 255, 255, 0.85)', backdropFilter: 'blur(12px)' }]}>
        <View style={styles.headerSpacer} />
        <ScaledText variant="h3" style={{ color: theme.text }}>{t('safetyChecklist')}</ScaledText>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Progress Section - matching design */}
        <View style={styles.progressSection}>
          <View style={styles.progressLabels}>
            <ScaledText variant="labelMedium" style={{ color: theme.textSecondary }}>{t('currentProgress')}</ScaledText>
            <ScaledText variant="labelLarge" style={{ color: theme.primary }}>
              {completedCount} {t('completed')}
            </ScaledText>
          </View>
          <View style={[styles.progressBar, { backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.1)' }]}>
            <View 
              style={[
                styles.progressFill, 
                { 
                  width: `${progressPercent}%`, 
                  backgroundColor: theme.primary,
                }
              ]} 
            />
          </View>
        </View>

        {/* Action Cards - matching design */}
        <View style={styles.cardsContainer}>
          {checklist.map((item) => (
            <TouchableOpacity
              key={item.id}
              style={[
                styles.actionCard,
                GlassStyle[isDarkMode ? 'dark' : 'light'],
                item.completed && { borderColor: theme.primary, borderWidth: 2 }
              ]}
              onPress={() => handleToggleItem(item.id)}
              activeOpacity={0.7}
            >
              {/* Icon */}
              <View style={[
                styles.cardIcon,
                { backgroundColor: item.completed ? theme.primary : isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)' }
              ]}>
                <IconSymbol 
                  size={28} 
                  name={item.icon} 
                  color={item.completed ? '#fff' : (isDarkMode ? theme.text : theme.textSecondary)} 
                />
              </View>
              
              {/* Content */}
              <View style={styles.cardContent}>
                <ScaledText variant="labelLarge" style={{ color: theme.text }}>{item.title}</ScaledText>
                <ScaledText variant="bodySmall" style={{ color: theme.textSecondary }}>
                  {item.description}
                </ScaledText>
              </View>
              
              {/* Checkbox */}
              <View style={[
                styles.checkbox,
                item.completed && { backgroundColor: theme.primary }
              ]}>
                {item.completed && (
                  <IconSymbol size={16} name="check" color="#fff" />
                )}
              </View>
            </TouchableOpacity>
          ))}
        </View>

        {/* Map Section - matching design */}
        <View style={[styles.mapCard, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
          <View style={[styles.mapOverlay, { backgroundColor: isDarkMode ? 'rgba(0, 0, 0, 0.6)' : 'rgba(0, 0, 0, 0.4)' }]}>
            <View style={styles.mapContent}>
              {/* Nearest Care indicator */}
              <View style={styles.nearestCareHeader}>
                <IconSymbol size={18} name="local_hospital" color={theme.primary} />
                <ScaledText variant="labelSmall" style={[styles.nearestCareLabel, { color: 'rgba(255, 255, 255, 0.8)' }]}>
                  {t('nearestCare')}
                </ScaledText>
              </View>
              
              <ScaledText variant="h2" style={styles.hospitalName}>{t('hospitalName')}</ScaledText>
              <ScaledText variant="bodyMedium" style={styles.hospitalInfo}>{t('hospitalOpen')}</ScaledText>
              
              <TouchableOpacity 
                style={[styles.navigateButton, { backgroundColor: theme.primary }]}
                onPress={navigateToHospital}
              >
                <IconSymbol size={20} name="directions" color="#fff" />
                <ScaledText variant="labelLarge" style={styles.navigateButtonText}>{t('navigate')}</ScaledText>
              </TouchableOpacity>
            </View>
          </View>
        </View>

        {/* Emergency Button - matching design */}
        <TouchableOpacity
          style={[styles.emergencyButton, { backgroundColor: theme.error }]}
          onPress={callEmergency}
          activeOpacity={0.8}
        >
          <IconSymbol size={28} name="phone_in_talk" color="#fff" />
          <ScaledText variant="h4" style={styles.emergencyButtonText}>{t('emergency')}</ScaledText>
        </TouchableOpacity>
      </ScrollView>

      {/* Bottom Navigation - matching design */}
      <View style={[
        styles.bottomNav, 
        BottomNavStyle.container,
        isDarkMode ? BottomNavStyle.dark : {}
      ]}>
        <TouchableOpacity 
          style={styles.navItem}
          onPress={() => router.push('/(tabs)/map')}
        >
          <IconSymbol size={28} name="map.fill" color={theme.tabIconDefault} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.tabIconDefault }]}>{t('navMap')}</ScaledText>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={styles.navItem}
          onPress={() => router.push('/(tabs)/alerts')}
        >
          <IconSymbol size={28} name="notifications" color={theme.tabIconDefault} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.tabIconDefault }]}>{t('navAlerts')}</ScaledText>
        </TouchableOpacity>
        
        <TouchableOpacity style={styles.navItem}>
          <IconSymbol size={28} name="shield.fill" color={theme.primary} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.primary }]}>{t('navSafety')}</ScaledText>
          <View style={[styles.activeDot, { backgroundColor: theme.primary }]} />
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
  progressSection: {
    marginBottom: DesignTokens.spacing.lg,
  },
  progressLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    marginBottom: DesignTokens.spacing.sm,
    paddingHorizontal: DesignTokens.spacing.sm,
  },
  progressLabel: {
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  progressValue: {
    fontSize: 12,
    fontWeight: '700',
  },
  progressBar: {
    height: 8,
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 4,
  },
  cardsContainer: {
    gap: DesignTokens.spacing.md,
    marginBottom: DesignTokens.spacing.lg,
  },
  actionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: DesignTokens.spacing.md + 4,
    borderRadius: DesignTokens.borderRadius.xl,
  },
  cardIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: DesignTokens.spacing.md,
  },
  cardContent: {
    flex: 1,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  cardDescription: {
    fontSize: 14,
    marginTop: 2,
  },
  checkbox: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: 'rgba(0, 0, 0, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  mapCard: {
    height: 180,
    borderRadius: DesignTokens.borderRadius.xl,
    overflow: 'hidden',
    marginBottom: DesignTokens.spacing.lg,
  },
  mapOverlay: {
    flex: 1,
    padding: DesignTokens.spacing.lg,
    justifyContent: 'center',
  },
  mapContent: {
    gap: DesignTokens.spacing.sm,
  },
  nearestCareHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: DesignTokens.spacing.sm,
  },
  nearestCareLabel: {
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  hospitalName: {
    fontSize: 22,
    fontWeight: '700',
    color: '#fff',
  },
  hospitalInfo: {
    fontSize: 14,
    color: 'rgba(255, 255, 255, 0.7)',
  },
  navigateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: DesignTokens.spacing.sm,
    paddingVertical: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.xl,
    marginTop: DesignTokens.spacing.sm,
  },
  navigateButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: 1,
  },
  emergencyButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: DesignTokens.spacing.md,
    paddingVertical: DesignTokens.spacing.lg + 4,
    borderRadius: DesignTokens.borderRadius.full,
    shadowColor: '#EF4444',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.4,
    shadowRadius: 25,
    elevation: 8,
  },
  emergencyButtonText: {
    color: '#fff',
    fontSize: 20,
    fontWeight: '900',
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
