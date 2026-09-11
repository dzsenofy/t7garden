import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "Siófok Command Control",
        short_name: "Siófok CC",
        description: "Smart-home dashboard for the Siófok house",
        theme_color: "#0f172a",
        background_color: "#0f172a",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" },
        ],
      },
      workbox: {
        // never cache API or streams; the dashboard must show live data
        navigateFallbackDenylist: [/^\/api/, /^\/ws/, /^\/stream/],
        runtimeCaching: [],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
      "/stream": { target: "http://127.0.0.1:1984", rewrite: (p) => p.replace(/^\/stream/, "") },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
