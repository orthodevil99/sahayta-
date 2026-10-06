import assert from "node:assert/strict";
import { reliabilityPct, reputationDetailOf, reputationTier } from "../reputation";

// Tier thresholds mirror backend/app/services/reputation.py.
assert.equal(reputationTier(95), "guardian");
assert.equal(reputationTier(90), "guardian");
assert.equal(reputationTier(70), "responder");
assert.equal(reputationTier(40), "helper");
assert.equal(reputationTier(39), "newcomer");
assert.equal(reputationTier(0), "newcomer");

// Reliability: completed / (completed + declined_after_commit).
assert.equal(reliabilityPct(9, 1), 90);
assert.equal(reliabilityPct(0, 0), 100); // no history: not penalized
assert.equal(reliabilityPct(5, 0), 100);

// Full read-model from a volunteer record (demo mode).
const d = reputationDetailOf({
  id: "vol-ravi-kumar-patna",
  reputation: 52,
  tasks_completed: 1,
  tasks_declined: 0,
  avg_response_min: 4.2,
});
assert.equal(d.volunteer_id, "vol-ravi-kumar-patna");
assert.equal(d.reputation, 52);
assert.equal(d.reliability_pct, 100);
assert.equal(d.tier, "helper");
assert.equal(d.avg_response_min, 4.2);

// Missing optional fields default sanely.
const d2 = reputationDetailOf({ id: "x", reputation: 50, tasks_completed: 0, avg_response_min: null });
assert.equal(d2.tasks_declined, 0);
assert.equal(d2.reliability_pct, 100);

console.log("reputation.test.ts: all assertions passed");
