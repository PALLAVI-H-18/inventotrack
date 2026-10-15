import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// react()       -> lets Vite understand JSX (the HTML-like code inside .jsx files)
// tailwindcss() -> turns Tailwind class names such as "bg-brand-600" into real CSS
export default defineConfig({
  plugins: [react(), tailwindcss()],
})
