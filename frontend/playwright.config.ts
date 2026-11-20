import { defineConfig } from "@playwright/test";

// Uses the locally installed Google Chrome; start the backend (port 8000) and frontend (port 3000) first.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: { baseURL: process.env.BASE_URL || "http://127.0.0.1:3000", channel: "chrome", headless: true },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 860 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
});
