import { Rocket, ShieldCheck, Anchor, Info } from "lucide-react";
import type { VolunteerTable as VTable } from "../api/types";
import SchoolCard from "./SchoolCard";

interface Props {
  table: VTable;
}

const BUCKETS = [
  { key: "sprint" as const, label: "冲", icon: Rocket, color: "text-orange-300", desc: "有希望但冒险" },
  { key: "stable" as const, label: "稳", icon: ShieldCheck, color: "text-emerald-300", desc: "匹配度最高" },
  { key: "safe" as const, label: "保", icon: Anchor, color: "text-sky-300", desc: "稳妥兜底" },
];

export default function VolunteerTable({ table }: Props) {
  const total = table.sprint.length + table.stable.length + table.safe.length;

  return (
    <div className="animate-slide-up">
      {/* 考生摘要 */}
      <div className="glass rounded-3xl p-6 mb-6 shadow-xl">
        <div className="flex flex-wrap items-center justify-around gap-4 text-center">
          <div>
            <div className="text-3xl font-bold bg-gradient-to-r from-pink-400 to-indigo-400 bg-clip-text text-transparent">
              {table.student_score}
            </div>
            <div className="text-xs text-white/50 mt-1">高考分数</div>
          </div>
          <div className="w-px h-12 bg-white/10" />
          <div>
            <div className="text-3xl font-bold text-white">
              {table.student_rank.toLocaleString()}
            </div>
            <div className="text-xs text-white/50 mt-1">全省位次</div>
          </div>
          {table.equivalent_rank !== null && table.equivalent_rank !== table.student_rank && (
            <>
              <div className="w-px h-12 bg-white/10" />
              <div>
                <div className="text-3xl font-bold text-white/70">
                  {table.equivalent_rank.toLocaleString()}
                </div>
                <div className="text-xs text-white/50 mt-1">等效位次</div>
              </div>
            </>
          )}
          <div className="w-px h-12 bg-white/10" />
          <div>
            <div className="text-xl font-bold text-white">{table.track}</div>
            <div className="text-xs text-white/50 mt-1">{table.data_year}年数据</div>
          </div>
        </div>
      </div>

      {total === 0 ? (
        <div className="glass rounded-3xl p-10 text-center text-white/50">
          <Info className="w-8 h-8 mx-auto mb-3 opacity-50" />
          该分数段暂无匹配的院校数据。
          <br />
          <span className="text-xs">可尝试切换数据年份或科类，或后续补充更多院校。</span>
        </div>
      ) : (
        <>
          {BUCKETS.map((b) => {
            const list = table[b.key];
            if (list.length === 0) return null;
            return (
              <div key={b.key} className="mb-7">
                <div className="flex items-center gap-2 mb-3 px-1">
                  <b.icon className={`w-5 h-5 ${b.color}`} />
                  <h3 className="font-bold text-lg">{b.label}</h3>
                  <span className="text-xs text-white/40">{b.desc}</span>
                  <span className="ml-auto text-xs text-white/40">{list.length} 所</span>
                </div>
                <div className="grid sm:grid-cols-2 gap-3">
                  {list.map((s, i) => (
                    <SchoolCard key={`${s.school}-${i}`} suggestion={s} index={i} />
                  ))}
                </div>
              </div>
            );
          })}
        </>
      )}

      {/* 来源说明 */}
      <div className="glass rounded-2xl p-4 mt-6 flex items-start gap-2 text-xs text-white/50">
        <Info className="w-4 h-4 mt-0.5 shrink-0" />
        <span>{table.source_note}</span>
      </div>
    </div>
  );
}
