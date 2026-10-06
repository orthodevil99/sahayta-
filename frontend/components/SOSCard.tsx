"use client";
/** SOSCard — the board's unit of information (design-system §5.4). */
import { MapPin } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { timeAgo } from "../lib/format";
import type { SOSReport } from "../lib/types";
import { DemoDataChip } from "./HonestyChip";
import SeverityBadge from "./SeverityBadge";
import CategoryChip, { SkillIcons } from "./CategoryChip";
import { StatusPill } from "./StatusPill";

export default function SOSCard({ report, onOpen, pulse = false, distanceKm }: {
  report: SOSReport; onOpen?: () => void; pulse?: boolean; distanceKm?: number;
}) {
  const { t } = useI18n();
  return (
    <article
      className={`card cursor-pointer p-4 text-start ${pulse ? "animate-slide-in" : ""}`}
      onClick={onOpen}
      onKeyDown={(e) => { if (e.key === "Enter" && onOpen) onOpen(); }}
      tabIndex={0}
      role="button"
      aria-label={`${t("common.view_details")}: ${report.description.slice(0, 60)}`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        {report.severity != null
          ? <SeverityBadge severity={report.severity} size="sm" />
          : <span className="pill bg-line text-muted">🔍 {t("report.awaiting_review")}</span>}
        <span className="flex items-center gap-2">
          {report.is_demo_data && <DemoDataChip />}
          <span className="num-ltr text-[13px] text-muted">{timeAgo(report.created_at)}</span>
        </span>
      </div>
      <p className="mb-2 line-clamp-2 text-[15px] leading-snug text-ink">{report.description}</p>
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <CategoryChip category={report.category} />
        <StatusPill status={report.status} pulse={pulse} />
        <span className="text-[12px] font-semibold uppercase tracking-wide text-muted">{t(`priority.${report.priority}`)}</span>
      </div>
      <div className="flex items-center justify-between text-[13px] text-muted">
        <span className="inline-flex items-center gap-1">
          <MapPin size={13} aria-hidden />
          {report.district_id ? report.district_id[0].toUpperCase() + report.district_id.slice(1) : "—"}
          {distanceKm != null && <span className="num-ltr">· {t("common.km_away", { n: distanceKm.toFixed(1) })}</span>}
        </span>
        {report.needed_skills?.length > 0 && (
          <span className="inline-flex items-center gap-1">
            <span className="text-[12px]">{t("board.needed")}:</span>
            <SkillIcons skills={report.needed_skills} />
          </span>
        )}
      </div>
    </article>
  );
}
