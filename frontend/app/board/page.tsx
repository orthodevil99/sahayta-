"use client";
/**
 * /board — SOS board (wireframes/sos-board.md).
 * Variant A map-first (≥1024px), Variant B list-first (mobile / low-bandwidth).
 * Filters map 1:1 to GET /api/sos params. Live via api.subscribe().
 */
import { Flag, LayoutGrid, Map as MapIcon, Search, ShieldCheck, UserPlus } from "lucide-react";
import dynamic from "next/dynamic";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useApi } from "../../lib/api";
import { useI18n, isLowBandwidth } from "../../lib/i18n";
import { timeAgo } from "../../lib/format";
import { useToast } from "../../components/Toast";
import { useOnline } from "../../components/Header";
import BottomSheet from "../../components/BottomSheet";
import CategoryChip from "../../components/CategoryChip";
import { DemoDataChip } from "../../components/HonestyChip";
import SeverityBadge from "../../components/SeverityBadge";
import SOSCard from "../../components/SOSCard";
import { StatusPill } from "../../components/StatusPill";
import { EmptyState, PageError, SectionTitle, SkeletonList } from "../../components/ui";
import type { District, SOSCategory, SOSReport, SOSStatus, WSEvent } from "../../lib/types";

const SosMap = dynamic(() => import("../../components/SosMap"), { ssr: false, loading: () => <div className="shimmer h-[420px] rounded-card" /> });

const CATS: SOSCategory[] = ["medical", "rescue", "food", "shelter", "infrastructure", "other"];
const STATUSES: SOSStatus[] = ["reported", "verified", "help_on_way", "resolved", "duplicate", "rejected"];

function BoardInner() {
  const { t } = useI18n();
  const { api, loading: apiLoading } = useApi();
  const { toast } = useToast();
  const online = useOnline();
  const params = useSearchParams();
  const [reports, setReports] = useState<SOSReport[]>([]);
  const [total, setTotal] = useState(0);
  const [districts, setDistricts] = useState<District[]>([]);
  const [district, setDistrict] = useState(params.get("district") ?? "");
  const [sevMin, setSevMin] = useState<number>(Number(params.get("severity_min") ?? 0));
  const [status, setStatus] = useState<string>("");
  const [category, setCategory] = useState<string>("");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"-created_at" | "severity">("-created_at");
  const [variant, setVariant] = useState<"auto" | "map" | "list">("auto");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState<SOSReport | null>(null);
  const [pulseId, setPulseId] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [reconnecting, setReconnecting] = useState(false);
  const [bw, setBw] = useState(false);
  const [isDesktop, setIsDesktop] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setBw(isLowBandwidth());
    const mq = window.matchMedia("(min-width: 1024px)");
    setIsDesktop(mq.matches);
    const onMq = (e: MediaQueryListEvent) => setIsDesktop(e.matches);
    mq.addEventListener("change", onMq);
    return () => mq.removeEventListener("change", onMq);
  }, []);

  const showMap = !bw && (variant === "map" || (variant === "auto" && isDesktop));

  const fetchReports = useCallback(async () => {
    if (!api) return;
    setLoading(true); setError(false);
    try {
      const page = await api.listSOS({
        district: district || undefined,
        severity_min: sevMin || undefined,
        status: (status || undefined) as SOSStatus | undefined,
        category: (category || undefined) as SOSCategory | undefined,
        q: q || undefined, limit: 100, sort,
      });
      setReports(page.items); setTotal(page.total);
      setUpdatedAt(new Date());
    } catch { setError(true); } finally { setLoading(false); }
  }, [api, district, sevMin, status, category, q, sort]);

  useEffect(() => { if (!apiLoading && api) { api.getDistricts().then(setDistricts).catch(() => {}); } }, [api, apiLoading]);
  useEffect(() => { if (!apiLoading && api) fetchReports(); }, [api, apiLoading, fetchReports]);

  // Live updates.
  useEffect(() => {
    if (!api) return;
    const unsub = api.subscribe((e: WSEvent) => {
      if (e.type === "sos.created") {
        const r = e.data as SOSReport;
        setReports((prev) => (prev.some((x) => x.id === r.id) ? prev : [r, ...prev]));
        setTotal((n) => n + 1); setUpdatedAt(new Date());
      } else if (e.type === "sos.assessed") {
        const d = e.data as { sos_id: string; severity: number };
        setReports((prev) => prev.map((r) => (r.id === d.sos_id ? { ...r, severity: d.severity as SOSReport["severity"] } : r)));
        setPulseId(d.sos_id); setTimeout(() => setPulseId(null), 2500);
      } else if (e.type === "sos.status_changed") {
        const d = e.data as { sos_id: string; to: SOSStatus };
        setReports((prev) => prev.map((r) => (r.id === d.sos_id ? { ...r, status: d.to } : r)));
        setPulseId(d.sos_id); setTimeout(() => setPulseId(null), 2500);
      }
    }, district ? [district] : []);
    return unsub;
  }, [api, district]);

  const openDetail = async (id: string) => {
    if (!api) return;
    try { setSelected(await api.getSOS(id)); }
    catch { const r = reports.find((x) => x.id === id); if (r) setSelected(r); }
  };

  const doVerify = async () => {
    if (!api || !selected) return;
    try { const r = await api.verifySOS(selected.id, "verified"); setSelected(r); setReports((p) => p.map((x) => (x.id === r.id ? r : x))); toast("success", t("toast.task_done")); }
    catch { toast("error", t("common.retry")); }
  };
  const doFlag = async () => {
    if (!api || !selected) return;
    try { await api.flagSOS(selected.id, "other", "flagged from board"); toast("success", t("toast.sent")); }
    catch { toast("error", t("common.retry")); }
  };

  const filterBar = (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <select value={district} onChange={(e) => setDistrict(e.target.value)} className="input w-auto" aria-label={t("board.f_district")}>
        <option value="">{t("board.f_district")}: {t("common.all")}</option>
        {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
      </select>
      <select value={sevMin} onChange={(e) => setSevMin(Number(e.target.value))} className="input w-auto" aria-label={t("board.f_sev")}>
        <option value={0}>{t("board.f_sev")} —</option>
        {[1, 2, 3, 4, 5].map((s) => <option key={s} value={s}>≥ {s}</option>)}
      </select>
      <select value={status} onChange={(e) => setStatus(e.target.value)} className="input w-auto" aria-label={t("board.f_status")}>
        <option value="">{t("board.f_status")}: {t("common.all")}</option>
        {STATUSES.map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}
      </select>
      <select value={category} onChange={(e) => setCategory(e.target.value)} className="input w-auto" aria-label={t("board.f_cat")}>
        <option value="">{t("board.f_cat")}: {t("common.all")}</option>
        {CATS.map((c) => <option key={c} value={c}>{t(`category.${c}`)}</option>)}
      </select>
      <div className="relative">
        <Search size={16} className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("board.f_search")} className="input ps-9" aria-label={t("board.f_search")} />
      </div>
      <select value={sort} onChange={(e) => setSort(e.target.value as "-created_at" | "severity")} className="input w-auto" aria-label="sort">
        <option value="-created_at">↓ {t("common.just_now")}</option>
        <option value="severity">◆ {t("board.f_sev")}</option>
      </select>
      {!bw && (
        <button onClick={() => setVariant((v) => (v === "map" ? "list" : v === "list" ? "auto" : "map"))}
          className="btn-secondary min-h-[48px] px-3" aria-label={t("a11y.toggle_view")}>
          {showMap ? <LayoutGrid size={18} aria-hidden /> : <MapIcon size={18} aria-hidden />}
          <span className="text-[14px]">{showMap ? t("board.list_view") : t("board.map_view")}</span>
        </button>
      )}
    </div>
  );

  const list = (
    <div ref={listRef} className="space-y-3" aria-label={t("a11y.map_list")}>
      {loading ? <SkeletonList /> : error ? <PageError onRetry={fetchReports} />
        : reports.length === 0 ? (
          <EmptyState title={t("board.no_results")} sub={t("board.no_results_sub")}
            action={<a href="/report" className="btn-sos">🚨 {t("board.report_one")}</a>} />
        ) : reports.map((r) => (
          <SOSCard key={r.id} report={r} pulse={pulseId === r.id} onOpen={() => openDetail(r.id)} />
        ))}
    </div>
  );

  return (
    <div>
      <SectionTitle>
        <span className="flex items-center gap-2">
          {t("board.title")}
          <span className="inline-flex items-center gap-1.5 text-[14px] font-semibold text-red-600" role="status" aria-live="polite">
            <span className="relative flex h-2.5 w-2.5"><span className="absolute h-full w-full animate-ping rounded-full bg-red-500 opacity-75" /><span className="h-2.5 w-2.5 rounded-full bg-red-600" /></span>
            {t("board.live")} · <span className="num-ltr">{total}</span> {t("board.reports")}
          </span>
          {updatedAt && <span className="text-[12px] font-normal text-muted">{t("board.updated_ago", { n: Math.max(1, Math.round((Date.now() - updatedAt.getTime()) / 1000)) })}</span>}
        </span>
      </SectionTitle>
      <div className="mb-2"><DemoDataChip /></div>
      {reconnecting && <p className="mb-2 text-[13px] text-amber-700">{t("common.reconnecting")}</p>}
      {!online && <p className="mb-2 text-[13px] text-muted">{t("board.cached_at", { t: updatedAt ? updatedAt.toLocaleTimeString() : "—" })}</p>}
      {filterBar}
      {showMap ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
          <SosMap reports={reports} showHeatmap onPinClick={openDetail} selectedId={selected?.id} height={480} />
          <div className="max-h-[480px] overflow-y-auto pe-1">{list}</div>
        </div>
      ) : list}

      {/* Detail sheet */}
      <BottomSheet open={!!selected} onClose={() => setSelected(null)} title={t("common.view_details")}>
        {selected && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              {selected.severity != null && <SeverityBadge severity={selected.severity} />}
              <CategoryChip category={selected.category} />
              <StatusPill status={selected.status} />
              {selected.is_demo_data && <DemoDataChip />}
            </div>
            <p className="text-[16px] leading-relaxed text-ink">{selected.description}</p>
            <p className="text-[13px] text-muted">
              {selected.district_id} · <span className="num-ltr">{timeAgo(selected.created_at)}</span>
              {selected.reporter_name && <> · {t("board.reported_by")}: {selected.reporter_name}</>}
            </p>
            {selected.assessment && (
              <div className="rounded-card border border-line bg-appbg p-3">
                <h4 className="mb-1 text-[14px] font-bold text-ink">{t("board.detail_assessment")}</h4>
                <p className="text-[14px] text-body">“{selected.assessment.rationale}”</p>
                <p className="mt-1 text-[12px] text-muted">{t("board.model_label")}: <span className="num-ltr">{selected.assessment.model}</span></p>
                {selected.assessment.area_tags?.length > 0 && (
                  <p className="mt-1 text-[12px] text-muted">{selected.assessment.area_tags.join(" · ")}</p>
                )}
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <button onClick={doVerify} className="btn-secondary min-h-[48px] px-4 text-[14px]"><ShieldCheck size={17} aria-hidden /> {t("board.verify")}</button>
              <button onClick={doFlag} className="btn-secondary min-h-[48px] px-4 text-[14px]"><Flag size={17} aria-hidden /> {t("board.flag")}</button>
              <a href={`/admin`} className="btn-secondary min-h-[48px] px-4 text-[14px]"><UserPlus size={17} aria-hidden /> {t("board.assign")}</a>
            </div>
          </div>
        )}
      </BottomSheet>
    </div>
  );
}

export default function BoardPage() {
  return (
    <Suspense fallback={<SkeletonList />}>
      <BoardInner />
    </Suspense>
  );
}
