import type { Config } from "tailwindcss";

// Imparency's visual identity is a ledger: ink-indigo for structure, marigold for the one
// action that moves money, a stamp-green/wax-red/ink-amber trio reserved for verification
// states only. Paper is warm, ruled ledger stock, not a flat neutral backdrop.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: "#1D2B4F", soft: "#324874" }, // indigo ink
        teal: { DEFAULT: "#B9650A", soft: "#F5E6CB" }, // marigold -- the only warm accent, spent on action
        paper: "#F7F1E3", // ledger ivory
        ink: "#2A2B26",
        muted: "#6B6355",
        line: "#DDD2B8",
        status: {
          pending: "#9C6B16", // ink amber
          approved: "#1F6F4A", // stamp green
          rejected: "#A23B32", // sealing wax
        },
      },
      fontFamily: {
        sans: ["var(--font-body)", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        display: ["var(--font-display)", "var(--font-body)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
