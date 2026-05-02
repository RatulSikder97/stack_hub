import typography from '@tailwindcss/typography'

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        // Light, ElevenLabs-flavored palette.
        bg: {
          base: '#ffffff',
          subtle: '#fafafa',
          sidebar: '#f7f7f8',
          card: '#ffffff',
          elevated: '#f4f4f5',
          hover: '#eeeef0',
          active: '#e9e9ed',
        },
        ink: {
          1: '#0a0a0a',
          2: '#3f3f46',
          3: '#71717a',
          4: '#a1a1aa',
          5: '#d4d4d8',
        },
        line: {
          subtle: '#ececef',
          DEFAULT: '#dfdfe3',
          strong: '#c9c9cf',
        },
        brand: {
          DEFAULT: '#000000',
          accent: '#6d28d9',
          glow: '#a78bfa',
        },
      },
      backgroundImage: {
        'gradient-brand': 'linear-gradient(135deg, #18181b 0%, #3f3f46 100%)',
        'tile-1': 'linear-gradient(135deg, #f4f4f5 0%, #e4e4e7 100%)',
      },
      boxShadow: {
        card: '0 1px 2px rgba(15, 23, 42, 0.04)',
        soft: '0 4px 16px rgba(15, 23, 42, 0.06)',
        pop: '0 8px 24px rgba(15, 23, 42, 0.08)',
      },
      animation: {
        'fade-in': 'fadeIn 200ms ease-out',
        'slide-up': 'slideUp 220ms ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [typography],
}
