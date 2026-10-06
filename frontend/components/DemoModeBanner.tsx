"use client";
/**
 * DemoModeBanner — striped amber banner (design-system §5.17) + the
 * "▶ Play Patna flood demo" entry point. Toggles demo/REST mode.
 */
import { FlaskConical, Play, RotateCcw } from "lucide-react";
import { useState } from "react";
import { setDemoMode, useApi } from "../lib/api";
import { playPatnaDemo, resetDemo, type DemoApiClient, type DemoStep } from "../lib/demo";
import { useI18n } from "../lib/i18n";
import BottomSheet from "./BottomSheet";

const STEP_LABEL_KEYS: Record<string, string> = {
  report: "demo.step_report", assess: "demo.step_assess", match: "demo.step_match",
  accept: "demo.step_accept", enroute: "demo.step_enroute", complete: "demo.step_complete",
  broadcast: "demo.step_broadcast", dashboard: "demo.step_dashboard",
};

export default function DemoModeBanner() {
  const { t } = useI18n();
  const { api, mode } = useApi();
  const [playing, setPlaying] = useState(false);
  const [steps, setSteps] = useState<DemoStep[]>([]);
  const [showSteps, setShowSteps] = useState(false);

  if (mode !== "demo") return null;

  const play = async () => {
    if (!api || playing) return;
    setPlaying(true);
    setShowSteps(true);
    try {
      await playPatnaDemo(api as DemoApiClient, setSteps);
    } finally {
      setPlaying(false);
    }
  };

  const goLive = () => {
    setDemoMode(false);
    window.dispatchEvent(new Event("sahayta:demo-toggle"));
  };

  return (
    <>
      <div
        className="flex items-center justify-center gap-2 px-3 py-2 text-center text-[13px] font-bold text-amber-950"
        style={{ background: "repeating-linear-gradient(45deg,#FEF3C7 0 16px,#FDE68A 16px 32px)" }}
        role="status"
      >
        <FlaskConical size={15} aria-hidden />
        <span>{t("common.demo_mode_banner")}</span>
        <button onClick={play} disabled={playing} className="underline underline-offset-2 disabled:opacity-50">
          <Play size={13} className="me-1 inline" aria-hidden />
          {t("landing.play_demo")}
        </button>
        <button
          onClick={() => { if (confirm(t("demo.reset_confirm"))) { resetDemo(); window.location.reload(); } }}
          className="underline underline-offset-2"
          title={t("demo.reset_label")}
          aria-label={t("demo.reset_label")}
        >
          <RotateCcw size={13} aria-hidden />
        </button>
        {process.env.NEXT_PUBLIC_API_URL && (
          <button onClick={goLive} className="underline underline-offset-2">{t("demo.go_live")}</button>
        )}
      </div>
      <BottomSheet open={showSteps} onClose={() => setShowSteps(false)} title={t("landing.play_demo")}>
        <ol className="space-y-2">
          {steps.map((s) => (
            <li key={s.key} className="flex items-center gap-3 text-[15px]">
              <span className={`flex h-7 w-7 items-center justify-center rounded-full text-[13px] font-bold ${s.done ? "bg-green-600 text-white" : "bg-line text-muted"}`}>
                {s.done ? "✓" : "·"}
              </span>
              <span className={s.done ? "text-ink" : "text-muted"}>{t(STEP_LABEL_KEYS[s.key] ?? "common.view_details")}</span>
            </li>
          ))}
        </ol>
        {!playing && steps.length > 0 && steps.every((s) => s.done) && (
          <p className="mt-4 text-[14px] font-semibold text-green-700">{t("demo.complete_note")}</p>
        )}
      </BottomSheet>
    </>
  );
}
