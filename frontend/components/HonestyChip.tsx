"use client";
/** Honesty chips — DEMO DATA / SIMULATED FEED. Translated strings (i18n plan §7). Always rendered when data is synthetic. */
import { FlaskConical, Radio } from "lucide-react";
import { useI18n } from "../lib/i18n";

export function DemoDataChip() {
  const { t } = useI18n();
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-dashed border-amber-600 bg-amber-50 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-amber-800 dark:bg-amber-950 dark:text-amber-200">
      <FlaskConical size={12} aria-hidden /> {t("common.demo_data")}
    </span>
  );
}

export function SimulatedFeedChip() {
  const { t } = useI18n();
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-dashed border-sky-600 bg-sky-50 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-sky-800 dark:bg-sky-950 dark:text-sky-200">
      <Radio size={12} aria-hidden /> {t("common.simulated_feed")}
    </span>
  );
}
