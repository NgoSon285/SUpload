import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev`   -> http://localhost:5173 (gọi API của `python app.py` ở cổng 5000)
// `npm run build` -> xuất ra ../web để Flask phục vụ trực tiếp
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../web",
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks: {
          mantine: ["@mantine/core", "@mantine/hooks", "@mantine/dates", "@mantine/dropzone", "@mantine/notifications", "@mantine/modals"],
          flow: ["@xyflow/react"],
        },
      },
    },
  },
  server: {
    proxy: { "/api": "http://127.0.0.1:5000", "/uploads": "http://127.0.0.1:5000" },
  },
});
