#!/usr/bin/env node
/**
 * scripts/i18n-coverage.mjs — honestly compute per-language i18n coverage.
 * For each locale in frontend/lib/i18n/*.json vs hi.json (the default locale):
 *   - keys present / total keys
 *   - non-empty values
 *   - placeholder parity ({vars} in hi value all survive translation)
 * Prints a table + writes scripts/i18n-coverage.json. Exit 1 if any locale < 100%.
 */
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const dir = join(here, "..", "frontend", "lib", "i18n");
const load = (f) => JSON.parse(readFileSync(join(dir, f), "utf8"));

function flat(o, prefix = "", out = {}) {
  for (const [k, v] of Object.entries(o)) {
    if (k === "_meta") continue;
    if (v && typeof v === "object") flat(v, prefix + k + ".", out);
    else out[prefix + k] = v;
  }
  return out;
}
const ph = (s) => [...String(s).matchAll(/\{([a-zA-Z0-9_]+)\}/g)].map((m) => m[1]).sort().join(",");

const hi = flat(load("hi.json"));
const total = Object.keys(hi).length;
const rows = [];
let fail = false;
for (const f of readdirSync(dir).filter((x) => x.endsWith(".json")).sort()) {
  const code = f.replace(".json", "");
  const d = flat(load(f));
  let present = 0, nonEmpty = 0, phOk = 0;
  const missing = [];
  for (const [k, hv] of Object.entries(hi)) {
    if (!(k in d)) { missing.push(k); continue; }
    present++;
    if (String(d[k]).length > 0) nonEmpty++;
    if (ph(d[k]) === ph(hv)) phOk++;
  }
  const pct = (present / total) * 100;
  if (pct < 100) fail = true;
  rows.push({ code, present, total, nonEmpty, phOk, pct: pct.toFixed(1), missing });
}

console.log("lang  keys            non-empty  ph-parity  coverage");
console.log("----  --------------  ---------  ---------  --------");
for (const r of rows) {
  console.log(
    `${r.code.padEnd(4)}  ${String(r.present + "/" + r.total).padEnd(14)}  ${String(r.nonEmpty).padEnd(9)}  ${String(r.phOk).padEnd(9)}  ${r.pct}%`
  );
  if (r.missing.length) console.log(`      MISSING: ${r.missing.join(", ")}`);
}
writeFileSync(join(here, "i18n-coverage.json"), JSON.stringify({ total, rows }, null, 2) + "\n");
console.log("\nwrote scripts/i18n-coverage.json");
process.exit(fail ? 1 : 0);
