"use client";
/** HeatmapLegend — fixed gradient bar (design-system §5.13). */
import { useI18n } from "../lib/i18n";

export default function HeatmapLegend() {
  const { t } = useI18n();
  return (
    <div className="pointer-events-none absolute bottom-3 start-3 z-[400] rounded-btn bg-surface/90 px-3 py-2 shadow-card backdrop-blur">
      <div className="h-2.5 w-36 rounded-full" style={{ background: "linear-gradient(90deg,#22C55E,#EAB308,#F97316,#DC2626)" }} aria-hidden />
      <div className="mt-1 flex justify-between text-[11px] font-medium text-muted">
        <span>{t("board.fewer")}</span>
        <span>{t("board.more")}</span>
      </div>
    </div>
  );
}
