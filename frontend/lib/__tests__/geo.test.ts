import assert from "node:assert/strict";
import { haversineKm, matchScore, nearestDistrict } from "../geo";

// Patna SOS pin → Ravi Kumar anchor (demo-scenario: ≈ 2.09 km).
const d = haversineKm(25.5941, 85.1376, 25.6071, 85.1526);
assert.ok(Math.abs(d - 2.09) < 0.15, `Ravi distance ≈ 2.09 km, got ${d}`);

// Same point → 0.
assert.equal(haversineKm(0, 0, 0, 0), 0);

// Known: 1 degree of latitude ≈ 111.19 km.
const lat1 = haversineKm(0, 0, 1, 0);
assert.ok(Math.abs(lat1 - 111.19) < 0.5, `1° lat ≈ 111.19 km, got ${lat1}`);

// Matching formula — the FROZEN contract formula. Ravi vs the demo SOS:
// needed [rescue, driving], has both, 2.09 km of 25 max, anytime, rep 50.
const { score, reasons } = matchScore({
  neededSkills: ["rescue", "driving"],
  volunteerSkills: ["rescue", "driving"],
  distanceKm: 2.09,
  maxDistanceKm: 25,
  availableNow: true,
  reputation: 50,
});
assert.ok(score >= 80, `Ravi match score ≥ 80 (demo acceptance), got ${score}`);
assert.ok(reasons.some((r) => r.includes("skill match: rescue")), "reasons mention skill match");

// No skill overlap → score drops.
const bad = matchScore({ neededSkills: ["medical"], volunteerSkills: ["driving"], distanceKm: 1, maxDistanceKm: 25, availableNow: true, reputation: 50 });
assert.ok(bad.score < score, "skill mismatch scores lower");

// Beyond max distance → excluded via distance_score 0 contribution.
const far = matchScore({ neededSkills: ["rescue"], volunteerSkills: ["rescue"], distanceKm: 30, maxDistanceKm: 25, availableNow: true, reputation: 50 });
assert.ok(far.score < 70, `far volunteer penalized, got ${far.score}`);

const districts = [
  { id: "patna", lat: 25.5941, lon: 85.1376 },
  { id: "gaya", lat: 24.79, lon: 85.0 },
];
assert.equal(nearestDistrict(25.6, 85.14, districts)?.id, "patna");
assert.equal(nearestDistrict(0, 0, []), null);

console.log("geo.test.ts: PASS");
