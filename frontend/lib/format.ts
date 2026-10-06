/** Time-ago formatting. Pure — unit-tested. */

const MIN = 60_000;
const HOUR = 3_600_000;
const DAY = 86_400_000;

export function timeAgo(iso: string, now: number = Date.now()): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const d = now - t;
  if (d < 0) return "now";
  if (d < MIN) return "now";
  if (d < HOUR) {
    const m = Math.floor(d / MIN);
    return `${m}m`;
  }
  if (d < DAY) {
    const h = Math.floor(d / HOUR);
    return `${h}h`;
  }
  const days = Math.floor(d / DAY);
  return `${days}d`;
}

/** "12,400" style grouping for recipient estimates etc. */
export function formatCount(n: number): string {
  return n.toLocaleString("en-IN");
}

/** Clamp a string to N chars without cutting mid-word; appends "…" if cut. */
export function clampWords(s: string, max: number): string {
  if (s.length <= max) return s;
  const cut = s.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  return (lastSpace > max * 0.5 ? cut.slice(0, lastSpace) : cut) + "…";
}
