import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  use: {
    baseURL: process.env.COFFEENCHAT_WEB_URL || "http://127.0.0.1:5173",
    trace: "retain-on-failure",
  },
  reporter: "list",
});
