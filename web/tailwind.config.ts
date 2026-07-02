import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#4F46E5",
          dark: "#4338CA",
          darker: "#312E81",
          light: "#E0E7FF",
          lighter: "#EEF2FF",
        },
        secondary: {
          DEFAULT: "var(--kb-secondary)",
          dark: "var(--kb-secondary-dark)",
          light: "var(--kb-secondary-light)",
          lighter: "var(--kb-secondary-lighter)",
        },
        accent: { teal: "#07968F" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        poppins: ["Poppins", "sans-serif"],
      },
      maxWidth: { content: "1192px" },
      boxShadow: {
        card: "0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.06)",
        "card-hover": "0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.07)",
      },
    },
  },
  plugins: [],
};

export default config;
