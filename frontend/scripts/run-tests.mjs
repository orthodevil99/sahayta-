/**
 * scripts/run-tests.mjs — compiles lib/ with tsc and runs the node test files.
 * Usage: npm test
 */
import { execSync } from "node:child_process";
import { readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const frontend = dirname(here);

console.log("compiling lib/ …");
execSync("npx tsc -p tsconfig.test.json", { cwd: frontend, stdio: "inherit" });

const buildDir = join(frontend, ".test-build", "__tests__");
// Must be set BEFORE test modules load (contracts.test.ts reads it at import).
process.env.SAHAYTA_DATA_DIR ??= join(frontend, "..", "data");
function walk(d) {
  const out = [];
  for (const f of readdirSync(d)) {
    const p = join(d, f);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (f.endsWith(".test.js")) out.push(p);
  }
  return out;
}

const files = walk(buildDir);
console.log(`running ${files.length} test files …`);
let failed = 0;
for (const f of files) {
  try {
    await import(pathToFileURL(f).href);
  } catch (e) {
    failed++;
    console.error(`FAIL ${f}:`, e.message);
  }
}
if (failed > 0) { console.error(`${failed} test file(s) failed`); process.exit(1); }
console.log("all tests passed");
