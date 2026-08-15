import type { Config } from 'tailwindcss';

/** Ranglar Django shablonlaridagi bilan BIR XIL — ikki tomon bir xil ko'rinsin. */
const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        primary: '#0ea5e9',
        secondary: '#2dd4bf',
        background: '#020617',
        surface: '#0f172a',
      },
    },
  },
  plugins: [],
};
export default config;
