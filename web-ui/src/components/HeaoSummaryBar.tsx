/**
 * heao 权威评估汇总条（放在志愿组统计区）。
 *
 * 读取 heao 评估数据 + 志愿组各校 planned_tier，汇总：
 * - 设定 vs 实际匹配数（✅一致 / ⚠️偏保守 / 🔺偏乐观）
 * - 列出"设定偏乐观"的高风险项（实际比设定更冲）
 */
import { useEffect, useState } from "react";
import { getHeaoAssessment, type HeaoSchoolAssessment } from "../api/client";
import type { UserVolunteerItem } from "../api/types";
import { TIER_STYLE } from "./volunteerTier";

// 模块级缓存（与 VolunteerItemRow 共享同一份）
let _cache: Record<string, HeaoSchoolAssessment> | null = null;
let _promise: Promise<Record<string, HeaoSchoolAssessment>> | null = null;
function loadAssessment() {
  if (_cache) return Promise.resolve(_cache);
  if (!_promise) {
    _promise = getHeaoAssessment()
      .then((d) => { _cache = d; return d; })
      .catch(() => { _promise = null; return {}; });
  }
  return _promise;
}

const TIER_ORDER: Record<string, number> = {
  "超冲": 0, "搏": 1, "冲": 2, "稳": 3, "保": 4, "垫": 5,
};

interface Props {
  items: UserVolunteerItem[];
}

export default function HeaoSummaryBar({ items }: Props) {
  const [assessment, setAssessment] = useState<Record<string, HeaoSchoolAssessment> | null>(null);

  useEffect(() => {
    loadAssessment().then(setAssessment);
  }, []);

  if (!assessment) {
    return (
      <div className="text-[10px] text-white/30 pt-1">heao 评估加载中…</div>
    );
  }

  // 汇总：每个志愿项的设定 tier vs 该校"最优组"（最容易录取的组）的实际 tier
  let match = 0, conservative = 0, optimistic = 0;
  const riskyItems: { name: string; planned: string; actual: string }[] = [];

  for (const it of items) {
    const key = it.school_name.split("(")[0];
    const school = assessment[key];
    if (!school || !school.groups.length) continue;

    // 该校各组里最容易录取的（advantage 最大的=位次差最大的）
    const bestGroup = school.groups.reduce((best, g) =>
      (g.advantage ?? -Infinity) > (best.advantage ?? -Infinity) ? g : best
    );
    const actualTier = bestGroup.tier;
    const plannedTier = it.planned_tier ?? it.effective_tier;

    if (plannedTier === actualTier) {
      match++;
    } else if ((TIER_ORDER[actualTier] ?? 9) < (TIER_ORDER[plannedTier] ?? 9)) {
      // 实际比设定更冲 = 设定偏乐观（高风险）
      optimistic++;
      riskyItems.push({ name: it.school_name, planned: plannedTier, actual: actualTier });
    } else {
      conservative++;
    }
  }

  if (match + conservative + optimistic === 0) {
    return null;
  }

  return (
    <div className="pt-1.5 mt-1.5 border-t border-white/10 space-y-1">
      <div className="text-[10px] text-white/50 flex items-center gap-2 flex-wrap">
        <span className="text-emerald-300/80">◆ heao设定校验</span>
        <span className="text-emerald-300">✅{match}一致</span>
        <span className="text-amber-300">⚠{conservative}偏保守</span>
        {optimistic > 0 && (
          <span className="text-rose-300">🔺{optimistic}偏乐观</span>
        )}
      </div>
      {riskyItems.length > 0 && (
        <div className="space-y-0.5">
          {riskyItems.map((r) => (
            <div key={r.name} className="text-[10px] text-rose-200/80 leading-tight">
              ⚠ {r.name}：设定{r.planned} → 实际
              <span className={`px-1 ml-0.5 rounded text-[9px] font-bold ${TIER_STYLE[r.actual] ?? ""}`}>
                {r.actual}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
