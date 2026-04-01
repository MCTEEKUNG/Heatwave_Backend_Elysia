import { useState, useEffect, useCallback } from 'react';
import { View, StyleSheet, TouchableOpacity, ScrollView, Linking, Platform, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { Colors, DesignTokens, GlassStyle, BottomNavStyle } from '@/constants/theme';
import { useSettings } from '@/hooks/useSettings';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { ScaledText } from '@/components/ui/ScaledText';
import useLocation from '@/hooks/useLocation';
import { getNearestCoolingPlaces, estimateTravelTime, type Place } from '@/services/nearbyPlaces';

// Checklist items - will use translations
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

export default function ChecklistScreen() {
  const { isDarkMode, t } = useSettings();
  const theme = Colors[isDarkMode ? 'dark' : 'light'];
  const [checklist, setChecklist] = useState(getChecklistItems(t));
  
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

  const completedCount = checklist.filter(item => item.completed).length;
  const totalCount = checklist.length;
  const progressPercent = (completedCount / totalCount) * 100;

  // Fetch nearby places when location changes
  const fetchNearbyPlaces = useCallback(async () => {
    if (!userLocation) return;
    
    setIsLoadingPlaces(true);
    setPlacesError(null);
    
    try {
      const places = await getNearestCoolingPlaces(
        userLocation.latitude,
        userLocation.longitude
      );
      setNearbyPlaces(places);
    } catch (error) {
      setPlacesError('Could not find nearby places');
    } finally {
      setIsLoadingPlaces(false);
    }
  }, [userLocation]);

  // Initial location fetch
  useEffect(() => {
    if (locationStatus === 'idle') {
      getCurrentLocation();
    }
  }, [locationStatus]);

  // Fetch places when location is available
  useEffect(() => {
    if (userLocation) {
      fetchNearbyPlaces();
    }
  }, [userLocation, fetchNearbyPlaces]);

  const handleToggleItem = (itemId: string) => {
    setChecklist(prev =>
      prev.map(item =>
        item.id === itemId ? { ...item, completed: !item.completed } : item
      )
    );
  };

  const handleRefreshLocation = async () => {
    if (locationStatus !== 'granted') {
      await requestPermission();
    }
    await getCurrentLocation();
  };

  const callEmergency = () => {
    Linking.openURL('tel:911');
  };

  const navigateToPlace = (place: Place) => {
    const { latitude, longitude, name } = place;
    const address = encodeURIComponent(name);
    const url = Platform.OS === 'ios' 
      ? `http://maps.apple.com/?daddr=${latitude},${longitude}`
      : `https://www.google.com/maps/dir/?api=1&destination=${latitude},${longitude}`;
    Linking.openURL(url);
  };

  const handleFindCoolingLocation = async () => {
    if (locationStatus !== 'granted') {
      const hasPermission = await requestPermission();
      if (!hasPermission) return;
    }
    
    if (!userLocation) {
      await getCurrentLocation();
    }
    
    // Refresh nearby places
    await fetchNearbyPlaces();
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]} edges={['top']}>
      {/* Header */}
      <View style={[
        styles.header, 
        { 
          backgroundColor: isDarkMode ? 'rgba(26, 21, 18, 0.85)' : 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(12px)'
        }
      ]}>
        <TouchableOpacity 
          style={styles.backButton}
          onPress={() => router.back()}
        >
          <IconSymbol size={20} name="arrow_back_ios_new" color={theme.icon} />
        </TouchableOpacity>
        <ScaledText variant="h3" style={[styles.headerTitle, { color: theme.text }]}>Safety Checklist</ScaledText>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Progress Section */}
        <View style={styles.progressSection}>
          <View style={styles.progressLabels}>
            <ScaledText variant="labelSmall" style={[styles.progressLabel, { color: theme.textSecondary }]}>Current Progress</ScaledText>
            <ScaledText variant="labelMedium" style={[styles.progressValue, { color: theme.primary }]}>
              {completedCount} of {totalCount} completed
            </ScaledText>
          </View>
          <View style={[styles.progressBar, { backgroundColor: isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0, 0, 0, 0.1)' }]}>
            <View 
              style={[
                styles.progressFill, 
                { 
                  width: `${progressPercent}%`,
                  backgroundColor: theme.primary 
                }
              ]} 
            />
          </View>
        </View>

        {/* Checklist Items */}
        <View style={styles.checklistSection}>
          {checklist.map((item) => (
            <TouchableOpacity
              key={item.id}
              style={[styles.checklistItem, GlassStyle[isDarkMode ? 'dark' : 'light']]}
              onPress={() => handleToggleItem(item.id)}
            >
              <View style={styles.checklistLeft}>
                <View style={[
                  styles.checkbox,
                  item.completed && { backgroundColor: theme.primary, borderColor: theme.primary }
                ]}>
                  {item.completed && (
                    <IconSymbol size={16} name="check" color="#fff" />
                  )}
                </View>
                <View style={styles.checklistContent}>
                  <ScaledText variant="labelLarge" style={[styles.checklistTitle, { color: theme.text }]}>{item.title}</ScaledText>
                  <ScaledText variant="bodySmall" style={[styles.checklistDesc, { color: theme.textSecondary }]}>
                    {item.description}
                  </ScaledText>
                </View>
              </View>
              <IconSymbol 
                size={20} 
                name={item.icon} 
                color={item.completed ? theme.primary : theme.textSecondary} 
              />
            </TouchableOpacity>
          ))}
        </View>

        {/* Nearest Rest Care Section - DYNAMIC */}
        <View style={styles.nearestCareSection}>
          <View style={styles.sectionHeader}>
            <IconSymbol size={18} name="place" color={theme.primary} />
            <ScaledText variant="labelSmall" style={[styles.sectionTitle, { color: theme.textSecondary }]}>
              NEAREST COOLING LOCATION
            </ScaledText>
            <TouchableOpacity 
              onPress={handleRefreshLocation}
              style={[styles.refreshButton, { backgroundColor: theme.primary + '20' }]}
            >
              <IconSymbol size={14} name="refresh" color={theme.primary} />
            </TouchableOpacity>
          </View>

          {isLoadingPlaces ? (
            <View style={[styles.loadingContainer, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
              <ActivityIndicator size="small" color={theme.primary} />
              <ScaledText variant="bodySmall" style={[styles.loadingText, { color: theme.textSecondary }]}>
                Finding nearest cooling locations...
              </ScaledText>
            </View>
          ) : placesError ? (
            <View style={[styles.errorContainer, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
              <IconSymbol size={24} name="error_outline" color={theme.error} />
              <ScaledText variant="labelMedium" style={[styles.errorText, { color: theme.error }]}>{placesError}</ScaledText>
              <TouchableOpacity 
                style={[styles.retryButton, { backgroundColor: theme.primary }]}
                onPress={handleFindCoolingLocation}
              >
                <ScaledText variant="labelMedium" style={styles.retryText}>Retry</ScaledText>
              </TouchableOpacity>
            </View>
          ) : nearbyPlaces.length > 0 ? (
            <View style={styles.placesList}>
              {nearbyPlaces.map((place, index) => {
                const isHighReliability = place.type === 'shopping_mall' || place.type === 'hospital';
                return (
                  <View 
                    key={place.id}
                    style={[styles.nearestCareCard, GlassStyle[isDarkMode ? 'dark' : 'light']]}
                  >
                    <View style={styles.nearestCareHeader}>
                      <View style={[styles.placeIconContainer, { backgroundColor: theme.primary }]}>
                        <IconSymbol 
                          size={24} 
                          name={getPlaceIcon(place.type)} 
                          color="#fff" 
                        />
                      </View>
                      <View style={styles.nearestCareInfo}>
                        <ScaledText variant="labelLarge" style={[styles.nearestCareName, { color: theme.text }]}>
                          {index + 1}. {place.name}
                        </ScaledText>
                        <ScaledText variant="bodySmall" style={[styles.nearestCareDetails, { color: theme.textSecondary }]}>
                          {place.isOpen24Hours ? 'Open 24/7' : place.openingHours}
                        </ScaledText>
                        
                        {/* High Reliability Badge */}
                        {isHighReliability && (
                          <View style={[styles.reliabilityBadge, { backgroundColor: theme.primary + '15' }]}>
                            <IconSymbol size={12} name="ac_unit" color={theme.primary} />
                            <ScaledText variant="caption" style={[styles.reliabilityText, { color: theme.primary }]}>
                              High Cooling Reliability
                            </ScaledText>
                          </View>
                        )}
                      </View>
                    </View>
                    <View style={styles.nearestCareFooter}>
                      <View style={styles.distanceContainer}>
                        <IconSymbol size={16} name="directions_walk" color={theme.textSecondary} />
                        <ScaledText variant="labelSmall" style={[styles.distanceText, { color: theme.text }]}>
                          {estimateTravelTime(place.distance)}
                        </ScaledText>
                        <ScaledText variant="labelSmall" style={[styles.distanceKm, { color: theme.textSecondary }]}>
                          ({(place.distance).toFixed(1)} km)
                        </ScaledText>
                      </View>
                      <TouchableOpacity 
                        style={[styles.navigateButton, { backgroundColor: theme.primary }]}
                        onPress={() => navigateToPlace(place)}
                      >
                        <IconSymbol size={16} name="navigation" color="#fff" />
                        <ScaledText variant="labelMedium" style={styles.navigateText}>Navigate</ScaledText>
                      </TouchableOpacity>
                    </View>
                  </View>
                );
              })}
            </View>
          ) : (
            <View style={[styles.noLocationContainer, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
              <IconSymbol size={32} name="location_off" color={theme.textSecondary} />
              <ScaledText variant="bodySmall" style={[styles.noLocationText, { color: theme.textSecondary }]}>
                {locationStatus === 'denied' 
                  ? 'Location access denied. Enable in Settings to find nearby cooling locations.'
                  : 'Enable location to find nearby cooling locations.'}
              </ScaledText>
              {locationStatus !== 'granted' && (
                <TouchableOpacity 
                  style={[styles.enableButton, { backgroundColor: theme.primary }]}
                  onPress={handleFindCoolingLocation}
                >
                  <ScaledText variant="labelMedium" style={styles.enableButtonText}>Enable Location</ScaledText>
                </TouchableOpacity>
              )}
            </View>
          )}
        </View>

        {/* Safety Tips */}
        <View style={styles.tipsSection}>
          <ScaledText variant="labelMedium" style={[styles.tipsTitle, { color: theme.text }]}>Heat Safety Tips</ScaledText>
          <View style={[styles.tipCard, { backgroundColor: theme.warning + '15' }]}>
            <IconSymbol size={20} name="lightbulb" color={theme.warning} />
            <ScaledText variant="bodySmall" style={[styles.tipText, { color: theme.text }]}>
              Stay hydrated and avoid outdoor activities during peak heat hours (12 PM - 4 PM).
            </ScaledText>
          </View>
        </View>

        {/* Emergency Button - Bottom of page (last escalation action) */}
        <TouchableOpacity 
          style={[styles.emergencyButton, { backgroundColor: theme.extreme }]}
          onPress={callEmergency}
        >
          <IconSymbol size={24} name="phone" color="#fff" />
          <ScaledText variant="labelLarge" style={styles.emergencyText}>CALL EMERGENCY (911)</ScaledText>
        </TouchableOpacity>
      </ScrollView>

      {/* Bottom Navigation */}
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
        
        <TouchableOpacity 
          style={styles.navItem}
          onPress={() => router.push('/(tabs)')}
        >
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
  backButton: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    letterSpacing: -0.5,
  },
  headerSpacer: {
    width: 40,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: DesignTokens.spacing.md,
    paddingBottom: 120,
  },
  progressSection: {
    marginBottom: DesignTokens.spacing.lg,
  },
  progressLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: DesignTokens.spacing.sm,
  },
  progressLabel: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  progressValue: {
    fontSize: 14,
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
  emergencyButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: DesignTokens.spacing.sm,
    padding: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.lg,
    marginBottom: DesignTokens.spacing.lg,
  },
  emergencyText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
  checklistSection: {
    gap: DesignTokens.spacing.md,
    marginBottom: DesignTokens.spacing.lg,
  },
  checklistItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.xl,
  },
  checklistLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: '#ccc',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: DesignTokens.spacing.md,
  },
  checklistContent: {
    flex: 1,
  },
  checklistTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  checklistDesc: {
    fontSize: 13,
    marginTop: 2,
  },
  nearestCareSection: {
    marginBottom: DesignTokens.spacing.lg,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: DesignTokens.spacing.sm,
    marginBottom: DesignTokens.spacing.md,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
    flex: 1,
  },
  refreshButton: {
    width: 28,
    height: 28,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: DesignTokens.spacing.md,
    padding: DesignTokens.spacing.lg,
    borderRadius: DesignTokens.borderRadius.xl,
  },
  loadingText: {
    fontSize: 14,
  },
  errorContainer: {
    alignItems: 'center',
    padding: DesignTokens.spacing.lg,
    borderRadius: DesignTokens.borderRadius.xl,
    gap: DesignTokens.spacing.md,
  },
  errorText: {
    fontSize: 14,
    textAlign: 'center',
  },
  retryButton: {
    paddingVertical: DesignTokens.spacing.sm,
    paddingHorizontal: DesignTokens.spacing.lg,
    borderRadius: DesignTokens.borderRadius.full,
  },
  retryText: {
    color: '#fff',
    fontWeight: '600',
  },
  placesList: {
    gap: DesignTokens.spacing.md,
  },
  nearestCareCard: {
    padding: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.xl,
    flexDirection: 'column',
  },
  nearestCareHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: DesignTokens.spacing.md,
    marginBottom: DesignTokens.spacing.md,
  },
  placeIconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  nearestCareInfo: {
    flex: 1,
  },
  nearestCareName: {
    fontSize: 16,
    fontWeight: '700',
  },
  nearestCareDetails: {
    fontSize: 13,
    marginTop: 2,
    marginBottom: 6,
  },
  reliabilityBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: DesignTokens.borderRadius.sm,
    gap: 4,
  },
  reliabilityText: {
    fontWeight: '600',
    fontSize: 11,
  },
  nearestCareFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderTopWidth: 1,
    borderTopColor: 'rgba(150, 150, 150, 0.2)',
    paddingTop: DesignTokens.spacing.md,
  },
  distanceContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  distanceText: {
    fontSize: 14,
    fontWeight: '600',
  },
  distanceKm: {
    fontSize: 12,
  },
  navigateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: DesignTokens.borderRadius.full,
  },
  navigateText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 14,
  },
  noLocationContainer: {
    alignItems: 'center',
    padding: DesignTokens.spacing.lg,
    borderRadius: DesignTokens.borderRadius.xl,
    gap: DesignTokens.spacing.md,
  },
  noLocationText: {
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
  },
  enableButton: {
    paddingVertical: DesignTokens.spacing.sm,
    paddingHorizontal: DesignTokens.spacing.lg,
    borderRadius: DesignTokens.borderRadius.full,
  },
  enableButtonText: {
    color: '#fff',
    fontWeight: '600',
  },
  tipsSection: {
    marginBottom: DesignTokens.spacing.lg,
  },
  tipsTitle: {
    fontSize: 16,
    fontWeight: '700',
    marginBottom: DesignTokens.spacing.md,
  },
  tipCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: DesignTokens.spacing.md,
    padding: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.xl,
  },
  tipText: {
    flex: 1,
    fontSize: 14,
    lineHeight: 20,
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
