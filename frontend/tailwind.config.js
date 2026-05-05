/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Override zinc to a blue-gray industrial palette (SolidWorks-inspired)
        zinc: {
          950: '#0D1117',
          900: '#121820',
          800: '#1A2232',
          750: '#1E2B3C',
          700: '#243347',
          600: '#2A3A52',
          500: '#3D5270',
          400: '#7A9AB8',
          300: '#A8C0D8',
          200: '#C8D8EA',
          100: '#D4E4F2',
          50:  '#E8F4FF',
        },
        // Override sky to SolidWorks blue
        sky: {
          50:  '#E8F4FB',
          100: '#C4DDF5',
          200: '#9DC6ED',
          300: '#6DACE3',
          400: '#3BA0D9',
          500: '#0078C8',
          600: '#0063A8',
          700: '#004E88',
          800: '#003A68',
          900: '#002848',
        },
        // Mastercam orange accent
        mc: {
          50:  '#FFF4E8',
          100: '#FFE0C0',
          200: '#FFCA90',
          300: '#FFAA55',
          400: '#FF8C30',
          500: '#E87722',
          600: '#CC6318',
          700: '#AA500F',
          800: '#8A3E08',
          900: '#6A2E03',
        },
        brand: {
          50:  '#E8F4FB',
          100: '#C4DDF5',
          200: '#9DC6ED',
          300: '#6DACE3',
          400: '#3BA0D9',
          500: '#0078C8',
          600: '#0063A8',
          700: '#004E88',
          800: '#003A68',
          900: '#002848',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'monospace'],
        ui: ['"Segoe UI"', '-apple-system', 'BlinkMacSystemFont', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
