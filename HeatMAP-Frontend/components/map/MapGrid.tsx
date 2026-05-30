/**
 * MapGrid Component - OSM Map with Grid-based Heatwave Overlay
 * 
 * Uses react-native-maps for cross-platform support
 * with vector-based square grid cells representing 
 * heatwave prediction severity by latitude/longitude bounding boxes.
 * 
 * Mock data simulates AI prediction results.
 * 
 * Grid System for Thailand:
 * - Covers full country boundaries (5.6°N to 20.5°N, 97.3°E to 105.6°E)
 * - Configurable cell size (default 0.5 degrees)
 * - Designed for future AI prediction integration
 */

import { useEffect, useState, useRef } from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';

// Dark/Light tile layer URLs for OpenStreetMap
const TILE_LAYERS = {
  light: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
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
export type Severity = 'extreme' | 'high' | 'moderate' | 'low';

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

// Seeded random for consistent mock data
function seededRandom(seed: number): number {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

// Generate severity based on location (simulating AI predictions)
// Northern regions tend to be hotter in summer
function generateMockSeverity(lat: number, lng: number, seed: number): Severity {
  const rand = seededRandom(seed);
  
  // Simulate regional heat patterns
  // Central plains (around Bangkok) tend to be hotter
  const isCentral = lat > 12 && lat < 16 && lng > 98 && lng < 102;
  // Northern region
  const isNorth = lat > 17;
  // Southern peninsula
  const isSouth = lat < 10;
  
  let extremeChance = 0.1; // Base chance
  if (isCentral) extremeChance = 0.3;
  if (isNorth) extremeChance = 0.25;
  if (isSouth) extremeChance = 0.15;
  
  const mediumChance = extremeChance + 0.35;
  
  if (rand < extremeChance) return 'extreme';
  if (rand < mediumChance) return 'medium';
  return 'low';
}

// Generate mock temperature based on severity and location
function generateMockTemperature(severity: Severity, lat: number, seed: number): number {
  const baseTemp = 32; // Base temperature
  const rand = seededRandom(seed * 2) * 5;
  
  switch (severity) {
    case 'extreme':
      return 40 + Math.floor(rand); // 40-45°C
    case 'medium':
      return 36 + Math.floor(rand); // 36-41°C
    case 'low':
      return 30 + Math.floor(rand + 2); // 32-37°C
  }
}

// Generate mock probability based on severity
function generateMockProbability(severity: Severity, seed: number): number {
  const base = seededRandom(seed * 3) * 20;
  switch (severity) {
    case 'extreme':
      return 85 + Math.floor(base); // 85-100%
    case 'medium':
      return 70 + Math.floor(base); // 70-90%
    case 'low':
      return 60 + Math.floor(base); // 60-80%
  }
}

/**
 * Generate grid cells covering Thailand
 * This function can be replaced with API call for real AI data
 * 
 * @param cellSize - Size of each grid cell in degrees
 * @returns Array of GridCell objects
 */
/**
 * Generate the base Thailand grid cells.
 * When `mockData` is false (default) cells are neutral (low severity, no colour)
 * and are meant to be overwritten by real AI forecast data from the backend.
 * Pass `mockData = true` only for Storybook / development previews.
 */
export function generateThailandGrid(
  cellSize: number = GRID_CONFIG.cellSize,
  mockData = false,
): GridCell[] {
  const cells: GridCell[] = [];
  const { north, south, east, west } = THAILAND_BOUNDS;

  const latSteps = Math.ceil((north - south) / cellSize);
  const lngSteps = Math.ceil((east - west) / cellSize);

  let cellId = 0;

  for (let row = 0; row < latSteps; row++) {
    for (let col = 0; col < lngSteps; col++) {
      const cellNorth = north - row * cellSize;
      const cellSouth = cellNorth - cellSize;
      const cellWest  = west  + col * cellSize;
      const cellEast  = cellWest + cellSize;

      const centerLat = (cellNorth + cellSouth) / 2;
      const centerLng = (cellWest  + cellEast)  / 2;

      let severity: Severity = 'low';
      let temperature = 28;
      let probability = 0;

      if (mockData) {
        const seed = Math.floor(centerLat * 1000) + Math.floor(centerLng * 1000) + cellId;
        severity    = generateMockSeverity(centerLat, centerLng, seed) as Severity;
        temperature = generateMockTemperature(severity as any, centerLat, seed);
        probability = generateMockProbability(severity as any, seed);
      }

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

      cellId++;
    }
  }

  return cells;
}

// Generate mock grid data for entire Thailand
export const MOCK_GRID_DATA: GridCell[] = generateThailandGrid();

// Hard-stop zone colours — NO gradient/blur (no alpha except low for visibility).
// Thresholds match Rothfusz Heat Index breakpoints used in the model.
export const getSeverityColor = (severity: Severity): string => {
  switch (severity) {
    case 'extreme':  return 'rgba(239, 68, 68, 0.85)';   // RED    — HI ≥ 41°C
    case 'high':     return 'rgba(249, 115, 22, 0.80)';  // ORANGE — HI 35–40°C
    case 'moderate': return 'rgba(234, 179, 8, 0.75)';   // YELLOW — HI 28–34°C
    case 'low':      return 'rgba(34, 197, 94, 0.55)';   // GREEN  — HI < 28°C
    default:         return 'transparent';
  }
};

// Get border color for severity level
export const getSeverityBorderColor = (severity: Severity): string => {
  switch (severity) {
    case 'extreme':
      return 'rgba(239, 68, 68, 0.9)';
    case 'medium':
      return 'rgba(255, 165, 0, 0.9)';
    case 'low':
      return 'rgba(52, 197, 89, 0.7)';
    default:
      return 'transparent';
  }
};

// Web Leaflet Map Component
function WebLeafletMap({ 
  gridData, 
  userLocation,
  onGetLocation,
  isDarkMode,
}: { 
  gridData: GridCell[];
  userLocation: { latitude: number; longitude: number } | null;
  onGetLocation: () => void;
  isDarkMode: boolean;
}) {
  const [MapView, setMapView] = useState<any>(null);

  useEffect(() => {
    if (Platform.OS !== 'web') return;
    try {
      const ReactLeaflet = require('react-leaflet');
      const { MapContainer, TileLayer, Polygon, Marker, useMap } = ReactLeaflet;
      setMapView({ MapContainer, TileLayer, Polygon, Marker, useMap, L: require('leaflet') });
    } catch (e) {
      console.log('Leaflet not available:', e);
    }
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

  const { MapContainer, TileLayer, Polygon, Marker } = MapView;

  // Get the appropriate tile layer URL based on theme
  const tileLayerUrl = isDarkMode ? TILE_LAYERS.dark : TILE_LAYERS.light;

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
        background: #3b82f6;
        border: 3px solid white;
        border-radius: 50%;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        position: relative;
      ">
        <div style="
          position: absolute;
          width: 48px;
          height: 48px;
          background: rgba(59, 130, 246, 0.2);
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
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url={tileLayerUrl}
      />
      
      <MapController userLoc={userLocation} />
      
      {/* Grid overlay polygons */}
      {gridData.map((cell) => (
        <Polygon
          key={cell.id}
          positions={getPolygonPositions(cell)}
          pathOptions={{
            fillColor: getSeverityColor(cell.severity),
            fillOpacity: 0.7,
            color: getSeverityBorderColor(cell.severity),
            weight: 2,
          }}
        />
      ))}
      
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
}: { 
  gridData: GridCell[];
  userLocation: { latitude: number; longitude: number } | null;
  onGetLocation: () => void;
  isDarkMode: boolean;
}) {
  const [mapModule, setMapModule] = useState<any>(null);

  useEffect(() => {
    try {
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

  const { default: MapView, Marker, Polygon, PROVIDER_GOOGLE } = mapModule;

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
      {/* Grid overlay polygons */}
      {gridData.map((cell) => (
        <Polygon
          key={cell.id}
          coordinates={[
            { latitude: cell.north, longitude: cell.west },
            { latitude: cell.north, longitude: cell.east },
            { latitude: cell.south, longitude: cell.east },
            { latitude: cell.south, longitude: cell.west },
          ]}
          fillColor={getSeverityColor(cell.severity)}
          strokeColor={getSeverityBorderColor(cell.severity)}
          strokeWidth={2}
        />
      ))}

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
  gridData = MOCK_GRID_DATA,
  userLocation = null,
  onUserLocationRequest,
  style,
  isDarkMode = false,
}: { 
  gridData?: GridCell[];
  userLocation?: { latitude: number; longitude: number } | null;
  onUserLocationRequest?: () => void;
  style?: any;
  isDarkMode?: boolean;
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
        />
      ) : (
        <NativeMapView 
          gridData={gridData}
          userLocation={userLocation}
          onGetLocation={handleGetLocation}
          isDarkMode={isDarkMode}
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
