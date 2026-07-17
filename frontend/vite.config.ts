/// <reference types="vitest/config" />
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
      manifest: {
        name: "Collector",
        short_name: "Collector",
        description: "Your books, movies and games — one shelf.",
        theme_color: "#0F0D20",
        background_color: "#0F0D20",
        display: "standalone",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "/icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        // App shell is precached; cover images are cached at runtime.
        navigateFallbackDenylist: [/^\/api/, /^\/media/],
        runtimeCaching: [
          {
            urlPattern: /^\/media\/covers\//,
            handler: "CacheFirst",
            options: {
              cacheName: "covers",
              expiration: { maxEntries: 500, maxAgeSeconds: 60 * 60 * 24 * 90 },
            },
          },
        ],
      },
    }),
  ],
  server: {
    // Dev-only proxy; in the container nginx does this instead.
    proxy: {
      "/api": "http://localhost:8000",
      "/media": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["src/test-setup.ts"],
    globals: true,
  },
});
