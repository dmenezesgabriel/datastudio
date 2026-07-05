import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built assets land in ./dist; the frontend deploys separately from the backend.
// In dev, the proxy forwards /api to the running API so the SPA can call it same-origin.
export default defineConfig({
  plugins: [react()],
  server: {
    // Bind 0.0.0.0 so the devcontainer's IPv4 port-forwarder can reach the server
    // (a localhost/IPv6-only bind makes the forwarded port hang in the browser).
    host: true,
    // Pin the forwarded port; fail loudly on a conflict instead of drifting to
    // 5174 (which isn't forwarded and silently "hangs" in the browser).
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
