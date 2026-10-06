import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { translate } from "../i18n";
import hi from "../i18n/hi.json";
import hing from "../i18n/hing.json";
import bn from "../i18n/bn.json";
import ta from "../i18n/ta.json";
import te from "../i18n/te.json";
import mr from "../i18n/mr.json";
import gu from "../i18n/gu.json";
import kn from "../i18n/kn.json";
import ml from "../i18n/ml.json";
import pa from "../i18n/pa.json";

/**
 * i18n coverage + fallback-chain + SMS-length guards (Agent 12, Wave 4).
 * - Every locale must have exact key parity with hi (the default locale).
 * - No empty strings; every {placeholder} in hi must survive translation.
 * - translate() falls back requested -> hi -> key name (never English, never blank).
 * - data/alert-templates/*.json templates must render <= 160 chars.
 */
type Dict = Record<string, unknown>;
const LANGS: Record<string, Dict> = { hi, hing, bn, ta, te, mr, gu, kn, ml, pa };

function flatKeys(o: Dict, prefix = ""): string[] {
  const out: string[] = [];
  for (const [k, v] of Object.entries(o)) {
    if (k === "_meta") continue;
    if (v && typeof v === "object") out.push(...flatKeys(v as Dict, prefix + k + "."));
    else out.push(prefix + k);
  }
  return out;
}
function getPath(o: Dict, dotted: string): unknown {
  let cur: unknown = o;
  for (const p of dotted.split(".")) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Dict)[p];
  }
  return cur;
}
const placeholders = (s: string): string[] =>
  [...s.matchAll(/\{([a-zA-Z0-9_]+)\}/g)].map((m) => m[1]).sort();

const hiKeys = flatKeys(hi as unknown as Dict);

// 1. Key parity with hi across all 10 locales.
for (const [code, dict] of Object.entries(LANGS)) {
  const ks = new Set(flatKeys(dict));
  const missing = hiKeys.filter((k) => !ks.has(k));
  const extra = [...ks].filter((k) => !hiKeys.includes(k));
  assert.equal(missing.length, 0, `${code} missing keys: ${missing.slice(0, 5).join(", ")}`);
  assert.equal(extra.length, 0, `${code} extra keys: ${extra.slice(0, 5).join(", ")}`);
}

// 2. No empty strings; placeholders preserved.
for (const [code, dict] of Object.entries(LANGS)) {
  for (const k of hiKeys) {
    const hv = getPath(hi as unknown as Dict, k);
    const v = getPath(dict, k);
    assert.equal(typeof v, "string", `${code}.${k} not a string`);
    assert.ok((v as string).length > 0, `${code}.${k} empty`);
    if (typeof hv === "string") {
      assert.deepEqual(placeholders(v as string), placeholders(hv), `${code}.${k} placeholder mismatch`);
    }
  }
}

// 3. Fallback chain: requested -> hi -> key name. Never English, never blank.
assert.equal(translate("hi", "nav.home"), getPath(hi as unknown as Dict, "nav.home"));
assert.equal(translate("bn", "nav.home"), getPath(bn as unknown as Dict, "nav.home"));
// Simulate a missing key in bn: falls back to Hindi, not English, not blank.
const bnDict = bn as unknown as Dict;
const common = (bnDict["common"] as Dict);
const saved = common["confirm"];
delete common["confirm"];
try {
  const got = translate("bn" as never, "common.confirm");
  assert.equal(got, getPath(hi as unknown as Dict, "common.confirm"), "fallback must be Hindi");
  assert.ok(got.length > 0 && !/^[A-Za-z ]+$/.test(got) , "fallback must not be bare English");
} finally {
  common["confirm"] = saved;
}
// Unknown key returns the key name itself (never blank).
assert.equal(translate("ta" as never, "no.such.key"), "no.such.key");
// Interpolation still works through the chain.
assert.ok(translate("ml", "common.outbox_n", { n: 3 }).includes("3"), "interpolation");

// 4. SMS templates: every alert template <= 160 chars in every language.
const DATA = process.env.SAHAYTA_DATA_DIR!;
assert.ok(DATA, "SAHAYTA_DATA_DIR must be set");
for (const f of readdirSync(DATA + "/alert-templates").filter((x) => x.endsWith(".json"))) {
  const d = JSON.parse(readFileSync(join(DATA, "alert-templates", f), "utf8"));
  for (const [lang, text] of Object.entries(d.templates as Record<string, string>)) {
    assert.ok(text.length <= 160, `${f} [${lang}] is ${text.length} chars (>160)`);
    for (const ph of ["{district}", "{helpline}"]) {
      // flood templates carry district+helpline; heatwave/cyclone carry their own set
      if (f === "flood.json") assert.ok(text.includes(ph), `${f} [${lang}] missing ${ph}`);
    }
  }
}

console.log("i18n.test.ts: PASS");
