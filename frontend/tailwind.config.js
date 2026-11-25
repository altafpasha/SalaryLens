/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          primary: '#090909',
          secondary: '#101010',
          sidebar: '#161616',
          card: '#181818',
          elevated: '#1f1f1f',
          input: '#1d1d1d',
        },
        accent: {
          primary: '#F15A43',
          hover: '#e24d36',
          subtle: 'rgba(241, 90, 67, 0.15)',
          purple: '#8B7CFF',
          purpleSubtle: 'rgba(139, 124, 255, 0.15)',
        },
        status: {
          success: '#22C55E',
          warning: '#F59E0B',
          danger: '#EF4444',
          info: '#38BDF8',
        },
        text: {
          primary: '#F5F5F5',
          secondary: '#A1A1AA',
          muted: '#71717A',
        },
      },
      borderRadius: {
        'xl': '16px',
        '2xl': '20px',
        '3xl': '24px',
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
        'glow-accent': '0 0 25px rgba(241, 90, 67, 0.25)',
        'glow-purple': '0 0 25px rgba(139, 124, 255, 0.2)',
      },
    },
  },
  plugins: [],
}
