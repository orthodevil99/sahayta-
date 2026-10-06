"use client";
/**
 * /volunteer — registration + task lifecycle (wireframes/volunteer-tasks.md).
 * Offline: task actions queue locally and sync on reconnect (outbox pattern).
 */
import { Star } from "lucide-react";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useApi, type RegisterVolunteerInput } from "../../lib/api";
import { useI18n, LANG_META } from "../../lib/i18n";
import { outboxAdd } from "../../lib/outbox";
import { useToast } from "../../components/Toast";
import { useOnline } from "../../components/Header";
import BottomSheet from "../../components/BottomSheet";
import { SkillIcons } from "../../components/CategoryChip";
import TaskCard, { type TaskActionBody } from "../../components/TaskCard";
import { EmptyState, SkeletonList } from "../../components/ui";
import type { District, Task, Volunteer, VolunteerReputation, VolunteerSkill, WSEvent } from "../../lib/types";

const SKILLS: VolunteerSkill[] = ["medical", "rescue", "driving", "cooking", "shelter_mgmt", "translation", "logistics", "counseling", "engineering"];
const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const VOL_LS = "sahayta.volunteer_id";

const TIER_STYLE: Record<string, string> = {
  guardian: "bg-purple-100 text-purple-800",
  responder: "bg-green-100 text-green-800",
  helper: "bg-amber-100 text-amber-800",
  newcomer: "bg-line text-muted",
};

function VolunteerInner() {
  const { t, lang } = useI18n();
  const { api, loading: apiLoading } = useApi();
  const { toast } = useToast();
  const online = useOnline();
  const params = useSearchParams();
  const [volunteerId, setVolunteerId] = useState<string | null>(null);
  const [volunteer, setVolunteer] = useState<Volunteer | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [districts, setDistricts] = useState<District[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [showRegister, setShowRegister] = useState(false);
  // Registration form
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [districtId, setDistrictId] = useState("patna");
  const [skills, setSkills] = useState<VolunteerSkill[]>(["rescue"]);
  const [langs, setLangs] = useState<string[]>([lang]);
  const [anytime, setAnytime] = useState(true);
  const [windows, setWindows] = useState<Array<{ day: string; start: string; end: string }>>([]);
  const [wDay, setWDay] = useState("mon");
  const [wStart, setWStart] = useState("09:00");
  const [wEnd, setWEnd] = useState("18:00");
  const [repDetail, setRepDetail] = useState<VolunteerReputation | null>(null);
  const [declineFor, setDeclineFor] = useState<string | null>(null);

  useEffect(() => {
    setVolunteerId(localStorage.getItem(VOL_LS));
    if (params.get("register") === "1") setShowRegister(true);
  }, [params]);

  const refresh = useCallback(async () => {
    if (!api) return;
    const id = localStorage.getItem(VOL_LS);
    if (!id) { setLoading(false); return; }
    try {
      const [v, tp] = await Promise.all([
        api.getVolunteer(id),
        api.listTasks({ volunteer_id: id, limit: 50 }),
      ]);
      setVolunteer(v);
      setTasks(tp.items);
      api.getVolunteerReputation(id).then(setRepDetail).catch(() => {});
    } catch { /* keep cached */ } finally { setLoading(false); }
  }, [api]);

  useEffect(() => {
    if (apiLoading || !api) return;
    api.getDistricts().then(setDistricts).catch(() => {});
    refresh();
    const unsub = api.subscribe((e: WSEvent) => {
      if (e.type === "task.assigned" || e.type === "task.updated") refresh();
    });
    // Re-sync queued actions when coming back online.
    const onOnline = () => refresh();
    window.addEventListener("online", onOnline);
    return () => { unsub(); window.removeEventListener("online", onOnline); };
  }, [api, apiLoading, refresh]);

  const register = async () => {
    if (!api || !name.trim()) return;
    if (!anytime && windows.length === 0) return;
    setBusy(true);
    try {
      const input: RegisterVolunteerInput = {
        name: name.trim(), phone: phone || undefined, district_id: districtId,
        skills, languages: langs, availability: anytime ? "anytime" : windows,
      };
      const v = await api.registerVolunteer(input);
      localStorage.setItem(VOL_LS, v.id);
      setVolunteerId(v.id); setVolunteer(v); setShowRegister(false);
      toast("success", t("toast.sent"));
      refresh();
    } catch { toast("error", t("common.retry")); } finally { setBusy(false); }
  };

  const toggleActive = async () => {
    if (!api || !volunteer) return;
    try {
      const v = await api.updateVolunteer(volunteer.id, { active: !volunteer.active });
      setVolunteer(v);
    } catch { toast("error", t("common.retry")); }
  };

  const act = async (taskId: string, action: "accept" | "decline" | "enroute" | "complete", body?: TaskActionBody) => {
    if (!api) return;
    // Photo proof needs connectivity (can't queue a file); other actions queue.
    const proofFile = body?.proofFile ?? null;
    if (!online) {
      await outboxAdd({
        client_report_id: `taskact-${taskId}-${action}-${Date.now()}`,
        kind: "volunteer_action", created_at: new Date().toISOString(), attempts: 0,
        payload: { action: "taskAction", url: `/api/tasks/${taskId}/${action}`, body: { ...(body?.note ? { note: body.note } : {}), ...(body?.reason ? { reason: body.reason } : {}) } },
      });
      toast("offline", t("toast.action_queued"), true);
      return;
    }
    setBusy(true);
    try {
      let proof_photo_id: string | undefined;
      if (proofFile) {
        const up = await api.uploadMedia(proofFile);
        proof_photo_id = up.photo_id;
      }
      await api.taskAction(taskId, action, {
        ...(body?.note ? { note: body.note } : {}),
        ...(body?.reason ? { reason: body.reason } : {}),
        ...(proof_photo_id ? { proof_photo_id } : {}),
      });
      toast("success", t("toast.task_done"));
      refresh();
    } catch { toast("error", t("common.retry")); } finally { setBusy(false); }
  };

  const toggleSkill = (s: VolunteerSkill) => setSkills((p) => (p.includes(s) ? p.filter((x) => x !== s) : [...p, s]));
  const toggleLang = (l: string) => setLangs((p) => (p.includes(l) ? p.filter((x) => x !== l) : [...p, l]));

  if (loading) return <SkeletonList />;

  /* ---------------- registration ---------------- */
  if (!volunteerId || showRegister) {
    return (
      <div className="mx-auto max-w-xl">
        <h1 className="mb-1 text-[22px] font-extrabold text-ink">{t("volunteer.reg_title")}</h1>
        <p className="mb-4 text-[15px] text-muted">{t("volunteer.reg_sub")}</p>
        <div className="card space-y-4 p-4">
          <div>
            <label className="mb-1 block text-[14px] font-semibold text-body">{t("volunteer.name")}</label>
            <input value={name} onChange={(e) => setName(e.target.value)} className="input" maxLength={120} />
          </div>
          <div>
            <label className="mb-1 block text-[14px] font-semibold text-body">{t("volunteer.phone")}</label>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" className="input" />
          </div>
          <div>
            <label className="mb-1 block text-[14px] font-semibold text-body">{t("volunteer.district")}</label>
            <select value={districtId} onChange={(e) => setDistrictId(e.target.value)} className="input">
              {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-[14px] font-semibold text-body">{t("volunteer.skills")}</label>
            <div className="flex flex-wrap gap-1.5">
              {SKILLS.map((s) => (
                <button key={s} onClick={() => toggleSkill(s)} aria-pressed={skills.includes(s)}
                  className={`chip min-h-[44px] px-3 text-[14px] ${skills.includes(s) ? "chip-active" : ""}`}>{s.replace("_", " ")}</button>
              ))}
            </div>
          </div>
          <div>
            <label className="mb-1 block text-[14px] font-semibold text-body">{t("volunteer.languages")}</label>
            <div className="flex flex-wrap gap-1.5">
              {(Object.keys(LANG_META) as Array<keyof typeof LANG_META>).map((c) => (
                <button key={c} onClick={() => toggleLang(c)} aria-pressed={langs.includes(c)}
                  className={`chip min-h-[44px] px-3 text-[14px] ${langs.includes(c) ? "chip-active" : ""}`}>{LANG_META[c].native}</button>
              ))}
            </div>
          </div>
          <div>
            <label className="mb-1 block text-[14px] font-semibold text-body">{t("volunteer.availability")}</label>
            <div className="flex gap-2">
              <button onClick={() => setAnytime(true)} aria-pressed={anytime} className={`chip flex-1 ${anytime ? "chip-active" : ""}`}>{t("volunteer.anytime")}</button>
              <button onClick={() => setAnytime(false)} aria-pressed={!anytime} className={`chip flex-1 ${!anytime ? "chip-active" : ""}`}>{t("volunteer.set_hours")}</button>
            </div>
            {!anytime && (
              <div className="mt-2 rounded-card bg-appbg p-3">
                <p className="mb-2 text-[13px] font-semibold text-body">{t("volunteer.hours_title")}</p>
                {windows.length === 0 && <p className="mb-2 text-[13px] text-muted">{t("volunteer.hours_empty")}</p>}
                <div className="mb-2 space-y-1.5">
                  {windows.map((w, i) => (
                    <div key={i} className="flex items-center justify-between rounded-card bg-surface px-2.5 py-1.5 text-[14px]">
                      <span className="num-ltr font-semibold text-body">{t(`volunteer.day_${w.day}`)} · {w.start}–{w.end}</span>
                      <button onClick={() => setWindows((p) => p.filter((_, j) => j !== i))} aria-label={t("common.remove")}
                        className="min-h-[36px] min-w-[36px] font-bold text-red-600">✕</button>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-1.5">
                  <select value={wDay} onChange={(e) => setWDay(e.target.value)} className="input min-h-[44px] flex-1" aria-label={t("volunteer.hours_title")}>
                    {DAYS.map((d) => <option key={d} value={d}>{t(`volunteer.day_${d}`)}</option>)}
                  </select>
                  <input type="time" value={wStart} onChange={(e) => setWStart(e.target.value)} className="input num-ltr min-h-[44px] w-[104px]" />
                  <input type="time" value={wEnd} onChange={(e) => setWEnd(e.target.value)} className="input num-ltr min-h-[44px] w-[104px]" />
                  <button
                    onClick={() => { if (wStart < wEnd && !windows.some((w) => w.day === wDay && w.start === wStart && w.end === wEnd)) setWindows((p) => [...p, { day: wDay, start: wStart, end: wEnd }]); }}
                    disabled={!(wStart < wEnd)}
                    className="btn-secondary min-h-[44px] shrink-0 px-3"
                  >{t("volunteer.hours_add")}</button>
                </div>
              </div>
            )}
          </div>
          <button onClick={register} disabled={busy || !name.trim() || (!anytime && windows.length === 0)} className="btn-primary w-full">
            ✓ {t("volunteer.register")}
          </button>
        </div>
      </div>
    );
  }

  /* ---------------- home ---------------- */
  const activeTasks = tasks.filter((x) => !["completed", "declined", "cancelled"].includes(x.status));
  const doneTasks = tasks.filter((x) => ["completed", "declined", "cancelled"].includes(x.status));

  return (
    <div className="mx-auto max-w-xl">
      <div className="card mb-4 p-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h1 className="text-[20px] font-extrabold text-ink">{t("volunteer.hello")}, {volunteer?.name}</h1>
            <p className="mt-0.5 flex items-center gap-2 text-[14px] text-muted">
              <span className="inline-flex items-center gap-1 font-bold text-amber-600">
                <Star size={15} aria-hidden className="fill-amber-500 text-amber-500" />
                <span className="num-ltr">{volunteer?.reputation}</span>
              </span>
              <span title={t("volunteer.rep_tooltip")} className="cursor-help underline decoration-dotted underline-offset-2">
                ({volunteer?.tasks_completed} {t("volunteer.tasks_done")})
              </span>
            </p>
            <p className="mt-1 flex items-center gap-2 text-[14px] text-muted">
              📍 {districts.find((d) => d.id === volunteer?.district_id)?.name} · <SkillIcons skills={volunteer?.skills ?? []} /> · {volunteer?.languages.map((l) => LANG_META[l as keyof typeof LANG_META]?.native ?? l).join(", ")}
            </p>
          </div>
        </div>
        <button onClick={toggleActive} aria-pressed={volunteer?.active}
          className={`mt-3 flex min-h-[48px] w-full items-center justify-center gap-2 rounded-btn font-bold ${volunteer?.active ? "bg-green-100 text-green-800" : "bg-line text-muted"}`}>
          <span className={`h-3 w-3 rounded-full ${volunteer?.active ? "bg-green-600" : "bg-gray-400"}`} aria-hidden />
          {volunteer?.active ? t("volunteer.available_now") : t("volunteer.off_duty")}
        </button>
        {!online && <p className="mt-2 text-[13px] text-amber-700">{t("volunteer.sync_note")}</p>}
      </div>

      {repDetail && (
        <div className="card mb-4 p-4" aria-label={t("volunteer.rep_tier")}>
          <div className="flex items-center justify-between">
            <span className={`rounded-card px-2.5 py-1 text-[13px] font-bold ${TIER_STYLE[repDetail.tier] ?? TIER_STYLE.newcomer}`}>
              {t("volunteer.rep_tier")}: {t(`volunteer.tier_${repDetail.tier}`)}
            </span>
            <span className="text-[13px] text-muted">
              {t("volunteer.rep_response")}: <span className="num-ltr font-semibold text-body">
                {repDetail.avg_response_min != null ? `${Math.round(repDetail.avg_response_min)} min` : "—"}
              </span>
            </span>
          </div>
          <div className="mt-2.5">
            <div className="mb-1 flex items-center justify-between text-[13px]">
              <span className="text-muted">{t("volunteer.rep_reliability")}</span>
              <span className="num-ltr font-bold text-body">{repDetail.reliability_pct}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-line" role="progressbar"
              aria-valuenow={repDetail.reliability_pct} aria-valuemin={0} aria-valuemax={100}
              aria-label={t("volunteer.rep_reliability")}>
              <div className="h-full rounded-full bg-green-600" style={{ width: `${repDetail.reliability_pct}%` }} />
            </div>
          </div>
        </div>
      )}

      <h2 className="mb-2 text-[18px] font-bold text-ink">{t("volunteer.my_tasks")}</h2>
      {activeTasks.length === 0 ? (
        <EmptyState title={t("volunteer.no_tasks")} sub={t("volunteer.no_tasks_sub")} />
      ) : (
        <div className="space-y-3">
          {activeTasks.map((task) => (
            <TaskCard key={task.id} task={task} busy={busy}
              onAction={(a, b) => { if (a === "decline") setDeclineFor(task.id); else act(task.id, a, b); }} />
          ))}
        </div>
      )}

      {doneTasks.length > 0 && (
        <>
          <h2 className="mb-2 mt-6 text-[16px] font-bold text-muted">{t("volunteer.task_log")}</h2>
          <div className="space-y-2">
            {doneTasks.map((task) => (
              <div key={task.id} className="card flex items-center justify-between p-3 text-[14px]">
                <span className="text-body">{task.sos?.description?.slice(0, 60) ?? task.id.slice(0, 8)}…</span>
                <span className="font-semibold text-muted">✓ {t("volunteer.done_suffix")}{task.status === "completed" && " +2 ★"}</span>
              </div>
            ))}
          </div>
        </>
      )}

      <p className="mt-6 text-center text-[13px] text-muted">🔔 {t("volunteer.new_task")}</p>

      <BottomSheet open={!!declineFor} onClose={() => setDeclineFor(null)} title={t("volunteer.decline_reason")}>
        <div className="flex flex-col gap-2">
          {(["r_far", "r_busy", "r_skill"] as const).map((r) => (
            <button key={r} onClick={() => { if (declineFor) act(declineFor, "decline", { reason: t(`volunteer.${r}`) }); setDeclineFor(null); }}
              className="btn-secondary w-full">{t(`volunteer.${r}`)}</button>
          ))}
        </div>
      </BottomSheet>
    </div>
  );
}

export default function VolunteerPage() {
  return (
    <Suspense fallback={<SkeletonList />}>
      <VolunteerInner />
    </Suspense>
  );
}
