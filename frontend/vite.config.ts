import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const demo = process.env.VITE_DEMO === "1";

export default defineConfig({
  base: "./",
  plugins: [react()],
  // The preview build is published as a static artifact, so its file names must be stable.
  build: demo
    ? {
        rollupOptions: {
          output: {
            entryFileNames: "assets/app.js",
            chunkFileNames: "assets/[name].js",
            assetFileNames: "assets/[name][extname]",
          },
        },
      }
    : {},
  server: {
    host: "0.0.0.0",
    port: 5173,
    // In dev the API is reached through the same origin, so no CORS juggling.
    proxy: { "/api": { target: process.env.VITE_API_PROXY ?? "http://localhost:8000", changeOrigin: true } },
  },
});
