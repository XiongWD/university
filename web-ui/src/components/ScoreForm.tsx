import { useState } from "react";
import { Search, Loader2 } from "lucide-react";
import type { RecommendRequest, RiskPreference } from "../api/types";

const PROVINCES = ["河南", "广东"];
const TRACKS_BY_PROVINCE: Record<string, { label: string; value: string }[]> = {
  河南: [
    { label: "物理类", value: "物理类" },
    { label: "历史类", value: "历史类" },
    { label: "理科(2024及以前)", value: "理科" },
    { label: "文科(2024及以前)", value: "文科" },
  ],
  广东: [
    { label: "物理类", value: "物理类" },
    { label: "历史类", value: "历史类" },
  ],
};
const RISK_OPTIONS: { value: RiskPreference; label: string; desc: string }[] = [
  { value: "冲", label: "冲", desc: "敢搏名校" },
  { value: "中", label: "中", desc: "平衡型" },
  { value: "稳", label: "稳", desc: "求稳保底" },
];
const YEARS = [2026, 2025, 2024];

interface Props {
  loading: boolean;
  onSubmit: (req: RecommendRequest) => void;
}

export default function ScoreForm({ loading, onSubmit }: Props) {
  const [province, setProvince] = useState("河南");
  const [totalScore, setTotalScore] = useState(543);
  const [track, setTrack] = useState("物理类");
  const [dataYear, setDataYear] = useState(2025);
  const [risk, setRisk] = useState<RiskPreference>("中");

  const tracks = TRACKS_BY_PROVINCE[province] || [];

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({ province, total_score: totalScore, track, data_year: dataYear, risk_preference: risk });
  }

  return (
    <form onSubmit={handleSubmit} className="glass rounded-3xl p-6 sm:p-8 shadow-2xl animate-slide-up">
      <h2 className="text-xl font-bold mb-1 flex items-center gap-2">
        <Search className="w-5 h-5 text-pink-400" />
        输入考生信息
      </h2>
      <p className="text-sm text-white/50 mb-6">填写分数与偏好，一键生成冲稳保志愿表</p>

      <div className="grid grid-cols-2 gap-4">
        {/* 省份 */}
        <label className="block">
          <span className="text-xs text-white/60 mb-1.5 block">省份</span>
          <select
            value={province}
            onChange={(e) => {
              setProvince(e.target.value);
              const t = TRACKS_BY_PROVINCE[e.target.value];
              if (t && !t.find((x) => x.value === track)) setTrack(t[0].value);
            }}
            className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400"
          >
            {PROVINCES.map((p) => (
              <option key={p} value={p} className="bg-slate-800">
                {p}
              </option>
            ))}
          </select>
        </label>

        {/* 高考总分 */}
        <label className="block">
          <span className="text-xs text-white/60 mb-1.5 block">高考总分</span>
          <input
            type="number"
            min={0}
            max={750}
            value={totalScore}
            onChange={(e) => setTotalScore(Number(e.target.value))}
            className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400"
          />
        </label>

        {/* 科类 */}
        <label className="block">
          <span className="text-xs text-white/60 mb-1.5 block">科类</span>
          <select
            value={track}
            onChange={(e) => setTrack(e.target.value)}
            className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400"
          >
            {tracks.map((t) => (
              <option key={t.value} value={t.value} className="bg-slate-800">
                {t.label}
              </option>
            ))}
          </select>
        </label>

        {/* 数据年份 */}
        <label className="block">
          <span className="text-xs text-white/60 mb-1.5 block">参考数据年份</span>
          <select
            value={dataYear}
            onChange={(e) => setDataYear(Number(e.target.value))}
            className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400"
          >
            {YEARS.map((y) => (
              <option key={y} value={y} className="bg-slate-800">
                {y} 年
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* 风险偏好 */}
      <div className="mt-5">
        <span className="text-xs text-white/60 mb-2 block">报考策略</span>
        <div className="grid grid-cols-3 gap-2">
          {RISK_OPTIONS.map((r) => (
            <button
              key={r.value}
              type="button"
              onClick={() => setRisk(r.value)}
              className={`py-3 rounded-xl text-sm font-bold transition border ${
                risk === r.value
                  ? "bg-gradient-to-br from-pink-500 to-indigo-500 border-transparent text-white shadow-lg"
                  : "bg-white/5 border-white/15 text-white/60 hover:bg-white/10"
              }`}
            >
              <div className="text-lg">{r.label}</div>
              <div className="text-xs font-normal opacity-70 mt-0.5">{r.desc}</div>
            </button>
          ))}
        </div>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="mt-6 w-full py-3.5 rounded-xl bg-gradient-to-r from-pink-500 via-fuchsia-500 to-indigo-500 font-bold text-white shadow-lg hover:shadow-pink-500/30 hover:scale-[1.01] active:scale-[0.99] transition disabled:opacity-50 disabled:hover:scale-100 flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" /> 生成中...
          </>
        ) : (
          <>生成志愿表</>
        )}
      </button>
    </form>
  );
}
