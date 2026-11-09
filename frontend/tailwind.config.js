/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        yolo: {
          light: "#dbeafe",
          border: "#2563eb",
          text: "#1e40af",
        },
        patchcore: {
          light: "#f3e8ff",
          border: "#7c3aed",
          text: "#6b21a8",
        },
        human: {
          confirmed: "#059669",
          rejected: "#dc2626",
          uncertain: "#d97706",
        },
      },
    },
  },
  plugins: [],
}

