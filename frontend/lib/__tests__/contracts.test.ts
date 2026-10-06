import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * Contract-shape guard: the bundled synthetic data must satisfy the enum and
 * referential constraints in docs/api-contracts.md, because the demo client
 * renders it directly. Run with SAHAYTA_DATA_DIR=/path/to/repo/data.
 */
const DATA = process.env.SAHAYTA_DATA_DIR!;
assert.ok(DATA, "SAHAYTA_DATA_DIR must be set");
const load = (p: string) => JSON.parse(readFileSync(join(DATA, p), "utf8"));

const SEV = [1, 2, 3, 4, 5];
const SOS_STATUS = ["reported", "verified", "help_on_way", "resolved", "duplicate", "rejected"];
const SOS_CAT = ["medical", "rescue", "food", "shelter", "infrastructure", "other"];
const PRIORITY = ["low", "medium", "high", "critical"];
const LANGS = ["hi", "hing", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa"];

// Districts — canonical slugs.
const districts = load("districts.json").districts;
assert.equal(districts.length, 20, "20 districts");
assert.equal(new Set(districts.map((d: { id: string }) => d.id)).size, 20, "unique slugs");
const slugs = new Set(districts.map((d: { id: string }) => d.id));
assert.ok(slugs.has("patna"), "patna is canonical");

// SOS reports.
const sos = load("sos-reports.json");
assert.equal(sos.reports.length, 3000, "3000 SOS reports");
for (const r of sos.reports) {
  assert.ok(SEV.includes(r.severity), `severity enum: ${r.severity}`);
  assert.ok(SOS_STATUS.includes(r.status), `status enum: ${r.status}`);
  assert.ok(SOS_CAT.includes(r.category), `category enum: ${r.category}`);
  assert.ok(PRIORITY.includes(r.priority), `priority enum: ${r.priority}`);
  assert.ok(slugs.has(r.district_id), `canonical district: ${r.district_id}`);
  assert.equal(r.is_demo_data, true, "SOS rows flagged demo data");
}
const patnaSev4 = sos.reports.filter((r: { district_id: string; severity: number }) => r.district_id === "patna" && r.severity === 4);
assert.ok(patnaSev4.length >= 25, `≥25 Patna sev-4 anchors, got ${patnaSev4.length}`);

// Volunteers.
const vols = load("volunteers.json").volunteers;
assert.equal(vols.length, 1000, "1000 volunteers");
const ravi = vols.find((v: { id: string }) => v.id === "vol-ravi-kumar-patna");
assert.ok(ravi, "Ravi Kumar anchor exists");
assert.deepEqual(ravi.skills, ["rescue", "driving"], "Ravi skills per demo-scenario");
assert.deepEqual(ravi.languages, ["hi", "hing"]);
assert.equal(ravi.reputation, 50);

// Shelters.
const shelters = load("shelters.json").shelters;
assert.equal(shelters.length, 500, "500 shelters");
for (const s of shelters.slice(0, 200)) {
  assert.ok(s.occupied <= s.capacity, `occupied ≤ capacity for ${s.id}`);
  assert.equal(s.is_demo_data, true, "shelters flagged demo data");
}

// Alert templates — 3 types × 10 languages, SMS-length.
for (const type of ["flood", "heatwave", "cyclone"]) {
  const tpl = load(`alert-templates/${type}.json`);
  for (const lang of LANGS) {
    const msg: string = tpl.templates[lang];
    assert.ok(typeof msg === "string" && msg.length > 20, `${type}/${lang} exists`);
    assert.ok(msg.length <= 480, `${type}/${lang} ≤ 480 chars (got ${msg.length})`);
  }
}

// Weather — 20 districts × 30 days.
const weather = load("weather-sample.json");
assert.equal(Object.keys(weather.districts).length, 20, "weather covers 20 districts");
for (const [id, series] of Object.entries(weather.districts) as Array<[string, Array<{ source: string }> ]>) {
  assert.equal(series.length, 30, `${id}: 30 daily records`);
  assert.ok(series.every((r) => r.source === "simulated"), `${id}: labeled simulated`);
}
assert.equal(weather.seed_hints.patna.risk, 82, "Patna seed risk 82");
assert.equal(weather.seed_hints.patna.risk_level, "high");

console.log("contracts.test.ts: PASS");
