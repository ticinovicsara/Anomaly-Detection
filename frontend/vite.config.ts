import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  // Override locally via frontend/.env.local (gitignored) with
  // BACKEND_PORT=<port> if 8000 isn't usable on your machine (e.g.
  // Windows sometimes reserves it in its excluded port range). No
  // VITE_ prefix needed -- this file runs in Node, not the browser.
  const env = loadEnv(mode, ".", "");
  const backendPort = env.BACKEND_PORT || "8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ""),
        },
      },
    },
  };
});
