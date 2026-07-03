import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  server: {
    proxy: {
      "/account": "http://localhost:8000",
      "/positions": "http://localhost:8000",
      "/trades": "http://localhost:8000",
      "/trade": "http://localhost:8000",
      "/exposure": "http://localhost:8000",
      "/market": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});