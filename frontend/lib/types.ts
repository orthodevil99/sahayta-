/**
 * Sahayta shared types — mirrors docs/api-contracts.md §0.6 enumerations
 * and shapes EXACTLY. Any drift from the backend must be flagged in
 * frontend/NOTES-agent4.md (contracts are DRAFT through Wave 2).
 */

export type Severity = 1 | 2 | 3 | 4 | 5;
export type SOSStatus = "reported" | "verified" | "help_on_way" | "resolved" | "duplicate" | "rejected";
export type SOSCategory = "medical" | "rescue" | "food" | "shelter" | "infrastructure" | "other";
export type Priority = "low" | "medium" | "high" | "critical";
export type TaskStatus = "assigned" | "accepted" | "declined" | "en_route" | "completed" | "cancelled";
export type AlertType = "flood" | "heatwave" | "cyclone" | "custom";
export type RiskLevel = "low" | "moderate" | "high" | "severe";
export type WeatherSource = "live" | "simulated";
export type VolunteerSkill = "medical" | "rescue" | "driving" | "cooking" | "shelter_mgmt" | "translation" | "logistics" | "counseling" | "engineering";

export type LangCode = "hi" | "hing" | "bn" | "ta" | "te" | "mr" | "gu" | "kn" | "ml" | "pa";
export const LANG_CODES: LangCode[] = ["hi", "hing", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa"];
export const DEFAULT_LANG: LangCode = "hi";

export interface SeverityAssessment {
  id: string;
  severity: Severity;
  rationale: string;
  area_tags: string[];
  model: string;
  assessed_at: string;
}

export interface SOSReport {
  id: string;
  client_report_id: string;
  description: string;
  language: string;
  category: SOSCategory;
  severity: Severity | null;
  severity_rationale: string | null;
  priority: Priority;
  status: SOSStatus;
  lat: number | null;
  lon: number | null;
  district_id: string | null;
  photo_url: string | null;
  photo_hash: string | null;
  photo_description?: string | null;
  reporter_name?: string | null;
  reporter_phone?: string | null;
  needed_skills: VolunteerSkill[];
  needs_review?: boolean;
  is_demo_data: boolean;
  created_at: string;
  updated_at: string;
  assessment?: SeverityAssessment | null;
  tasks?: TaskSummary[];
  /** Wave 2 amendment (issue #9): machine-readable verify reason on queue items. */
  reason?: string | null;
  /** Wave 4 (Agent 10): reporter trust tier on verify-queue items. */
  reporter_trust_tier?: "trusted" | "standard" | "new" | "flagged" | null;
}

export interface TaskSummary {
  id: string;
  volunteer_id: string;
  volunteer_name?: string;
  status: TaskStatus;
}

export interface Volunteer {
  id: string;
  name: string;
  phone?: string;
  district_id: string;
  lat: number | null;
  lon: number | null;
  skills: VolunteerSkill[];
  languages: string[];
  availability: "anytime" | Array<{ day: string; start: string; end: string }>;
  active: boolean;
  reputation: number;
  tasks_completed: number;
  avg_response_min: number | null;
  created_at?: string;
}

export interface VolunteerMatch {
  volunteer: Volunteer;
  score: number;
  distance_km: number;
  reasons: string[];
  /** Wave 3 (Agent 8, additive): 0–1 formula components from the backend. */
  score_breakdown?: { skill: number; distance: number; availability: number; reputation: number };
}

export interface VolunteerReputation {
  volunteer_id: string;
  reputation: number;
  tasks_completed: number;
  tasks_declined: number;
  avg_response_min: number | null;
  reliability_pct: number;
  tier: "guardian" | "responder" | "helper" | "newcomer";
}

export interface Task {
  id: string;
  sos_id: string;
  volunteer_id: string;
  status: TaskStatus;
  note?: string | null;
  assigned_at: string;
  accepted_at: string | null;
  completed_at: string | null;
  proof_photo_url: string | null;
  created_at: string;
  updated_at: string;
  volunteer?: Volunteer;
  sos?: Pick<SOSReport, "id" | "description" | "severity" | "category" | "priority" | "lat" | "lon" | "district_id" | "status">;
}

export interface Shelter {
  id: string;
  name: string;
  district_id: string;
  area: string;
  lat: number;
  lon: number;
  capacity: number;
  occupied: number;
  facilities: string[];
  contact_name: string;
  contact_phone: string;
  is_demo_data: boolean;
  updated_at: string;
}

export interface District {
  id: string;
  name: string;
  state: string;
  lat: number;
  lon: number;
  population: number;
  risk: number;
  risk_level: RiskLevel;
  active_sos: number;
  active_volunteers: number;
  updated_at: string;
}

export interface RiskFactor {
  name: string;
  value: number | string;
  weight: number;
  contribution: number;
  note: string;
}

export interface DistrictRisk {
  district_id: string;
  risk: number;
  risk_level: RiskLevel;
  factors: RiskFactor[];
  computed_at: string;
  weather_source: WeatherSource;
  advisory: string;
}

export interface ForecastHour {
  ts: string;
  rain_mm: number;
  temp_c: number;
  humidity: number;
  wind_kph: number;
  risk: number;
  risk_level: RiskLevel;
}

export interface AlertItem {
  id: string;
  district_ids: string[];
  type: AlertType;
  severity: Severity;
  languages: string[];
  message: string;
  messages?: Record<string, string>;
  created_at: string;
}

export interface BroadcastResult {
  broadcast_id: string;
  status: string;
  rendered: Record<string, string>;
  recipient_estimate: number;
  created_at: string;
}

export interface AdminOverview {
  district_id: string | null;
  sos_by_status: Record<string, number>;
  sos_by_severity: Record<string, number>;
  active_tasks: number;
  volunteers_active: number;
  volunteers_on_task: number;
  shelters_open: number;
  shelter_occupancy_pct: number;
  district_risk: number;
  risk_level: RiskLevel;
  pending_verifications: number;
  open_safety_flags: number;
  generated_at: string;
}

export interface SafetyFlag {
  id: string;
  type: "possible_duplicate" | "conflicting_reports" | "spam_burst";
  sos_ids: string[];
  district_id: string;
  evidence: string;
  status: string;
  created_at: string;
}

export interface AuditEntry {
  id: string;
  ts: string;
  actor: string;
  action: string;
  target_type: string;
  target_id: string;
  details: Record<string, unknown>;
}

export interface WarningsStatus {
  enabled: boolean;
  mode: "live" | "simulated";
  weather_api: string;
  districts_tracked: number;
  last_ingest_at: string;
  last_ingest_ok: boolean;
  last_risk_recompute_at: string;
  next_ingest_at: string;
}

export interface HealthStatus {
  status: string;
  version: string;
  db: string;
  llm: string;
  weather: string;
  ts: string;
}

export interface LanguageMeta {
  code: string;
  name: string;
  native_name: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

/** Filters for GET /api/sos — map 1:1 to the contract query params. */
export interface SOSFilters {
  district?: string;
  severity_min?: number;
  severity_max?: number;
  status?: SOSStatus;
  category?: SOSCategory;
  priority?: Priority;
  q?: string;
  verified_only?: boolean;
  since?: string;
  limit?: number;
  offset?: number;
  sort?: "-created_at" | "severity" | "priority";
}

export interface SOSCreateInput {
  photo?: File | null;
  photo_description?: string;
  description: string;
  lat?: number | null;
  lon?: number | null;
  district_id?: string;
  language?: string;
  reporter_name?: string;
  reporter_phone?: string;
  client_report_id: string; // minted at wizard open — idempotency key
}

/** WebSocket envelope — contracts §10. */
export interface WSEvent<T = unknown> {
  event_id: number;
  type:
    | "sos.created" | "sos.assessed" | "sos.status_changed"
    | "task.assigned" | "task.updated"
    | "alert.broadcast" | "risk.updated" | "volunteer.registered"
    | "ping" | "pong" | "subscribed";
  ts: string;
  data: T;
}
