"use client";
/**
 * i18n provider — zero hardcoded UI strings outside the default locale.
 * Dictionaries live in lib/i18n/*.json. Fallback chain: requested → hi.
 * (Agent 12 completes per-language coverage; see _meta.coverage in each file.)
 */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { LangCode } from "./types";
import { DEFAULT_LANG, LANG_CODES } from "./types";
import hi from "./i18n/hi.json";
import hing from "./i18n/hing.json";
import bn from "./i18n/bn.json";
import ta from "./i18n/ta.json";
import te from "./i18n/te.json";
import mr from "./i18n/mr.json";
import gu from "./i18n/gu.json";
import kn from "./i18n/kn.json";
import ml from "./i18n/ml.json";
import pa from "./i18n/pa.json";

type Dict = Record<string, unknown>;
const DICTS: Record<LangCode, Dict> = { hi, hing, bn, ta, te, mr, gu, kn, ml, pa } as unknown as Record<LangCode, Dict>;

export const LANG_META: Record<LangCode, { name: string; native: string }> = {
  hi: { name: "Hindi", native: "हिन्दी" },
  hing: { name: "Hinglish", native: "Hinglish" },
  bn: { name: "Bengali", native: "বাংলা" },
  ta: { name: "Tamil", native: "தமிழ்" },
  te: { name: "Telugu", native: "తెలుగు" },
  mr: { name: "Marathi", native: "मराठी" },
  gu: { name: "Gujarati", native: "ગુજરાતી" },
  kn: { name: "Kannada", native: "ಕನ್ನಡ" },
  ml: { name: "Malayalam", native: "മലയാളം" },
  pa: { name: "Punjabi", native: "ਪੰਜਾਬੀ" },
};

function lookup(dict: Dict, key: string): string | undefined {
  const parts = key.split(".");
  let cur: unknown = dict;
  for (const p of parts) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Dict)[p];
  }
  return typeof cur === "string" ? cur : undefined;
}

export function translate(lang: LangCode, key: string, vars?: Record<string, string | number>): string {
  let s = lookup(DICTS[lang], key) ?? lookup(DICTS[DEFAULT_LANG], key) ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
}

interface I18nCtx {
  lang: LangCode;
  setLang: (l: LangCode) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const Ctx = createContext<I18nCtx>({ lang: DEFAULT_LANG, setLang: () => {}, t: (k) => k });

export function useI18n(): I18nCtx {
  return useContext(Ctx);
}

const LS_LANG = "sahayta.lang";
const LS_FONT = "sahayta.fontsize"; // S | M | L
const LS_THEME = "sahayta.theme"; // light | dark
const LS_HC = "sahayta.highcontrast";
const LS_BW = "sahayta.lowbandwidth";

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<LangCode>(DEFAULT_LANG);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem(LS_LANG);
    if (saved && (LANG_CODES as string[]).includes(saved)) {
      setLangState(saved as LangCode);
    } else {
      // First run: offer the browser language once via the header toast (layout handles it).
      const nav = navigator.language?.slice(0, 2).toLowerCase();
      const map: Record<string, LangCode> = { bn: "bn", ta: "ta", te: "te", mr: "mr", gu: "gu", kn: "kn", ml: "ml", pa: "pa", hi: "hi" };
      if (nav && map[nav] && map[nav] !== DEFAULT_LANG) {
        sessionStorage.setItem("sahayta.suggest_lang", map[nav]);
      }
    }
    // Restore display prefs
    const font = localStorage.getItem(LS_FONT) || "M";
    document.documentElement.style.fontSize = font === "S" ? "100%" : font === "L" ? "125%" : "112.5%";
    const theme = localStorage.getItem(LS_THEME);
    if (theme === "dark" || (!theme && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
      document.documentElement.classList.add("dark");
    }
    if (localStorage.getItem(LS_HC) === "1") document.body.classList.add("high-contrast");
    if (localStorage.getItem(LS_BW) === "1" || (navigator as unknown as { connection?: { saveData?: boolean } }).connection?.saveData) {
      document.body.classList.add("low-bandwidth");
    }
    setReady(true);
  }, []);

  const setLang = useCallback((l: LangCode) => {
    setLangState(l);
    localStorage.setItem(LS_LANG, l);
    document.documentElement.lang = l === "hing" ? "hi-Latn" : l;
  }, []);

  const t = useCallback((key: string, vars?: Record<string, string | number>) => translate(lang, key, vars), [lang]);

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  if (!ready) return null;
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** Display-preference helpers used by the header a11y cluster. */
export function cycleFontSize(): string {
  const cur = localStorage.getItem(LS_FONT) || "M";
  const next = cur === "S" ? "M" : cur === "M" ? "L" : "S";
  localStorage.setItem(LS_FONT, next);
  document.documentElement.style.fontSize = next === "S" ? "100%" : next === "L" ? "125%" : "112.5%";
  return next;
}
export function toggleTheme(): boolean {
  const dark = document.documentElement.classList.toggle("dark");
  localStorage.setItem(LS_THEME, dark ? "dark" : "light");
  return dark;
}
export function toggleHighContrast(): boolean {
  const on = document.body.classList.toggle("high-contrast");
  localStorage.setItem(LS_HC, on ? "1" : "0");
  return on;
}
export function toggleLowBandwidth(): boolean {
  const on = document.body.classList.toggle("low-bandwidth");
  localStorage.setItem(LS_BW, on ? "1" : "0");
  return on;
}
export function isLowBandwidth(): boolean {
  return typeof document !== "undefined" && document.body.classList.contains("low-bandwidth");
}
