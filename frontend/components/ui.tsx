"use client";
/** Small shared UI atoms: EmptyState, skeletons, section headers. */
import { MapPinned } from "lucide-react";
import { useI18n } from "../lib/i18n";

export function EmptyState({ icon, title, sub, action }: { icon?: React.ReactNode; title: string; sub?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <div className="text-muted">{icon ?? <MapPinned size={64} strokeWidth={1.25} aria-hidden />}</div>
      <h3 className="text-[18px] font-bold text-ink">{title}</h3>
      {sub && <p className="max-w-xs text-[15px] text-muted">{sub}</p>}
      {action}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="card space-y-3 p-4" aria-hidden>
      <div className="shimmer h-6 w-2/3 rounded" />
      <div className="shimmer h-4 w-full rounded" />
      <div className="shimmer h-4 w-5/6 rounded" />
    </div>
  );
}

export function SkeletonList({ n = 3 }: { n?: number }) {
  return (
    <div className="space-y-3" aria-label="loading">
      {Array.from({ length: n }).map((_, i) => <CardSkeleton key={i} />)}
    </div>
  );
}

export function PageError({ onRetry }: { onRetry: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <p className="text-[16px] font-semibold text-ink">⚠</p>
      <button onClick={onRetry} className="btn-secondary">{t("common.retry")}</button>
    </div>
  );
}

export function SectionTitle({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className="text-[18px] font-bold text-ink">{children}</h2>
      {action}
    </div>
  );
}

export function StatTile({ value, label, demoNote }: { value: string; label: string; demoNote?: string }) {
  return (
    <div className="card flex flex-col items-start gap-1 p-4">
      <span className="num-ltr text-[32px] font-extrabold leading-none text-brand-700 dark:text-brand-100">{value}</span>
      <span className="text-[14px] font-medium text-body">{label}</span>
      {demoNote && <span className="text-[11px] text-muted">{demoNote}</span>}
    </div>
  );
}
