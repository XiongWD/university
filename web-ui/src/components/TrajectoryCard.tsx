import {
  Wallet, Briefcase, TrendingUp, Clock,
} from "lucide-react";
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
  const { cost, career, payback } = item;

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
          <div className="text-[10px] text-white/40">录取概率</div>
          {/* hover tooltip：算法说明 */}
          <div className="absolute right-0 top-full mt-1 z-10 hidden group-hover:block w-64 bg-slate-900/95 border border-white/15 rounded-xl p-3 text-left shadow-xl">
            <div className="text-[10px] font-bold text-white/80 mb-1.5">录取概率算法</div>
            <div className="text-[9px] text-white/60 leading-relaxed space-y-1">
              <p><b className="text-white/80">输入</b>：考生位次 vs 学校历年最低录取位次</p>
              <p><b className="text-white/80">核心比值</b>：ratio = 校录位次 ÷ 考生位次</p>
              <div className="bg-white/5 rounded p-1.5 font-mono text-[8px] text-emerald-300/80">
                ratio ≥ 1（保）：概率 = 0.9 + (ratio-1)×0.3，上限99%<br/>
                ratio &lt; 1（冲）：概率 = 0.9 - (1-ratio)×2.5，下限5%
              </div>
              <p className="text-white/40">考生位次{item.student_rank} vs 校录位次{item.last_year_rank}</p>
              <p className="text-amber-300/50 text-[8px] pt-1 border-t border-white/10">
                ⚠ 基于历年位次的粗估，非精确概率。2026投档线8月公布后可校准。
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 三栏：费用 / 就业 / 回本 */}
      <div className="grid grid-cols-3 gap-2 mt-3">
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

        {/* 回本 */}
        <div className="bg-emerald-500/10 rounded-xl p-2.5 border border-emerald-400/20">
          <div className="flex items-center gap-1 text-[10px] text-emerald-300 mb-1">
            <TrendingUp className="w-3 h-3" /> 回本周期
          </div>
          {payback ? (
            <>
              <div className="text-base font-bold text-emerald-200">{payback.years_to_break_even}年</div>
              <div className="text-[9px] text-white/40 mt-0.5">15年净¥{wan(payback.lifetime_15y_net)}</div>
            </>
          ) : (
            <div className="text-xs text-white/30 py-1">无数据</div>
          )}
        </div>
      </div>

      {/* 回本判断 */}
      {payback && (
        <div className="mt-2 flex items-center gap-1 text-[10px] text-white/50">
          <Clock className="w-3 h-3" />
          {payback.note}
        </div>
      )}
    </div>
  );
}
