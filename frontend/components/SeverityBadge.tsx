"use client";
/** SeverityBadge — FROZEN scale (design-system §1.1/§5.2). Never invent a 6th level. */
import { Circle, Diamond, Triangle } from "lucide-react";
import { useI18n } from "../lib/i18n";
import type { Severity } from "../lib/types";

const STYLE: Record<Severity, { bg: string; tint: string; text: string; Icon: typeof Circle }> = {
  1: { bg: "#16A34A", tint: "#DCFCE7", text: "#14532D", Icon: Circle },
  2: { bg: "#65A30D", tint: "#ECFCCB", text: "#365314", Icon: Circle },
  3: { bg: "#D97706", tint: "#FEF3C7", text: "#78350F", Icon: Triangle },
  4: { bg: "#DC2626", tint: "#FEE2E2", text: "#7F1D1D", Icon: Diamond },
  5: { bg: "#7F1D1D", tint: "#FECACA", text: "#450A0A", Icon: Diamond },
};

export function severityStyle(sev: Severity) {
  return STYLE[sev];
}

export default function SeverityBadge({ severity, size = "md" }: { severity: Severity; size?: "sm" | "md" | "lg" }) {
  const { t } = useI18n();
  const s = STYLE[severity];
  const name = t(`severity.s${severity}`);
  const pad = size === "sm" ? "min-h-[32px] px-2.5 text-[13px]" : size === "lg" ? "min-h-[56px] px-5 text-[20px]" : "min-h-[44px] px-3.5 text-[16px]";
  const iconSize = size === "sm" ? 14 : size === "lg" ? 24 : 18;
  return (
    <span
      role="img"
      aria-label={t("a11y.severity_badge", { n: severity, name })}
      className={`inline-flex items-center gap-2 rounded-full font-extrabold text-white ${pad} ${severity === 5 ? "sev5-stripes" : ""}`}
      style={{ backgroundColor: severity === 5 ? undefined : s.bg }}
    >
      {severity === 5 ? (
        <span aria-hidden className="flex flex-col gap-[3px]">
          <span className="block h-[4px] w-[18px] rounded-sm bg-white" />
          <span className="block h-[4px] w-[18px] rounded-sm bg-white" />
        </span>
      ) : (
        <s.Icon size={iconSize} aria-hidden fill="currentColor" strokeWidth={0} />
      )}
      <span className="num-ltr tabular-nums">{severity}</span>
      <span className="text-[12px] font-bold uppercase tracking-wide">{name}</span>
    </span>
  );
}
