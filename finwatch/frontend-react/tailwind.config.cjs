/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#06131d',
        panel: '#0c2233',
        accent: '#00b894',
        warn: '#ffb347',
        danger: '#ff5f56',
      },
      boxShadow: {
        panel: '0 12px 40px rgba(0, 0, 0, 0.28)',
      },
    },
  },
  plugins: [],
}
