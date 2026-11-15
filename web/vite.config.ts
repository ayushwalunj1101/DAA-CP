import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8010" } },
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        // Chart engines and framework code change rarely: separate chunks cache well.
        manualChunks: {
          echarts: ["echarts"],
          "lightweight-charts": ["lightweight-charts"],
          react: ["react", "react-dom", "react-router-dom", "@tanstack/react-query", "@tanstack/react-table"],
          ui: ["framer-motion", "cmdk", "@radix-ui/react-dialog", "@radix-ui/react-slider", "@radix-ui/react-switch", "lucide-react"],
        },
      },
    },
  },
  test: { environment: "jsdom", globals: true, setupFiles: "./src/test-setup.ts", css: false },
});
