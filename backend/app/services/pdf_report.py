"""Server-side PDF incident reports (reportlab). Wave 4, Agent 11.

Ships the ``?format=pdf`` branch of
``GET /api/admin/incidents/{district_id}/export`` — a REAL PDF download,
never a fake. Bundled font subsets (``assets/fonts/``):

- ``deva-*.ttf`` — Noto Sans Devanagari subset (Devanagari block only; the
  upstream font ships no Latin letters)
- ``sans-*.ttf`` — DejaVu Sans subset (Latin, Latin-1, punctuation, ₹)

Text is segmented by script at render time (``_rich``): Devanagari runs use
the Deva font, everything else uses Sans. This keeps both Hindi alert copy
and Latin text extractable/searchable in the PDF.

Limitation (honest): reportlab does not do Indic complex-text shaping, so
Devanagari conjuncts render as constituent codepoints — readable, not
typographically perfect. See ``assets/fonts/README.md``.
"""
from __future__ import annotations

import html
import io
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"
_DEVA = "SahaytaDeva"
_DEVA_B = "SahaytaDeva-Bold"
_SANS = "SahaytaSans"
_SANS_B = "SahaytaSans-Bold"

_registered = False


def _register_fonts() -> None:
    """Register the bundled font subsets (idempotent)."""
    global _registered
    if _registered:
        return
    pdfmetrics.registerFont(TTFont(_DEVA, str(_FONTS_DIR / "deva-regular.ttf")))
    pdfmetrics.registerFont(TTFont(_DEVA_B, str(_FONTS_DIR / "deva-bold.ttf")))
    pdfmetrics.registerFont(TTFont(_SANS, str(_FONTS_DIR / "sans-regular.ttf")))
    pdfmetrics.registerFont(TTFont(_SANS_B, str(_FONTS_DIR / "sans-bold.ttf")))
    _registered = True


def _covered(cp: int) -> bool:
    """Codepoint ranges covered by the bundled subsets."""
    return (
        (0x20 <= cp <= 0x7E)  # ASCII
        or (0xA0 <= cp <= 0xFF)  # Latin-1
        or (0x900 <= cp <= 0x97F)  # Devanagari
        or (0x2000 <= cp <= 0x206F)  # general punctuation
        or cp == 0x20B9  # ₹
    )


def _is_deva(ch: str) -> bool:
    return 0x900 <= ord(ch) <= 0x97F


def _rich(text: Any, bold: bool = False) -> str:
    """Render ``text`` as reportlab paragraph markup with script-aware fonts.

    Devanagari runs use the Deva subset, all other runs use the Sans subset.
    Uncovered codepoints (emoji etc.) are dropped so the PDF never shows
    .notdef tofu. HTML-escaped per segment.
    """
    s = "" if text is None else str(text)
    s = "".join(ch if _covered(ord(ch)) or ch in "\n\t" else "" for ch in s)
    deva_font = _DEVA_B if bold else _DEVA
    sans_font = _SANS_B if bold else _SANS
    out: list[str] = []
    buf: list[str] = []
    in_deva: bool | None = None

    def flush() -> None:
        if buf:
            seg = html.escape("".join(buf)).replace("\n", "<br/>")
            out.append(
                f'<font name="{deva_font if in_deva else sans_font}">{seg}</font>'
            )
            buf.clear()

    for ch in s:
        d = _is_deva(ch)
        if in_deva is None:
            in_deva = d
        if d != in_deva:
            flush()
            in_deva = d
        buf.append(ch)
    flush()
    return "".join(out)


def _short(text: Any, n: int = 140) -> str:
    s = "" if text is None else str(text)
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _fmt_ts(value: Any) -> str:
    if not value:
        return "—"
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(value)


_SEV_HEX = {5: "7f1d1d", 4: "dc2626", 3: "f97316", 2: "eab308", 1: "22c55e"}


def _styles() -> dict[str, ParagraphStyle]:
    def _mk(name: str, font: str, **kw: Any) -> ParagraphStyle:
        d: dict[str, Any] = dict(fontName=font, fontSize=9, leading=12.5,
                                 textColor=colors.HexColor("#1f2937"))
        d.update(kw)
        return ParagraphStyle(name, **d)

    return {
        "h1": _mk("h1", _DEVA_B, fontSize=20, leading=24,
                  textColor=colors.HexColor("#111827"), spaceAfter=2 * mm),
        "h2": _mk("h2", _DEVA_B, fontSize=13, leading=16,
                  textColor=colors.HexColor("#1e3a8a"), spaceBefore=5 * mm,
                  spaceAfter=2.5 * mm, keepWithNext=True),
        "body": _mk("body", _SANS),
        "small": _mk("small", _SANS, fontSize=8, leading=10.5,
                     textColor=colors.HexColor("#6b7280")),
        "cell": _mk("cell", _SANS, fontSize=8, leading=10),
        "cell_b": _mk("cell_b", _SANS_B, fontSize=8, leading=10),
        "banner": _mk("banner", _SANS_B, fontSize=9, leading=12,
                      textColor=colors.white, alignment=1),
    }


def _banner_table(st: dict[str, ParagraphStyle]) -> Table:
    t = Table(
        [[Paragraph(_rich("SYNTHETIC DEMO DATA — not a real incident. "
                          "Do not act on this report.", bold=True), st["banner"])]],
        colWidths=[170 * mm],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#b45309")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _kv_table(st: dict[str, ParagraphStyle], rows: list[tuple[str, str]]) -> Table:
    data = [[Paragraph(_rich(k, bold=True), st["cell_b"]),
             Paragraph(_rich(v), st["cell"])] for k, v in rows]
    t = Table(data, colWidths=[52 * mm, 118 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#e5e7eb")),
    ]))
    return t


def _grid_table(st: dict[str, ParagraphStyle], header: list[str],
                rows: list[list[str]], widths: list[float],
                bold_first_col: bool = False) -> Table:
    data = [[Paragraph(_rich(h, bold=True), st["cell_b"]) for h in header]]
    for r in rows:
        data.append([
            Paragraph(_rich(c, bold=(bold_first_col and i == 0)), st["cell"])
            for i, c in enumerate(r)
        ])
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eff6ff")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
    ]))
    return t


def build_incident_pdf(bundle: dict[str, Any]) -> bytes:
    """Render the incident bundle dict as PDF bytes.

    ``bundle`` keys: ``district`` {id,name,state}, ``exported_at`` (iso),
    ``exported_by``, ``risk`` {risk, risk_level, factors[], weather_source,
    computed_at} | None, ``sos_reports`` [sos_to_read dicts],
    ``tasks`` [{id, sos_id, volunteer_id, volunteer_name, status}],
    ``alerts`` [{id, type, severity, languages, messages{}, created_at}],
    ``audit`` [{ts, actor, action, target_id}].
    """
    _register_fonts()
    st = _styles()
    district = bundle.get("district") or {}
    dname = str(district.get("name") or bundle.get("district_id") or "?")
    story: list[Any] = []

    story.append(_banner_table(st))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(_rich(f"Sahayta — Incident Report: {dname}", bold=True), st["h1"]))
    story.append(Paragraph(
        _rich(f"District {district.get('id', '')} · {district.get('state', '')} | "
              f"Exported {_fmt_ts(bundle.get('exported_at'))} | "
              f"By {bundle.get('exported_by', 'admin')}"),
        st["small"],
    ))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#1e3a8a"),
                            spaceAfter=3 * mm, spaceBefore=2 * mm))

    # ---- risk snapshot -------------------------------------------------
    story.append(Paragraph(_rich("District risk snapshot", bold=True), st["h2"]))
    risk = bundle.get("risk")
    if risk:
        story.append(_kv_table(st, [
            ("Risk score", f"{risk.get('risk')} / 100 ({risk.get('risk_level', '?')})"),
            ("Weather source", str(risk.get("weather_source", "?"))),
            ("Computed at", _fmt_ts(risk.get("computed_at"))),
        ]))
        factors = risk.get("factors") or []
        if factors:
            story.append(Spacer(1, 2 * mm))
            story.append(_grid_table(
                st,
                ["Factor", "Value", "Contribution"],
                [[str(f.get("name", "?")), _short(f.get("value", ""), 60),
                  str(f.get("contribution", ""))] for f in factors],
                [60, 70, 40],
            ))
    else:
        story.append(Paragraph(_rich("No risk snapshot available."), st["body"]))

    # ---- SOS reports ---------------------------------------------------
    sos_reports: list[dict[str, Any]] = bundle.get("sos_reports") or []
    story.append(Paragraph(_rich(f"SOS reports ({len(sos_reports)})", bold=True), st["h2"]))
    by_sev: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for r in sos_reports:
        sev = r.get("severity")
        by_sev[str(sev) if sev else "unassessed"] = by_sev.get(str(sev) if sev else "unassessed", 0) + 1
        by_status[str(r.get("status", "?"))] = by_status.get(str(r.get("status", "?")), 0) + 1
    story.append(Paragraph(
        _rich("By severity: " + ", ".join(f"{k}: {v}" for k, v in sorted(by_sev.items()))
              + " | By status: " + ", ".join(f"{k}: {v}" for k, v in sorted(by_status.items()))),
        st["small"],
    ))
    if sos_reports:
        ordered = sorted(
            sos_reports,
            key=lambda r: (-(r.get("severity") or 0), str(r.get("created_at", ""))),
        )[:50]
        rows = []
        for r in ordered:
            sev = r.get("severity")
            sev_txt = str(sev) if sev else "—"
            color = _SEV_HEX.get(sev, "111827") if isinstance(sev, int) else "111827"
            rows.append([
                f'<font color="#{color}"><b>{sev_txt}</b></font>',
                str(r.get("category", "?")),
                str(r.get("status", "?")).replace("_", " "),
                _fmt_ts(r.get("created_at")),
                _short(r.get("description", ""), 150),
            ])
        # NOTE: severity cell carries raw markup, so build this table inline
        # instead of via _grid_table (which would escape it).
        data = [[Paragraph(_rich(h, bold=True), st["cell_b"])
                 for h in ["Sev", "Category", "Status", "Reported", "Description"]]]
        for row in rows:
            data.append([
                Paragraph(row[0], st["cell"]),
                Paragraph(_rich(row[1]), st["cell"]),
                Paragraph(_rich(row[2]), st["cell"]),
                Paragraph(_rich(row[3]), st["cell"]),
                Paragraph(_rich(row[4]), st["cell"]),
            ])
        t = Table(data, colWidths=[12 * mm, 24 * mm, 26 * mm, 30 * mm, 78 * mm],
                  repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eff6ff")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ]))
        story.append(Spacer(1, 2 * mm))
        story.append(t)
        if len(sos_reports) > 50:
            story.append(Paragraph(
                _rich(f"Showing 50 of {len(sos_reports)} reports (most severe first). "
                      "Full list in the JSON export."), st["small"]))

    # ---- volunteer tasks ------------------------------------------------
    tasks: list[dict[str, Any]] = bundle.get("tasks") or []
    story.append(Paragraph(_rich(f"Volunteer tasks ({len(tasks)})", bold=True), st["h2"]))
    if tasks:
        story.append(_grid_table(
            st,
            ["Task", "Volunteer", "Status", "SOS"],
            [[str(tk.get("id", ""))[:8],
              str(tk.get("volunteer_name") or tk.get("volunteer_id", "?")),
              str(tk.get("status", "?")).replace("_", " "),
              str(tk.get("sos_id", ""))[:8]] for tk in tasks[:50]],
            [30, 60, 40, 40],
        ))
    else:
        story.append(Paragraph(_rich("No tasks recorded."), st["body"]))

    # ---- broadcasts ------------------------------------------------------
    alerts: list[dict[str, Any]] = bundle.get("alerts") or []
    story.append(Paragraph(_rich(f"Alert broadcasts ({len(alerts)})", bold=True), st["h2"]))
    if alerts:
        for a in alerts:
            langs = a.get("languages") or []
            story.append(Paragraph(
                _rich(f"{str(a.get('type', '?')).title()} · severity {a.get('severity', '?')} "
                      f"· [{', '.join(langs)}] · {_fmt_ts(a.get('created_at'))}", bold=True),
                st["cell_b"],
            ))
            messages = a.get("messages") or {}
            ordered_langs = [l for l in ("hi", "hing") if l in messages] + \
                [l for l in messages if l not in ("hi", "hing")]
            for l in ordered_langs[:4]:
                story.append(Paragraph(_rich(f"{l}: {messages[l]}"), st["cell"]))
            if len(ordered_langs) > 4:
                story.append(Paragraph(
                    _rich(f"+ {len(ordered_langs) - 4} more languages in the JSON export."),
                    st["small"]))
            story.append(Spacer(1, 2 * mm))
    else:
        story.append(Paragraph(_rich("No broadcasts sent."), st["body"]))

    # ---- incident timeline -------------------------------------------------
    audit: list[dict[str, Any]] = bundle.get("audit") or []
    story.append(Paragraph(_rich(f"Incident timeline ({len(audit)} events)", bold=True), st["h2"]))
    if audit:
        story.append(_grid_table(
            st,
            ["Time (UTC)", "Event", "Actor"],
            [[_fmt_ts(e.get("ts")), str(e.get("action", "?")), str(e.get("actor", "?"))]
             for e in audit[:80]],
            [38, 72, 60],
        ))
    else:
        story.append(Paragraph(_rich("No audit events recorded."), st["body"]))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        _rich("End of report. Generated by Sahayta (synthetic demo data). "
              "For the machine-readable bundle, use the JSON export."),
        st["small"],
    ))

    buf = io.BytesIO()

    def _footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont(_SANS, 7)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawString(15 * mm, 10 * mm,
                          "Sahayta incident report \u2014 SYNTHETIC DEMO DATA, not a real incident.")
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=14 * mm, bottomMargin=16 * mm,
        title=f"Sahayta incident report — {dname}",
        author="Sahayta",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
