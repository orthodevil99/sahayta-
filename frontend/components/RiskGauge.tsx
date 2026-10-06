"use client";
/** RiskGauge — 0–100 semicircular gauge (design-system §5.12). */
import { useI18n } from "../lib/i18n";
import type { RiskFactor, RiskLevel } from "../lib/types";

const BAND_COLOR: Record<RiskLevel, string> = { low: "#16A34A", moderate: "#EAB308", high: "#F97316", severe: "#DC2626" };

export default function RiskGauge({ risk, level, factors }: { risk: number; level: RiskLevel; factors?: RiskFactor[] }) {
  const { t } = useI18n();
  const angle = -90 + (Math.min(100, Math.max(0, risk)) / 100) * 180;
  const color = BAND_COLOR[level];
  const maxContrib = Math.max(1, ...(factors ?? []).map((f) => f.contribution));
  return (
    <div className="card p-4">
      <div className="relative mx-auto h-[110px] w-[220px]" role="img" aria-label={`Risk ${risk}, ${t(`risk.${level}`)}`}>
        <svg viewBox="0 0 220 110" className="h-full w-full">
          <path d="M 20 100 A 90 90 0 0 1 200 100" fill="none" stroke="#E2E8F0" strokeWidth="18" strokeLinecap="round" />
          <path d="M 20 100 A 90 90 0 0 1 200 100" fill="none" stroke={color} strokeWidth="18" strokeLinecap="round"
            strokeDasharray={`${(risk / 100) * 283} 283`} />
          <g transform={`rotate(${angle} 110 100)`}>
            <line x1="110" y1="100" x2="110" y2="30" stroke="#0F172A" strokeWidth="4" strokeLinecap="round" className="dark:stroke-white" />
          </g>
          <circle cx="110" cy="100" r="8" fill="#0F172A" className="dark:fill-white" />
        </svg>
        <div className="absolute inset-x-0 bottom-0 text-center">
          <span className="num-ltr num-big" style={{ color }}>{risk}</span>
          <div className="text-[13px] font-bold uppercase tracking-wide" style={{ color }}>{t(`risk.${level}`)}</div>
        </div>
      </div>
      {factors && factors.length > 0 && (
        <div className="mt-3 space-y-2">
          {factors.map((f) => (
            <div key={f.name} title={f.note}>
              <div className="flex items-baseline justify-between text-[13px]">
                <span className="font-medium text-body">{f.name.replaceAll("_", " ")}</span>
                <span className="num-ltr font-bold text-ink">+{f.contribution}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-line">
                <div className="h-full rounded-full" style={{ width: `${(f.contribution / maxContrib) * 100}%`, backgroundColor: color }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
