"use client";
/**
 * Landing (/) — wireframes/landing.md. Hero, 4-step how-it-works, live
 * StatTiles from seed data, mini map, demo-mode entry, volunteer CTA.
 */
import { ArrowRight, Camera, Cpu, LifeBuoy, Megaphone, Play, Siren, Sprout } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useOnline } from "../components/Header";
import { DemoDataChip as Honesty } from "../components/HonestyChip";
import { CardSkeleton, SectionTitle, StatTile } from "../components/ui";
import { playPatnaDemo, type DemoApiClient } from "../lib/demo";
import { useApi } from "../lib/api";
import { useI18n, isLowBandwidth } from "../lib/i18n";
import { useToast } from "../components/Toast";
import type { District, SOSReport } from "../lib/types";

const SosMap = dynamic(() => import("../components/SosMap"), { ssr: false, loading: () => <div className="shimmer h-[220px] rounded-card" /> });

const STEPS = [
  { Icon: Camera, t: "landing.step1t", d: "landing.step1d" },
  { Icon: Cpu, t: "landing.step2t", d: "landing.step2d" },
  { Icon: LifeBuoy, t: "landing.step3t", d: "landing.step3d" },
  { Icon: Megaphone, t: "landing.step4t", d: "landing.step4d" },
] as const;

function LandingInner() {
  const { t } = useI18n();
  const { api, mode, loading } = useApi();
  const { toast } = useToast();
  const online = useOnline();
  const [stats, setStats] = useState<{ sos: number; vol: number; shelters: number; districts: number } | null>(null);
  const [pins, setPins] = useState<SOSReport[]>([]);
  const [failed, setFailed] = useState(false);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (loading || !api) return;
    let alive = true;
    (async () => {
      try {
        const [sosPage, vols, shelters, districts] = await Promise.all([
          api.listSOS({ limit: 50, sort: "severity" }),
          api.listVolunteers({ limit: 1 }),
          api.listShelters({ limit: 1 }),
          api.getDistricts(),
        ]);
        if (!alive) return;
        setStats({ sos: sosPage.total, vol: vols.total, shelters: shelters.total, districts: districts.length });
        setPins(sosPage.items.filter((r) => r.lat != null));
      } catch {
        if (alive) setFailed(true);
      }
    })();
    return () => { alive = false; };
  }, [api, loading]);

  const playDemo = async () => {
    if (!api || playing || mode !== "demo") return;
    setPlaying(true);
    try {
      await playPatnaDemo(api as DemoApiClient, () => {});
      toast("success", t("toast.sent"));
    } finally {
      setPlaying(false);
      window.location.href = "/board?district=patna&severity_min=4";
    }
  };

  return (
    <div className="space-y-8">
      {/* Hero */}
      <section className="pt-4 text-center sm:pt-8">
        <h1 className="font-serif text-display text-ink">{t("landing.hero_title")}</h1>
        <p className="mx-auto mt-3 max-w-xl text-[17px] text-body">{t("landing.hero_sub")}</p>
        <div className="mx-auto mt-6 flex max-w-md flex-col gap-3">
          <Link href="/report" className="btn-sos w-full" aria-label={t("a11y.sos_button")}>
            <Siren size={22} aria-hidden /> {t("landing.report_sos")}
          </Link>
          {mode === "demo" && (
            <button onClick={playDemo} disabled={playing} className="btn-secondary w-full">
              <Play size={20} aria-hidden /> {playing ? t("common.loading") : t("landing.play_demo")}
            </button>
          )}
        </div>
        {!online && <p className="mt-3 text-[14px] font-medium text-amber-700">📶 {t("common.offline_banner")}</p>}
      </section>

      {/* How it works */}
      <section>
        <SectionTitle>{t("landing.how_it_works")}</SectionTitle>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {STEPS.map(({ Icon, t: tk, d: dk }, i) => (
            <div key={tk} className="card flex flex-col items-center gap-1 p-4 text-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-100 text-brand-700 dark:bg-brand-600 dark:text-white">
                <Icon size={24} aria-hidden />
              </span>
              <span className="num-ltr text-[12px] font-bold text-muted">0{i + 1}</span>
              <span className="text-[15px] font-bold text-ink">{t(tk)}</span>
              <span className="text-[13px] text-muted">{t(dk)}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Live stats */}
      <section>
        <SectionTitle>
          <span className="flex items-center gap-2">{t("landing.live_title")} <Honesty /></span>
        </SectionTitle>
        {failed ? (
          <div className="card p-4 text-center">
            <p className="mb-2 text-[14px] text-muted">{t("landing.api_down")}</p>
            <button onClick={() => window.location.reload()} className="btn-secondary">{t("common.retry")}</button>
          </div>
        ) : !stats ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4"><CardSkeleton /><CardSkeleton /><CardSkeleton /><CardSkeleton /></div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile value={stats.sos.toLocaleString("en-IN")} label={t("landing.stat_sos")} demoNote={t("landing.live_sub")} />
              <StatTile value={stats.vol.toLocaleString("en-IN")} label={t("landing.stat_volunteers")} demoNote={t("landing.live_sub")} />
              <StatTile value={stats.shelters.toLocaleString("en-IN")} label={t("landing.stat_shelters")} demoNote={t("landing.live_sub")} />
              <StatTile value={String(stats.districts)} label={t("landing.stat_districts")} demoNote={t("landing.live_sub")} />
            </div>
            {stats.sos === 0 && (
              <button onClick={playDemo} className="btn-secondary mt-3 w-full">
                <Sprout size={18} aria-hidden /> {t("landing.load_demo_data")}
              </button>
            )}
          </>
        )}
      </section>

      {/* Mini map */}
      <section>
        <SectionTitle>{t("landing.mini_map_title")}</SectionTitle>
        {isLowBandwidth() ? (
          <div className="card p-4">
            <p className="mb-2 text-[14px] text-muted">{t("common.text_list_note")}</p>
            <ul className="space-y-1">
              {pins.slice(0, 5).map((p) => (
                <li key={p.id} className="text-[14px] text-body">◆{p.severity} · {p.description.slice(0, 60)}…</li>
              ))}
            </ul>
            <Link href="/board" className="mt-2 inline-flex items-center gap-1 font-semibold text-brand-700">
              {t("landing.tap_to_board")} <ArrowRight size={16} aria-hidden className="flip-rtl" />
            </Link>
          </div>
        ) : (
          <Link href="/board" aria-label={t("landing.tap_to_board")} className="block">
            <SosMap reports={pins} height={220} showHeatmap zoom={6} center={[23.5, 82]} />
          </Link>
        )}
      </section>

      <section className="pb-4 text-center">
        <Link href="/volunteer?register=1" className="btn-secondary">
          {t("landing.become_volunteer")} <ArrowRight size={17} aria-hidden className="flip-rtl" />
        </Link>
        <p className="mt-4 text-[13px] text-muted">{t("landing.footer")}</p>
      </section>
    </div>
  );
}

export default function LandingPage() {
  return (
    <Suspense fallback={<CardSkeleton />}>
      <LandingInner />
    </Suspense>
  );
}
