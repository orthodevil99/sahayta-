# Bundled fonts for PDF incident reports

Subsets generated with fontTools (see Wave 4 Agent 11):

- `deva-regular.ttf` / `deva-bold.ttf` — Noto Sans Devanagari subset
  (SIL Open Font License 1.1). The upstream font ships Devanagari only
  (no Latin letters), so it is paired with the Sans subsets below.
- `sans-regular.ttf` / `sans-bold.ttf` — DejaVu Sans subset
  (Bitstream Vera license). Covers Latin, Latin-1, punctuation, ₹ (U+20B9).

Subset command:

```
pyftsubset <font>.ttf \
  --unicodes="U+0020-007E,U+00A0-00FF,U+0900-097F,U+2000-206F,U+20B9" \
  --drop-tables+=GSUB,GPOS
```

GSUB/GPOS are deliberately dropped: it keeps the ToUnicode CMap 1:1 so
text stays selectable/searchable, and avoids ligature-substitution
artifacts in subset fonts.

Used by `backend/app/services/pdf_report.py` (reportlab) and
`frontend/public/fonts/` (pdf-lib, demo-mode client-side PDFs).
Text is segmented by script at render time: Devanagari runs use the
Deva font, everything else uses Sans.

Note: neither renderer does Indic complex-text shaping; conjuncts render
as constituent codepoints (readable, not typographically perfect).
