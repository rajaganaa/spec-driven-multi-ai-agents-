import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Relative base so the build works whether it's served from
  // https://you.github.io/ (user/org page) or
  // https://you.github.io/repo-name/ (project page) without having to
  // hardcode the repo name here.
  base: "./",
  build: {
    outDir: "dist",
  },
});
