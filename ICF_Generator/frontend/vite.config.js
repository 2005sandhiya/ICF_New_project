import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite configuration for Phase 1
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: false,
  },
});
