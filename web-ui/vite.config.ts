import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 后端 FastAPI 跑在 8000，前端 dev 5173。CORS 已在后端开启。
// 前端 API 用相对路径 /api，由 vite proxy 转发到后端（同源，不触发 CORS）。
// host: 0.0.0.0 允许局域网设备访问（如手机/平板 http://<本机IP>:5173）。
// 生产可后端 mount dist 单端口部署。
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",  // 允许局域网访问（默认只 localhost）
    port: 5173,
    proxy: {
      // 开发时把 /api 代理到后端，避免跨域配置漂移
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
