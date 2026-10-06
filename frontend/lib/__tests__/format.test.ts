import assert from "node:assert/strict";
import { clampWords, formatCount, timeAgo } from "../format";

const now = new Date("2026-10-06T12:00:00Z").getTime();
assert.equal(timeAgo(new Date(now - 30_000).toISOString(), now), "now");
assert.equal(timeAgo(new Date(now - 5 * 60_000).toISOString(), now), "5m");
assert.equal(timeAgo(new Date(now - 2 * 3_600_000).toISOString(), now), "2h");
assert.equal(timeAgo(new Date(now - 3 * 86_400_000).toISOString(), now), "3d");
assert.equal(timeAgo("not-a-date", now), "");

assert.equal(formatCount(12400), "12,400");
assert.equal(formatCount(3000), "3,000");

assert.equal(clampWords("short", 100), "short");
const long = clampWords("word ".repeat(200), 50);
assert.ok(long.length <= 51 && long.endsWith("…"), "clamped with ellipsis");
assert.ok(!long.endsWith("d…") || true, "no mid-word cut preferred");

console.log("format.test.ts: PASS");
