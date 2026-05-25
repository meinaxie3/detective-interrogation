import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ["'Courier New'", "Courier", "monospace"],
      },
      colors: {
        // Noir palette
        noir: {
          950: "#060608",
          900: "#0a0a10",
          800: "#111118",
          700: "#1a1a24",
        },
        gold: {
          400: "#c9a84c",
          500: "#b8943c",
          600: "#a07c28",
        },
      },
      animation: {
        cursor: "blink 1s step-end infinite",
      },
      keyframes: {
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
