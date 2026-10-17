import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// O build vai para dentro do pacote Python: `python -m tarvo.web` serve sem precisar de Node.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { outDir: "../src/tarvo/web/static", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
