"use client";
/**
 * /report — 4-step SOS wizard (wireframes/report-sos.md).
 * client_report_id is minted when the wizard OPENS (idempotent offline replay).
 * Draft persists to localStorage; back-navigation preserves inputs.
 */
import { Camera, Check, ChevronLeft, ImagePlus, MapPin, Mic, Navigation, Siren } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "../../lib/api";
import { ApiError } from "../../lib/api";
import { useI18n, isLowBandwidth } from "../../lib/i18n";
import { newClientReportId, outboxAdd, getDeviceId } from "../../lib/outbox";
import { nearestDistrict } from "../../lib/geo";
import { useToast } from "../../components/Toast";
import { useOnline } from "../../components/Header";
import SeverityBadge from "../../components/SeverityBadge";
import type { District, SOSReport } from "../../lib/types";

const SosMap = dynamic(() => import("../../components/SosMap"), { ssr: false, loading: () => <div className="shimmer h-[260px] rounded-card" /> });

const DRAFT_KEY = "sahayta.report_draft";
const HINTS = ["report.hint_knee", "report.hint_roof", "report.hint_elderly"] as const;

interface Draft { photoDataUrl: string | null; photoName: string | null; description: string; lat: number | null; lon: number | null; districtId: string; name: string; phone: string; }

function loadDraft(): Draft {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (raw) return JSON.parse(raw) as Draft;
  } catch { /* */ }
  return { photoDataUrl: null, photoName: null, description: "", lat: null, lon: null, districtId: "", name: "", phone: "" };
}

export default function ReportPage() {
  const { t, lang } = useI18n();
  const { api, loading: apiLoading } = useApi();
  const { toast } = useToast();
  const online = useOnline();
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<Draft>(() => (typeof window === "undefined" ? { photoDataUrl: null, photoName: null, description: "", lat: null, lon: null, districtId: "", name: "", phone: "" } : loadDraft()));
  const [clientReportId] = useState(() => (typeof window !== "undefined" ? newClientReportId() : ""));
  const [districts, setDistricts] = useState<District[]>([]);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<SOSReport | null>(null);
  const [queued, setQueued] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [gpsBusy, setGpsBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [bw, setBw] = useState(false);
  const recogRef = useRef<unknown>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { setBw(isLowBandwidth()); }, []);
  useEffect(() => { localStorage.setItem(DRAFT_KEY, JSON.stringify(draft)); }, [draft]);
  useEffect(() => {
    if (apiLoading || !api) return;
    api.getDistricts().then(setDistricts).catch(() => {});
  }, [api, apiLoading]);

  const set = useCallback((p: Partial<Draft>) => setDraft((d) => ({ ...d, ...p })), []);

  // Auto-district from pin.
  useEffect(() => {
    if (draft.lat != null && draft.lon != null && districts.length && !draft.districtId) {
      const n = nearestDistrict(draft.lat, draft.lon, districts);
      if (n) set({ districtId: n.id });
    }
  }, [draft.lat, draft.lon, districts, draft.districtId, set]);

  const onPhoto = (f: File | undefined) => {
    if (!f) return;
    if (f.size > 8 * 1024 * 1024) { setFieldError(t("report.err_photo_big")); return; }
    setFieldError(null);
    const reader = new FileReader();
    reader.onload = () => set({ photoDataUrl: String(reader.result), photoName: f.name });
    reader.readAsDataURL(f);
  };

  const toggleMic = () => {
    type SRConstructor = new () => SpeechRec;
    const w = window as unknown as { SpeechRecognition?: SRConstructor; webkitSpeechRecognition?: SRConstructor };
    const SR = w.SpeechRecognition ?? w.webkitSpeechRecognition;
    if (!SR) { toast("error", t("toast.voice_unavailable")); return; }
    if (listening) { (recogRef.current as SpeechRec | null)?.stop(); setListening(false); return; }
    try {
      const rec = new SR();
      recogRef.current = rec;
      rec.lang = lang === "hing" ? "hi-IN" : `${lang}-IN`;
      rec.interimResults = true;
      rec.onresult = (e: SpeechResultEvent) => {
        let text = "";
        for (let i = e.resultIndex; i < e.results.length; i++) text += e.results[i][0].transcript;
        set({ description: (draft.description + " " + text).trim() });
      };
      rec.onend = () => setListening(false);
      rec.onerror = () => { setListening(false); toast("error", t("toast.voice_unavailable")); };
      rec.start();
      setListening(true);
    } catch {
      toast("error", t("toast.voice_unavailable"));
    }
  };

  const useGps = () => {
    if (!navigator.geolocation) { setFieldError(t("report.gps_denied")); return; }
    setGpsBusy(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => { set({ lat: pos.coords.latitude, lon: pos.coords.longitude }); setGpsBusy(false); setFieldError(null); },
      () => { setGpsBusy(false); setFieldError(t("report.gps_denied")); },
      { timeout: 10000 },
    );
  };

  const canNext = () => {
    if (step === 1) return draft.description.trim().length >= 10;
    if (step === 2) return (draft.lat != null && draft.lon != null) || draft.districtId !== "";
    return true;
  };

  const next = () => {
    if (step === 1 && draft.description.trim().length < 10) { setFieldError(t("report.err_desc_short")); return; }
    if (step === 2 && !canNext()) { setFieldError(t("report.err_location")); return; }
    setFieldError(null);
    setStep((s) => Math.min(3, s + 1));
  };

  const send = async () => {
    if (!api || sending) return;
    setSending(true);
    setFieldError(null);
    try {
      if (!online) {
        // Offline: queue to IndexedDB outbox (service worker replays on reconnect).
        await outboxAdd({
          client_report_id: clientReportId, kind: "sos", created_at: new Date().toISOString(), attempts: 0,
          payload: {
            description: draft.description, lat: draft.lat, lon: draft.lon,
            district_id: draft.districtId || undefined, language: lang,
            reporter_name: draft.name || undefined, reporter_phone: draft.phone || undefined,
            client_report_id: clientReportId,
            photo_description: draft.photoName ? `User photo: ${draft.photoName}` : undefined,
          },
        });
        try { await navigator.serviceWorker.ready.then((r) => (r as unknown as { sync?: { register: (t: string) => Promise<void> } }).sync?.register("sahayta-sos-sync")); } catch { /* bg sync optional */ }
        setQueued(true);
        toast("offline", t("toast.queued_ok"), true);
        localStorage.removeItem(DRAFT_KEY);
        return;
      }
      const report = await api.createSOS({
        description: draft.description,
        lat: draft.lat, lon: draft.lon,
        district_id: draft.districtId || undefined,
        language: lang,
        reporter_name: draft.name || undefined,
        reporter_phone: draft.phone || undefined,
        client_report_id: clientReportId,
        photo_description: draft.photoName ? `User photo: ${draft.photoName}` : undefined,
      });
      setResult(report);
      toast("success", t("toast.sent"));
      localStorage.removeItem(DRAFT_KEY);
      void getDeviceId;
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 429) setFieldError(t("report.err_rate"));
        else if (e.status === 413) setFieldError(t("report.err_photo_big"));
        else if (e.status === 422) setFieldError(t("report.err_desc_short"));
        else if (e.status === 0) {
          // Network dropped mid-send → fall back to the offline queue path.
          await outboxAdd({
            client_report_id: clientReportId, kind: "sos", created_at: new Date().toISOString(), attempts: 0,
            payload: { description: draft.description, lat: draft.lat, lon: draft.lon, district_id: draft.districtId || undefined, language: lang, client_report_id: clientReportId },
          });
          setQueued(true);
          toast("offline", t("toast.queued_ok"), true);
          localStorage.removeItem(DRAFT_KEY);
        } else setFieldError(e.detail);
      } else setFieldError(String(e));
    } finally {
      setSending(false);
    }
  };

  /* ---------- success / queued screens ---------- */
  if (result) {
    return (
      <div className="mx-auto max-w-md py-8 text-center">
        <span className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100 text-green-700">
          <Check size={32} aria-hidden />
        </span>
        <h1 className="mb-3 text-[24px] font-extrabold text-ink">{t("report.success_title")}</h1>
        <div className="card mb-4 p-4 text-start">
          {result.severity != null ? (
            <>
              <SeverityBadge severity={result.severity} />
              <p className="mt-2 text-[14px] text-body">{t(`category.${result.category}`)} · {t(`priority.${result.priority}`)}</p>
              {result.severity_rationale && <p className="mt-1 text-[15px] text-ink">“{result.severity_rationale}”</p>}
            </>
          ) : (
            <p className="text-[15px] font-semibold text-ink">🔍 {t("report.awaiting_review")}<br /><span className="text-[14px] font-normal text-muted">{t("report.awaiting_sub")}</span></p>
          )}
        </div>
        <p className="mb-6 text-[15px] text-muted">{t("report.success_sub")}</p>
        <div className="flex flex-col gap-2">
          <Link href={`/board?district=${result.district_id ?? ""}`} className="btn-primary w-full">{t("report.track_board")}</Link>
          <button onClick={() => { setResult(null); setStep(0); setDraft({ photoDataUrl: null, photoName: null, description: "", lat: null, lon: null, districtId: "", name: "", phone: "" }); }} className="btn-secondary w-full">
            {t("report.report_another")}
          </button>
        </div>
      </div>
    );
  }
  if (queued) {
    return (
      <div className="mx-auto max-w-md py-8 text-center">
        <span className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 text-amber-700 text-[28px]" aria-hidden>⏳</span>
        <h1 className="mb-3 text-[24px] font-extrabold text-ink">{t("report.queued_title")}</h1>
        <p className="mb-6 text-[15px] text-muted">{t("report.queued_sub")}</p>
        <Link href="/board" className="btn-primary w-full">{t("report.track_board")}</Link>
      </div>
    );
  }

  const steps = [t("report.step1"), t("report.step2"), t("report.step3"), t("report.step4")];

  return (
    <div className="mx-auto max-w-xl">
      <div className="mb-4 flex items-center gap-3">
        {step > 0 && (
          <button onClick={() => setStep((s) => s - 1)} aria-label={t("common.back")} className="flex min-h-[48px] min-w-[48px] items-center justify-center rounded-btn text-body hover:bg-line/60">
            <ChevronLeft size={22} aria-hidden className="flip-rtl rotate-180" />
          </button>
        )}
        <h1 className="text-[22px] font-extrabold text-ink">{t("report.title")}</h1>
        <div className="ms-auto flex gap-1.5" role="progressbar" aria-valuenow={step + 1} aria-valuemin={1} aria-valuemax={4} aria-label={steps[step]}>
          {steps.map((s, i) => (
            <span key={s} title={s} className={`h-2.5 w-8 rounded-full ${i <= step ? "bg-brand-600" : "bg-line"}`} />
          ))}
        </div>
      </div>

      {step === 0 && (
        <section aria-label={steps[0]}>
          <button onClick={() => fileRef.current?.click()}
            className="flex h-[220px] w-full flex-col items-center justify-center gap-2 rounded-card border-2 border-dashed border-line bg-surface text-muted hover:border-brand-600">
            {draft.photoDataUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={draft.photoDataUrl} alt="" className="h-full w-full rounded-card object-cover" />
            ) : (
              <>
                <Camera size={44} strokeWidth={1.5} aria-hidden />
                <span className="text-[16px] font-semibold">{t("report.photo_title")}</span>
              </>
            )}
          </button>
          <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" aria-hidden
            onChange={(e) => onPhoto(e.target.files?.[0])} />
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button onClick={() => fileRef.current?.click()} className="btn-secondary"><Camera size={18} aria-hidden /> {t("report.take_photo")}</button>
            <button onClick={() => fileRef.current?.click()} className="btn-secondary"><ImagePlus size={18} aria-hidden /> {t("report.choose_file")}</button>
          </div>
          <p className="mt-3 text-[14px] text-muted">{t("report.photo_hint")}</p>
          {draft.photoDataUrl && <p className="mt-1 text-[13px] text-muted">{t("report.photo_privacy")}</p>}
          <button onClick={() => setStep(1)} className="mt-4 w-full text-center text-[15px] font-semibold text-brand-700 underline underline-offset-4">{t("report.skip_photo")} →</button>
        </section>
      )}

      {step === 1 && (
        <section aria-label={steps[1]}>
          <label htmlFor="sos-desc" className="mb-2 block text-[17px] font-bold text-ink">{t("report.describe_title")}</label>
          <div className="relative">
            <textarea id="sos-desc" rows={5} value={draft.description}
              onChange={(e) => set({ description: e.target.value })}
              placeholder={t("report.describe_ph")} className="input pe-14" />
            <button onClick={toggleMic} aria-label={t("a11y.mic_button")} aria-pressed={listening}
              className={`absolute end-2 top-2 flex h-12 w-12 items-center justify-center rounded-full ${listening ? "bg-alert-600 text-white" : "bg-brand-100 text-brand-700"}`}>
              <Mic size={22} aria-hidden />
            </button>
          </div>
          <p className="mt-2 text-[14px] text-muted">{t("report.mic_hint")}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {HINTS.map((h) => (
              <button key={h} onClick={() => set({ description: (draft.description + " " + t(h)).trim() })} className="chip min-h-[40px] px-3 text-[14px]">
                {t(h)}
              </button>
            ))}
          </div>
          <button onClick={next} className="btn-primary mt-5 w-full">{t("common.continue")} →</button>
        </section>
      )}

      {step === 2 && (
        <section aria-label={steps[2]}>
          <h2 className="mb-2 text-[17px] font-bold text-ink">{t("report.location_title")}</h2>
          {bw ? (
            <div>
              <label className="mb-1 block text-[14px] font-semibold text-body">{t("report.district_label")}</label>
              <select value={draft.districtId} onChange={(e) => set({ districtId: e.target.value })} className="input">
                <option value="">—</option>
                {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
          ) : (
            <>
              <SosMap
                reports={draft.lat != null ? [{ id: "draft", client_report_id: "", description: "", language: "", category: "other", severity: 3, severity_rationale: null, priority: "medium", status: "reported", lat: draft.lat, lon: draft.lon, district_id: null, photo_url: null, photo_hash: null, reporter_name: null, reporter_phone: null, needed_skills: [], is_demo_data: false, created_at: "", updated_at: "" }] : []}
                center={draft.lat != null ? [draft.lat, draft.lon!] : [25.5941, 85.1376]}
                zoom={draft.lat != null ? 14 : 6}
                showHeatmap={false}
                height={260}
              />
              <p className="mt-1 text-[13px] text-muted">{t("report.location_hint")}</p>
              <button onClick={useGps} disabled={gpsBusy} className="btn-secondary mt-3 w-full">
                <Navigation size={18} aria-hidden /> {gpsBusy ? t("common.loading") : t("report.use_gps")}
              </button>
              {draft.lat != null && (
                <p className="num-ltr mt-2 text-center text-[14px] text-muted">
                  <MapPin size={14} className="inline" aria-hidden /> {draft.lat.toFixed(4)}, {draft.lon!.toFixed(4)}
                </p>
              )}
            </>
          )}
          <label className="mb-1 mt-3 block text-[14px] font-semibold text-body">{t("report.district_label")}</label>
          <select value={draft.districtId} onChange={(e) => set({ districtId: e.target.value })} className="input">
            <option value="">—</option>
            {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <button onClick={next} className="btn-primary mt-5 w-full">{t("common.continue")} →</button>
        </section>
      )}

      {step === 3 && (
        <section aria-label={steps[3]}>
          <h2 className="mb-3 text-[17px] font-bold text-ink">{t("report.review_title")}</h2>
          <div className="card mb-3 flex gap-3 p-3">
            {draft.photoDataUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={draft.photoDataUrl} alt="" className="h-16 w-16 rounded-btn object-cover" />
            )}
            <div className="min-w-0">
              <p className="line-clamp-2 text-[15px] text-ink">{draft.description}</p>
              <p className="mt-1 text-[13px] text-muted">
                📍 {draft.districtId ? districts.find((d) => d.id === draft.districtId)?.name : `${draft.lat?.toFixed(2)}, ${draft.lon?.toFixed(2)}`}
              </p>
            </div>
          </div>
          <label className="mb-1 block text-[14px] font-semibold text-body">{t("report.name_label")} <span className="font-normal text-muted">({t("common.optional")})</span></label>
          <input value={draft.name} onChange={(e) => set({ name: e.target.value })} placeholder={t("report.name_ph")} className="input mb-3" maxLength={120} />
          <label className="mb-1 block text-[14px] font-semibold text-body">{t("report.phone_label")} <span className="font-normal text-muted">({t("common.optional")})</span></label>
          <input value={draft.phone} onChange={(e) => set({ phone: e.target.value })} placeholder={t("report.phone_ph")} inputMode="tel" className="input mb-4" />
          {fieldError && <p role="alert" className="mb-3 rounded-btn bg-red-50 p-3 text-[14px] font-semibold text-red-700">{fieldError}</p>}
          <button onClick={send} disabled={sending || apiLoading} className="btn-sos w-full" aria-label={t("a11y.sos_button")}>
            <Siren size={22} aria-hidden /> {sending ? t("report.sending") : t("report.send_sos")}
          </button>
          <p className="mt-2 text-center text-[13px] text-muted">{t("report.offline_note")}</p>
        </section>
      )}

      {fieldError && step !== 3 && <p role="alert" className="mt-4 rounded-btn bg-red-50 p-3 text-[14px] font-semibold text-red-700">{fieldError}</p>}
      {step === 0 && <div className="mt-2" />}
    </div>
  );
}

/* Minimal local types for the Web Speech API (no DOM lib defs in older TS). */
interface SpeechRec { lang: string; interimResults: boolean; onresult: ((e: SpeechResultEvent) => void) | null; onend: (() => void) | null; onerror: (() => void) | null; start(): void; stop(): void; }
interface SpeechResultEvent { resultIndex: number; results: Array<Array<{ transcript: string }>>; }
