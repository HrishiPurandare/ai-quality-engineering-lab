import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The UI calls /api/...; in development Vite forwards those requests to FastAPI on :8000.
// Same origin for the browser, so the API needs no CORS setup.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: API_URL, rewrite: (path) => path.replace(/^\/api/, "") },
    },
  },
});
