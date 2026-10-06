/**
 * Client-side incident-report PDF (demo mode) — pdf-lib.
 * Mirrors the server-side reportlab layout (backend/app/services/pdf_report.py):
 * banner, title, risk snapshot, SOS list, tasks, broadcasts, timeline, footer.
 * Real PDF bytes, never a fake download.
 *
 * Fonts: subset Noto Sans Devanagari (deva-*.ttf) + DejaVu Sans (sans-*.ttf)
 * from /fonts/. Text is segmented by script: Devanagari runs use the Deva
 * font, everything else uses Sans — same approach as the server builder.
 */
import { PDFDocument, PDFFont, RGB, rgb } from "pdf-lib";
import fontkit from "@pdf-lib/fontkit";
// fontkit's UMD bundle needs the regenerator runtime for its OpenType
// shaping state machines (Node/CJS quirk; harmless in the browser bundle).
import "regenerator-runtime/runtime";

export interface IncidentPdfData {
  district: { id: string; name: string; state?: string };
  exportedAt: string;
  exportedBy: string;
  risk: {
    risk: number; risk_level: string; weather_source?: string; computed_at?: string;
    factors?: Array<{ name: string; value?: string; contribution?: number }>;
  } | null;
  sos: Array<{
    id: string; severity: number | null; category?: string; status: string;
    district_id?: string | null; created_at?: string; description?: string;
  }>;
  tasks: Array<{
    id: string; sos_id: string; volunteer_id: string; volunteer_name?: string; status: string;
  }>;
  alerts: Array<{
    id: string; type: string; severity?: number; languages: string[];
    messages: Record<string, string>; created_at?: string;
  }>;
  audit: Array<{ ts?: string; actor: string; action: string }>;
}

const DEVA = (cp: number) => cp >= 0x900 && cp <= 0x97f;
const COVERED = (cp: number) =>
  (cp >= 0x20 && cp <= 0x7e) || (cp >= 0xa0 && cp <= 0xff) ||
  (cp >= 0x900 && cp <= 0x97f) || (cp >= 0x2000 && cp <= 0x206f) || cp === 0x20b9;

type Fonts = { deva: PDFFont; devaB: PDFFont; sans: PDFFont; sansB: PDFFont };

async function loadFonts(doc: PDFDocument): Promise<Fonts> {
  const base = typeof window !== "undefined" ? window.location.origin : "";
  const get = async (p: string) => {
    const r = await fetch(`${base}/fonts/${p}`);
    if (!r.ok) throw new Error(`font fetch failed: ${p}`);
    return r.arrayBuffer();
  };
  // Embed into the caller's document — font objects are bound to the
  // PDFDocument they are embedded in and must not be shared across docs.
  doc.registerFontkit(fontkit);
  const [deva, devaB, sans, sansB] = await Promise.all([
    doc.embedFont(await get("deva-regular.ttf")),
    doc.embedFont(await get("deva-bold.ttf")),
    doc.embedFont(await get("sans-regular.ttf")),
    doc.embedFont(await get("sans-bold.ttf")),
  ]);
  return { deva, devaB, sans, sansB };
}

/** Split text into script runs: [isDevanagari, text][]. */
function runs(text: string): Array<[boolean, string]> {
  const clean = [...text].filter((ch) => { const cp = ch.codePointAt(0)!; return COVERED(cp) || cp === 10 || cp === 9; }).join("");
  const out: Array<[boolean, string]> = [];
  let buf = "", cur: boolean | null = null;
  const flush = () => { if (buf) { out.push([cur!, buf]); buf = ""; } };
  for (const ch of clean) {
    const d = DEVA(ch.codePointAt(0)!);
    if (cur === null) cur = d;
    if (d !== cur) { flush(); cur = d; }
    buf += ch;
  }
  flush();
  return out;
}

const INK = rgb(0.11, 0.16, 0.21);
const MUTED = rgb(0.42, 0.45, 0.5);
const BLUE = rgb(0.12, 0.23, 0.54);
const SEVC: Record<number, RGB> = {
  5: rgb(0.5, 0.11, 0.11), 4: rgb(0.86, 0.15, 0.15), 3: rgb(0.98, 0.45, 0.09),
  2: rgb(0.92, 0.7, 0.05), 1: rgb(0.13, 0.77, 0.36),
};

class Writer {
  doc!: PDFDocument;
  fonts!: Fonts;
  page: ReturnType<PDFDocument["addPage"]> | null = null;
  y = 0;
  pageNo = 0;
  W = 595; H = 842; M = 42;
  district = "";

  async init(district: string) {
    this.doc = await PDFDocument.create();
    this.fonts = await loadFonts(this.doc);
    this.district = district;
    this.doc.setTitle(`Sahayta incident report — ${district}`);
    this.doc.setAuthor("Sahayta");
    this.newPage();
  }

  private footer() {
    if (!this.page) return;
    const f = this.fonts.sans;
    this.page.drawText("Sahayta incident report — SYNTHETIC DEMO DATA, not a real incident.", {
      x: this.M, y: 28, size: 7, font: f, color: MUTED,
    });
    const label = `Page ${this.pageNo}`;
    this.page.drawText(label, {
      x: this.W - this.M - f.widthOfTextAtSize(label, 7), y: 28, size: 7, font: f, color: MUTED,
    });
  }

  newPage() {
    if (this.page) this.footer();
    this.page = this.doc.addPage([this.W, this.H]);
    this.pageNo++;
    this.y = this.H - this.M;
  }

  need(h: number) {
    if (this.y - h < this.M + 14) this.newPage();
  }

  private pick(bold: boolean, deva: boolean): PDFFont {
    const f = this.fonts;
    return bold ? (deva ? f.devaB : f.sansB) : (deva ? f.deva : f.sans);
  }

  /** Draw (possibly mixed-script) text with word wrap. Returns lines used. */
  para(text: string, size: number, opts: { bold?: boolean; color?: RGB; gap?: number; indent?: number } = {}): void {
    const { bold = false, color = INK, gap = 4, indent = 0 } = opts;
    const maxW = this.W - 2 * this.M - indent;
    const words = text.split(/\s+/).filter(Boolean);
    const spaceW = this.fonts.sans.widthOfTextAtSize(" ", size);
    const wordW = (w: string) => runs(w).reduce((a, [d, t]) => a + this.pick(bold, d).widthOfTextAtSize(t, size), 0);
    const lines: string[][] = [[]];
    let lw = 0;
    for (const w of words) {
      const ww = wordW(w);
      if (lw + (lw ? spaceW : 0) + ww > maxW && lw > 0) { lines.push([]); lw = 0; }
      lines[lines.length - 1].push(w);
      lw += (lw ? spaceW : 0) + ww;
    }
    const lh = size * 1.35;
    this.need(lines.length * lh + gap);
    for (const line of lines) {
      let x = this.M + indent;
      line.forEach((w, i) => {
        if (i > 0) x += spaceW;
        for (const [d, t] of runs(w)) {
          const f = this.pick(bold, d);
          this.page!.drawText(t, { x, y: this.y, size, font: f, color });
          x += f.widthOfTextAtSize(t, size);
        }
      });
      this.y -= lh;
    }
    this.y -= gap;
  }

  heading(text: string) {
    this.need(30);
    this.y -= 6;
    this.para(text, 13, { bold: true, color: BLUE, gap: 6 });
  }

  divider() {
    this.need(10);
    this.page!.drawLine({ start: { x: this.M, y: this.y }, end: { x: this.W - this.M, y: this.y }, thickness: 0.6, color: BLUE });
    this.y -= 10;
  }

  banner() {
    this.need(26);
    const h = 20;
    this.page!.drawRectangle({ x: this.M, y: this.y - h, width: this.W - 2 * this.M, height: h, color: rgb(0.71, 0.33, 0.04) });
    const t = "SYNTHETIC DEMO DATA — not a real incident. Do not act on this report.";
    const f = this.fonts.sansB;
    this.page!.drawText(t, {
      x: this.M + (this.W - 2 * this.M - f.widthOfTextAtSize(t, 9)) / 2,
      y: this.y - 14, size: 9, font: f, color: rgb(1, 1, 1),
    });
    this.y -= h + 10;
  }

  async bytes(): Promise<Uint8Array> {
    this.footer();
    return this.doc.save();
  }
}

const fmtTs = (v?: string) => {
  if (!v) return "—";
  const d = new Date(v);
  return isNaN(+d) ? v : d.toISOString().slice(0, 16).replace("T", " ") + " UTC";
};

export async function buildIncidentPdf(d: IncidentPdfData): Promise<Uint8Array> {
  const w = new Writer();
  await w.init(d.district.name);

  w.banner();
  w.para(`Sahayta — Incident Report: ${d.district.name}`, 20, { bold: true, gap: 2 });
  w.para(`District ${d.district.id} · ${d.district.state ?? ""} | Exported ${fmtTs(d.exportedAt)} | By ${d.exportedBy}`, 8, { color: MUTED, gap: 2 });
  w.divider();

  w.heading("District risk snapshot");
  if (d.risk) {
    w.para(`Risk score: ${d.risk.risk} / 100 (${d.risk.risk_level})`, 9, {});
    w.para(`Weather source: ${d.risk.weather_source ?? "?"} | Computed: ${fmtTs(d.risk.computed_at)}`, 9, {});
    for (const f of d.risk.factors ?? []) {
      w.para(`• ${f.name}: ${f.value ?? ""} (contribution ${f.contribution ?? "?"})`, 8, { gap: 2, indent: 8 });
    }
  } else {
    w.para("No risk snapshot available.", 9, {});
  }

  w.heading(`SOS reports (${d.sos.length})`);
  const bySev: Record<string, number> = {};
  const byStatus: Record<string, number> = {};
  for (const r of d.sos) {
    const k = r.severity == null ? "unassessed" : String(r.severity);
    bySev[k] = (bySev[k] ?? 0) + 1;
    byStatus[r.status] = (byStatus[r.status] ?? 0) + 1;
  }
  w.para(`By severity: ${Object.entries(bySev).map(([k, v]) => `${k}: ${v}`).join(", ")}`, 8, { color: MUTED, gap: 1 });
  w.para(`By status: ${Object.entries(byStatus).map(([k, v]) => `${k}: ${v}`).join(", ")}`, 8, { color: MUTED, gap: 6 });
  const ordered = [...d.sos].sort((a, b) => (b.severity ?? 0) - (a.severity ?? 0)).slice(0, 50);
  for (const r of ordered) {
    const sev = r.severity == null ? "—" : String(r.severity);
    w.para(`SEV ${sev} · ${r.category ?? "?"} · ${r.status.replace(/_/g, " ")} · ${fmtTs(r.created_at)}`, 8, { bold: true, gap: 1, color: r.severity != null && SEVC[r.severity] ? SEVC[r.severity] : INK });
    if (r.description) w.para(r.description.slice(0, 280), 8, { gap: 5, indent: 8 });
  }
  if (d.sos.length > 50) w.para(`Showing 50 of ${d.sos.length} reports (most severe first). Full list in the JSON export.`, 8, { color: MUTED });

  w.heading(`Volunteer tasks (${d.tasks.length})`);
  if (d.tasks.length === 0) w.para("No tasks recorded.", 9, {});
  for (const t of d.tasks.slice(0, 50)) {
    w.para(`${t.volunteer_name ?? t.volunteer_id} — ${t.status.replace(/_/g, " ")} (SOS ${t.sos_id.slice(0, 8)})`, 8, { gap: 3 });
  }

  w.heading(`Alert broadcasts (${d.alerts.length})`);
  if (d.alerts.length === 0) w.para("No broadcasts sent.", 9, {});
  for (const a of d.alerts) {
    w.para(`${a.type} · severity ${a.severity ?? "?"} · [${a.languages.join(", ")}] · ${fmtTs(a.created_at)}`, 8, { bold: true, gap: 2 });
    const langs = ["hi", "hing"].filter((l) => a.messages[l]).concat(Object.keys(a.messages).filter((l) => l !== "hi" && l !== "hing"));
    for (const l of langs.slice(0, 4)) w.para(`${l}: ${a.messages[l]}`, 8, { gap: 2, indent: 8 });
    if (langs.length > 4) w.para(`+ ${langs.length - 4} more languages in the JSON export.`, 8, { color: MUTED });
  }

  w.heading(`Incident timeline (${d.audit.length} events)`);
  if (d.audit.length === 0) w.para("No audit events recorded.", 9, {});
  for (const e of d.audit.slice(0, 80)) {
    w.para(`${fmtTs(e.ts)} — ${e.action} · ${e.actor}`, 8, { gap: 2 });
  }

  w.para("End of report. Generated by Sahayta (synthetic demo data). For the machine-readable bundle, use the JSON export.", 8, { color: MUTED, gap: 0 });
  return w.bytes();
}
