"use client";
/**
 * DemoApiClient — the seeded demo backend. Implements SahaytaApi against the
 * bundled synthetic data (public/demo-data/*.json, copied from repo data/ by
 * scripts/prepare-demo-data.mjs) + localStorage deltas. NO network needed.
 *
 * This is what the 2–3 min demo video records against: one click on
 * "▶ Play Patna flood demo" loads the full Patna scenario deterministically.
 * Every number shown is labeled DEMO DATA in the UI (HonestyChip).
 */
import type {
  AdminOverview, AlertItem, AlertType, AuditEntry, BroadcastResult, District,
  DistrictRisk, ForecastHour, HealthStatus, LanguageMeta, Paginated, SafetyFlag,
  Shelter, SOSCreateInput, SOSFilters, SOSReport, SOSStatus, Task, TaskStatus,
  Volunteer, VolunteerMatch, VolunteerSkill, WarningsStatus, WSEvent,
} from "./types";
import type { AssessResult } from "./demo-assess";
import type {
  BroadcastInput, ListAlertsParams, ListSheltersParams, ListTasksParams,
  ListVolunteersParams, RegisterVolunteerInput, SahaytaApi,
} from "./api";
import { assessSeverity } from "./demo-assess";
import { haversineKm, matchScore, nearestDistrict } from "./geo";
import { getDeviceId } from "./outbox";
import { reputationDetailOf } from "./reputation";

/* Demo-mode media store: photo_id -> object URL (uploadMedia below). */
const demoMedia = new Map<string, string>();

const DD = "/demo-data";
const LS = {
  sosAdd: "sahayta.demo.sos_add",
  sosPatch: "sahayta.demo.sos_patch", // {id: partial}
  tasks: "sahayta.demo.tasks",
  volunteersAdd: "sahayta.demo.volunteers_add",
  volunteersPatch: "sahayta.demo.volunteers_patch",
  alerts: "sahayta.demo.alerts",
  audit: "sahayta.demo.audit",
  flags: "sahayta.demo.flags",
};

/* District names in Hindi (Devanagari) for alert rendering; other scripts
   fall back to English in demo mode (documented limitation). */
const DISTRICT_HI: Record<string, string> = {
  patna: "पटना", vaishali: "वैशाली", gaya: "गया", muzaffarpur: "मुजफ्फरपुर",
  darbhanga: "दरभंगा", bhagalpur: "भागलपुर", purnia: "पूर्णिया", katihar: "कटिहार",
  samastipur: "समस्तीपुर", sitamarhi: "सीतामढ़ी", lucknow: "लखनऊ", gorakhpur: "गोरखपुर",
  varanasi: "वाराणसी", prayagraj: "प्रयागराज", kanpur: "कानपुर", guwahati: "गुवाहाटी",
  dibrugarh: "डिब्रूगढ़", kolkata: "कोलकाता", howrah: "हावड़ा", puri: "पुरी",
  nagpur: "नागपुर", chennai: "चेन्नई",
};

interface Bundle {
  districts: Array<{ id: string; name: string; state: string; lat: number; lon: number; population: number; hazards: string[] }>;
  sos: SOSReport[];
  volunteers: Volunteer[];
  shelters: Shelter[];
  weather: Record<string, Array<{ date: string; rain_mm: number; temp_c: number; humidity_pct: number; wind_kph: number; river_level_m?: number; river_trend?: string; source: string }>>;
  seedHints: Record<string, { risk: number; risk_level: string; note: string }>;
  templates: Record<string, { templates: Record<string, string>; max_chars: number }>;
}

let bundlePromise: Promise<Bundle> | null = null;
async function loadBundle(): Promise<Bundle> {
  if (!bundlePromise) {
    bundlePromise = (async () => {
      const get = async (p: string) => (await fetch(`${DD}/${p}`)).json();
      const [districts, sos, volunteers, shelters, weather, flood, heatwave, cyclone] = await Promise.all([
        get("districts.json"), get("sos-reports.json"), get("volunteers.json"),
        get("shelters.json"), get("weather-sample.json"),
        get("alert-templates/flood.json"), get("alert-templates/heatwave.json"), get("alert-templates/cyclone.json"),
      ]);
      return {
        districts: districts.districts,
        sos: (sos.reports as SOSReport[]).map((r) => ({ ...r, is_demo_data: true })),
        volunteers: (volunteers.volunteers as Volunteer[]).map((v) => ({ ...v, created_at: "2026-10-03T00:00:00Z" })),
        shelters: shelters.shelters as Shelter[],
        weather: weather.districts,
        seedHints: weather.seed_hints,
        templates: { flood, heatwave, cyclone },
      };
    })();
  }
  return bundlePromise;
}

function lsGet<T>(k: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(k);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch { return fallback; }
}
function lsSet(k: string, v: unknown) {
  try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* quota — demo continues in-memory */ }
}

type Emitter = (e: WSEvent) => void;

function paginate<T>(items: T[], limit = 20, offset = 0): Paginated<T> {
  return { items: items.slice(offset, offset + limit), total: items.length, limit, offset };
}

const RISK_BAND = (r: number) => (r >= 85 ? "severe" : r >= 70 ? "high" : r >= 40 ? "moderate" : "low") as DistrictRisk["risk_level"];

/** Demo risk model — mirrors the contract's factor shape; Patna pinned to seed hint (82/high). */
function computeRisk(districtId: string, b: Bundle): DistrictRisk {
  const hint = b.seedHints[districtId];
  const series = b.weather[districtId] ?? [];
  const last = series[series.length - 1];
  if (hint) {
    return {
      district_id: districtId, risk: hint.risk, risk_level: hint.risk_level as DistrictRisk["risk_level"],
      factors: [
        { name: "rainfall_24h_mm", value: last?.rain_mm ?? 184.7, weight: 0.35, contribution: 28.9, note: `${last?.rain_mm ?? 184.7} mm in 24h (severe)` },
        { name: "river_level_trend", value: last?.river_trend ?? "rising", weight: 0.25, contribution: 21.0, note: `Ganga rising at Gandhi Ghat` },
        { name: "sos_density", value: 14, weight: 0.2, contribution: 16.4, note: "14 active SOS in district" },
        { name: "forecast_rain_12h", value: last?.rain_mm ?? 120, weight: 0.2, contribution: 15.7, note: "heavy rain forecast next 12h" },
      ],
      computed_at: new Date().toISOString(), weather_source: "simulated",
      advisory: "Heavy flooding likely in low-lying wards within 12h.",
    };
  }
  // Heuristic for other districts from their weather series.
  const rain = last?.rain_mm ?? 0;
  const temp = last?.temp_c ?? 30;
  const wind = last?.wind_kph ?? 10;
  let risk = 8 + Math.min(60, rain * 0.35) + Math.max(0, (temp - 38) * 4) + Math.min(25, Math.max(0, wind - 60) * 0.5);
  risk = Math.round(Math.min(100, risk));
  return {
    district_id: districtId, risk, risk_level: RISK_BAND(risk),
    factors: [
      { name: "rainfall_24h_mm", value: rain, weight: 0.4, contribution: Math.round(Math.min(60, rain * 0.35) * 10) / 10, note: `${rain} mm in 24h` },
      { name: "heat_index", value: temp, weight: 0.3, contribution: Math.round(Math.max(0, (temp - 38) * 4) * 10) / 10, note: `${temp}°C max temp` },
      { name: "wind_gust", value: wind, weight: 0.3, contribution: Math.round(Math.min(25, Math.max(0, wind - 60) * 0.5) * 10) / 10, note: `${wind} kph winds` },
    ],
    computed_at: new Date().toISOString(), weather_source: "simulated",
    advisory: risk >= 70 ? "Adverse conditions likely — stay alert." : "No immediate threat.",
  };
}

export class DemoApiClient implements SahaytaApi {
  readonly mode = "demo" as const;
  private emitters = new Set<Emitter>();
  private eventId = 1;
  private sosCache: SOSReport[] | null = null;

  getAdminKey() { return localStorage.getItem("sahayta.admin_key"); }
  setAdminKey(k: string | null) { k ? localStorage.setItem("sahayta.admin_key", k) : localStorage.removeItem("sahayta.admin_key"); }

  private emit(type: WSEvent["type"], data: unknown, districtIds?: string[]) {
    const e: WSEvent = { event_id: this.eventId++, type, ts: new Date().toISOString(), data: { ...(data as object), ...(districtIds ? { district_ids: districtIds } : {}) } };
    this.emitters.forEach((cb) => { try { cb(e); } catch { /* */ } });
  }

  subscribe(cb: Emitter, districts?: string[]): () => void {
    const wrapped: Emitter = (e) => {
      if (districts?.length) {
        const d = e.data as { district_id?: string; district_ids?: string[] };
        const ids = d.district_ids ?? (d.district_id ? [d.district_id] : []);
        if (ids.length && !ids.some((id) => districts.includes(id))) return;
      }
      cb(e);
    };
    this.emitters.add(wrapped);
    return () => { this.emitters.delete(wrapped); };
  }

  private async allSOS(): Promise<SOSReport[]> {
    const b = await loadBundle();
    if (!this.sosCache) this.sosCache = b.sos.map((r) => ({ ...r }));
    const added = lsGet<SOSReport[]>(LS.sosAdd, []);
    const patches = lsGet<Record<string, Partial<SOSReport>>>(LS.sosPatch, {});
    const byId = new Map(this.sosCache.map((r) => [r.id, { ...r }]));
    for (const [id, p] of Object.entries(patches)) {
      const cur = byId.get(id);
      if (cur) byId.set(id, { ...cur, ...p });
    }
    for (const r of added) byId.set(r.id, r);
    return [...byId.values()].sort((a, b) => b.created_at.localeCompare(a.created_at));
  }

  private persistSOS(r: SOSReport, isNew: boolean) {
    if (isNew) {
      const added = lsGet<SOSReport[]>(LS.sosAdd, []);
      lsSet(LS.sosAdd, [...added.filter((x) => x.id !== r.id && x.client_report_id !== r.client_report_id), r]);
    } else {
      const patches = lsGet<Record<string, Partial<SOSReport>>>(LS.sosPatch, {});
      patches[r.id] = { status: r.status, updated_at: r.updated_at, tasks: r.tasks };
      lsSet(LS.sosPatch, patches);
    }
    this.sosCache = null;
  }

  private audit(actor: string, action: string, target_type: string, target_id: string, details: Record<string, unknown> = {}) {
    const log = lsGet<AuditEntry[]>(LS.audit, []);
    log.push({ id: `audit-${Date.now()}-${log.length}`, ts: new Date().toISOString(), actor, action, target_type, target_id, details });
    lsSet(LS.audit, log.slice(-500));
  }

  async health(): Promise<HealthStatus> {
    return { status: "ok", version: "1.0.0-wave2-demo", db: "demo-bundle", llm: "fallback", weather: "simulated", ts: new Date().toISOString() };
  }
  async metaLanguages(): Promise<{ languages: LanguageMeta[] }> {
    const { LANG_META } = await import("./i18n");
    return { languages: (Object.keys(LANG_META) as Array<keyof typeof LANG_META>).map((code) => ({ code, name: LANG_META[code].name, native_name: LANG_META[code].native })) };
  }

  /* ---------------- SOS ---------------- */
  async listSOS(f: SOSFilters): Promise<Paginated<SOSReport>> {
    let items = await this.allSOS();
    if (f.district) items = items.filter((r) => r.district_id === f.district);
    if (f.severity_min != null) items = items.filter((r) => (r.severity ?? 0) >= f.severity_min!);
    if (f.severity_max != null) items = items.filter((r) => (r.severity ?? 0) <= f.severity_max!);
    if (f.status) items = items.filter((r) => r.status === f.status);
    if (f.category) items = items.filter((r) => r.category === f.category);
    if (f.priority) items = items.filter((r) => r.priority === f.priority);
    if (f.q) { const q = f.q.toLowerCase(); items = items.filter((r) => r.description.toLowerCase().includes(q)); }
    if (f.verified_only) items = items.filter((r) => r.status !== "reported");
    if (f.since) items = items.filter((r) => r.created_at >= f.since!);
    if (f.sort === "severity") items = [...items].sort((a, b) => (b.severity ?? 0) - (a.severity ?? 0));
    else if (f.sort === "priority") {
      const rank = { critical: 4, high: 3, medium: 2, low: 1 } as const;
      items = [...items].sort((a, b) => rank[b.priority] - rank[a.priority]);
    }
    const list = items.map(({ assessment, ...rest }) => rest as SOSReport); // contract: list omits nested assessment
    return paginate(list, f.limit ?? 20, f.offset ?? 0);
  }

  async getSOS(id: string): Promise<SOSReport> {
    const items = await this.allSOS();
    const r = items.find((x) => x.id === id);
    if (!r) throw Object.assign(new Error("not found"), { status: 404 });
    return r;
  }

  async createSOS(input: SOSCreateInput): Promise<SOSReport> {
    const b = await loadBundle();
    // Idempotent replay on client_report_id (contracts §0.5).
    const existing = (await this.allSOS()).find((r) => r.client_report_id === input.client_report_id);
    if (existing) return existing;
    const a = assessSeverity(input.description, input.language ?? "hi");
    const district = input.district_id
      ?? (input.lat != null && input.lon != null ? nearestDistrict(input.lat, input.lon, b.districts)?.id ?? null : null);
    const now = new Date().toISOString();
    const report: SOSReport = {
      id: `demo-${input.client_report_id.slice(0, 8)}`,
      client_report_id: input.client_report_id,
      description: input.description,
      language: input.language ?? "hi",
      category: a.category,
      severity: a.severity,
      severity_rationale: a.rationale,
      priority: a.priority,
      status: "reported",
      lat: input.lat ?? null, lon: input.lon ?? null,
      district_id: district,
      photo_url: null, photo_hash: null,
      photo_description: input.photo_description ?? null,
      reporter_name: input.reporter_name ?? null,
      reporter_phone: input.reporter_phone ?? null,
      needed_skills: a.suggested_skills,
      needs_review: false,
      is_demo_data: true,
      created_at: now, updated_at: now,
      assessment: { id: `assess-${input.client_report_id.slice(0, 8)}`, severity: a.severity, rationale: a.rationale, area_tags: a.area_tags, model: a.model, assessed_at: now },
      tasks: [],
    };
    this.persistSOS(report, true);
    this.audit(`device:${getDeviceId()}`, "sos.created", "sos", report.id, {});
    this.emit("sos.created", report, district ? [district] : []);
    setTimeout(() => this.emit("sos.assessed", { sos_id: report.id, severity: a.severity, category: a.category, priority: a.priority, rationale: a.rationale }, district ? [district] : []), 600);
    return report;
  }

  async updateSOSStatus(id: string, status: SOSStatus, note?: string): Promise<SOSReport> {
    const allowed: Record<SOSStatus, SOSStatus[]> = {
      reported: ["verified", "duplicate", "rejected"], verified: ["help_on_way", "resolved", "rejected"],
      help_on_way: ["resolved"], resolved: [], duplicate: [], rejected: [],
    };
    const r = await this.getSOS(id);
    if (!allowed[r.status].includes(status)) throw Object.assign(new Error(`illegal transition ${r.status} → ${status}`), { status: 400 });
    const updated = { ...r, status, updated_at: new Date().toISOString() };
    this.persistSOS(updated, false);
    this.audit(`device:${getDeviceId()}`, "sos.status_changed", "sos", id, { from: r.status, to: status, note });
    this.emit("sos.status_changed", { sos_id: id, from: r.status, to: status, note }, r.district_id ? [r.district_id] : []);
    return updated;
  }

  async verifySOS(id: string, verdict: "verified" | "rejected" | "duplicate", duplicateOf?: string | null, note?: string): Promise<SOSReport> {
    const to: SOSStatus = verdict === "verified" ? "verified" : verdict === "rejected" ? "rejected" : "duplicate";
    const r = await this.getSOS(id);
    const updated = { ...r, status: to, updated_at: new Date().toISOString() };
    this.persistSOS(updated, false);
    this.audit("admin:demo", "sos.verified", "sos", id, { verdict, duplicate_of: duplicateOf, note });
    this.emit("sos.status_changed", { sos_id: id, from: r.status, to, note }, r.district_id ? [r.district_id] : []);
    return updated;
  }

  async flagSOS(id: string, reason: string, note?: string) {
    const flags = lsGet<SafetyFlag[]>(LS.flags, []);
    const r = await this.getSOS(id);
    const flag: SafetyFlag = { id: `flag-${Date.now()}`, type: reason === "duplicate" ? "possible_duplicate" : "conflicting_reports", sos_ids: [id], district_id: r.district_id ?? "patna", evidence: note ?? reason, status: "open", created_at: new Date().toISOString() };
    lsSet(LS.flags, [...flags, flag]);
    return { id: flag.id, status: "received" };
  }

  async assess(description: string, language = "hi", lat?: number, lon?: number): Promise<AssessResult> {
    return assessSeverity(description, language);
  }

  /* ---------------- Shelters & districts ---------------- */
  async listShelters(p: ListSheltersParams): Promise<Paginated<Shelter>> {
    const b = await loadBundle();
    let items = b.shelters;
    if (p.district) items = items.filter((s) => s.district_id === p.district);
    if (p.q) { const q = p.q.toLowerCase(); items = items.filter((s) => (s.name + " " + s.area).toLowerCase().includes(q)); }
    if (p.has_capacity) items = items.filter((s) => s.occupied < s.capacity);
    if (p.facility?.length) items = items.filter((s) => p.facility!.every((f) => s.facilities.includes(f)));
    return paginate(items, p.limit ?? 20, p.offset ?? 0);
  }

  async getDistricts(): Promise<District[]> {
    const b = await loadBundle();
    const sos = await this.allSOS();
    const vols = await this.allVolunteers();
    return b.districts.map((d) => {
      const risk = computeRisk(d.id, b);
      return {
        id: d.id, name: d.name, state: d.state, lat: d.lat, lon: d.lon, population: d.population,
        risk: risk.risk, risk_level: risk.risk_level,
        active_sos: sos.filter((r) => r.district_id === d.id && !["resolved", "duplicate", "rejected"].includes(r.status)).length,
        active_volunteers: vols.filter((v) => v.district_id === d.id && v.active).length,
        updated_at: new Date().toISOString(),
      };
    });
  }

  async getDistrictRisk(id: string): Promise<DistrictRisk> {
    const b = await loadBundle();
    return computeRisk(id, b);
  }

  async getForecast(id: string) {
    const b = await loadBundle();
    const risk = computeRisk(id, b);
    const hours: ForecastHour[] = Array.from({ length: 72 }, (_, i) => {
      const ts = new Date(Date.now() + i * 3_600_000).toISOString();
      const jitter = Math.sin(i / 6) * 8;
      const rain = Math.max(0, 12 + jitter + (id === "patna" ? 4 : 0));
      const r = Math.round(Math.min(100, Math.max(5, risk.risk * 0.9 + jitter)));
      return { ts, rain_mm: Math.round(rain * 10) / 10, temp_c: 30.5, humidity: 88, wind_kph: 18, risk: r, risk_level: (r >= 85 ? "severe" : r >= 70 ? "high" : r >= 40 ? "moderate" : "low") as ForecastHour["risk_level"] };
    });
    return { district_id: id, weather_source: "simulated", hours };
  }

  /* ---------------- Volunteers & tasks ---------------- */
  private async allVolunteers(): Promise<Volunteer[]> {
    const b = await loadBundle();
    const added = lsGet<Volunteer[]>(LS.volunteersAdd, []);
    const patches = lsGet<Record<string, Partial<Volunteer>>>(LS.volunteersPatch, {});
    const byId = new Map(b.volunteers.map((v) => [v.id, { ...v }]));
    for (const [id, p] of Object.entries(patches)) { const cur = byId.get(id); if (cur) byId.set(id, { ...cur, ...p }); }
    for (const v of added) byId.set(v.id, v);
    return [...byId.values()];
  }

  async registerVolunteer(input: RegisterVolunteerInput): Promise<Volunteer> {
    const now = new Date().toISOString();
    const v: Volunteer = {
      id: `vol-${Date.now().toString(36)}`, name: input.name, phone: input.phone,
      district_id: input.district_id, lat: input.lat ?? null, lon: input.lon ?? null,
      skills: input.skills, languages: input.languages, availability: input.availability,
      active: input.active ?? true, reputation: 50, tasks_completed: 0, avg_response_min: null, created_at: now,
    };
    const added = lsGet<Volunteer[]>(LS.volunteersAdd, []);
    lsSet(LS.volunteersAdd, [...added, v]);
    this.audit(`device:${getDeviceId()}`, "volunteer.registered", "volunteer", v.id, {});
    this.emit("volunteer.registered", v, [v.district_id]);
    return v;
  }

  async listVolunteers(p: ListVolunteersParams): Promise<Paginated<Volunteer>> {
    let items = await this.allVolunteers();
    if (p.district) items = items.filter((v) => v.district_id === p.district);
    if (p.skill) items = items.filter((v) => v.skills.includes(p.skill!));
    if (p.language) items = items.filter((v) => v.languages.includes(p.language!));
    if (p.available_now) items = items.filter((v) => v.active && v.availability === "anytime");
    if (p.active != null) items = items.filter((v) => v.active === p.active);
    return paginate(items, p.limit ?? 20, p.offset ?? 0);
  }

  async getVolunteer(id: string): Promise<Volunteer> {
    const v = (await this.allVolunteers()).find((x) => x.id === id);
    if (!v) throw Object.assign(new Error("not found"), { status: 404 });
    return v;
  }

  async updateVolunteer(id: string, patch: Partial<Volunteer>): Promise<Volunteer> {
    const v = await this.getVolunteer(id);
    const updated = { ...v, ...patch };
    const patches = lsGet<Record<string, Partial<Volunteer>>>(LS.volunteersPatch, {});
    patches[id] = { ...(patches[id] ?? {}), ...patch };
    lsSet(LS.volunteersPatch, patches);
    return updated;
  }

  /* Wave 3 (Agent 8): reputation read-model, mirrored from the backend formula. */
  async getVolunteerReputation(id: string) {
    const v = await this.getVolunteer(id);
    return reputationDetailOf(v);
  }

  /* Wave 3 (Agent 8): demo-mode photo upload — object URL, no network. */
  async uploadMedia(file: File) {
    const photo_id = `demo-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
    const url = URL.createObjectURL(file);
    demoMedia.set(photo_id, url);
    return { photo_id, url, photo_hash: "demo" };
  }

  async matchVolunteers(sosId: string, maxResults = 5, maxDistanceKm = 25) {
    const sos = await this.getSOS(sosId);
    const vols = (await this.allVolunteers()).filter((v) => v.active && v.lat != null && v.lon != null && sos.lat != null && sos.lon != null);
    const matches = vols
      .map((v): VolunteerMatch | null => {
        const distanceKm = haversineKm(sos.lat!, sos.lon!, v.lat!, v.lon!);
        if (distanceKm > maxDistanceKm) return null;
        const { score, reasons } = matchScore({
          neededSkills: sos.needed_skills, volunteerSkills: v.skills,
          distanceKm, maxDistanceKm,
          availableNow: v.availability === "anytime" && v.active,
          reputation: v.reputation,
        });
        // Wave 3 (Agent 8): breakdown parity with the backend's score_breakdown.
        const needed = sos.needed_skills ?? [];
        const skillMatch = needed.length === 0 ? 1 : needed.filter((s) => v.skills.includes(s)).length / needed.length;
        return {
          volunteer: v, score, distance_km: Math.round(distanceKm * 10) / 10, reasons,
          score_breakdown: {
            skill: Math.round(skillMatch * 1000) / 1000,
            distance: Math.round(Math.max(0, 1 - distanceKm / maxDistanceKm) * 1000) / 1000,
            availability: v.availability === "anytime" && v.active ? 1 : 0.3,
            reputation: Math.round(Math.min(1, Math.max(0, v.reputation / 100)) * 1000) / 1000,
          },
        };
      })
      .filter((m): m is VolunteerMatch => m !== null)
      .sort((a, b) => b.score - a.score)
      .slice(0, maxResults);
    return { sos_id: sosId, matches };
  }

  private async allTasks(): Promise<Task[]> {
    return lsGet<Task[]>(LS.tasks, []);
  }
  private saveTask(t: Task) {
    const tasks = lsGet<Task[]>(LS.tasks, []);
    lsSet(LS.tasks, [...tasks.filter((x) => x.id !== t.id), t]);
  }

  async createTask(sosId: string, volunteerId: string, note?: string): Promise<Task> {
    const tasks = await this.allTasks();
    const active = tasks.find((t) => t.sos_id === sosId && t.volunteer_id === volunteerId && !["completed", "declined", "cancelled"].includes(t.status));
    if (active) throw Object.assign(new Error("duplicate task"), { status: 409 });
    const now = new Date().toISOString();
    const t: Task = { id: `task-${Date.now().toString(36)}`, sos_id: sosId, volunteer_id: volunteerId, status: "assigned", note: note ?? null, assigned_at: now, accepted_at: null, completed_at: null, proof_photo_url: null, created_at: now, updated_at: now };
    this.saveTask(t);
    this.audit("admin:demo", "task.assigned", "task", t.id, { sos_id: sosId, volunteer_id: volunteerId });
    const v = await this.getVolunteer(volunteerId).catch(() => null);
    const sos = await this.getSOS(sosId);
    this.emit("task.assigned", { ...t, volunteer: v }, sos.district_id ? [sos.district_id] : []);
    return t;
  }

  async listTasks(p: ListTasksParams): Promise<Paginated<Task>> {
    let items = await this.allTasks();
    if (p.volunteer_id) items = items.filter((t) => t.volunteer_id === p.volunteer_id);
    if (p.sos_id) items = items.filter((t) => t.sos_id === p.sos_id);
    if (p.status) items = items.filter((t) => t.status === p.status);
    if (p.district) {
      const sos = await this.allSOS();
      const ids = new Set(sos.filter((r) => r.district_id === p.district).map((r) => r.id));
      items = items.filter((t) => ids.has(t.sos_id));
    }
    items = [...items].sort((a, b) => b.created_at.localeCompare(a.created_at));
    return paginate(items, p.limit ?? 20, p.offset ?? 0);
  }

  async getTask(id: string): Promise<Task> {
    const t = (await this.allTasks()).find((x) => x.id === id);
    if (!t) throw Object.assign(new Error("not found"), { status: 404 });
    const volunteer = await this.getVolunteer(t.volunteer_id).catch(() => undefined);
    const sos = await this.getSOS(t.sos_id).catch(() => undefined);
    return {
      ...t,
      volunteer,
      sos: sos ? { id: sos.id, description: sos.description, severity: sos.severity, category: sos.category, priority: sos.priority, lat: sos.lat, lon: sos.lon, district_id: sos.district_id, status: sos.status } : undefined,
    };
  }

  async taskAction(id: string, action: "accept" | "decline" | "enroute" | "complete" | "cancel", body: Record<string, unknown> = {}): Promise<Task> {
    const tasks = await this.allTasks();
    const t = tasks.find((x) => x.id === id);
    if (!t) throw Object.assign(new Error("not found"), { status: 404 });
    const next: Record<string, TaskStatus[]> = {
      assigned: ["accepted", "declined", "cancelled"], accepted: ["en_route", "declined", "cancelled"],
      en_route: ["completed", "cancelled"], declined: [], completed: [], cancelled: [],
    };
    const to: Record<string, TaskStatus> = { accept: "accepted", decline: "declined", enroute: "en_route", complete: "completed", cancel: "cancelled" };
    const target = to[action];
    if (!next[t.status].includes(target)) throw Object.assign(new Error(`illegal transition ${t.status} → ${target}`), { status: 400 });
    const now = new Date().toISOString();
    const updated: Task = { ...t, status: target, updated_at: now };
    if (action === "accept") updated.accepted_at = now;
    if (action === "complete") {
      updated.completed_at = now;
      updated.note = (body.note as string) ?? updated.note;
      // Wave 3 (Agent 8): optional photo proof, minted by uploadMedia.
      const proofId = body.proof_photo_id as string | undefined;
      const proofUrl = proofId ? demoMedia.get(proofId) : undefined;
      if (proofUrl) updated.proof_photo_url = proofUrl;
    }
    this.saveTask(updated);
    this.audit(`device:${getDeviceId()}`, `task.${action}`, "task", id, {});
    const sos = await this.getSOS(t.sos_id).catch(() => null);
    this.emit("task.updated", { task_id: id, sos_id: t.sos_id, from: t.status, to: target }, sos?.district_id ? [sos.district_id] : []);
    if (action === "enroute" && sos && sos.status === "verified") {
      const s2 = { ...sos, status: "help_on_way" as SOSStatus, updated_at: now };
      this.persistSOS(s2, false);
      this.emit("sos.status_changed", { sos_id: sos.id, from: "verified", to: "help_on_way" }, [sos.district_id!]);
    }
    if (action === "complete") {
      // Reputation +2 (cap 100); SOS → resolved when no other active tasks.
      const v = await this.getVolunteer(t.volunteer_id).catch(() => null);
      if (v) {
        const patches = lsGet<Record<string, Partial<Volunteer>>>(LS.volunteersPatch, {});
        const cur = { ...(patches[t.volunteer_id] ?? {}) };
        const rep = Math.min(100, (cur.reputation ?? v.reputation) + 2);
        const done = (cur.tasks_completed ?? v.tasks_completed) + 1;
        patches[t.volunteer_id] = { ...cur, reputation: rep, tasks_completed: done };
        lsSet(LS.volunteersPatch, patches);
      }
      const rest = (await this.allTasks()).filter((x) => x.sos_id === t.sos_id && x.id !== t.id && !["completed", "declined", "cancelled"].includes(x.status));
      if (rest.length === 0 && sos && sos.status !== "resolved") {
        const s2 = { ...sos, status: "resolved" as SOSStatus, updated_at: now };
        this.persistSOS(s2, false);
        this.emit("sos.status_changed", { sos_id: sos.id, from: sos.status, to: "resolved" }, [sos.district_id!]);
      }
    }
    return this.getTask(id);
  }

  /* ---------------- Alerts ---------------- */
  async broadcast(input: BroadcastInput): Promise<BroadcastResult> {
    const b = await loadBundle();
    const langs = input.languages?.length ? input.languages : ["hi", "hing", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa"];
    const template = b.templates[input.type]?.templates as Record<string, string> | undefined;
    const rendered: Record<string, string> = {};
    for (const lang of langs) {
      if (template?.[lang] && !input.body.trim()) {
        rendered[lang] = template[lang]
          .replaceAll("{district}", lang === "hi" || lang === "mr" ? DISTRICT_HI[input.district_ids[0]] ?? input.district_ids[0] : input.district_ids[0])
          .replaceAll("{helpline}", "1078").replaceAll("{temp}", "45").replaceAll("{wind}", "110");
      } else {
        // Novel alert: compose from title + body, length-checked ≤ 480.
        const prefix = template?.[lang]?.split(":")[0] ?? input.type;
        const msg = `${prefix}: ${input.body}`.slice(0, 480);
        rendered[lang] = msg;
      }
    }
    const now = new Date().toISOString();
    const alert: AlertItem = {
      id: `alert-${Date.now().toString(36)}`, district_ids: input.district_ids, type: input.type,
      severity: input.severity, languages: langs, message: rendered[input.languages?.[0] ?? "hi"] ?? rendered.hi,
      messages: rendered, created_at: now,
    };
    const alerts = lsGet<AlertItem[]>(LS.alerts, []);
    lsSet(LS.alerts, [alert, ...alerts].slice(0, 200));
    this.audit("admin:demo", "alert.broadcast", "alert", alert.id, { districts: input.district_ids, languages: langs });
    this.emit("alert.broadcast", { broadcast_id: alert.id, district_ids: input.district_ids, type: input.type, severity: input.severity, languages: langs }, input.district_ids);
    return { broadcast_id: alert.id, status: "sent", rendered, recipient_estimate: input.district_ids.length * 12400, created_at: now };
  }

  private async seedAlerts(): Promise<AlertItem[]> {
    // A few canned historical alerts so the feed isn't empty in demo mode.
    const b = await loadBundle();
    const t = b.templates.flood.templates as Record<string, string>;
    const mk = (id: string, district: string, hoursAgo: number): AlertItem => {
      const messages: Record<string, string> = {};
      for (const [lang, tpl] of Object.entries(t)) {
        messages[lang] = tpl.replaceAll("{district}", lang === "hi" || lang === "mr" ? DISTRICT_HI[district] ?? district : district).replaceAll("{helpline}", "1078");
      }
      return {
        id, district_ids: [district], type: "flood", severity: 4, languages: Object.keys(t),
        message: messages.hi, messages,
        created_at: new Date(Date.now() - hoursAgo * 3_600_000).toISOString(),
      };
    };
    return [mk("alert-seed-1", "patna", 5), mk("alert-seed-2", "vaishali", 9), mk("alert-seed-3", "muzaffarpur", 14)];
  }

  async listAlerts(p: ListAlertsParams): Promise<Paginated<AlertItem>> {
    const mine = lsGet<AlertItem[]>(LS.alerts, []);
    const seeded = await this.seedAlerts();
    const seen = new Set(mine.map((a) => a.id));
    let items = [...mine, ...seeded.filter((a) => !seen.has(a.id))];
    if (p.district) items = items.filter((a) => a.district_ids.includes(p.district!));
    if (p.type) items = items.filter((a) => a.type === p.type);
    if (p.lang) items = items.map((a) => ({ ...a, message: a.messages?.[p.lang!] ?? a.message }));
    items = [...items].sort((a, b) => b.created_at.localeCompare(a.created_at));
    return paginate(items, p.limit ?? 20, p.offset ?? 0);
  }

  async getAlert(id: string): Promise<AlertItem> {
    const page = await this.listAlerts({ limit: 200 });
    const a = page.items.find((x) => x.id === id);
    if (!a) throw Object.assign(new Error("not found"), { status: 404 });
    return a;
  }

  /* ---------------- Admin ---------------- */
  async adminOverview(district?: string): Promise<AdminOverview> {
    const b = await loadBundle();
    const sos = await this.allSOS();
    const vols = await this.allVolunteers();
    const tasks = await this.allTasks();
    const inD = (d?: string | null) => !district || d === district;
    const ds = sos.filter((r) => inD(r.district_id));
    const byStatus: Record<string, number> = {};
    const bySev: Record<string, number> = { "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 };
    for (const r of ds) {
      byStatus[r.status] = (byStatus[r.status] ?? 0) + 1;
      if (r.severity) bySev[String(r.severity)] = (bySev[String(r.severity)] ?? 0) + 1;
    }
    const shelters = b.shelters.filter((s) => inD(s.district_id));
    const open = shelters.filter((s) => s.occupied < s.capacity);
    const occ = shelters.reduce((a, s) => a + s.occupied, 0);
    const cap = shelters.reduce((a, s) => a + s.capacity, 0);
    const risk = district ? computeRisk(district, b) : { risk: 0, risk_level: "low" as const };
    const activeIds = new Set(tasks.filter((t) => !["completed", "declined", "cancelled"].includes(t.status)).map((t) => t.volunteer_id));
    return {
      district_id: district ?? null,
      sos_by_status: byStatus, sos_by_severity: bySev,
      active_tasks: tasks.filter((t) => !["completed", "declined", "cancelled"].includes(t.status)).length,
      volunteers_active: vols.filter((v) => v.active && inD(v.district_id)).length,
      volunteers_on_task: vols.filter((v) => activeIds.has(v.id) && inD(v.district_id)).length,
      shelters_open: open.length,
      shelter_occupancy_pct: cap ? Math.round((occ / cap) * 1000) / 10 : 0,
      district_risk: risk.risk, risk_level: risk.risk_level,
      pending_verifications: ds.filter((r) => r.status === "reported" || r.needs_review).length,
      open_safety_flags: lsGet<SafetyFlag[]>(LS.flags, []).filter((f) => f.status === "open").length,
      generated_at: new Date().toISOString(),
    };
  }

  async verifyQueue(limit = 20, offset = 0): Promise<Paginated<SOSReport>> {
    const items = (await this.allSOS())
      .filter((r) => r.needs_review || r.status === "reported")
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
    return paginate(items, limit, offset);
  }

  async safetyFlags(): Promise<SafetyFlag[]> {
    return lsGet<SafetyFlag[]>(LS.flags, []);
  }

  async resolveFlag(id: string, resolution: string, note?: string): Promise<SafetyFlag> {
    const flags = lsGet<SafetyFlag[]>(LS.flags, []);
    const f = flags.find((x) => x.id === id);
    if (!f) throw Object.assign(new Error("not found"), { status: 404 });
    const updated = { ...f, status: resolution };
    lsSet(LS.flags, flags.map((x) => (x.id === id ? updated : x)));
    this.audit("admin:demo", "safety.flag_resolved", "flag", id, { resolution, note });
    return updated;
  }

  async adminAudit(limit = 50, offset = 0): Promise<AuditEntry[]> {
    const log = lsGet<AuditEntry[]>(LS.audit, []);
    return [...log].reverse().slice(offset, offset + limit);
  }

  /** Wave 4 (Agent 11): real PDF incident report built client-side from the
   *  seeded bundle + localStorage deltas — the demo video records against
   *  this path (no backend). Never a fake download. */
  async exportIncidentPdf(district: string): Promise<Blob> {
    const { buildIncidentPdf } = await import("./pdf");
    const b = await loadBundle();
    const d = b.districts.find((x) => x.id === district);
    const risk = await this.getDistrictRisk(district);
    const sosPage = await this.listSOS({ district, limit: 500, sort: "-created_at" });
    const tasksPage = await this.listTasks({ district, limit: 200 });
    const alertsPage = await this.listAlerts({ district, limit: 100 });
    const audit = await this.adminAudit(200);
    const vols = await this.allVolunteers();
    const vName = new Map(vols.map((v) => [v.id, v.name]));
    const bytes = await buildIncidentPdf({
      district: { id: district, name: d?.name ?? district, state: d?.state },
      exportedAt: new Date().toISOString(),
      exportedBy: "admin:demo",
      risk: {
        risk: risk.risk, risk_level: risk.risk_level,
        weather_source: risk.weather_source, computed_at: risk.computed_at,
        factors: risk.factors.map((f) => ({ name: f.name, value: String(f.value ?? ""), contribution: f.contribution })),
      },
      sos: sosPage.items.map((r) => ({
        id: r.id, severity: r.severity, category: r.category, status: r.status,
        district_id: r.district_id, created_at: r.created_at, description: r.description,
      })),
      tasks: tasksPage.items.map((t) => ({
        id: t.id, sos_id: t.sos_id, volunteer_id: t.volunteer_id,
        volunteer_name: vName.get(t.volunteer_id), status: t.status,
      })),
      alerts: alertsPage.items.map((a) => ({
        id: a.id, type: a.type, severity: a.severity, languages: a.languages,
        messages: a.messages ?? { [a.languages[0] ?? "en"]: a.message },
        created_at: a.created_at,
      })),
      audit: audit.map((e) => ({ ts: e.ts, actor: e.actor, action: e.action })),
    });
    return new Blob([bytes as BlobPart], { type: "application/pdf" });
  }

  async warningsStatus(): Promise<WarningsStatus> {
    const b = await loadBundle();
    return {
      enabled: true, mode: "simulated", weather_api: "https://api.open-meteo.com/v1/forecast",
      districts_tracked: b.districts.length,
      last_ingest_at: new Date().toISOString(), last_ingest_ok: true,
      last_risk_recompute_at: new Date().toISOString(),
      next_ingest_at: new Date(Date.now() + 900_000).toISOString(),
    };
  }
}

/* ------------------------------------------------------------------ */
/* Demo director lite — "▶ Play Patna flood demo"                       */
/* ------------------------------------------------------------------ */

export const DEMO_FIXTURE = {
  description: "पटना के कंकड़बाग इलाके में घुटनों तक पानी भर गया है। दो गलियों में घरों में पानी घुस गया है, बुजुर्ग छत पर हैं। तुरंत मदद चाहिए।",
  lat: 25.5941,
  lon: 85.1376,
  district_id: "patna",
  volunteer_id: "vol-ravi-kumar-patna",
};

export function resetDemo() {
  for (const k of Object.values(LS)) localStorage.removeItem(k);
  if (typeof window !== "undefined") window.dispatchEvent(new Event("sahayta:demo-reset"));
}

export type DemoStep = { key: string; done: boolean };

/**
 * Plays the 14-step Patna scenario on a timeline (~35 s). Calls onStep after
 * each beat so the landing page can show progress. Idempotent: replays create
 * a fresh SOS each run (new client_report_id) — resetDemo() clears history.
 */
export async function playPatnaDemo(api: DemoApiClient, onStep: (steps: DemoStep[]) => void): Promise<void> {
  const steps: DemoStep[] = [
    { key: "report", done: false }, { key: "assess", done: false },
    { key: "match", done: false }, { key: "accept", done: false },
    { key: "enroute", done: false }, { key: "complete", done: false },
    { key: "broadcast", done: false }, { key: "dashboard", done: false },
  ];
  const mark = (i: number) => { steps[i].done = true; onStep([...steps]); };
  const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

  // 1. Citizen reports the fixture SOS.
  const report = await api.createSOS({
    description: DEMO_FIXTURE.description,
    lat: DEMO_FIXTURE.lat, lon: DEMO_FIXTURE.lon,
    district_id: DEMO_FIXTURE.district_id,
    language: "hi", reporter_name: "Demo Citizen",
    client_report_id: `demo-director-${Date.now()}`,
    photo_description: "Waist-deep water across a residential lane in Kankarbagh; residents on rooftops.",
  });
  mark(0); mark(1);
  await wait(2500);

  // 2. Match → Ravi Kumar (anchor volunteer, ~2.1 km, score ≥ 80 by construction).
  const { matches } = await api.matchVolunteers(report.id, 5, 25);
  const ravi = matches.find((m) => m.volunteer.id === DEMO_FIXTURE.volunteer_id) ?? matches[0];
  const task = await api.createTask(report.id, ravi.volunteer.id, "Nearest rescue volunteer");
  mark(2);
  await wait(2500);

  // 3. Verify first (so enroute flips help_on_way per the backend rule).
  await api.verifySOS(report.id, "verified", null, "Demo: field team confirmed");
  await api.taskAction(task.id, "accept");
  mark(3);
  await wait(2500);

  await api.taskAction(task.id, "enroute");
  mark(4);
  await wait(3000);

  await api.taskAction(task.id, "complete", { note: "Residents moved to relief camp" });
  mark(5);
  await wait(2000);

  // 4. Hindi + Hinglish broadcast.
  await api.broadcast({
    district_ids: ["patna"], type: "flood",
    title: "बाढ़ चेतावनी",
    body: "पटना के कंकड़बाग इलाके में पानी बढ़ रहा है। तुरंत ऊँची जगह जाएँ। राहत शिविर खुले हैं। हेल्पलाइन: 1078",
    severity: 4, languages: ["hi", "hing"],
  });
  mark(6); mark(7);
}
