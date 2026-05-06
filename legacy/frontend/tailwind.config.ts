import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ocean: {
          50: "#eff8ff",
          100: "#dbeffe",
          200: "#bfe3fd",
          500: "#3b9eed",
          700: "#1d6fb3",
          900: "#153b5e",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
