"use client";
/**
 * Header — wordmark, nav, a11y cluster (🌐 language | A± font | ◐ contrast |
 * theme | 📶 low-bandwidth), offline banner, queue badge.
 */
import { Contrast, Home, Megaphone, Moon, ClipboardList, Signal, Siren, Sun, Type, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cycleFontSize, isLowBandwidth, toggleHighContrast, toggleLowBandwidth, toggleTheme, useI18n } from "../lib/i18n";
import { outboxCount } from "../lib/outbox";
import { useToast } from "./Toast";
import DemoModeBanner from "./DemoModeBanner";
import LanguageSwitcher from "./LanguageSwitcher";

const NAV = [
  { href: "/", key: "nav.home", Icon: Home },
  { href: "/report", key: "nav.report", Icon: Siren },
  { href: "/board", key: "nav.board", Icon: ClipboardList },
  { href: "/volunteer", key: "nav.volunteer", Icon: Users },
  { href: "/alerts", key: "nav.alerts", Icon: Megaphone },
  { href: "/admin", key: "nav.admin", Icon: Signal },
];

export function useOnline(): boolean {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    setOnline(navigator.onLine);
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);
  return online;
}

export default function Header() {
  const { t, lang } = useI18n();
  const pathname = usePathname();
  const online = useOnline();
  const { toast } = useToast();
  const [queue, setQueue] = useState(0);
  const [bw, setBw] = useState(false);
  const [dark, setDark] = useState(false);
  const [hc, setHc] = useState(false);

  useEffect(() => {
    setBw(isLowBandwidth());
    setDark(document.documentElement.classList.contains("dark"));
    setHc(document.body.classList.contains("high-contrast"));
    let alive = true;
    const refresh = async () => { try { const n = await outboxCount(); if (alive) setQueue(n); } catch { /* */ } };
    refresh();
    const id = setInterval(refresh, 5000);
    // First-run language suggestion toast (i18n §1).
    const sug = sessionStorage.getItem("sahayta.suggest_lang");
    if (sug) {
      sessionStorage.removeItem("sahayta.suggest_lang");
      toast("success", `Switch to ${sug}? Use the 🌐 button anytime.`);
    }
    return () => { alive = false; clearInterval(id); };
  }, [toast]);

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-surface/95 backdrop-blur">
      <DemoModeBanner />
      {!online && (
        <div className="bg-[#FEF3C7] px-3 py-1.5 text-center text-[13px] font-semibold text-amber-900" role="alert">
          📶 {t("common.offline_banner")}
        </div>
      )}
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-1 px-3">
        <Link href="/" className="flex min-h-[56px] items-center gap-2" aria-label={t("common.app_name")}>
          <span className="flex h-9 w-9 items-center justify-center rounded-btn bg-alert-600 text-white">
            <Siren size={20} aria-hidden />
          </span>
          <span className="text-[19px] font-extrabold tracking-tight text-ink">{t("common.app_name")}</span>
        </Link>
        <div className="flex items-center">
          <LanguageSwitcher />
          <button onClick={() => { cycleFontSize(); }} aria-label={t("a11y.font_toggle")} title={t("a11y.font_toggle")}
            className="flex min-h-[48px] min-w-[48px] items-center justify-center rounded-btn text-body hover:bg-line/60">
            <Type size={19} aria-hidden />
          </button>
          <button onClick={() => setHc(toggleHighContrast())} aria-label={t("a11y.hc_toggle")} aria-pressed={hc} title={t("a11y.hc_toggle")}
            className={`flex min-h-[48px] min-w-[48px] items-center justify-center rounded-btn hover:bg-line/60 ${hc ? "text-brand-600" : "text-body"}`}>
            <Contrast size={19} aria-hidden />
          </button>
          <button onClick={() => setDark(toggleTheme())} aria-label={t("a11y.theme_toggle")} title={t("a11y.theme_toggle")}
            className="hidden min-h-[48px] min-w-[48px] items-center justify-center rounded-btn text-body hover:bg-line/60 sm:flex">
            {dark ? <Sun size={19} aria-hidden /> : <Moon size={19} aria-hidden />}
          </button>
          <button onClick={() => setBw(toggleLowBandwidth())} aria-label={t("a11y.bw_toggle")} aria-pressed={bw} title={t("a11y.bw_toggle")}
            className={`flex min-h-[48px] min-w-[48px] items-center justify-center rounded-btn hover:bg-line/60 ${bw ? "text-brand-600" : "text-body"}`}>
            <Signal size={19} aria-hidden />
          </button>
        </div>
      </div>
      <nav className="border-t border-line" aria-label="primary">
        <div className="mx-auto flex max-w-6xl items-stretch gap-0.5 overflow-x-auto px-2">
          {NAV.map(({ href, key, Icon }) => {
            const active = pathname === href || (href !== "/" && pathname.startsWith(href));
            return (
              <Link key={href} href={href}
                aria-current={active ? "page" : undefined}
                className={`relative flex min-h-[52px] flex-1 items-center justify-center gap-1.5 whitespace-nowrap px-3 text-[14px] font-semibold ${active ? "text-brand-700 dark:text-brand-100" : "text-muted hover:text-body"}`}>
                <Icon size={17} aria-hidden />
                <span className="hidden sm:inline">{t(key)}</span>
                {href === "/report" && queue > 0 && (
                  <span className="num-ltr absolute end-1 top-1 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-amber-500 px-1 text-[11px] font-bold text-white" title={t("common.outbox_n", { n: queue })}>
                    {queue}
                  </span>
                )}
                {active && <span className="absolute inset-x-2 bottom-0 h-[3px] rounded-full bg-brand-600" aria-hidden />}
              </Link>
            );
          })}
        </div>
      </nav>
      <span className="hidden">{lang}</span>
    </header>
  );
}
