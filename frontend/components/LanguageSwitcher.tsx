"use client";
/** LanguageSwitcher — header globe + bottom sheet (design-system §5.16, i18n §1). */
import { Check, Globe } from "lucide-react";
import { useState } from "react";
import { LANG_META, useI18n } from "../lib/i18n";
import { LANG_CODES, type LangCode } from "../lib/types";
import BottomSheet from "./BottomSheet";

export default function LanguageSwitcher() {
  const { lang, setLang, t } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label={t("a11y.lang_switcher")}
        className="flex min-h-[48px] items-center gap-1.5 rounded-btn px-3 text-[15px] font-semibold text-body hover:bg-line/60"
      >
        <Globe size={20} aria-hidden />
        <span>{LANG_META[lang].native}</span>
      </button>
      <BottomSheet open={open} onClose={() => setOpen(false)} title={t("common.language")}>
        <ul className="divide-y divide-line">
          {LANG_CODES.map((code: LangCode) => (
            <li key={code}>
              <button
                onClick={() => { setLang(code); setOpen(false); }}
                className="flex min-h-[56px] w-full items-center justify-between px-2 text-start hover:bg-appbg"
                aria-pressed={code === lang}
              >
                <span>
                  <span className="block text-[16px] font-semibold text-ink">{LANG_META[code].native}</span>
                  <span className="block text-[13px] text-muted">{LANG_META[code].name}</span>
                </span>
                {code === lang && <Check size={20} className="text-brand-600" aria-hidden />}
              </button>
            </li>
          ))}
        </ul>
      </BottomSheet>
    </>
  );
}
