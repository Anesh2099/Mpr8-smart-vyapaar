import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // This stops Vite from choking on native Mac binaries
  optimizeDeps: {
    exclude: ['fsevents', 'lightningcss']
  }
});