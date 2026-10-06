"use client";
/**
 * /alerts — multilingual alert feed (wireframes/alerts-feed.md).
 * Per-alert language switcher = the multilingual wow-moment. Low-bandwidth:
 * this screen is already text-first.
 */
import { ChevronDown, Megaphone } from "lucide-react";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useApi } from "../../lib/api";
import { useI18n, LANG_META } from "../../lib/i18n";
import { timeAgo } from "../../lib/format";
import { useToast } from "../../components/Toast";
import BottomSheet from "../../components/BottomSheet";
import { DemoDataChip } from "../../components/HonestyChip";
import SeverityBadge from "../../components/SeverityBadge";
import { EmptyState, PageError, SectionTitle, SkeletonList } from "../../components/ui";
import type { AlertItem, AlertType, District, WSEvent } from "../../lib/types";

const TYPES: AlertType[] = ["flood", "heatwave", "cyclone", "custom"];
const TYPE_ICON: Record<AlertType, string> = { flood: "🌊", heatwave: "🌡️", cyclone: "🌀", custom: "📣" };

function AlertCard({ alert, districts }: { alert: AlertItem; districts: District[] }) {
  const { t, lang } = useI18n();
  const { api } = useApi();
  const [viewLang, setViewLang] = useState<string>(lang);
  const [sheet, setSheet] = useState(false);
  const [full, setFull] = useState<AlertItem>(alert);

  const openAll = async () => {
    setSheet(true);
    if (!full.messages && api) {
      try { setFull(await api.getAlert(alert.id)); } catch { /* keep card copy */ }
    }
  };

  const districtName = (id: string) => districts.find((d) => d.id === id)?.name ?? id;
  const shown = full.messages?.[viewLang] ?? alert.message;

  return (
    <article className="card animate-slide-in p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {alert.severity != null && <SeverityBadge severity={alert.severity} size="sm" />}
        <span className="pill border border-line bg-surface text-body">{TYPE_ICON[alert.type]} {t(`atype.${alert.type}`)}</span>
        <DemoDataChip />
      </div>
      <p className="text-alert-sms mb-2 text-ink" lang={viewLang}>{shown}</p>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-2 text-[13px] text-muted">
        <span>
          📍 {alert.district_ids.map(districtName).join(", ")} · <span className="num-ltr">{timeAgo(alert.created_at)}</span> · {t("alerts.via_sms")} ✓
        </span>
        <button onClick={openAll} className="inline-flex min-h-[44px] items-center gap-1 font-semibold text-brand-700">
          {t("alerts.view_in")}: {LANG_META[viewLang as keyof typeof LANG_META]?.native} <ChevronDown size={15} aria-hidden />
        </button>
      </div>
      <BottomSheet open={sheet} onClose={() => setSheet(false)} title={t("alerts.all_languages")}>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {alert.languages.map((c) => (
            <button key={c} onClick={() => setViewLang(c)} aria-pressed={viewLang === c}
              className={`chip min-h-[44px] px-3 text-[14px] ${viewLang === c ? "chip-active" : ""}`}>
              {LANG_META[c as keyof typeof LANG_META]?.native ?? c}
            </button>
          ))}
        </div>
        {(full.messages ? Object.entries(full.messages) : [[viewLang, shown]] as [string, string][]).map(([c, msg]) => (
          <div key={c} className="mb-2 rounded-card border border-line p-3">
            <p className="mb-1 text-[12px] font-bold uppercase tracking-wide text-muted">{LANG_META[c as keyof typeof LANG_META]?.native ?? c}</p>
            <p className="text-alert-sms text-ink" lang={c}>{msg}</p>
          </div>
        ))}
      </BottomSheet>
    </article>
  );
}

function AlertsInner() {
  const { t } = useI18n();
  const { api, loading: apiLoading } = useApi();
  const params = useSearchParams();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [districts, setDistricts] = useState<District[]>([]);
  const [district, setDistrict] = useState(params.get("district") ?? "");
  const [type, setType] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [risk, setRisk] = useState<{ risk: number; level: string } | null>(null);

  const fetchAlerts = useCallback(async () => {
    if (!api) return;
    setLoading(true); setError(false);
    try {
      const page = await api.listAlerts({ district: district || undefined, type: (type || undefined) as AlertType | undefined, limit: 50 });
      setAlerts(page.items);
      if (district) {
        const r = await api.getDistrictRisk(district);
        setRisk({ risk: r.risk, level: r.risk_level });
      } else setRisk(null);
    } catch { setError(true); } finally { setLoading(false); }
  }, [api, district, type]);

  useEffect(() => { if (!apiLoading && api) api.getDistricts().then(setDistricts).catch(() => {}); }, [api, apiLoading]);
  useEffect(() => { if (!apiLoading && api) fetchAlerts(); }, [api, apiLoading, fetchAlerts]);

  useEffect(() => {
    if (!api) return;
    const unsub = api.subscribe((e: WSEvent) => {
      if (e.type === "alert.broadcast") fetchAlerts();
    }, district ? [district] : []);
    return unsub;
  }, [api, district, fetchAlerts]);

  return (
    <div className="mx-auto max-w-2xl">
      <SectionTitle>{t("alerts.title")}</SectionTitle>
      <div className="mb-3 flex flex-wrap gap-2">
        <select value={district} onChange={(e) => setDistrict(e.target.value)} className="input w-auto" aria-label={t("alerts.f_district")}>
          <option value="">{t("alerts.f_district")}: {t("common.all")}</option>
          {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <select value={type} onChange={(e) => setType(e.target.value)} className="input w-auto" aria-label={t("alerts.f_type")}>
          <option value="">{t("alerts.f_type")}: {t("common.all")}</option>
          {TYPES.map((k) => <option key={k} value={k}>{TYPE_ICON[k]} {t(`atype.${k}`)}</option>)}
        </select>
      </div>

      {loading ? <SkeletonList /> : error ? <PageError onRetry={fetchAlerts} />
        : alerts.length === 0 ? (
          <EmptyState icon={<Megaphone size={64} strokeWidth={1.25} aria-hidden />}
            title={t("alerts.no_alerts")}
            sub={risk ? `${t("alerts.no_alerts_sub")} ${risk.risk} · ${risk.level}` : t("alerts.no_alerts_sub")} />
        ) : (
          <div className="space-y-3">
            {alerts.map((a) => <AlertCard key={a.id} alert={a} districts={districts} />)}
          </div>
        )}
    </div>
  );
}

export default function AlertsPage() {
  return (
    <Suspense fallback={<SkeletonList />}>
      <AlertsInner />
    </Suspense>
  );
}
