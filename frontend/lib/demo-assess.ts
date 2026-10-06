/**
 * Client-side rule-based severity estimator — the demo-mode twin of
 * ai-engine/severity.py's rule fallback. It MUST agree with the backend
 * rule-fallback on the demo fixture (severity 4, tuned keywords per
 * docs/demo-scenario.md Act 2).
 *
 * Honest labeling: results from this path report model "rule-fallback-v1 (demo)".
 */
import type { Priority, Severity, SOSCategory, VolunteerSkill } from "./types";

export interface AssessResult {
  severity: Severity;
  rationale: string;
  area_tags: string[];
  category: SOSCategory;
  priority: Priority;
  suggested_skills: VolunteerSkill[];
  model: string;
}

interface DepthHit { re: RegExp; pts: number }

/** Strongest depth signal wins (not additive) — prevents keyword pile-up. */
const DEPTH: DepthHit[] = [
  { re: /छाती\s*तक|गर्दन\s*तक|chest[\s-]*deep|neck[\s-]*deep/i, pts: 3 },
  { re: /कमर\s*तक|waist[\s-]*deep/i, pts: 2 },
  { re: /घुटनों?\s*तक|घुटने\s*तक|knee[\s-]*deep/i, pts: 1 },
  { re: /पानी|बाढ़|flood|water|बारिश|rain|डूब/i, pts: 1 },
];
/** People at risk is a single bucket — one vulnerable group or five, it is one +1. */
const PEOPLE_AT_RISK = /छत\s*पर|rooftop|\broof\b|बुजुर्ग|बच्चे|elderly|children|फंसे|trapped|stuck/i;
const URGENT = /तुरंत\s*मदद|तुरन्त\s*मदद|immediately|urgent|तुरंत/i;
const CATEGORY_HINTS: Array<{ re: RegExp; cat: SOSCategory; skills: VolunteerSkill[] }> = [
  // Rescue first: flood/water contexts dominate, and vulnerability markers
  // (elderly/children on rooftops) mean rescue, not medical.
  { re: /पानी|बाढ़|flood|water|छत|roof|फंसे|trapped|नाव|boat|rescue/i, cat: "rescue", skills: ["rescue", "driving"] },
  { re: /चोट|खून|बीमार|medical|injured|blood|sick|दवा|एम्बुलेंस|ambulance/i, cat: "medical", skills: ["medical", "driving"] },
  { re: /खाना|भूख|food|hungry|राशन/i, cat: "food", skills: ["cooking", "logistics"] },
  { re: /शिविर|ठहर|shelter|camp|रहने/i, cat: "shelter", skills: ["shelter_mgmt", "logistics"] },
  { re: /सड़क|बिजली|पुल|road|power|bridge|तार/i, cat: "infrastructure", skills: ["engineering", "logistics"] },
];

export function assessSeverity(description: string, language = "hi"): AssessResult {
  const text = description || "";
  let depthPts = 0;
  for (const k of DEPTH) {
    if (k.re.test(text)) { depthPts = k.pts; break; } // strongest signal wins
  }
  const peoplePts = PEOPLE_AT_RISK.test(text) ? 1 : 0;
  const urgentPts = URGENT.test(text) ? 1 : 0;
  const severity = Math.max(1, Math.min(5, 1 + depthPts + peoplePts + urgentPts)) as Severity;

  let category: SOSCategory = "other";
  let suggested: VolunteerSkill[] = ["logistics"];
  for (const h of CATEGORY_HINTS) {
    if (h.re.test(text)) { category = h.cat; suggested = h.skills; break; }
  }
  const priority: Priority =
    severity >= 4 ? "critical" : severity === 3 ? "high" : severity === 2 ? "medium" : "low";

  const area_tags: string[] = [];
  if (/सड़क|road|गलि|lane/i.test(text)) area_tags.push("road_submerged");
  if (/घर|home|residential|इलाक/i.test(text)) area_tags.push("residential");
  if (/स्कूल|school|अस्पताल|hospital/i.test(text)) area_tags.push("public_building");
  if (area_tags.length === 0) area_tags.push("unspecified");

  const rationale = rationaleFor(severity, language, text);
  return { severity, rationale, area_tags, category, priority, suggested_skills: suggested, model: "rule-fallback-v1 (demo)" };
}

function rationaleFor(sev: Severity, lang: string, text: string): string {
  const depthBit = /घुटनों?\s*तक|knee/i.test(text)
    ? { hi: "घुटनों तक पानी", hing: "ghutno tak paani", en: "knee-deep water" }
    : /कमर|waist/i.test(text)
      ? { hi: "कमर तक पानी", hing: "kamar tak paani", en: "waist-deep water" }
      : { hi: "पानी भरा हुआ", hing: "paani bhara hua", en: "waterlogging" };
  const riskBit = /छत|roof/i.test(text)
    ? { hi: "लोग छतों पर हैं", hing: "log chhaton par hain", en: "people on rooftops" }
    : /फंसे|trapped/i.test(text)
      ? { hi: "लोग फंसे हुए हैं", hing: "log fanse hue hain", en: "people trapped" }
      : { hi: "रिहायशी इलाका प्रभावित", hing: "rihayshi ilaka prabhavit", en: "residential area affected" };
  const sevWord: Record<string, Record<Severity, string>> = {
    hi: { 1: "हल्का", 2: "मध्यम", 3: "गंभीर", 4: "अति गंभीर", 5: "विनाशकारी" },
    hing: { 1: "halka", 2: "madhyam", 3: "gambhir", 4: "ati gambhir", 5: "vinashkari" },
  };
  const pick = (o: { hi: string; hing: string; en: string }) =>
    lang === "hing" ? o.hing : lang === "hi" ? o.hi : o.en;
  const words = sevWord[lang] ?? sevWord.hi;
  const sthiti = lang === "hing" ? "sthiti" : lang === "hi" ? "स्थिति" : "situation";
  return `${pick(depthBit)}; ${pick(riskBit)} — ${words[sev]} ${sthiti}.`;
}
