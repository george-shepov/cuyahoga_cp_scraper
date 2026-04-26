/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        steel: "#263342",
        accent: "#b56a34",
      },
      fontFamily: {
        serif: ["Baskerville", "Iowan Old Style", "Palatino Linotype", "serif"],
        sans: ["Avenir Next", "Segoe UI", "Trebuchet MS", "sans-serif"],
      },
    },
  },
  plugins: [],
};
