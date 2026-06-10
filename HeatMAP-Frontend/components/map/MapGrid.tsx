/**
 * MapGrid Component - OSM Map with Grid-based Heatwave Overlay
 * 
 * Uses react-native-maps for cross-platform support
 * with vector-based square grid cells representing 
 * heatwave prediction severity by latitude/longitude bounding boxes.
 * 
 * Cells are coloured from real per-province AI forecast data fetched
 * from the backend (/api/forecast/map); the grid starts neutral.
 * 
 * Grid System for Thailand:
 * - Covers full country boundaries (5.6°N to 20.5°N, 97.3°E to 105.6°E)
 * - Configurable cell size (default 0.5 degrees)
 * - Designed for future AI prediction integration
 */

import { useEffect, useState, useRef } from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';

import { RiskColors, type RiskLevel } from '@/constants/theme';

// Calm Authority: desaturated CARTO basemaps (free; OSM data) so the only
// saturated colour on screen is the risk layer itself.
const TILE_LAYERS = {
  light: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
  dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
};
const TILE_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, &copy; <a href="https://carto.com/attributions">CARTO</a>';

// ── Province choropleth (the model forecasts per PROVINCE per day — heatwaves
// are regional, not point hotspots, so polygons are the honest rendering) ──
export interface ProvinceRisk {
  level: RiskLevel;       // safe | watch | warning | extreme
  nameTh: string;
  probability: number;    // 0-100
}

const THAILAND_GEOJSON_URL =
  'https://raw.githubusercontent.com/apisit/thailand.json/master/thailand.json';
let thailandGeoPromise: Promise<any> | null = null;
function fetchThailandGeo(): Promise<any> {
  if (!thailandGeoPromise) {
    thailandGeoPromise = fetch(THAILAND_GEOJSON_URL).then((r) => r.json())
      .catch((e) => { thailandGeoPromise = null; throw e; });
  }
  return thailandGeoPromise;
}

// Normalise English province names so the GeoJSON ("Bangkok Metropolis",
// "Phangnga") joins with the DB's name_en ("Bangkok", "Phang Nga").
export function normalizeProvinceName(name: string): string {
  return name.toLowerCase().replace(/[^a-z]/g, '');
}

export function riskForFeatureName(
  geoName: string,
  byNormName: Record<string, ProvinceRisk>,
): ProvinceRisk | null {
  const n = normalizeProvinceName(geoName);
  if (byNormName[n]) return byNormName[n];
  for (const key of Object.keys(byNormName)) {
    if (n.includes(key) || key.includes(n)) return byNormName[key];
  }
  return null;
}

const RISK_LABEL_TH: Record<RiskLevel, string> = {
  safe: 'ปกติ',
  watch: 'เฝ้าระวัง',
  warning: 'เตือนภัย',
  extreme: 'อันตราย',
};

// Thailand geographic boundaries
const THAILAND_BOUNDS = {
  north: 20.5,
  south: 5.6,
  east: 105.6,
  west: 97.3,
};

// Grid configuration
const GRID_CONFIG = {
  cellSize: 0.5, // degrees - adjustable for resolution
};

// Types for grid cell data
// Four tiers matching Heat Index thresholds:
//   extreme  = HI ≥ 41°C  → RED
//   high     = HI 35–40°C → ORANGE
//   moderate = HI 28–34°C → YELLOW
//   low      = HI < 28°C  → GREEN
// Plus a non-data 'neutral' tier (GREY) used while the forecast is loading or
// failed — so "no data yet" is visually distinct from genuine low risk.
export type Severity = 'extreme' | 'high' | 'moderate' | 'low' | 'neutral';

export interface GridCell {
  id: string;
  // Latitude/Longitude bounding box
  north: number;
  south: number;
  east: number;
  west: number;
  // Center point for label
  centerLat: number;
  centerLng: number;
  // Prediction data (from AI or mock)
  severity: Severity;
  temperature: number;
  probability: number; // 0-100 confidence
  timestamp: string;
  // Grid position for reference
  gridRow: number;
  gridCol: number;
}

// Default map region - showing all of Thailand
const DEFAULT_REGION = {
  latitude: 13.5,
  longitude: 100.5,
  latitudeDelta: 16,
  longitudeDelta: 10,
};

/**
 * Generate the base Thailand grid cells.
 * Cells start neutral (low severity, no colour) and are meant to be
 * overwritten by real per-province AI forecast data from the backend.
 *
 * @param cellSize - Size of each grid cell in degrees
 * @returns Array of GridCell objects
 */
export function generateThailandGrid(
  cellSize: number = GRID_CONFIG.cellSize,
): GridCell[] {
  const cells: GridCell[] = [];
  const { north, south, east, west } = THAILAND_BOUNDS;

  const latSteps = Math.ceil((north - south) / cellSize);
  const lngSteps = Math.ceil((east - west) / cellSize);

  for (let row = 0; row < latSteps; row++) {
    for (let col = 0; col < lngSteps; col++) {
      const cellNorth = north - row * cellSize;
      const cellSouth = cellNorth - cellSize;
      const cellWest  = west  + col * cellSize;
      const cellEast  = cellWest + cellSize;

      const centerLat = (cellNorth + cellSouth) / 2;
      const centerLng = (cellWest  + cellEast)  / 2;

      const severity: Severity = 'low';
      const temperature = 28;
      const probability = 0;

      cells.push({
        id: `cell-${row}-${col}`,
        north: cellNorth,
        south: cellSouth,
        east:  cellEast,
        west:  cellWest,
        centerLat,
        centerLng,
        severity,
        temperature,
        probability,
        timestamp:  new Date().toISOString(),
        gridRow: row,
        gridCol: col,
      });
    }
  }

  return cells;
}

// Hard-stop zone colours — NO gradient/blur (no alpha except low for visibility).
// Thresholds match Rothfusz Heat Index breakpoints used in the model.
export const getSeverityColor = (severity: Severity): string => {
  switch (severity) {
    case 'extreme':  return 'rgba(239, 68, 68, 0.85)';   // RED    — HI ≥ 41°C
    case 'high':     return 'rgba(249, 115, 22, 0.80)';  // ORANGE — HI 35–40°C
    case 'moderate': return 'rgba(234, 179, 8, 0.75)';   // YELLOW — HI 28–34°C
    case 'low':      return 'rgba(34, 197, 94, 0.55)';   // GREEN  — HI < 28°C
    case 'neutral':  return 'rgba(148, 163, 184, 0.35)'; // GREY   — no data / loading
    default:         return 'transparent';
  }
};

// Get border color for severity level
export const getSeverityBorderColor = (severity: Severity): string => {
  switch (severity) {
    case 'extreme':  return 'rgba(239, 68, 68, 0.9)';
    case 'high':     return 'rgba(249, 115, 22, 0.9)';
    case 'moderate': return 'rgba(234, 179, 8, 0.9)';
    case 'low':      return 'rgba(52, 197, 89, 0.7)';
    case 'neutral':  return 'rgba(148, 163, 184, 0.55)'; // GREY — no data / loading
    default:         return 'transparent';
  }
};

// Web Leaflet Map Component
function WebLeafletMap({
  gridData,
  userLocation,
  onGetLocation,
  isDarkMode,
  neutral,
  provinceRisk,
}: {
  gridData: GridCell[];
  userLocation: { latitude: number; longitude: number } | null;
  onGetLocation: () => void;
  isDarkMode: boolean;
  neutral: boolean;
  provinceRisk?: Record<string, ProvinceRisk> | null;
}) {
  const [MapView, setMapView] = useState<any>(null);
  const [thailandGeo, setThailandGeo] = useState<any>(null);

  useEffect(() => {
    if (Platform.OS !== 'web') return;
    try {
      // Web-only dynamic require: react-leaflet/leaflet must never be bundled for native.
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const ReactLeaflet = require('react-leaflet');
      const { MapContainer, TileLayer, Polygon, Marker, GeoJSON, useMap } = ReactLeaflet;
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      setMapView({ MapContainer, TileLayer, Polygon, Marker, GeoJSON, useMap, L: require('leaflet') });
    } catch (e) {
      console.log('Leaflet not available:', e);
    }
  }, []);

  useEffect(() => {
    if (Platform.OS !== 'web') return;
    fetchThailandGeo().then(setThailandGeo).catch((e) => {
      console.warn('Thailand GeoJSON unavailable, falling back to grid:', e);
    });
  }, []);

  // Component to handle map ref and user location
  const MapController = ({ userLoc }: { userLoc: { latitude: number; longitude: number } | null }) => {
    const map = MapView?.useMap();
    
    useEffect(() => {
      if (map && userLoc) {
        map.setView([userLoc.latitude, userLoc.longitude], 13);
      }
    }, [userLoc, map]);
    
    return null;
  };

  if (!MapView) {
    return (
      <View style={styles.webFallback}>
        <Text style={styles.loadingText}>Loading map...</Text>
      </View>
    );
  }

  const { MapContainer, TileLayer, Polygon, Marker, GeoJSON } = MapView;

  // Get the appropriate tile layer URL based on theme
  const tileLayerUrl = isDarkMode ? TILE_LAYERS.dark : TILE_LAYERS.light;

  // Choropleth mode: real province polygons shaded by forecast tier. Active
  // whenever the boundaries + per-province risk are both available.
  const choropleth = !neutral && provinceRisk && Object.keys(provinceRisk).length > 0 && thailandGeo;

  // Convert grid cell to Leaflet polygon positions
  const getPolygonPositions = (cell: GridCell): [number, number][] => {
    return [
      [cell.north, cell.west],
      [cell.north, cell.east],
      [cell.south, cell.east],
      [cell.south, cell.west],
    ];
  };

  // Custom user location marker icon
  const userLocationIcon = MapView.L?.divIcon({
    className: 'user-marker',
    html: `
      <div style="
        width: 24px;
        height: 24px;
        background: #16324F;
        border: 3px solid white;
        border-radius: 50%;
        box-shadow: 0 2px 8px rgba(16,36,58,0.35);
        position: relative;
      ">
        <div style="
          position: absolute;
          width: 48px;
          height: 48px;
          background: rgba(22, 50, 79, 0.2);
          border-radius: 50%;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          animation: pulse 2s infinite;
        "></div>
      </div>
      <style>
        @keyframes pulse {
          0% { transform: translate(-50%, -50%) scale(1); opacity: 0.8; }
          100% { transform: translate(-50%, -50%) scale(2); opacity: 0; }
        }
      </style>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });

  const initialRegion = userLocation 
    ? { 
        latitude: userLocation.latitude, 
        longitude: userLocation.longitude,
        latitudeDelta: 0.15,
        longitudeDelta: 0.15,
      }
    : DEFAULT_REGION;

  return (
    <MapContainer
      center={[initialRegion.latitude, initialRegion.longitude]}
      zoom={6}
      style={{ flex: 1, width: '100%', height: '100%' }}
      zoomControl={false}
    >
      <TileLayer attribution={TILE_ATTRIBUTION} url={tileLayerUrl} />

      <MapController userLoc={userLocation} />

      {choropleth ? (
        /* Province choropleth — warm fill ONLY where risk exists */
        <GeoJSON
          key={`choro-${Object.keys(provinceRisk!).length}`}
          data={thailandGeo}
          style={(feature: any) => {
            const z = riskForFeatureName(feature?.properties?.name ?? '', provinceRisk!);
            if (z && z.level !== 'safe') {
              return {
                color: '#FFFFFF', weight: 1,
                fillColor: RiskColors[z.level], fillOpacity: 0.34,
              };
            }
            return { color: '#B3C4D2', weight: 0.6, fillColor: '#7E93A6', fillOpacity: 0.05 };
          }}
          onEachFeature={(feature: any, layer: any) => {
            const z = riskForFeatureName(feature?.properties?.name ?? '', provinceRisk!);
            layer.bindPopup(z
              ? `<b>${z.nameTh}</b><br>ระดับ${RISK_LABEL_TH[z.level]} · โอกาสเกิด ${Math.round(z.probability)}%`
              : `<b>${feature?.properties?.name ?? ''}</b><br>ความเสี่ยงต่ำ`);
          }}
        />
      ) : (
        /* Grid fallback — grey ('neutral') while data isn't ready */
        gridData.map((cell) => {
          const sev: Severity = neutral ? 'neutral' : cell.severity;
          return (
            <Polygon
              key={cell.id}
              positions={getPolygonPositions(cell)}
              pathOptions={{
                fillColor: getSeverityColor(sev),
                fillOpacity: 0.35,
                color: getSeverityBorderColor(sev),
                weight: 1,
              }}
            />
          );
        })
      )}
      
      {/* User location marker - ANCHORED TO MAP, not screen */}
      {userLocation && (
        <Marker 
          position={[userLocation.latitude, userLocation.longitude]}
          icon={userLocationIcon}
        />
      )}
    </MapContainer>
  );
}

// Native Map Component using react-native-maps
function NativeMapView({
  gridData,
  userLocation,
  onGetLocation,
  isDarkMode,
  neutral,
}: {
  gridData: GridCell[];
  userLocation: { latitude: number; longitude: number } | null;
  onGetLocation: () => void;
  isDarkMode: boolean;
  neutral: boolean;
}) {
  const [mapModule, setMapModule] = useState<any>(null);

  useEffect(() => {
    try {
      // Native-only dynamic require: react-native-maps is unavailable on web.
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      setMapModule(require('react-native-maps'));
    } catch (e) {
      console.log('react-native-maps not available:', e);
    }
  }, []);

  const mapRef = useRef<any>(null);

  if (!mapModule) {
    return (
      <View style={styles.nativeFallback}>
        <Text style={styles.loadingText}>Map not available</Text>
      </View>
    );
  }

  const { default: MapView, Marker, Polygon } = mapModule;

  const initialRegion = userLocation 
    ? { 
        latitude: userLocation.latitude, 
        longitude: userLocation.longitude,
        latitudeDelta: 0.15,
        longitudeDelta: 0.15,
      }
    : DEFAULT_REGION;

  return (
    <MapView
      ref={mapRef}
      style={styles.nativeMap}
      initialRegion={initialRegion}
      showsUserLocation={false}
      showsMyLocationButton={false}
      showsCompass={false}
    >
      {/* Grid overlay polygons — grey ('neutral') while data isn't ready */}
      {gridData.map((cell) => {
        const sev: Severity = neutral ? 'neutral' : cell.severity;
        return (
          <Polygon
            key={cell.id}
            coordinates={[
              { latitude: cell.north, longitude: cell.west },
              { latitude: cell.north, longitude: cell.east },
              { latitude: cell.south, longitude: cell.east },
              { latitude: cell.south, longitude: cell.west },
            ]}
            fillColor={getSeverityColor(sev)}
            strokeColor={getSeverityBorderColor(sev)}
            strokeWidth={2}
          />
        );
      })}

      {/* User location marker - ANCHORED TO MAP COORDINATES */}
      {userLocation && (
        <Marker
          coordinate={{
            latitude: userLocation.latitude,
            longitude: userLocation.longitude,
          }}
          anchor={{ x: 0.5, y: 0.5 }}
          centerOffset={{ x: 0, y: 0 }}
        >
          <View style={styles.nativeMarkerContainer}>
            <View style={styles.nativeMarkerPulse} />
            <View style={styles.nativeMarkerDot} />
          </View>
        </Marker>
      )}
    </MapView>
  );
}

// Main component
export function MapGrid({
  gridData = generateThailandGrid(),
  userLocation = null,
  onUserLocationRequest,
  style,
  isDarkMode = false,
  neutral = false,
  provinceRisk = null,
}: {
  gridData?: GridCell[];
  userLocation?: { latitude: number; longitude: number } | null;
  onUserLocationRequest?: () => void;
  style?: any;
  isDarkMode?: boolean;
  // When true, every cell renders GREY instead of its real severity colour —
  // used while the forecast is loading / failed so "no data" ≠ "low risk".
  neutral?: boolean;
  // Per-province risk keyed by NORMALISED English name (normalizeProvinceName).
  // When provided (web), renders the honest province choropleth instead of the grid.
  provinceRisk?: Record<string, ProvinceRisk> | null;
}) {
  const [isWeb, setIsWeb] = useState(false);
  
  useEffect(() => {
    setIsWeb(Platform.OS === 'web');
  }, []);

  const handleGetLocation = onUserLocationRequest || (() => {});

  return (
    <View style={[styles.container, style]}>
      {isWeb ? (
        <WebLeafletMap
          gridData={gridData}
          userLocation={userLocation}
          onGetLocation={handleGetLocation}
          isDarkMode={isDarkMode}
          neutral={neutral}
          provinceRisk={provinceRisk}
        />
      ) : (
        <NativeMapView
          gridData={gridData}
          userLocation={userLocation}
          onGetLocation={handleGetLocation}
          isDarkMode={isDarkMode}
          neutral={neutral}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    position: 'relative',
  },
  webFallback: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f0f0f0',
  },
  nativeFallback: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#e0e0e0',
  },
  loadingText: {
    fontSize: 16,
    color: '#666',
  },
  nativeMap: {
    flex: 1,
  },
  nativeMarkerContainer: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  nativeMarkerPulse: {
    position: 'absolute',
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(59, 130, 246, 0.3)',
  },
  nativeMarkerDot: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#3b82f6',
    borderWidth: 3,
    borderColor: '#fff',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
    elevation: 4,
  },
});
