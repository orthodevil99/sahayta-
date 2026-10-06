/**
 * scripts/prepare-demo-data.mjs
 * Copies the canonical synthetic datasets (repo data/) into
 * frontend/public/demo-data/ so the statically-exported PWA is
 * self-contained. Run: npm run prepare-demo-data (also runs pre-build).
 * The copied files ARE committed — the Devpost demo link must work offline.
 */
import { cpSync, mkdirSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const frontend = dirname(here);
const repoData = join(frontend, "..", "data");
const out = join(frontend, "public", "demo-data");

const FILES = [
  "districts.json",
  "sos-reports.json",
  "volunteers.json",
  "shelters.json",
  "weather-sample.json",
  "alert-templates/flood.json",
  "alert-templates/heatwave.json",
  "alert-templates/cyclone.json",
  "DEMO_DATA_README.md",
];

mkdirSync(join(out, "alert-templates"), { recursive: true });
let ok = 0;
for (const f of FILES) {
  const src = join(repoData, f);
  const dst = join(out, f);
  mkdirSync(dirname(dst), { recursive: true });
  if (!existsSync(src)) { console.error(`MISSING: ${src}`); process.exitCode = 1; continue; }
  cpSync(src, dst);
  ok++;
}
console.log(`demo-data: copied ${ok}/${FILES.length} files → public/demo-data/`);
