import { defineConfig } from "@playwright/test";

// Playwright 配置：针对本地 dev 服务器（前端 5173 / 后端 8000）做真实流程测试。
// 前后端需已启动（不在 playwright 内自动起服务，避免与手动 dev 冲突）。
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: "http://localhost:5173",
    headless: true,
    viewport: { width: 1280, height: 900 },
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
  ],
});
