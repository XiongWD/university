import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    // 仅跑 src 下的单元测试；e2e/ 是 playwright 测试，tests/ 是 markdown 快照，都排除
    include: ["src/**/*.test.{ts,tsx}"],
    exclude: ["e2e/**", "tests/**", "node_modules/**", "dist/**"],
  },
});
