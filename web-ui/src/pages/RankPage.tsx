import { useState } from "react";
import { ArrowLeftRight, Loader2 } from "lucide-react";
import { scoreToRank, rankToScore, ApiError } from "../api/client";
import type { RankResponse } from "../api/types";

const PROVINCES = ["河南", "广东"];
const TRACKS = ["物理类", "历史类", "理科", "文科"];
const YEARS = [2026, 2025, 2024];

export default function RankPage() {
  const [mode, setMode] = useState<"s2r" | "r2s">("s2r");
  const [province, setProvince] = useState("河南");
  const [year, setYear] = useState(2025);
  const [track, setTrack] = useState("物理类");
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RankResponse | (RankResponse & { score: number | null }) | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleQuery() {
    const v = Number(value);
    if (!value || isNaN(v)) {
      setError("请输入有效数字");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r =
        mode === "s2r"
          ? await scoreToRank(province, year, track, v)
          : await rankToScore(province, year, track, v);
      setResult(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "查询失败");
    } finally {
      setLoading(false);
    }
  }

  const resultValue =
    result && mode === "s2r"
      ? (result as RankResponse).rank
      : result && "score" in result
      ? (result as RankResponse & { score: number | null }).score
      : null;

  return (
    <div className="max-w-2xl mx-auto">
      <div className="text-center mb-6">
        <h1 className="text-3xl font-bold flex items-center justify-center gap-2">
          <ArrowLeftRight className="w-7 h-7 text-pink-400" />
          位次查询工具
        </h1>
        <p className="text-white/50 text-sm mt-1">分数 ↔ 位次 双向换算（位次法核心）</p>
      </div>

      <div className="glass rounded-3xl p-6 shadow-xl space-y-4">
        {/* 模式切换 */}
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => { setMode("s2r"); setResult(null); }}
            className={`py-2.5 rounded-xl text-sm font-medium transition ${
              mode === "s2r" ? "bg-gradient-to-r from-pink-500 to-indigo-500 text-white" : "bg-white/5 text-white/60"
            }`}
          >
            分数 → 位次
          </button>
          <button
            onClick={() => { setMode("r2s"); setResult(null); }}
            className={`py-2.5 rounded-xl text-sm font-medium transition ${
              mode === "r2s" ? "bg-gradient-to-r from-pink-500 to-indigo-500 text-white" : "bg-white/5 text-white/60"
            }`}
          >
            位次 → 分数
          </button>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <select value={province} onChange={(e) => setProvince(e.target.value)} className="bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm">
            {PROVINCES.map((p) => <option key={p} className="bg-slate-800">{p}</option>)}
          </select>
          <select value={year} onChange={(e) => setYear(Number(e.target.value))} className="bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm">
            {YEARS.map((y) => <option key={y} value={y} className="bg-slate-800">{y}年</option>)}
          </select>
          <select value={track} onChange={(e) => setTrack(e.target.value)} className="bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm">
            {TRACKS.map((t) => <option key={t} className="bg-slate-800">{t}</option>)}
          </select>
        </div>

        <div className="flex gap-2">
          <input
            type="number"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={mode === "s2r" ? "输入高考分数，如 543" : "输入全省位次，如 30000"}
            className="flex-1 bg-white/10 border border-white/15 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400"
          />
          <button
            onClick={handleQuery}
            disabled={loading}
            className="px-5 rounded-xl bg-gradient-to-r from-pink-500 to-indigo-500 font-bold text-sm disabled:opacity-50 flex items-center gap-1.5"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "查询"}
          </button>
        </div>

        {error && <p className="text-red-300 text-sm">{error}</p>}

        {result && resultValue !== null && (
          <div className="glass rounded-2xl p-6 text-center animate-fade-in">
            <div className="text-xs text-white/50 mb-1">
              {mode === "s2r" ? "全省累计位次" : "对应分数"}
            </div>
            <div className="text-4xl font-bold bg-gradient-to-r from-pink-400 to-indigo-400 bg-clip-text text-transparent">
              {resultValue.toLocaleString()}
            </div>
            {result.source && (
              <div className="text-xs text-white/40 mt-3">来源：{result.source}</div>
            )}
          </div>
        )}
        {result && resultValue === null && (
          <p className="text-white/50 text-sm text-center">该年份/科类暂无数据</p>
        )}
      </div>
    </div>
  );
}
