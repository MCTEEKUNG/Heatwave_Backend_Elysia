/**
 * Geospatial helper: find the nearest province to a coordinate via haversine.
 */

export interface ProvincePoint {
  id: number;
  name_th: string;
  name_en: string;
  lat: number | string;
  lon: number | string;
}

const R_KM = 6371; // mean Earth radius

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

/** Great-circle distance in kilometres between two lat/lon points. */
export function haversineKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

/**
 * Return the province nearest to (lat, lon), or null if the list is empty.
 * `lat`/`lon` on provinces may be numeric or string (postgres numeric → string).
 */
export function nearestProvince<T extends ProvincePoint>(
  lat: number,
  lon: number,
  provinces: T[]
): T | null {
  let best: T | null = null;
  let bestDist = Infinity;
  for (const p of provinces) {
    const plat = typeof p.lat === "string" ? parseFloat(p.lat) : p.lat;
    const plon = typeof p.lon === "string" ? parseFloat(p.lon) : p.lon;
    if (!Number.isFinite(plat) || !Number.isFinite(plon)) continue;
    const d = haversineKm(lat, lon, plat, plon);
    if (d < bestDist) {
      bestDist = d;
      best = p;
    }
  }
  return best;
}
