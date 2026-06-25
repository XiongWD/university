import { useState } from "react";
import { AlertCircle } from "lucide-react";
import ScoreForm from "../components/ScoreForm";
import VolunteerTable from "../components/VolunteerTable";
import { recommend, ApiError } from "../api/client";
import type { RecommendRequest, VolunteerTable as VTable } from "../api/types";

export default function HomePage() {
  const [loading, setLoading] = useState(false);
  const [table, setTable] = useState<VTable | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(req: RecommendRequest) {
    setLoading(true);
    setError(null);
    try {
      const t = await recommend(req);
      setTable(t);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "请求失败，请确认后端服务已启动";
      setError(msg);
      setTable(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Hero */}
      {!table && (
        <div className="text-center py-6 animate-fade-in">
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight">
            <span className="bg-gradient-to-r from-pink-400 via-fuchsia-400 to-indigo-400 bg-clip-text text-transparent">
              一键生成你的冲稳保志愿表
            </span>
          </h1>
          <p className="text-white/60 mt-3 text-sm sm:text-base">
            基于位次法 · 真实历年录取数据 · 河南/广东新高考
          </p>
        </div>
      )}

      <ScoreForm loading={loading} onSubmit={handleSubmit} />

      {error && (
        <div className="glass rounded-2xl p-4 border border-red-400/30 flex items-start gap-2 text-sm text-red-200">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <div>
            <p className="font-medium">出错了</p>
            <p className="text-red-200/70 text-xs mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {table && <VolunteerTable table={table} />}
    </div>
  );
}
