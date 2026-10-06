/** Pure geo helpers — unit-tested (lib/__tests__/geo.test.ts). */

/** Haversine distance in km between two lat/lon points. */
export function haversineKm(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const R = 6371;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(bLat - aLat);
  const dLon = toRad(bLon - aLon);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/**
 * Volunteer matching score — mirrors the FROZEN formula in api-contracts.md §5:
 * score = 0.45*skill_match + 0.30*distance_score + 0.15*availability + 0.10*reputation_norm
 * The demo client uses this so demo-mode matching agrees with the backend formula.
 */
export function matchScore(opts: {
  neededSkills: string[];
  volunteerSkills: string[];
  distanceKm: number;
  maxDistanceKm: number;
  availableNow: boolean;
  reputation: number; // 0–100
}): { score: number; reasons: string[] } {
  const { neededSkills, volunteerSkills, distanceKm, maxDistanceKm, availableNow, reputation } = opts;
  const matched = neededSkills.filter((s) => volunteerSkills.includes(s));
  const skillMatch = neededSkills.length === 0 ? 1 : matched.length / neededSkills.length;
  const distanceScore = Math.max(0, 1 - distanceKm / maxDistanceKm);
  const availability = availableNow ? 1 : 0.3;
  const reputationNorm = Math.min(1, Math.max(0, reputation / 100));
  const score = Math.round((0.45 * skillMatch + 0.3 * distanceScore + 0.15 * availability + 0.1 * reputationNorm) * 1000) / 10;
  const reasons: string[] = [];
  matched.forEach((s) => reasons.push(`skill match: ${s}`));
  reasons.push(`${distanceKm.toFixed(1)} km away`);
  reasons.push(availableNow ? "available now" : "limited availability");
  reasons.push(`reputation ${reputation}`);
  return { score, reasons };
}

/** Nearest-district lookup for a lat/lon against the canonical district list. */
export function nearestDistrict<T extends { id: string; lat: number; lon: number }>(
  lat: number,
  lon: number,
  districts: T[],
): T | null {
  if (districts.length === 0) return null;
  let best = districts[0];
  let bestD = haversineKm(lat, lon, best.lat, best.lon);
  for (const d of districts.slice(1)) {
    const dist = haversineKm(lat, lon, d.lat, d.lon);
    if (dist < bestD) {
      bestD = dist;
      best = d;
    }
  }
  return best;
}
