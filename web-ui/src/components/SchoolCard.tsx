import { TrendingUp, Award, BookOpen } from "lucide-react";
import type { VolunteerSuggestion } from "../api/types";

interface Props {
  suggestion: VolunteerSuggestion;
  index: number;
}

// 冲=橙红 稳=翠绿 保=天蓝
const STYLE = {
  冲: {
    grad: "from-orange-500/20 to-red-500/20",
    border: "border-orange-400/30",
    badge: "bg-gradient-to-r from-orange-500 to-red-500",
    probColor: "text-orange-300",
  },
  稳: {
    grad: "from-emerald-500/20 to-green-500/20",
    border: "border-emerald-400/30",
    badge: "bg-gradient-to-r from-emerald-500 to-green-500",
    probColor: "text-emerald-300",
  },
  保: {
    grad: "from-sky-500/20 to-blue-500/20",
    border: "border-sky-400/30",
    badge: "bg-gradient-to-r from-sky-500 to-blue-500",
    probColor: "text-sky-300",
  },
};

export default function SchoolCard({ suggestion: s, index }: Props) {
  const st = STYLE[s.strategy] || STYLE.稳;
  const pct = Math.round(s.probability.probability * 100);

  return (
    <div
      className={`glass rounded-2xl p-4 border ${st.border} bg-gradient-to-br ${st.grad} animate-fade-in hover:scale-[1.02] transition`}
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs font-bold px-2 py-0.5 rounded-md ${st.badge} text-white`}>
              {s.strategy}
            </span>
            <h3 className="font-bold text-base truncate">{s.school}</h3>
          </div>
          {s.major && s.major !== "普通类" && (
            <p className="text-xs text-white/60 mt-1 flex items-center gap-1">
              <BookOpen className="w-3 h-3" /> {s.major}
              {s.major_group && <span className="opacity-60">· 组{s.major_group}</span>}
            </p>
          )}
          {s.subject_requirement && (
            <p className="text-xs text-white/50 mt-1">选科：{s.subject_requirement}</p>
          )}
        </div>

        {/* 概率圆环 */}
        <div className="flex flex-col items-center shrink-0 relative group">
          <div className="relative w-14 h-14 cursor-help">
            <svg className="w-14 h-14 -rotate-90" viewBox="0 0 56 56">
              <circle cx="28" cy="28" r="24" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="5" />
              <circle
                cx="28" cy="28" r="24" fill="none" stroke="currentColor"
                strokeWidth="5" strokeLinecap="round"
                className={st.probColor}
                strokeDasharray={`${2 * Math.PI * 24 * (pct / 100)} ${2 * Math.PI * 24}`}
              />
            </svg>
            <span className={`absolute inset-0 flex items-center justify-center text-sm font-bold ${st.probColor}`}>
              {pct}%
            </span>
          </div>
          <span className="text-[10px] text-white/40 mt-0.5">录取概率 ⓘ</span>
          {/* hover tooltip */}
          <div className="absolute right-0 top-full mt-2 z-50 hidden group-hover:block w-80 bg-slate-800 border border-white/25 rounded-xl p-4 text-left shadow-2xl">
            <div className="text-sm font-bold text-white mb-2">录取概率算法</div>
            <div className="text-xs text-white/80 leading-relaxed space-y-2">
              <div className="bg-white/10 rounded-lg p-2.5 space-y-1">
                <div className="text-[11px] font-bold text-amber-300">历年录取数据（参考2025同制度）</div>
                <div className="flex justify-between text-[11px] text-white/70">
                  <span>校录最低分</span><span className="text-white font-mono">{s.last_year_score}分</span>
                </div>
                <div className="flex justify-between text-[11px] text-white/70">
                  <span>校录最低位次</span><span className="text-white font-mono">{s.last_year_rank.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-[11px] text-white/70">
                  <span>考生今年位次</span><span className="text-white font-mono">{s.student_rank.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-[11px] text-white/70">
                  <span>2025本科省控线</span><span className="text-white/60 font-mono">历史类471分</span>
                </div>
                <div className="flex justify-between text-[11px] text-white/70">
                  <span>2026本科省控线</span><span className="text-white/60 font-mono">历史类459分</span>
                </div>
              </div>
              <p className="font-bold text-white/90 text-[11px]">计算公式（ratio = 校录位次 ÷ 考生位次）：</p>
              <div className="bg-white/10 rounded-lg p-2 font-mono text-[11px] text-emerald-300 leading-relaxed">
                ratio ≥ 1（保档）：<br/>概率 = 0.9 + (ratio-1) × 0.3，上限99%<br/><br/>
                ratio &lt; 1（冲档）：<br/>概率 = 0.9 - (1-ratio) × 2.5，下限5%
              </div>
              <p className="text-white/50 text-[11px]">{s.probability.basis}</p>
              <p className="text-amber-300/70 text-[11px] pt-1 border-t border-white/15">
                ⚠ 基于2025历年位次的粗略估算，非精确概率。2026投档线8月公布后可校准。
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 位次信息 */}
      <div className="mt-3 pt-3 border-t border-white/10 flex items-center gap-4 text-xs">
        <span className="flex items-center gap-1 text-white/70">
          <TrendingUp className="w-3.5 h-3.5 text-pink-400" />
          校录位次 <b className="text-white">{s.last_year_rank.toLocaleString()}</b>
        </span>
        <span className="flex items-center gap-1 text-white/70">
          <Award className="w-3.5 h-3.5 text-indigo-400" />
          校录分 <b className="text-white">{s.last_year_score}</b>
        </span>
      </div>
      <p className="text-[10px] text-white/30 mt-1.5">{s.probability.basis}</p>
    </div>
  );
}
