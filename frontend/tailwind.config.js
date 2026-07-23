/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#f8f9ff',
        surface: '#ffffff',
        primary: '#2563eb',
        'primary-hover': '#1d4ed8',
        outline: '#e5e7eb',
        textMain: '#111827',
        textMuted: '#6b7280',
      },
      fontFamily: {
        sans: ['Poppins', 'sans-serif'],
        display: ['Poppins', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
