"use client";
/**
 * /admin — command dashboard (wireframes/admin-dashboard.md).
 * Wave 4 Agent 11: fleshed-out district-official view — KPI row, live SOS map,
 * risk panel, volunteer board (reputation tiers + on-task), multilingual
 * broadcast composer, verify queue (reason + trust tier + duplicate merge),
 * safety flags (full records + resolve), incident timeline, real PDF export.
 * Role-gated via X-Admin-Key. Panels fail independently.
 */
import { Download, KeyRound, Lock } from "lucide-react";
import dynamic from "next/dynamic";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ApiError, useApi } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import { timeAgo } from "../../lib/format";
import { useToast } from "../../components/Toast";
import BottomSheet from "../../components/BottomSheet";
import BroadcastComposer from "../../components/BroadcastComposer";
import { DemoDataChip, SimulatedFeedChip } from "../../components/HonestyChip";
import RiskGauge from "../../components/RiskGauge";
import SeverityBadge from "../../components/SeverityBadge";
import SOSCard from "../../components/SOSCard";
import { CardSkeleton, SectionTitle, SkeletonList } from "../../components/ui";
import type { AdminOverview, AuditEntry, District, DistrictRisk, SafetyFlag, SOSReport, Task, Volunteer, WSEvent } from "../../lib/types";

const SosMap = dynamic(() => import("../../components/SosMap"), { ssr: false, loading: () => <div className="shimmer h-[380px] rounded-card" /> });

function Panel({ title, children, onRetry, loading }: { title: string; children: React.ReactNode; onRetry?: () => void; loading?: boolean }) {
  const { t } = useI18n();
  return (
    <section className="card p-4">
      <h3 className="mb-3 text-[16px] font-bold text-ink">{title}</h3>
      {loading ? <CardSkeleton /> : children}
      {onRetry && <button onClick={onRetry} className="btn-secondary mt-2 min-h-[44px] px-4 text-[14px]">⚠ {t("common.retry")}</button>}
    </section>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card p-3 text-center">
      <div className="num-ltr num-big text-ink">{value}</div>
      <div className="text-[13px] font-medium text-muted">{label}</div>
      {sub && <div className="text-[12px] text-muted">{sub}</div>}
    </div>
  );
}

const TIER_EMOJI: Record<string, string> = { trusted: "🛡️", standard: "✓", new: "🆕", flagged: "⚠️" };

function AdminInner() {
  const { t } = useI18n();
  const { api, mode, loading: apiLoading } = useApi();
  const { toast } = useToast();
  const params = useSearchParams();
  const [unlocked, setUnlocked] = useState(false);
  const [keyInput, setKeyInput] = useState("");
  const [keyError, setKeyError] = useState(false);
  const [district, setDistrict] = useState(params.get("district") ?? "patna");
  const [districts, setDistricts] = useState<District[]>([]);
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [risk, setRisk] = useState<DistrictRisk | null>(null);
  const [sos, setSos] = useState<SOSReport[]>([]);
  const [volunteers, setVolunteers] = useState<Volunteer[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [verifyQ, setVerifyQ] = useState<SOSReport[]>([]);
  const [flags, setFlags] = useState<SafetyFlag[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [tab, setTab] = useState<"map" | "verify" | "flags">("map");
  const [failures, setFailures] = useState<Record<string, boolean>>({});
  const [busyVerify, setBusyVerify] = useState<string | null>(null);
  const [busyFlag, setBusyFlag] = useState<string | null>(null);
  const [busyPdf, setBusyPdf] = useState(false);
  const [dupOf, setDupOf] = useState<Record<string, string>>({});
  const [flagRes, setFlagRes] = useState<Record<string, string>>({});
  const [flagNote, setFlagNote] = useState<Record<string, string>>({});

  useEffect(() => {
    if (apiLoading || !api) return;
    if (mode === "demo" || api.getAdminKey() === "demo-admin-key") setUnlocked(true);
    else if (api.getAdminKey()) {
      // Validate the stored key against a cheap admin endpoint.
      api.adminOverview().then(() => setUnlocked(true)).catch(() => setUnlocked(false));
    }
    api.getDistricts().then(setDistricts).catch(() => {});
  }, [api, apiLoading, mode]);

  const load = useCallback(async () => {
    if (!api || !unlocked) return;
    const fail = (k: string) => setFailures((f) => ({ ...f, [k]: true }));
    const ok = (k: string) => setFailures((f) => ({ ...f, [k]: false }));
    api.adminOverview(district).then((o) => { setOverview(o); ok("overview"); }).catch(() => fail("overview"));
    api.getDistrictRisk(district).then((r) => { setRisk(r); ok("risk"); }).catch(() => fail("risk"));
    api.listSOS({ district, limit: 100, sort: "-created_at" }).then((p) => { setSos(p.items); ok("sos"); }).catch(() => fail("sos"));
    api.listVolunteers({ district, limit: 100 }).then((p) => { setVolunteers(p.items); ok("vols"); }).catch(() => fail("vols"));
    api.listTasks({ district, limit: 200 }).then((p) => { setTasks(p.items); ok("tasks"); }).catch(() => fail("tasks"));
    api.verifyQueue(20).then((p) => { setVerifyQ(p.items.filter((r) => !district || r.district_id === district)); ok("verify"); }).catch(() => fail("verify"));
    api.safetyFlags().then((f) => { setFlags(f.filter((x) => !district || x.district_id === district)); ok("flags"); }).catch(() => fail("flags"));
    api.adminAudit(30).then(setAudit).catch(() => {});
  }, [api, unlocked, district]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!api || !unlocked) return;
    const unsub = api.subscribe((e: WSEvent) => {
      if (["sos.created", "sos.assessed", "sos.status_changed", "task.assigned", "task.updated", "alert.broadcast", "risk.updated", "safety.flag_raised"].includes(e.type)) load();
    }, [district]);
    return unsub;
  }, [api, unlocked, district, load]);

  const unlock = async () => {
    if (!api) return;
    api.setAdminKey(keyInput);
    try {
      await api.adminOverview();
      setUnlocked(true); setKeyError(false);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
        setKeyError(true);
        api.setAdminKey(null);
      } else if (mode === "demo") {
        // Demo client accepts any key — it never 401s on overview.
        setUnlocked(true);
      }
    }
  };

  const verify = async (id: string, verdict: "verified" | "rejected" | "duplicate") => {
    if (!api) return;
    setBusyVerify(id);
    try {
      await api.verifySOS(id, verdict, verdict === "duplicate" ? (dupOf[id] || null) : null);
      toast("success", t("toast.task_done"));
      load();
    } catch { toast("error", t("common.retry")); } finally { setBusyVerify(null); }
  };

  const resolveSafetyFlag = async (id: string) => {
    if (!api) return;
    setBusyFlag(id);
    try {
      await api.resolveFlag(id, flagRes[id] || "confirmed", flagNote[id] || undefined);
      toast("success", t("admin.resolve_done"));
      load();
    } catch { toast("error", t("common.retry")); } finally { setBusyFlag(null); }
  };

  const exportJson = async () => {
    if (!api) return;
    try {
      const [ov, sosPage, tasksPage, alerts] = await Promise.all([
        api.adminOverview(district), api.listSOS({ district, limit: 500 }),
        api.listTasks({ district, limit: 200 }), api.listAlerts({ district, limit: 100 }),
      ]);
      const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), district, overview: ov, sos: sosPage.items, tasks: tasksPage.items, alerts: alerts.items, demo_data: true }, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `sahayta-incident-${district}.json`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch { toast("error", t("common.retry")); }
  };

  const exportPdf = async () => {
    if (!api || busyPdf) return;
    setBusyPdf(true);
    try {
      const blob = await api.exportIncidentPdf(district);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `sahayta-incident-${district}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
      toast("success", t("admin.pdf_done"));
    } catch { toast("error", t("common.retry")); } finally { setBusyPdf(false); }
  };

  if (!unlocked) {
    return (
      <div className="mx-auto max-w-md py-10 text-center">
        <span className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-line text-muted">
          <Lock size={30} aria-hidden />
        </span>
        <h1 className="mb-2 text-[22px] font-extrabold text-ink">{t("admin.lock_title")}</h1>
        <p className="mb-4 text-[15px] text-muted">{t("admin.lock_sub")}</p>
        <label className="mb-1 block text-start text-[14px] font-semibold text-body">{t("admin.key_label")}</label>
        <div className="flex gap-2">
          <input type="password" value={keyInput} onChange={(e) => setKeyInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") unlock(); }}
            placeholder={t("admin.key_ph")} className="input flex-1" autoComplete="off" />
          <button onClick={unlock} className="btn-primary"><KeyRound size={18} aria-hidden /> {t("admin.unlock")}</button>
        </div>
        {keyError && <p role="alert" className="mt-2 text-[14px] font-semibold text-red-600">{t("admin.invalid_key")}</p>}
        <p className="mt-3 text-[13px] text-muted">{t("admin.demo_hint")}</p>
      </div>
    );
  }

  const districtName = districts.find((d) => d.id === district)?.name ?? district;
  const ACTIVE_TASK = new Set(["assigned", "accepted", "en_route"]);
  const onTaskByVol = new Map<string, Task>();
  for (const tk of tasks) if (ACTIVE_TASK.has(tk.status)) onTaskByVol.set(tk.volunteer_id, tk);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-[22px] font-extrabold text-ink">{t("admin.title")} · {districtName}</h1>
        <select value={district} onChange={(e) => setDistrict(e.target.value)} className="input w-auto" aria-label={t("board.f_district")}>
          {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        {mode === "demo" && <DemoDataChip />}
      </div>

      {/* KPI row */}
      {failures.overview ? <Panel title={t("admin.panel_kpis")} onRetry={load}><span /></Panel> : overview ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          <Kpi label={t("admin.kpi_active_sos")} value={String(Object.entries(overview.sos_by_status).filter(([k]) => !["resolved", "duplicate", "rejected"].includes(k)).reduce((a, [, v]) => a + (v as number), 0))} />
          <Kpi label={t("admin.kpi_sev4")} value={String((Number(overview.sos_by_severity["4"]) || 0) + (Number(overview.sos_by_severity["5"]) || 0))} />
          <Kpi label={t("admin.kpi_volunteers")} value={String(overview.volunteers_active)} sub={`${overview.volunteers_on_task} ${t("admin.on_task")}`} />
          <Kpi label={t("admin.kpi_risk")} value={String(overview.district_risk)} sub={t(`risk.${overview.risk_level}`)} />
          <Kpi label={t("admin.kpi_shelters")} value={`${overview.shelter_occupancy_pct}%`} sub={`${overview.shelters_open} open`} />
        </div>
      ) : <SkeletonList n={1} />}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-line" role="tablist">
        {(["map", "verify", "flags"] as const).map((k) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`min-h-[48px] px-4 text-[15px] font-semibold ${tab === k ? "border-b-[3px] border-brand-600 text-brand-700" : "text-muted"}`}>
            {k === "map" ? t("board.map_view") : k === "verify" ? `${t("admin.verify_queue")} (${verifyQ.length})` : `${t("admin.safety_flags")} (${flags.length})`}
          </button>
        ))}
      </div>

      {tab === "map" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title={t("board.map_view")} onRetry={failures.sos ? load : undefined}>
            {failures.sos ? <p className="text-[14px] text-muted">{t("admin.panel_error")}</p>
              : <SosMap reports={sos} showHeatmap height={380} />}
            <div className="mt-2 max-h-64 space-y-2 overflow-y-auto" aria-label={t("a11y.map_list")}>
              {sos.slice(0, 10).map((r) => <SOSCard key={r.id} report={r} />)}
            </div>
          </Panel>
          <div className="space-y-4">
            <Panel title={t("admin.risk_title")} onRetry={failures.risk ? load : undefined}>
              {failures.risk || !risk ? <p className="text-[14px] text-muted">{t("admin.panel_error")}</p> : (
                <>
                  <RiskGauge risk={risk.risk} level={risk.risk_level} factors={risk.factors} />
                  <div className="mt-2 flex items-center gap-2">
                    {risk.weather_source === "simulated" && <SimulatedFeedChip />}
                    <span className="text-[12px] text-muted">{risk.advisory}</span>
                  </div>
                </>
              )}
            </Panel>
            <Panel title={t("admin.volunteer_board")} onRetry={failures.vols ? load : undefined}>
              {failures.vols ? <p className="text-[14px] text-muted">{t("admin.panel_error")}</p> : (
                <ul className="max-h-64 space-y-2 overflow-y-auto">
                  {volunteers.slice(0, 15).map((v) => {
                    const ot = onTaskByVol.get(v.id);
                    return (
                      <li key={v.id} className="rounded-btn border border-line p-2">
                        <div className="flex items-center justify-between text-[14px]">
                          <span className="font-semibold text-ink">{v.name}</span>
                          <span className="text-muted">★<span className="num-ltr">{v.reputation}</span>
                            {ot ? ` · 🟡 ${t("admin.on_task")} (#${ot.sos_id.slice(0, 6)})`
                              : v.active ? ` · 🟢 ${t("admin.available")}` : ` · ⚪ ${t("volunteer.off_duty")}`}
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {v.skills.slice(0, 4).map((s) => (
                            <span key={s} className="chip px-2 py-0.5 text-[12px]">{s}</span>
                          ))}
                          <span className="num-ltr text-[12px] text-muted">{v.tasks_completed} ✓</span>
                        </div>
                      </li>
                    );
                  })}
                  {volunteers.length === 0 && <li className="py-4 text-center text-[14px] text-muted">—</li>}
                </ul>
              )}
            </Panel>
          </div>
        </div>
      )}

      {tab === "verify" && (
        <div className="space-y-2">
          {failures.verify ? <Panel title={t("admin.verify_queue")} onRetry={load}><span /></Panel>
            : verifyQ.length === 0 ? <p className="py-8 text-center text-muted">—</p>
            : verifyQ.map((r) => (
              <div key={r.id} className="card space-y-2 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  {r.severity != null && <SeverityBadge severity={r.severity} size="sm" />}
                  <p className="line-clamp-1 min-w-0 flex-1 text-[14px] font-medium text-ink">{r.description}</p>
                </div>
                <p className="text-[12px] text-muted">
                  <span className="num-ltr">{timeAgo(r.created_at)}</span> · {r.district_id}
                  {r.reason && <> · <span className="font-semibold">{r.reason.replaceAll("_", " ")}</span></>}
                  {r.reporter_trust_tier && <> · {TIER_EMOJI[r.reporter_trust_tier] ?? ""} {t("admin.trust_tier")}: <span className="font-semibold">{r.reporter_trust_tier}</span></>}
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <button disabled={busyVerify === r.id} onClick={() => verify(r.id, "verified")} className="btn-secondary min-h-[44px] px-3 text-[13px]">✓ {t("admin.verify_btn")}</button>
                  <button disabled={busyVerify === r.id} onClick={() => verify(r.id, "rejected")} className="btn-danger-ghost min-h-[44px] px-3 text-[13px]">⦸ {t("admin.reject_btn")}</button>
                  <input value={dupOf[r.id] ?? ""} onChange={(e) => setDupOf((m) => ({ ...m, [r.id]: e.target.value }))}
                    placeholder={t("admin.dup_of_ph")} className="input min-h-[44px] w-40 text-[13px]" aria-label={t("admin.dup_of_ph")} />
                  <button disabled={busyVerify === r.id} onClick={() => verify(r.id, "duplicate")} className="btn-secondary min-h-[44px] px-3 text-[13px]">⧉ {t("admin.dup_btn")}</button>
                </div>
              </div>
            ))}
        </div>
      )}

      {tab === "flags" && (
        <div className="space-y-2">
          {failures.flags ? <Panel title={t("admin.safety_flags")} onRetry={load}><span /></Panel>
            : flags.length === 0 ? <p className="py-8 text-center text-muted">—</p>
            : flags.map((f) => (
              <div key={f.id} className="card space-y-2 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-[14px] font-bold text-ink">{f.type.replaceAll("_", " ")}</p>
                  <span className={`chip px-2 py-0.5 text-[12px] ${f.status === "open" ? "chip-active" : ""}`}>{f.status}</span>
                </div>
                <p className="text-[13px] text-muted">{f.evidence}</p>
                <p className="text-[12px] text-muted">{f.sos_ids.length} reports · {f.district_id} · <span className="num-ltr font-mono">{f.sos_ids.map((s) => s.slice(0, 8)).join(", ")}</span></p>
                {f.status === "open" && (
                  <div className="flex flex-wrap items-center gap-2">
                    <label className="text-[13px] font-semibold text-body">{t("admin.flag_resolution")}</label>
                    <select value={flagRes[f.id] ?? "confirmed"} onChange={(e) => setFlagRes((m) => ({ ...m, [f.id]: e.target.value }))} className="input min-h-[44px] w-auto text-[13px]">
                      <option value="confirmed">confirmed</option>
                      <option value="confirmed_duplicate">confirmed_duplicate</option>
                      <option value="false_alarm">false_alarm</option>
                    </select>
                    <input value={flagNote[f.id] ?? ""} onChange={(e) => setFlagNote((m) => ({ ...m, [f.id]: e.target.value }))}
                      placeholder={t("admin.flag_note_ph")} className="input min-h-[44px] min-w-0 flex-1 text-[13px]" />
                    <button disabled={busyFlag === f.id} onClick={() => resolveSafetyFlag(f.id)} className="btn-primary min-h-[44px] px-4 text-[13px]">
                      {t("admin.resolve")}
                    </button>
                  </div>
                )}
              </div>
            ))}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <BroadcastComposer districts={districts} onSent={load} />
        <Panel title={t("admin.timeline")}>
          <ol className="max-h-72 space-y-1.5 overflow-y-auto">
            {audit.slice(0, 20).map((a) => (
              <li key={a.id} className="flex gap-2 text-[13px]">
                <span className="num-ltr shrink-0 text-muted">{new Date(a.ts).toLocaleTimeString()}</span>
                <span className="text-body"><span className="num-ltr font-mono text-[12px]">{a.action}</span> <span className="text-muted">· {a.actor}</span></span>
              </li>
            ))}
            {audit.length === 0 && <li className="text-[13px] text-muted">—</li>}
          </ol>
          <div className="mt-3 flex flex-wrap gap-2">
            <button onClick={exportJson} className="btn-secondary min-h-[48px] px-4 text-[14px]">
              <Download size={16} aria-hidden /> {t("admin.export_json")}
            </button>
            <button onClick={exportPdf} disabled={busyPdf} className="btn-secondary min-h-[48px] px-4 text-[14px]">
              <Download size={16} aria-hidden /> {busyPdf ? t("common.loading") : t("admin.export_pdf")}
            </button>
          </div>
        </Panel>
      </div>
    </div>
  );
}

export default function AdminPage() {
  return (
    <Suspense fallback={<SkeletonList />}>
      <AdminInner />
    </Suspense>
  );
}
