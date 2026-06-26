import { Wallet, Briefcase } from "lucide-react";
import type { TrajectoryItem } from "../api/types";

const STYLE = {
  冲: { border: "border-orange-400/30", badge: "bg-gradient-to-r from-orange-500 to-red-500" },
  稳: { border: "border-emerald-400/30", badge: "bg-gradient-to-r from-emerald-500 to-green-500" },
  保: { border: "border-sky-400/30", badge: "bg-gradient-to-r from-sky-500 to-blue-500" },
};

const fmt = (n: number) => n.toLocaleString();
const wan = (n: number) => (n >= 10000 ? `${(n / 10000).toFixed(1)}万` : fmt(n));

export default function TrajectoryCard({ item, index }: { item: TrajectoryItem; index: number }) {
  const st = STYLE[item.strategy as keyof typeof STYLE] || STYLE.稳;
  const pct = Math.round(item.probability * 100);
  const { cost, career } = item;

  return (
    <div
      className={`glass rounded-2xl p-4 border ${st.border} animate-fade-in hover:scale-[1.01] transition`}
      style={{ animationDelay: `${index * 60}ms` }}
    >
      {/* 头部：学校 + 概率 */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs font-bold px-2 py-0.5 rounded-md ${st.badge} text-white`}>
              {item.strategy}
            </span>
            <h3 className="font-bold text-base truncate">{item.school}</h3>
            {item.degree_level && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                item.degree_level === "本科"
                  ? "bg-indigo-500/20 text-indigo-300"
                  : "bg-gray-500/20 text-gray-300"
              }`}>{item.degree_level}</span>
            )}
            {cost && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-white/60">
                {cost.nature}
              </span>
            )}
            {item.batch && item.batch !== "本科批" && (
              <span className="text-[10px] text-white/40">{item.batch}</span>
            )}
          </div>
          {item.major && (
            <p className="text-xs text-white/60 mt-1">{item.major}</p>
          )}
          {/* 选科/外语要求展示 */}
          {(item.subject_requirement || (item as any).foreign_language_required) && (
            <div className="flex flex-wrap gap-1 mt-1">
              {item.subject_requirement && (
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/10 text-white/50">
                  选科:{item.subject_requirement}
                </span>
              )}
            </div>
          )}
          {item.note && (
            <p className="text-[9px] text-amber-300/70 mt-1">⚠ {item.note}</p>
          )}
        </div>
        <div className="text-right shrink-0 relative group">
          <div className="text-lg font-bold text-white cursor-help underline decoration-dotted decoration-white/30">{pct}%</div>
          <div className="text-[10px] text-white/40">录取概率 ⓘ</div>
          {/* hover tooltip：完整算法+数据来源 */}
          <div className="absolute right-0 top-full mt-2 z-50 hidden group-hover:block w-80 bg-slate-800 border border-white/25 rounded-xl p-4 text-left shadow-2xl">
            <div className="text-sm font-bold text-white mb-2">录取概率算法</div>
            <div className="text-xs text-white/80 leading-relaxed space-y-2">
              {/* 历年参考数据 */}
              <div className="bg-white/10 rounded-lg p-2.5 space-y-1">
                <div className="text-[11px] font-bold text-amber-300">历年录取数据（参考2025同制度）</div>
                <div className="flex justify-between text-[11px] text-white/70">
                  <span>校录最低分</span><span className="text-white font-mono">{item.last_year_score}分</span>
                </div>
                <div className="flex justify-between text-[11px] text-white/70">
                  <span>校录最低位次</span><span className="text-white font-mono">{item.last_year_rank.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-[11px] text-white/70">
                  <span>考生今年位次</span><span className="text-white font-mono">{item.student_rank.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-[11px] text-white/70">
                  <span>2025本科省控线</span><span className="text-white/60 font-mono">历史类471分</span>
                </div>
                <div className="flex justify-between text-[11px] text-white/70">
                  <span>2026本科省控线</span><span className="text-white/60 font-mono">历史类459分</span>
                </div>
              </div>
              {/* 算法公式 */}
              <p className="font-bold text-white/90 text-[11px]">计算公式（ratio = 校录位次 ÷ 考生位次）：</p>
              <div className="bg-white/10 rounded-lg p-2 font-mono text-[11px] text-emerald-300 leading-relaxed">
                ratio ≥ 1（保档）：<br/>概率 = 0.9 + (ratio-1) × 0.3，上限99%<br/><br/>
                ratio &lt; 1（冲档）：<br/>概率 = 0.9 - (1-ratio) × 2.5，下限5%
              </div>
              <p className="text-amber-300/70 text-[11px] pt-1 border-t border-white/15">
                ⚠ 基于2025历年位次的粗略估算，非精确概率。位次受试卷难度/招生计划影响会有波动，2026投档线8月公布后可校准。
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 两栏：费用 / 就业 */}
      <div className="grid grid-cols-2 gap-2 mt-3">
        {/* 费用 */}
        <div className="bg-pink-500/10 rounded-xl p-2.5 border border-pink-400/20">
          <div className="flex items-center gap-1 text-[10px] text-pink-300 mb-1">
            <Wallet className="w-3 h-3" /> 大学总花费
          </div>
          {cost ? (
            <>
              <div className="text-base font-bold text-pink-200">¥{wan(cost.grand_total)}</div>
              <div className="text-[9px] text-white/40 mt-0.5">
                学{wan(cost.tuition_total)}·住{wan(cost.accommodation_total)}·活{wan(cost.living_total)}
              </div>
            </>
          ) : (
            <div className="text-xs text-white/30 py-1">无数据</div>
          )}
        </div>

        {/* 就业 */}
        <div className="bg-indigo-500/10 rounded-xl p-2.5 border border-indigo-400/20">
          <div className="flex items-center gap-1 text-[10px] text-indigo-300 mb-1">
            <Briefcase className="w-3 h-3" /> 毕业起薪
          </div>
          {career ? (
            <>
              <div className="text-base font-bold text-indigo-200">¥{fmt(career.entry_salary_mid)}</div>
              <div className="text-[9px] text-white/40 mt-0.5">
                {fmt(career.entry_salary_low)}-{fmt(career.entry_salary_high)}/月
                {career.mid_salary_5y && `·5年${fmt(career.mid_salary_5y)}`}
              </div>
            </>
          ) : (
            <div className="text-xs text-white/30 py-1">无数据</div>
          )}
        </div>
      </div>
    </div>
  );
}
