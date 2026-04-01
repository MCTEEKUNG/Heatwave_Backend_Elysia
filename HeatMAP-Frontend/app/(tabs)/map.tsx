import { useState, useEffect, useCallback, useMemo } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Platform, ActivityIndicator } from 'react-native';
import { router } from 'expo-router';
import { Colors, DesignTokens, GlassStyle, BottomNavStyle, useResponsive } from '@/constants/theme';
import { useSettings } from '@/hooks/useSettings';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { MapGrid, MOCK_GRID_DATA, generateThailandGrid, type GridCell } from '@/components/map';
import useLocation from '@/hooks/useLocation';
import { ScaledText } from '@/components/ui/ScaledText';

const API_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:3000';

// Helper function to find grid cell containing user's location
const findUserGridCell = (
  latitude: number,
  longitude: number,
  gridData: GridCell[]
): GridCell | null => {
  for (const cell of gridData) {
    if (
      latitude >= cell.south &&
      latitude <= cell.north &&
      longitude >= cell.west &&
      longitude <= cell.east
    ) {
      return cell;
    }
  }
  return null;
};

// Hourly forecast data
const getHourlyForecast = (t: (key: any) => string) => [
  { time: t('now'), icon: 'sunny', temp: 42 },
  { time: '+2h', icon: 'sunny', temp: 40 },
  { time: '+4h', icon: 'cloud', temp: 38 },
  { time: '+6h', icon: 'partly_cloudy_day', temp: 35 },
  { time: '+8h', icon: 'bedtime', temp: 32 },
];

export default function MapScreen() {
  const { isDarkMode, t } = useSettings();
  const theme = Colors[isDarkMode ? 'dark' : 'light'];
  const [gridData, setGridData] = useState<GridCell[]>(MOCK_GRID_DATA);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const { isDesktop, isTablet, width } = useResponsive();
  const HOURLY_FORECAST = getHourlyForecast(t);

  // Fetch real prediction data from Backend
  useEffect(() => {
    const fetchPredictions = async () => {
      try {
        setIsLoadingData(true);
        // Generate base grid cells for Thailand
        const baseGrid = generateThailandGrid();

        // Build CSV input from grid center points
        const header = 't2m,d2m,sp,u10,v10,ndvi,ndvi_lag1,ndvi_lag2';
        const rows = baseGrid.map(cell => {
          const lat = (cell.north + cell.south) / 2;
          // Approximate feature values based on latitude (Thailand)
          const t2m = 308 - (lat - 5) * 0.5;  // ~35°C in Kelvin
          const d2m = 295;
          const sp = 101325;
          const u10 = 2.0;
          const v10 = 1.5;
          const ndvi = 0.35;
          return `${t2m},${d2m},${sp},${u10},${v10},${ndvi},${ndvi},${ndvi}`;
        });
        const inputData = [header, ...rows].join('\n');

        const response = await fetch(`${API_URL}/api/predict`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: 'balanced_rf',
            inputData,
            includeProba: true
          })
        });

        if (!response.ok) throw new Error('API error');
        const result = await response.json();

        if (result.success && result.predictions?.length > 0) {
          const updatedGrid = baseGrid.map((cell, i) => {
            const pred = result.predictions[i];
            const prob = pred ? parseFloat(pred.heatwave_probability ?? '0') : 0;
            const isHeatwave = pred ? pred.predicted_heatwave === '1' : false;
            const severity = prob >= 0.8 ? 'extreme' : prob >= 0.5 ? 'medium' : 'low';
            const temperature = Math.round(30 + prob * 12); // estimate °C from probability
            return { ...cell, severity, temperature, probability: prob } as GridCell;
          });
          setGridData(updatedGrid);
        }
      } catch (error) {
        console.warn('[MapScreen] Failed to fetch predictions, using mock data:', error);
        // Fallback to mock data on error
        setGridData(MOCK_GRID_DATA);
      } finally {
        setIsLoadingData(false);
      }
    };

    fetchPredictions();
  }, []);
  
  // Location hook
  const { 
    location: userLocation, 
    status: locationStatus,
    getCurrentLocation,
    requestPermission,
    isLoading: isLocationLoading,
  } = useLocation();

  // Calculate user's current grid cell based on location
  const userGridCell = useMemo(() => {
    if (!userLocation) return null;
    return findUserGridCell(userLocation.latitude, userLocation.longitude, gridData);
  }, [userLocation, gridData]);

  // Get current severity level (null if low/no risk)
  const currentSeverity = userGridCell?.severity || null;

  // Check if any extreme severity exists
  const hasExtreme = gridData.some(cell => cell.severity === 'extreme');
  
  // Calculate responsive values
  const cardWidth = isDesktop ? 200 : isTablet ? 180 : 160;
  const fabRight = isDesktop ? 32 : 24;
  const timelineBottom = isDesktop ? 140 : 120;

  // Handle location button press
  const handleGetLocation = useCallback(async () => {
    if (locationStatus === 'granted') {
      await getCurrentLocation();
    } else {
      const hasPermission = await requestPermission();
      if (hasPermission) {
        await getCurrentLocation();
      }
    }
  }, [locationStatus, requestPermission, getCurrentLocation]);

  // Auto-get location on first load (optional)
  useEffect(() => {
    // Auto-request location on mount
    if (locationStatus === 'idle') {
      getCurrentLocation();
    }
  }, []);

  // Get location coordinates for MapGrid
  const locationCoords = userLocation 
    ? { latitude: userLocation.latitude, longitude: userLocation.longitude }
    : null;

  return (
    <View style={[styles.container, { backgroundColor: theme.background }]}>
      {/* Dynamic Warning Banner based on user's current grid cell */}
      {currentSeverity === 'extreme' && (
        <View style={[styles.warningBanner, { backgroundColor: theme.extreme }]}>
          <IconSymbol size={20} name="warning" color="#fff" />
          <ScaledText variant="labelLarge" style={styles.warningText}>{t('dangerZoneDetected')}</ScaledText>
        </View>
      )}

      {currentSeverity === 'medium' && (
        <View style={[styles.warningBanner, { backgroundColor: theme.medium }]}>
          <IconSymbol size={20} name="warning" color="#fff" />
          <ScaledText variant="labelLarge" style={styles.warningText}>{t('mediumRiskArea')}</ScaledText>
        </View>
      )}

      {/* Map Area with OSM and Grid Overlay */}
      <View style={styles.mapArea}>
        <MapGrid 
          gridData={gridData}
          userLocation={locationCoords}
          onUserLocationRequest={handleGetLocation}
          isDarkMode={isDarkMode}
          style={styles.mapGrid}
        />

        {/* Floating Temperature Card */}
        <View style={[
          styles.tempCard, 
          GlassStyle[isDarkMode ? 'dark' : 'light'],
          { width: cardWidth }
        ]}>
          <ScaledText variant="labelSmall" style={{ color: theme.primary, textTransform: 'uppercase', letterSpacing: 1 }}>{t('currentlyTemp')}</ScaledText>
          <ScaledText variant="displaySmall" style={{ color: theme.text, fontWeight: '700' }}>
            {userGridCell ? `${userGridCell.temperature}°C` : '--°C'}
          </ScaledText>
          <View style={styles.tempStatus}>
            <View style={[
              styles.tempIndicator, 
              { backgroundColor: currentSeverity === 'extreme' ? theme.extreme : currentSeverity === 'medium' ? theme.medium : theme.low }
            ]} />
            <ScaledText variant="labelSmall" style={{ 
              color: currentSeverity === 'extreme' ? theme.extreme : currentSeverity === 'medium' ? theme.medium : theme.low, 
              textTransform: 'uppercase' 
            }}>
              {currentSeverity === 'extreme' ? t('extremeHeat') : currentSeverity === 'medium' ? t('heatRiskLevelMedium').split(': ')[1] || 'Medium' : t('lowRisk')}
            </ScaledText>
          </View>
        </View>

        {/* Floating Action Buttons */}
        <View style={[styles.fabContainer, { right: fabRight }]}>
          {/* Location Button */}
          <TouchableOpacity 
            style={[
              styles.fab, 
              GlassStyle[isDarkMode ? 'dark' : 'light'],
              locationStatus === 'granted' && styles.fabActive
            ]}
            onPress={handleGetLocation}
            disabled={isLocationLoading}
          >
            {isLocationLoading ? (
              <ActivityIndicator size="small" color={theme.primary} />
            ) : (
              <IconSymbol 
                size={24} 
                name="my_location" 
                color={locationStatus === 'granted' ? theme.primary : theme.textSecondary} 
              />
            )}
          </TouchableOpacity>
          
          {/* Zoom Controls */}
          <View style={[styles.zoomControls, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
            <TouchableOpacity style={styles.zoomButton}>
              <IconSymbol size={24} name="add" color={theme.textSecondary} />
            </TouchableOpacity>
            <View style={[styles.zoomDivider, { backgroundColor: isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)' }]} />
            <TouchableOpacity style={styles.zoomButton}>
              <IconSymbol size={24} name="remove" color={theme.textSecondary} />
            </TouchableOpacity>
          </View>
        </View>

        {/* Location Status Indicator */}
        {locationStatus === 'granted' && (
          <View style={[styles.locationStatus, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
            <View style={styles.locationStatusDot} />
            <ScaledText variant="labelMedium" style={[styles.locationStatusText, { color: theme.textSecondary }]}>
              {userLocation ? t('locationActive') : t('gettingLocation')}
            </ScaledText>
          </View>
        )}
      </View>

      {/* Bottom Timeline */}
      <View style={[
        styles.timelineContainer, 
        GlassStyle[isDarkMode ? 'dark' : 'light'],
        { bottom: timelineBottom }
      ]}>
        <View style={styles.timelineContent}>
          {HOURLY_FORECAST.map((item, index) => (
            <View 
              key={index} 
              style={[
                styles.timelineItem,
                index === 0 && styles.timelineItemActive
              ]}
            >
              <ScaledText variant="labelSmall" style={[
                styles.timelineTime,
                { color: index === 0 ? theme.primary : theme.textSecondary }
              ]}>
                {item.time}
              </ScaledText>
              <IconSymbol 
                size={22} 
                name={item.icon} 
                color={index === 0 ? theme.text : theme.textSecondary} 
              />
              <ScaledText variant="labelMedium" style={[
                styles.timelineTemp,
                { color: theme.text },
                index === 0 && styles.timelineTempActive
              ]}>
                {item.temp}°C
              </ScaledText>
            </View>
          ))}
        </View>
      </View>

      {/* Bottom Navigation */}
      <View style={[
        styles.bottomNav, 
        BottomNavStyle.container,
        isDarkMode ? BottomNavStyle.dark : {}
      ]}>
        <TouchableOpacity style={styles.navItem}>
          <IconSymbol size={28} name="map.fill" color={theme.primary} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.primary }]}>{t('navMap')}</ScaledText>
          <View style={[styles.activeDot, { backgroundColor: theme.primary }]} />
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
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  warningBanner: {
    position: 'absolute',
    top: 60,
    left: 24,
    right: 24,
    zIndex: 40,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: DesignTokens.spacing.sm,
    paddingVertical: DesignTokens.spacing.sm,
    paddingHorizontal: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.full,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 4,
  },
  warningText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  warningSubText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '500',
    opacity: 0.9,
  },
  mapArea: {
    flex: 1,
    position: 'relative',
  },
  mapGrid: {
    flex: 1,
  },
  tempCard: {
    position: 'absolute',
    left: 24,
    top: 140,
    padding: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.xl,
    zIndex: 10,
  },
  tempLabel: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 4,
  },
  tempValue: {
    fontSize: 38,
    fontWeight: '700',
  },
  tempStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 6,
  },
  tempIndicator: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  tempStatusText: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  fabContainer: {
    position: 'absolute',
    top: 140,
    zIndex: 10,
    gap: DesignTokens.spacing.sm,
  },
  fab: {
    width: 48,
    height: 48,
    borderRadius: DesignTokens.borderRadius.xl,
    justifyContent: 'center',
    alignItems: 'center',
  },
  fabActive: {
    borderWidth: 2,
    borderColor: '#3b82f6',
  },
  zoomControls: {
    borderRadius: DesignTokens.borderRadius.xl,
    overflow: 'hidden',
  },
  zoomButton: {
    width: 48,
    height: 48,
    justifyContent: 'center',
    alignItems: 'center',
  },
  zoomDivider: {
    height: 1,
  },
  locationStatus: {
    position: 'absolute',
    bottom: 16,
    left: 24,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: DesignTokens.borderRadius.full,
    zIndex: 10,
  },
  locationStatusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#3b82f6',
  },
  locationStatusText: {
    fontSize: 12,
    fontWeight: '500',
  },
  timelineContainer: {
    position: 'absolute',
    left: 24,
    right: 24,
    borderRadius: DesignTokens.borderRadius.xl,
    zIndex: 10,
  },
  timelineContent: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingVertical: DesignTokens.spacing.md + 4,
    paddingHorizontal: DesignTokens.spacing.md,
  },
  timelineItem: {
    alignItems: 'center',
    gap: 6,
    opacity: 0.6,
    minWidth: 50,
  },
  timelineItemActive: {
    opacity: 1,
  },
  timelineTime: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  timelineTemp: {
    fontSize: 14,
    fontWeight: '500',
  },
  timelineTempActive: {
    fontWeight: '700',
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
    paddingVertical: 8,
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
    bottom: -4,
    width: 4,
    height: 4,
    borderRadius: 2,
  },
});
