"use client";
/**
 * BroadcastComposer — admin multilingual broadcast (design-system §5.14).
 * Confirm modal is MANDATORY (NOTES-agent3 #9). Char counter ≤ 480 per language.
 */
import { Megaphone, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useApi, type BroadcastInput } from "../lib/api";
import { useI18n, LANG_META } from "../lib/i18n";
import { LANG_CODES, type AlertType, type District, type Severity } from "../lib/types";
import { useToast } from "./Toast";
import SeverityBadge from "./SeverityBadge";
import BottomSheet from "./BottomSheet";

const TYPE_ICON: Record<AlertType, string> = { flood: "🌊", heatwave: "🌡️", cyclone: "🌀", custom: "📣" };

export default function BroadcastComposer({ districts, onSent }: { districts: District[]; onSent?: () => void }) {
  const { t, lang } = useI18n();
  const { api } = useApi();
  const { toast } = useToast();
  const [selDistricts, setSelDistricts] = useState<string[]>(["patna"]);
  const [type, setType] = useState<AlertType>("flood");
  const [severity, setSeverity] = useState<Severity>(4);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [langs, setLangs] = useState<string[]>([...LANG_CODES]);
  const [previewLang, setPreviewLang] = useState<string>(lang);
  const [confirming, setConfirming] = useState(false);
  const [sending, setSending] = useState(false);

  const toggle = (list: string[], v: string, set: (x: string[]) => void) =>
    set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  const preview = useMemo(() => {
    // Client-side preview mirrors the template ground truth; the server/AI
    // renders the final copy. Kept short on purpose.
    const head = t(`atype.${type}`);
    return `${head}: ${body || title}`.slice(0, 480);
  }, [type, title, body, t]);

  const canSend = selDistricts.length > 0 && body.trim().length >= 10 && langs.length > 0 && !sending;

  const send = async () => {
    if (!api || !canSend) return;
    setSending(true);
    try {
      const input: BroadcastInput = {
        district_ids: selDistricts, type, title: title || t(`atype.${type}`),
        body, severity, languages: langs,
      };
      const res = await api.broadcast(input);
      toast("success", t("toast.broadcast_done"));
      setConfirming(false);
      onSent?.();
      void res;
    } catch {
      toast("error", t("common.retry"));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="card p-4">
      <h3 className="mb-3 flex items-center gap-2 text-[17px] font-bold text-ink">
        <Megaphone size={19} aria-hidden /> {t("admin.broadcast_title")}
      </h3>

      <label className="mb-1 block text-[14px] font-semibold text-body">{t("admin.b_districts")}</label>
      <div className="mb-3 flex max-h-28 flex-wrap gap-1.5 overflow-y-auto">
        {districts.map((d) => (
          <button key={d.id} onClick={() => toggle(selDistricts, d.id, setSelDistricts)}
            className={`chip min-h-[40px] px-3 text-[14px] ${selDistricts.includes(d.id) ? "chip-active" : ""}`}
            aria-pressed={selDistricts.includes(d.id)}>
            {d.name} {selDistricts.includes(d.id) && <X size={14} aria-hidden />}
          </button>
        ))}
      </div>

      <div className="mb-3 grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-[14px] font-semibold text-body">{t("admin.b_type")}</label>
          <select value={type} onChange={(e) => setType(e.target.value as AlertType)} className="input">
            {(Object.keys(TYPE_ICON) as AlertType[]).map((k) => (
              <option key={k} value={k}>{TYPE_ICON[k]} {t(`atype.${k}`)}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-[14px] font-semibold text-body">{t("admin.b_severity")}</label>
          <div className="flex gap-1">
            {([1, 2, 3, 4, 5] as Severity[]).map((s) => (
              <button key={s} onClick={() => setSeverity(s)} aria-pressed={severity === s}
                className={`flex min-h-[48px] min-w-[48px] items-center justify-center rounded-btn border-2 text-[16px] font-extrabold ${severity === s ? "border-brand-600 bg-brand-100" : "border-line"}`}>
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      <label className="mb-1 block text-[14px] font-semibold text-body">{t("admin.b_title")}</label>
      <input value={title} onChange={(e) => setTitle(e.target.value)} className="input mb-3" maxLength={120} />

      <label className="mb-1 flex items-center justify-between text-[14px] font-semibold text-body">
        {t("admin.b_body")}
        <span className={`num-ltr text-[13px] ${body.length > 480 ? "font-bold text-alert-600" : "text-muted"}`}>{body.length} / 480</span>
      </label>
      <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} className="input mb-3" />

      <label className="mb-1 block text-[14px] font-semibold text-body">{t("admin.b_langs")}</label>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {LANG_CODES.map((c) => (
          <button key={c} onClick={() => toggle(langs, c, setLangs)}
            className={`chip min-h-[40px] px-3 text-[13px] ${langs.includes(c) ? "chip-active" : ""}`}
            aria-pressed={langs.includes(c)}>
            {LANG_META[c].native}
          </button>
        ))}
      </div>

      <label className="mb-1 block text-[14px] font-semibold text-body">{t("admin.b_preview")}</label>
      <div className="mb-3 flex gap-1 overflow-x-auto">
        {langs.map((c) => (
          <button key={c} onClick={() => setPreviewLang(c)}
            className={`chip min-h-[40px] whitespace-nowrap px-3 text-[13px] ${previewLang === c ? "chip-active" : ""}`}>
            {LANG_META[c as keyof typeof LANG_META].native}
          </button>
        ))}
      </div>
      <div className="mb-3 rounded-card border border-line bg-appbg p-3">
        <div className="mb-2"><SeverityBadge severity={severity} size="sm" /></div>
        <p className="text-alert-sms text-ink" lang={previewLang}>{preview}</p>
      </div>

      <button onClick={() => setConfirming(true)} disabled={!canSend} className="btn-sos w-full">
        <Megaphone size={20} aria-hidden /> {t("admin.b_send")}
      </button>

      <BottomSheet open={confirming} onClose={() => setConfirming(false)} title={t("admin.confirm_title")}>
        <p className="mb-2 text-[15px] text-body">{t("admin.confirm_sub")}</p>
        <p className="num-ltr mb-3 text-[28px] font-extrabold text-ink">~{(selDistricts.length * 12400).toLocaleString("en-IN")}</p>
        <div className="mb-4 rounded-card border border-line bg-appbg p-3">
          <p className="text-alert-sms text-ink" lang={previewLang}>{preview}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={send} disabled={sending} className="btn-sos flex-1">
            {sending ? t("common.loading") : t("admin.confirm_send")}
          </button>
          <button onClick={() => setConfirming(false)} className="btn-secondary">{t("common.cancel")}</button>
        </div>
      </BottomSheet>
    </div>
  );
}
