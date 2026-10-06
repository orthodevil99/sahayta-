/**
 * Reputation read-model helpers — mirrors backend/app/services/reputation.py
 * for demo mode (the backend is canonical; these pure functions let the
 * seeded DemoApiClient and the volunteer profile render the same numbers
 * without a live backend).
 */
export interface ReputationDetail {
  volunteer_id: string;
  reputation: number;
  tasks_completed: number;
  tasks_declined: number;
  avg_response_min: number | null;
  reliability_pct: number;
  tier: "guardian" | "responder" | "helper" | "newcomer";
}

export function reliabilityPct(tasksCompleted: number, tasksDeclined: number): number {
  const denom = (tasksCompleted || 0) + (tasksDeclined || 0);
  if (denom === 0) return 100;
  return Math.round((100 * (tasksCompleted || 0)) / denom * 10) / 10;
}

export function reputationTier(score: number): ReputationDetail["tier"] {
  const s = score || 0;
  if (s >= 90) return "guardian";
  if (s >= 70) return "responder";
  if (s >= 40) return "helper";
  return "newcomer";
}

export function reputationDetailOf(v: {
  id: string;
  reputation: number;
  tasks_completed: number;
  tasks_declined?: number;
  avg_response_min: number | null;
}): ReputationDetail {
  const declined = v.tasks_declined ?? 0;
  return {
    volunteer_id: v.id,
    reputation: v.reputation ?? 50,
    tasks_completed: v.tasks_completed ?? 0,
    tasks_declined: declined,
    avg_response_min: v.avg_response_min ?? null,
    reliability_pct: reliabilityPct(v.tasks_completed ?? 0, declined),
    tier: reputationTier(v.reputation ?? 50),
  };
}
