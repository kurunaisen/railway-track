/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        rail: {
          bg: "#0f1419",
          surface: "#1a2332",
          border: "#2d3f56",
          accent: "#3b9eff",
          muted: "#8ba3bc",
        },
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
