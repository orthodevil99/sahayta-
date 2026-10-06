import type { Config } from "tailwindcss";

// Sahayta design-system v1.0 (Agent 3, FROZEN) as Tailwind tokens.
// Severity badge colors are IDENTICAL in dark mode (recognition > theme purity).
const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { 100: "#DBEAFE", 600: "#1D4ED8", 700: "#1E40AF" },
        alert: { 600: "#DC2626", 700: "#B91C1C" },
        ink: "var(--ink)",
        body: "var(--body)",
        muted: "var(--muted)",
        line: "var(--line)",
        appbg: "var(--bg)",
        surface: "var(--surface)",
        success: "#16A34A",
        info: "#0284C7",
        sev1: { bg: "#16A34A", tint: "#DCFCE7", text: "#14532D" },
        sev2: { bg: "#65A30D", tint: "#ECFCCB", text: "#365314" },
        sev3: { bg: "#D97706", tint: "#FEF3C7", text: "#78350F" },
        sev4: { bg: "#DC2626", tint: "#FEE2E2", text: "#7F1D1D" },
        sev5: { bg: "#7F1D1D", tint: "#FECACA", text: "#450A0A" },
      },
      fontFamily: {
        sans: [
          '"Noto Sans"',
          '"Noto Sans Devanagari"',
          '"Noto Sans Bengali"',
          '"Noto Sans Tamil"',
          '"Noto Sans Telugu"',
          '"Noto Sans Kannada"',
          '"Noto Sans Malayalam"',
          '"Noto Sans Gujarati"',
          '"Noto Sans Gurmukhi"',
          "system-ui",
          "sans-serif",
        ],
        serif: ['"Noto Serif"', '"Noto Serif Devanagari"', "serif"],
      },
      fontSize: {
        display: ["32px", { lineHeight: "40px", fontWeight: "800" }],
        "alert-sms": ["15px", { lineHeight: "22px" }],
      },
      borderRadius: { card: "16px", btn: "12px", sheet: "24px" },
      boxShadow: {
        card: "0 1px 3px rgb(15 23 42 / 0.08)",
        sheet: "0 -8px 32px rgb(15 23 42 / 0.18)",
      },
      minHeight: { touch: "48px" },
      keyframes: {
        "slide-in": { from: { transform: "translateY(-12px)", opacity: "0" }, to: { transform: "translateY(0)", opacity: "1" } },
        pulseonce: { "0%": { transform: "scale(1)" }, "50%": { transform: "scale(1.15)" }, "100%": { transform: "scale(1)" } },
        shimmer: { "0%": { backgroundPosition: "-400px 0" }, "100%": { backgroundPosition: "400px 0" } },
      },
      animation: {
        "slide-in": "slide-in 240ms ease-out",
        pulseonce: "pulseonce 400ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
