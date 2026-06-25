import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 后端 FastAPI 跑在 8000，前端 dev 5173。CORS 已在后端开启。
// 生产可后端 mount dist 单端口部署。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 开发时把 /api 代理到后端，避免跨域配置漂移
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
