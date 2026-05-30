/**
 * Nearby Places Service
 * 
 * Fetches nearby rest care / cooling centers based on user location.
 * 
 * In production, this would call:
 * - Google Places API
 * - Overpass API (OpenStreetMap)
 * - A custom backend API
 * 
 * For now, we generate mock data based on coordinates.
 */

export interface Place {
  id: string;
  name: string;
  type: 'shopping_mall' | 'hospital' | 'supermarket' | 'convenience_store' | 'library' | 'government_building' | 'transit_station' | 'cooling_center' | 'unknown';
  address: string;
  latitude: number;
  longitude: number;
  distance: number; // in km
  openingHours: string;
  isOpen24Hours: boolean;
  phone?: string;
}

// Types of cooling/rest places (Updated for Thailand context)
const PLACE_TYPES: { type: Place['type']; name: string; openingHours: string; open24: boolean }[] = [
  { type: 'shopping_mall', name: 'Shopping Mall', openingHours: '10:00 AM - 10:00 PM', open24: false },
  { type: 'hospital', name: 'Hospital', openingHours: '24/7', open24: true },
  { type: 'supermarket', name: 'Supermarket', openingHours: '8:00 AM - 10:00 PM', open24: false },
  { type: 'convenience_store', name: 'Convenience Store', openingHours: '24/7', open24: true },
  { type: 'library', name: 'Public Library', openingHours: '8:00 AM - 6:00 PM', open24: false },
  { type: 'government_building', name: 'Government Building', openingHours: '8:30 AM - 4:30 PM', open24: false },
  { type: 'transit_station', name: 'Transit Station', openingHours: '6:00 AM - 12:00 AM', open24: false },
];

/**
 * Calculate distance between two coordinates using Haversine formula
 */
function calculateDistance(
  lat1: number, 
  lon1: number, 
  lat2: number, 
  lon2: number
): number {
  const R = 6371; // Earth's radius in km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

const GOOGLE_MAPS_API_KEY = process.env.EXPO_PUBLIC_GOOGLE_MAPS_API_KEY;

/**
 * Fetch places using Google Maps Places API
 */
async function searchGooglePlaces(
  latitude: number,
  longitude: number,
  radiusKm: number
): Promise<Place[]> {
  if (!GOOGLE_MAPS_API_KEY || GOOGLE_MAPS_API_KEY === 'YOUR_API_KEY') {
    throw new Error('Google Maps API Key not available');
  }

  // Google uses meters
  const radiusMeters = radiusKm * 1000;
  // Multiple types allowed by chaining or running multiple queries, 
  // but nearbysearch only accepts one `type`. We will use Google's 'keyword' or multiple requests.
  // To save requests, we'll do one query with multiple keywords or just use a generic 'point of interest' if we must.
  // A better approach for nearbysearch with multiple types in one call is not supported directly. 
  // We'll search for 'mall OR hospital OR supermarket OR convenience OR station' using `keyword`.
  const keyword = encodeURIComponent('mall OR hospital OR supermarket OR convenience OR station');
  const url = `https://maps.googleapis.com/maps/api/place/nearbysearch/json?location=${latitude},${longitude}&radius=${radiusMeters}&keyword=${keyword}&key=${GOOGLE_MAPS_API_KEY}`;

  const response = await fetch(url);
  if (!response.ok) throw new Error('Google Places API Error');
  
  const data = await response.json();
  if (data.status !== 'OK' && data.status !== 'ZERO_RESULTS') {
    throw new Error(`Google Places API returned status: ${data.status}`);
  }

  return (data.results || []).map((result: any, index: number) => {
    // Map Google types to our app's types
    let type: Place['type'] = 'unknown';
    const types = result.types || [];
    if (types.includes('shopping_mall')) type = 'shopping_mall';
    else if (types.includes('hospital')) type = 'hospital';
    else if (types.includes('supermarket')) type = 'supermarket';
    else if (types.includes('convenience_store')) type = 'convenience_store';
    else if (types.includes('library')) type = 'library';
    else if (types.includes('transit_station') || types.includes('train_station')) type = 'transit_station';
    else if (types.includes('local_government_office')) type = 'government_building';
    else type = 'shopping_mall'; // default fallback for 'mall' keyword

    const distance = calculateDistance(latitude, longitude, result.geometry.location.lat, result.geometry.location.lng);

    return {
      id: `google-${result.place_id || index}`,
      name: result.name || 'Unknown Place',
      type: type,
      address: result.vicinity || `Coordinate: ${result.geometry.location.lat}, ${result.geometry.location.lng}`,
      latitude: result.geometry.location.lat,
      longitude: result.geometry.location.lng,
      distance: distance,
      openingHours: result.opening_hours?.open_now ? 'Open Now' : 'Hours Info Unavailable',
      isOpen24Hours: false, // Google nearby doesn't surface 24/7 directly without Details API
    } as Place;
  });
}

/**
 * Fetch places using OpenStreetMap (Overpass API)
 * Specifically tuned for Thailand's available amenity/shop types
 */
async function searchOSMPlaces(
  latitude: number,
  longitude: number,
  radiusKm: number
): Promise<Place[]> {
  const radiusMeters = radiusKm * 1000;
  
  // Overpass QL Query
  const query = `
    [out:json][timeout:15];
    (
      node["shop"="mall"](around:${radiusMeters},${latitude},${longitude});
      way["shop"="mall"](around:${radiusMeters},${latitude},${longitude});
      
      node["amenity"="hospital"](around:${radiusMeters},${latitude},${longitude});
      way["amenity"="hospital"](around:${radiusMeters},${latitude},${longitude});
      
      node["shop"="supermarket"](around:${radiusMeters},${latitude},${longitude});
      way["shop"="supermarket"](around:${radiusMeters},${latitude},${longitude});
      
      node["shop"="convenience"](around:${radiusMeters},${latitude},${longitude});
      
      node["public_transport"="station"](around:${radiusMeters},${latitude},${longitude});
    );
    out center;
  `;

  const url = `https://overpass-api.de/api/interpreter`;
  const response = await fetch(url, {
    method: 'POST',
    body: query,
  });

  if (!response.ok) throw new Error('Overpass API Error');
  const data = await response.json();

  const places: Place[] = [];
  
  for (const element of data.elements || []) {
    const lat = element.lat || element.center?.lat;
    const lon = element.lon || element.center?.lon;
    if (!lat || !lon) continue;

    const tags = element.tags || {};
    
    // Ignore items without a proper name (unless it's a known big brand like 7-eleven tag)
    const name = tags['name:en'] || tags.name || tags['name:th'] || tags.brand;
    if (!name) continue;

    let type: Place['type'] = 'unknown';
    if (tags.shop === 'mall') type = 'shopping_mall';
    else if (tags.amenity === 'hospital') type = 'hospital';
    else if (tags.shop === 'supermarket') type = 'supermarket';
    else if (tags.shop === 'convenience') type = 'convenience_store';
    else if (tags.public_transport === 'station') type = 'transit_station';

    const distance = calculateDistance(latitude, longitude, lat, lon);

    places.push({
      id: `osm-${element.id}`,
      name: name,
      type: type,
      address: `${distance.toFixed(1)} km away`,
      latitude: lat,
      longitude: lon,
      distance: distance,
      openingHours: tags.opening_hours || 'Varies',
      isOpen24Hours: tags.opening_hours === '24/7',
    });
  }

  return places;
}

/**
 * Get nearest cooling places (Shopping Malls, Hospitals, etc.)
 * Expands radius from 1km to 3km if nothing is found.
 */
export async function getNearestCoolingPlaces(
  latitude: number,
  longitude: number
): Promise<Place[]> {
  let places: Place[] = [];
  
  // Try Google First
  try {
    places = await searchGooglePlaces(latitude, longitude, 1);
    if (places.length === 0) {
      places = await searchGooglePlaces(latitude, longitude, 3);
    }
  } catch (error) {
    console.log("Google Places API failed or unavailable, falling back to OSM", error);
    // Fallback to OSM
    try {
      places = await searchOSMPlaces(latitude, longitude, 1);
      if (places.length === 0) {
        places = await searchOSMPlaces(latitude, longitude, 3);
      }
    } catch (osmError) {
      console.error("OSM API also failed", osmError);
    }
  }
  
  // Priority order for ranking (index determines priority, lower is better)
  const priorityOrder: Place['type'][] = [
    'shopping_mall',
    'hospital',
    'supermarket',
    'convenience_store',
    'library',
    'government_building',
    'transit_station',
  ];
  
  // Sort by priority first, then by distance
  places.sort((a, b) => {
    const priorityA = priorityOrder.indexOf(a.type);
    const priorityB = priorityOrder.indexOf(b.type);
    
    // Fallback for unknown types
    const pA = priorityA === -1 ? 99 : priorityA;
    const pB = priorityB === -1 ? 99 : priorityB;
    
    if (pA !== pB) {
      return pA - pB;
    }
    
    return a.distance - b.distance;
  });
  
  // Return top 5 places
  return places.slice(0, 5);
}

/**
 * Calculate estimated travel time (mock)
 */
export function estimateTravelTime(distanceKm: number): string {
  // Assume average speed of 30 km/h in city
  const hours = distanceKm / 30;
  const minutes = Math.round(hours * 60);
  
  if (minutes < 1) return 'Less than 1 min';
  if (minutes === 1) return '1 min';
  if (minutes < 60) return `${minutes} min`;
  
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}m` : `${h} hour${h > 1 ? 's' : ''}`;
}

export default {
  getNearestCoolingPlaces,
  estimateTravelTime,
};
