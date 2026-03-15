/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        heading: ['Bebas Neue', 'Impact', 'Arial Black', 'sans-serif'],
        body: ['Roboto', 'Arial', 'sans-serif'],
      },
      colors: {
        lb: {
          'red-primary': '#B91C1C',
          'red-dark': '#991B1B',
          'red-light': '#DC2626',
          'yellow': '#FDB80E',
          'yellow-light': '#FDE047',
          'yellow-dark': '#CA8A04',
          'dark-gray': '#1F2937',
          'darker-gray': '#111827',
          white: '#FFFFFF',
          'off-white': '#F9FAFB',
          'blue-accent': '#3B82F6',
          'green-success': '#059669',
          'gray-border': '#E5E7EB',
          'gray-text': '#6B7280',
        },
      },
    },
  },
  plugins: [],
}