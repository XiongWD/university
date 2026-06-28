import { useState } from "react";
import { Loader2, Calendar } from "lucide-react";
import { getControlLine, ApiError } from "../api/client";
import type { ControlLine } from "../api/types";

const YEARS = [2026, 2025, 2024];

const BATCH_LABELS: { key: keyof ControlLine["batches"]; label: string }[] = [
  { key: "special_line", label: "特殊类型招生控制线" },
  { key: "undergrad_batch", label: "本科批" },
  { key: "first_batch", label: "一本线" },
  { key: "second_batch", label: "二本线" },
  { key: "junior_college", label: "专科批" },
];

export default function ControlLinePage() {
  const [year, setYear] = useState(2026);
  const [loading, setLoading] = useState(false);
  const [lines, setLines] = useState<ControlLine[]>([]);
  const [queried, setQueried] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleQuery() {
    setLoading(true);
    setError(null);
    setQueried(true);
    try {
      const r = await getControlLine("河南", year, "历史类");
      setLines(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "查询失败");
      setLines([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="text-center mb-6">
        <h1 className="text-3xl font-bold flex items-center justify-center gap-2">
          <Calendar className="w-7 h-7 text-pink-400" />
          省控线查询
        </h1>
        <p className="text-white/50 text-sm mt-1">各批次录取控制分数线</p>
      </div>

      <div className="glass rounded-3xl p-6 shadow-xl space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white/80">
            河南 / 历史类
          </div>
          <select value={year} onChange={(e) => setYear(Number(e.target.value))} className="bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm">
            {YEARS.map((y) => <option key={y} value={y} className="bg-slate-800">{y}年</option>)}
          </select>
        </div>

        <button
          onClick={handleQuery}
          disabled={loading}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-pink-500 to-indigo-500 font-bold text-sm disabled:opacity-50 flex items-center justify-center gap-1.5"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "查询省控线"}
        </button>

        {error && <p className="text-red-300 text-sm">{error}</p>}

        {queried && !loading && lines.length === 0 && !error && (
          <p className="text-white/50 text-sm text-center">该年份/科类暂无省控线数据</p>
        )}

        {lines.map((line) => (
          <div key={line.id} className="glass rounded-2xl p-5 animate-fade-in">
            <div className="flex items-center justify-between mb-3">
              <span className="font-bold">{line.province} · {line.track}</span>
              <span className="text-xs text-white/40">{line.year}年</span>
            </div>
            <div className="space-y-2">
              {BATCH_LABELS.map(({ key, label }) => {
                const v = line.batches[key];
                if (v === null || v === undefined) return null;
                return (
                  <div key={key} className="flex items-center justify-between text-sm py-1.5 border-b border-white/5 last:border-0">
                    <span className="text-white/60">{label}</span>
                    <span className="font-bold text-lg bg-gradient-to-r from-pink-400 to-indigo-400 bg-clip-text text-transparent">
                      {v}
                    </span>
                  </div>
                );
              })}
            </div>
            {line.source && (
              <div className="text-xs text-white/40 mt-3">来源：{line.source}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
