import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built assets land in ./dist; the frontend deploys separately from the backend.
// In dev, the proxy forwards /api to the running API so the SPA can call it same-origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
