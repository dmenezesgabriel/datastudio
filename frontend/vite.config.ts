import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built assets land in ./dist, which the FastAPI app serves via
// AppSettings.frontend_dist_path. The dev proxy forwards /api to the running API.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
