import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  // Override locally via frontend/.env.local (gitignored) with
  // VITE_BACKEND_PORT=<port> if 3000 isn't usable on your machine
  // (e.g. Windows sometimes reserves a default port in its excluded range).
  const env = loadEnv(mode, ".", "");
  const backendPort = env.VITE_BACKEND_PORT || "3000";

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
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
