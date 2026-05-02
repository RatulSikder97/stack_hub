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
        bg: {
          base: '#08080d',
          sidebar: '#0d0d14',
          card: '#13131c',
          elevated: '#1a1a25',
          hover: '#21212e',
        },
        ink: {
          1: '#f4f4f5',
          2: '#a1a1aa',
          3: '#71717a',
          4: '#52525b',
        },
        line: {
          subtle: '#22222d',
          DEFAULT: '#2d2d3a',
        },
        brand: {
          DEFAULT: '#a78bfa',
          deep: '#7c3aed',
          glow: '#c084fc',
        },
      },
      backgroundImage: {
        'gradient-brand': 'linear-gradient(135deg, #8b5cf6 0%, #c026d3 100%)',
        'gradient-glow': 'radial-gradient(circle at 50% 50%, rgba(139, 92, 246, 0.18), transparent 70%)',
      },
      boxShadow: {
        glow: '0 0 32px rgba(139, 92, 246, 0.25)',
        card: '0 1px 2px rgba(0, 0, 0, 0.4), 0 8px 24px rgba(0, 0, 0, 0.2)',
      },
      animation: {
        'fade-in': 'fadeIn 200ms ease-out',
        'slide-up': 'slideUp 220ms ease-out',
        pulse: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
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
