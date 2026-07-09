/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Neutral near-black scale (premium SaaS dark, à la Linear/Vercel).
        // Only 700/800/900 are overridden; 50–600 keep Tailwind's cool-gray
        // for muted labels. Kept close to true-neutral so the electric-blue
        // accent reads as the only chromatic element in the UI.
        gray: {
          700: '#26262b',   // solid hairlines, hover fills, badges, inputs
          800: '#141417',   // elevated surface (cards, sidebar, header)
          900: '#0a0a0c',   // app background (near-black)
        },
        // Electric-blue accent — the single vibrant color in the system.
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#58a6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        accent: {
          50: '#faf5ff',
          100: '#f3e8ff',
          200: '#e9d5ff',
          300: '#d8b4fe',
          400: '#c084fc',
          500: '#a855f7',
          600: '#9333ea',
          700: '#7e22ce',
          800: '#6b21a8',
          900: '#581c87',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
