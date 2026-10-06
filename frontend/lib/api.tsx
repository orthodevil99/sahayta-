"use client";
/**
 * Typed API client — implements docs/api-contracts.md EXACTLY.
 * Two backends behind one interface:
 *   - RestApiClient: talks to the FastAPI backend (Agent 5). Base URL from
 *     NEXT_PUBLIC_API_URL. Auth via X-Device-Id (guest) + X-Admin-Key (admin).
 *   - DemoApiClient (lib/demo.ts, lazy-loaded): seeded demo mode, reads the
 *     bundled data/*.json + localStorage, needs NO backend — this is what the
 *     demo video records against.
 * Mode selection: ?demo=1 (or localStorage sahayta.demo=1) forces demo;
 * otherwise NEXT_PUBLIC_API_URL set → REST; unset → demo (safe default).
 */
import type {
  AdminOverview, AlertItem, AlertType, AuditEntry, BroadcastResult,
  District, DistrictRisk, ForecastHour, HealthStatus, LanguageMeta, Paginated,
  SafetyFlag, Severity, Shelter, SOSCreateInput, SOSFilters, SOSReport, SOSStatus,
  Task, TaskStatus, Volunteer, VolunteerMatch, VolunteerReputation, VolunteerSkill, WarningsStatus, WSEvent,
} from "./types";
import type { AssessResult } from "./demo-assess";
import { assessSeverity } from "./demo-assess";
import { getDeviceId } from "./outbox";

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(`API ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

export type ApiMode = "rest" | "demo";

export function resolveApiMode(): ApiMode {
  if (typeof window === "undefined") return "demo";
  const q = new URLSearchParams(window.location.search);
  if (q.get("demo") === "1") return "demo";
  if (localStorage.getItem("sahayta.demo") === "1") return "demo";
  if (q.get("demo") === "0" || localStorage.getItem("sahayta.demo") === "0") {
    return process.env.NEXT_PUBLIC_API_URL ? "rest" : "demo";
  }
  return process.env.NEXT_PUBLIC_API_URL ? "rest" : "demo";
}

export function setDemoMode(on: boolean) {
  localStorage.setItem("sahayta.demo", on ? "1" : "0");
}

/* ------------------------------------------------------------------ */
/* Interface — one method per contract endpoint                         */
/* ------------------------------------------------------------------ */

export interface ListSheltersParams { district?: string; q?: string; has_capacity?: boolean; facility?: string[]; limit?: number; offset?: number; }
export interface ListVolunteersParams { district?: string; skill?: VolunteerSkill; language?: string; available_now?: boolean; active?: boolean; limit?: number; offset?: number; }
export interface ListTasksParams { volunteer_id?: string; sos_id?: string; status?: TaskStatus; district?: string; limit?: number; offset?: number; }
export interface ListAlertsParams { district?: string; type?: AlertType; lang?: string; limit?: number; offset?: number; }
export interface BroadcastInput { district_ids: string[]; type: AlertType; title: string; body: string; severity: Severity; languages?: string[]; scheduled_at?: string | null; }
export interface RegisterVolunteerInput { name: string; phone?: string; district_id: string; lat?: number | null; lon?: number | null; skills: VolunteerSkill[]; languages: string[]; availability: "anytime" | Array<{ day: string; start: string; end: string }>; active?: boolean; }

export interface SahaytaApi {
  readonly mode: ApiMode;
  health(): Promise<HealthStatus>;
  metaLanguages(): Promise<{ languages: LanguageMeta[] }>;
  // SOS
  listSOS(f: SOSFilters): Promise<Paginated<SOSReport>>;
  getSOS(id: string): Promise<SOSReport>;
  createSOS(input: SOSCreateInput): Promise<SOSReport>;
  updateSOSStatus(id: string, status: SOSStatus, note?: string): Promise<SOSReport>;
  verifySOS(id: string, verdict: "verified" | "rejected" | "duplicate", duplicateOf?: string | null, note?: string): Promise<SOSReport>;
  flagSOS(id: string, reason: string, note?: string): Promise<{ id: string; status: string }>;
  assess(description: string, language?: string, lat?: number, lon?: number): Promise<AssessResult>;
  // Shelters & districts
  listShelters(p: ListSheltersParams): Promise<Paginated<Shelter>>;
  getDistricts(): Promise<District[]>;
  getDistrictRisk(id: string): Promise<DistrictRisk>;
  getForecast(id: string): Promise<{ district_id: string; weather_source: string; hours: ForecastHour[] }>;
  // Volunteers & tasks
  registerVolunteer(input: RegisterVolunteerInput): Promise<Volunteer>;
  listVolunteers(p: ListVolunteersParams): Promise<Paginated<Volunteer>>;
  getVolunteer(id: string): Promise<Volunteer>;
  updateVolunteer(id: string, patch: Partial<Pick<Volunteer, "active" | "skills" | "languages" | "availability" | "lat" | "lon">>): Promise<Volunteer>;
  matchVolunteers(sosId: string, maxResults?: number, maxDistanceKm?: number): Promise<{ sos_id: string; matches: VolunteerMatch[] }>;
  createTask(sosId: string, volunteerId: string, note?: string): Promise<Task>;
  listTasks(p: ListTasksParams): Promise<Paginated<Task>>;
  getTask(id: string): Promise<Task>;
  taskAction(id: string, action: "accept" | "decline" | "enroute" | "complete" | "cancel", body?: Record<string, unknown>): Promise<Task>;
  /** Wave 3 (Agent 8): full reputation read-model for a volunteer. */
  getVolunteerReputation(id: string): Promise<VolunteerReputation>;
  /** Wave 3 (Agent 8): upload a photo via POST /api/media, returns {photo_id, url, photo_hash}. */
  uploadMedia(file: File): Promise<{ photo_id: string; url: string; photo_hash: string }>;
  // Alerts
  broadcast(input: BroadcastInput): Promise<BroadcastResult>;
  listAlerts(p: ListAlertsParams): Promise<Paginated<AlertItem>>;
  getAlert(id: string): Promise<AlertItem>;
  // Admin
  adminOverview(district?: string): Promise<AdminOverview>;
  verifyQueue(limit?: number, offset?: number): Promise<Paginated<SOSReport>>;
  safetyFlags(): Promise<SafetyFlag[]>;
  resolveFlag(id: string, resolution: string, note?: string): Promise<SafetyFlag>;
  adminAudit(limit?: number, offset?: number): Promise<AuditEntry[]>;
  warningsStatus(): Promise<WarningsStatus>;
  /** Wave 4 (Agent 11): real PDF incident report — REST downloads the
   *  server-rendered file, demo builds it client-side from seed data. */
  exportIncidentPdf(district: string): Promise<Blob>;
  // Realtime — unified subscribe; REST uses WS, demo uses a local emitter.
  subscribe(cb: (e: WSEvent) => void, districts?: string[]): () => void;
  /** Admin key management (demo key convenience). */
  getAdminKey(): string | null;
  setAdminKey(k: string | null): void;
}

/* ------------------------------------------------------------------ */
/* REST client                                                         */
/* ------------------------------------------------------------------ */

const ADMIN_LS = "sahayta.admin_key";

export class RestApiClient implements SahaytaApi {
  readonly mode: ApiMode = "rest";
  private base: string;
  constructor(base?: string) {
    this.base = (base ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
  }
  getAdminKey(): string | null { return localStorage.getItem(ADMIN_LS); }
  setAdminKey(k: string | null) { k ? localStorage.setItem(ADMIN_LS, k) : localStorage.removeItem(ADMIN_LS); }

  private headers(json = true): HeadersInit {
    const h: Record<string, string> = { "X-Device-Id": getDeviceId() };
    const admin = this.getAdminKey();
    if (admin) h["X-Admin-Key"] = admin;
    if (json) h["Content-Type"] = "application/json";
    return h;
  }

  private async req<T>(path: string, init?: RequestInit): Promise<T> {
    let res: Response;
    try {
      res = await fetch(this.base + path, { ...init, headers: { ...this.headers(), ...(init?.headers ?? {}) } });
    } catch {
      throw new ApiError(0, "network unreachable");
    }
    if (!res.ok) {
      let detail = res.statusText;
      try { const j = await res.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* keep */ }
      throw new ApiError(res.status, detail);
    }
    if (res.status === 204) return undefined as unknown as T;
    return res.json() as Promise<T>;
  }

  private qs(params: Record<string, unknown>): string {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === "") continue;
      if (Array.isArray(v)) v.forEach((x) => sp.append(k, String(x)));
      else sp.set(k, String(v));
    }
    const s = sp.toString();
    return s ? `?${s}` : "";
  }

  health() { return this.req<HealthStatus>("/api/health"); }
  metaLanguages() { return this.req<{ languages: LanguageMeta[] }>("/api/meta/languages"); }

  listSOS(f: SOSFilters) { return this.req<Paginated<SOSReport>>("/api/sos" + this.qs(f as Record<string, unknown>)); }
  getSOS(id: string) { return this.req<SOSReport>(`/api/sos/${id}`); }

  async createSOS(input: SOSCreateInput): Promise<SOSReport> {
    // Online path: real POST. Offline is handled by the caller (outbox) —
    // this method assumes connectivity.
    if (input.photo) {
      const fd = new FormData();
      fd.append("photo", input.photo);
      fd.append("description", input.description);
      if (input.lat != null) fd.append("lat", String(input.lat));
      if (input.lon != null) fd.append("lon", String(input.lon));
      if (input.district_id) fd.append("district_id", input.district_id);
      if (input.language) fd.append("language", input.language);
      if (input.reporter_name) fd.append("reporter_name", input.reporter_name);
      if (input.reporter_phone) fd.append("reporter_phone", input.reporter_phone);
      fd.append("client_report_id", input.client_report_id);
      const res = await fetch(this.base + "/api/sos", { method: "POST", headers: { "X-Device-Id": getDeviceId(), ...(this.getAdminKey() ? { "X-Admin-Key": this.getAdminKey()! } : {}) }, body: fd });
      if (!res.ok) throw new ApiError(res.status, res.statusText);
      return res.json();
    }
    return this.req<SOSReport>("/api/sos", {
      method: "POST",
      body: JSON.stringify({
        description: input.description,
        photo_description: input.photo_description,
        lat: input.lat, lon: input.lon,
        district_id: input.district_id,
        language: input.language,
        reporter_name: input.reporter_name,
        reporter_phone: input.reporter_phone,
        client_report_id: input.client_report_id,
      }),
    });
  }

  updateSOSStatus(id: string, status: SOSStatus, note?: string) {
    return this.req<SOSReport>(`/api/sos/${id}`, { method: "PATCH", body: JSON.stringify({ status, note }) });
  }
  verifySOS(id: string, verdict: "verified" | "rejected" | "duplicate", duplicateOf?: string | null, note?: string) {
    return this.req<SOSReport>(`/api/sos/${id}/verify`, { method: "POST", body: JSON.stringify({ verdict, duplicate_of: duplicateOf ?? null, note }) });
  }
  flagSOS(id: string, reason: string, note?: string) {
    return this.req<{ id: string; status: string }>(`/api/sos/${id}/flag`, { method: "POST", body: JSON.stringify({ reason, note }) });
  }
  assess(description: string, language = "hi", lat?: number, lon?: number) {
    return this.req<AssessResult>("/api/assess", { method: "POST", body: JSON.stringify({ description, language, lat, lon }) });
  }

  listShelters(p: ListSheltersParams) { return this.req<Paginated<Shelter>>("/api/shelters" + this.qs(p as Record<string, unknown>)); }
  getDistricts() { return this.req<District[]>("/api/districts"); }
  getDistrictRisk(id: string) { return this.req<DistrictRisk>(`/api/districts/${id}/risk`); }
  getForecast(id: string) { return this.req<{ district_id: string; weather_source: string; hours: ForecastHour[] }>(`/api/districts/${id}/forecast`); }

  registerVolunteer(input: RegisterVolunteerInput) { return this.req<Volunteer>("/api/volunteers", { method: "POST", body: JSON.stringify(input) }); }
  listVolunteers(p: ListVolunteersParams) { return this.req<Paginated<Volunteer>>("/api/volunteers" + this.qs(p as Record<string, unknown>)); }
  getVolunteer(id: string) { return this.req<Volunteer>(`/api/volunteers/${id}`); }
  updateVolunteer(id: string, patch: Partial<Volunteer>) { return this.req<Volunteer>(`/api/volunteers/${id}`, { method: "PATCH", body: JSON.stringify(patch) }); }

  matchVolunteers(sosId: string, maxResults = 5, maxDistanceKm = 25) {
    return this.req<{ sos_id: string; matches: VolunteerMatch[] }>("/api/tasks/match", { method: "POST", body: JSON.stringify({ sos_id: sosId, max_results: maxResults, max_distance_km: maxDistanceKm }) });
  }
  createTask(sosId: string, volunteerId: string, note?: string) {
    return this.req<Task>("/api/tasks", { method: "POST", body: JSON.stringify({ sos_id: sosId, volunteer_id: volunteerId, note }) });
  }
  listTasks(p: ListTasksParams) { return this.req<Paginated<Task>>("/api/tasks" + this.qs(p as Record<string, unknown>)); }
  getTask(id: string) { return this.req<Task>(`/api/tasks/${id}`); }
  getVolunteerReputation(id: string) { return this.req<VolunteerReputation>(`/api/volunteers/${id}/reputation`); }
  async uploadMedia(file: File) {
    const fd = new FormData();
    fd.append("photo", file);
    const res = await fetch(this.base + "/api/media", { method: "POST", headers: this.headers(false), body: fd });
    if (!res.ok) {
      let detail = res.statusText;
      try { const j = await res.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* keep */ }
      throw new ApiError(res.status, detail);
    }
    return res.json() as Promise<{ photo_id: string; url: string; photo_hash: string }>;
  }
  taskAction(id: string, action: "accept" | "decline" | "enroute" | "complete" | "cancel", body?: Record<string, unknown>) {
    return this.req<Task>(`/api/tasks/${id}/${action}`, { method: "POST", body: JSON.stringify(body ?? {}) });
  }

  broadcast(input: BroadcastInput) { return this.req<BroadcastResult>("/api/alerts/broadcast", { method: "POST", body: JSON.stringify(input) }); }
  listAlerts(p: ListAlertsParams) { return this.req<Paginated<AlertItem>>("/api/alerts" + this.qs(p as Record<string, unknown>)); }
  getAlert(id: string) { return this.req<AlertItem>(`/api/alerts/${id}`); }

  adminOverview(district?: string) { return this.req<AdminOverview>("/api/admin/overview" + this.qs({ district })); }
  verifyQueue(limit = 20, offset = 0) { return this.req<Paginated<SOSReport>>(`/api/admin/verify-queue${this.qs({ limit, offset })}`); }
  safetyFlags() { return this.req<SafetyFlag[]>("/api/safety/flags"); }
  resolveFlag(id: string, resolution: string, note?: string) { return this.req<SafetyFlag>(`/api/admin/safety/flags/${id}/resolve`, { method: "POST", body: JSON.stringify({ resolution, note }) }); }
  adminAudit(limit = 50, offset = 0) { return this.req<AuditEntry[]>(`/api/admin/audit${this.qs({ limit, offset })}`); }
  warningsStatus() { return this.req<WarningsStatus>("/api/warnings/status"); }

  async exportIncidentPdf(district: string): Promise<Blob> {
    let res: Response;
    try {
      res = await fetch(this.base + `/api/admin/incidents/${encodeURIComponent(district)}/export?format=pdf`, { headers: this.headers(false) });
    } catch {
      throw new ApiError(0, "network unreachable");
    }
    if (!res.ok) {
      let detail = res.statusText;
      try { const j = await res.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* keep */ }
      throw new ApiError(res.status, detail);
    }
    return res.blob();
  }

  subscribe(cb: (e: WSEvent) => void, districts?: string[]): () => void {
    const wsBase = this.base.replace(/^http/, "ws");
    const admin = this.getAdminKey();
    const url = `${wsBase}/api/stream?device_id=${getDeviceId()}${admin ? `&admin_key=${encodeURIComponent(admin)}` : ""}`;
    let ws: WebSocket | null = null;
    let closed = false;
    let lastEventId = 0;
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    const onMessage = (raw: string) => {
      try {
        const e = JSON.parse(raw) as WSEvent;
        if (typeof e.event_id === "number") lastEventId = Math.max(lastEventId, e.event_id);
        if (districts && districts.length > 0) {
          const d = (e.data as { district_id?: string; district_ids?: string[] }) ?? {};
          const ids = d.district_ids ?? (d.district_id ? [d.district_id] : []);
          if (ids.length > 0 && !ids.some((id) => districts.includes(id))) return;
        }
        cb(e);
      } catch { /* ignore malformed */ }
    };

    const startPollFallback = () => {
      if (pollTimer) return;
      // Silent REST poll ?since= every 15 s while WS is down (wireframe sos-board).
      pollTimer = setInterval(async () => {
        try {
          const since = new Date(Date.now() - 20_000).toISOString();
          const page = await this.listSOS({ since, limit: 20, sort: "-created_at" });
          for (const r of page.items) onMessage(JSON.stringify({ event_id: ++lastEventId, type: "sos.created", ts: r.created_at, data: r }));
        } catch { /* stay silent */ }
      }, 15_000);
    };

    const connect = () => {
      if (closed) return;
      try {
        ws = new WebSocket(url);
      } catch { startPollFallback(); return; }
      ws.onopen = () => {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
        ws?.send(JSON.stringify({ type: "ping" }));
        if (districts?.length) ws?.send(JSON.stringify({ type: "subscribe", districts }));
        if (lastEventId > 0) ws?.send(JSON.stringify({ type: "resync", last_event_id: lastEventId }));
      };
      ws.onmessage = (m) => onMessage(String(m.data));
      ws.onclose = () => { if (!closed) { startPollFallback(); setTimeout(connect, 3000); } };
      ws.onerror = () => { try { ws?.close(); } catch { /* */ } };
    };
    connect();
    return () => { closed = true; if (pollTimer) clearInterval(pollTimer); try { ws?.close(); } catch { /* */ } };
  }
}

/* ------------------------------------------------------------------ */
/* Factory (async — demo client is code-split)                           */
/* ------------------------------------------------------------------ */

import React from "react";

const ApiCtx = React.createContext<{ api: SahaytaApi | null; mode: ApiMode; loading: boolean }>({
  api: null, mode: "demo", loading: true,
});

export function useApi() {
  return React.useContext(ApiCtx);
}

export function ApiProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<{ api: SahaytaApi | null; mode: ApiMode; loading: boolean }>({
    api: null, mode: "demo", loading: true,
  });
  React.useEffect(() => {
    let alive = true;
    (async () => {
      const mode = resolveApiMode();
      if (mode === "rest") {
        if (alive) setState({ api: new RestApiClient(), mode, loading: false });
      } else {
        const { DemoApiClient } = await import("./demo");
        if (alive) setState({ api: new DemoApiClient(), mode, loading: false });
      }
    })();
    // Re-resolve when demo mode is toggled from the banner.
    const onToggle = () => {
      const mode = resolveApiMode();
      if (mode === "rest") setState({ api: new RestApiClient(), mode, loading: false });
      else import("./demo").then(({ DemoApiClient }) => setState({ api: new DemoApiClient(), mode, loading: false }));
    };
    window.addEventListener("sahayta:demo-toggle", onToggle);
    return () => window.removeEventListener("sahayta:demo-toggle", onToggle);
  }, []);
  return <ApiCtx.Provider value={state}>{children}</ApiCtx.Provider>;
}

/** Client-side assess fallback shared by demo + offline paths (re-export). */
export { assessSeverity };
