import assert from "node:assert/strict";
import { assessSeverity } from "../demo-assess";
import { DEMO_FIXTURE } from "../demo";

// The exact demo-scenario fixture MUST score 4 (acceptance test, Act 2).
const r = assessSeverity(DEMO_FIXTURE.description, "hi");
assert.equal(r.severity, 4, `fixture severity = 4, got ${r.severity}`);
assert.equal(r.category, "rescue");
assert.equal(r.priority, "critical");
assert.deepEqual(r.suggested_skills, ["rescue", "driving"]);
assert.ok(r.rationale.length > 10 && r.rationale.length < 200, "one-line rationale");
assert.ok(r.area_tags.includes("road_submerged"), "area tags include road_submerged");
assert.ok(r.area_tags.includes("residential"), "area tags include residential");
assert.equal(r.model, "rule-fallback-v1 (demo)");

// Hinglish twin returns Latin-script rationale.
const rh = assessSeverity("Knee-deep water in Kankarbagh, elderly on rooftops, need help immediately", "hing");
assert.equal(rh.severity, 4, `hinglish fixture severity = 4, got ${rh.severity}`);
assert.ok(!/[\u0900-\u097F]/.test(rh.rationale), "hinglish rationale is Latin script");

// Mild report stays low.
const mild = assessSeverity("Light rain in the market area, no disruption.", "hi");
assert.ok(mild.severity <= 2, `mild report ≤ 2, got ${mild.severity}`);

// Catastrophic keywords push to 5.
const cat = assessSeverity("गर्दन तक पानी, बच्चे छत पर फंसे हैं, तुरंत मदद चाहिए, घर डूब गए", "hi");
assert.equal(cat.severity, 5, `catastrophic = 5, got ${cat.severity}`);

// Medical text categorizes correctly.
const med = assessSeverity("चोट लगी है, खून बह रहा है, दवा चाहिए", "hi");
assert.equal(med.category, "medical");
assert.ok(med.suggested_skills.includes("medical"));

// Severity always within 1..5, priority consistent.
for (const sev of [r.severity, rh.severity, mild.severity, cat.severity, med.severity]) {
  assert.ok(sev >= 1 && sev <= 5, `severity in range: ${sev}`);
}

console.log("demo-assess.test.ts: PASS");
