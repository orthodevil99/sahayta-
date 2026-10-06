"use client";
/** BottomSheet — mobile-first detail container (design-system §5.6). */
import { X } from "lucide-react";
import { useEffect } from "react";
import { useI18n } from "../lib/i18n";

export default function BottomSheet({
  open, onClose, title, children,
}: {
  open: boolean; onClose: () => void; title?: string; children: React.ReactNode;
}) {
  const { t } = useI18n();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-[#0F172A]/50" onClick={onClose} aria-hidden />
      <div className="relative max-h-[70vh] w-full max-w-lg overflow-y-auto rounded-t-sheet bg-surface p-5 shadow-sheet sm:rounded-card">
        <div className="mx-auto mb-3 h-1.5 w-12 rounded-full bg-line" aria-hidden />
        <div className="mb-3 flex items-center justify-between">
          {title ? <h3 className="text-[18px] font-bold text-ink">{title}</h3> : <span />}
          <button onClick={onClose} aria-label={t("a11y.close_sheet")} className="flex min-h-[48px] min-w-[48px] items-center justify-center rounded-full text-muted hover:bg-appbg">
            <X size={22} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
