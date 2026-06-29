import { useState } from "react";
import { Calculator, MapPin } from "lucide-react";
import type { HenanTargetItem } from "../api/types";
import { fmtMoney, fmtRank, fmtBaselineGranularity, OWNERSHIP_STYLE } from "./HenanItemCard";

// 冲稳保垫档位徽章配色
const BUCKET_STYLE: Record<string, string> = {
  搏: "bg-rose-500/20 text-rose-300",
  冲: "bg-orange-500/20 text-orange-300",
  稳: "bg-emerald-500/20 text-emerald-300",
  保: "bg-sky-500/20 text-sky-300",
  垫: "bg-indigo-500/20 text-indigo-300",
};

interface Props {
  items: HenanTargetItem[];   // 同一学校、同一档位的多个专业组
  bucketKey: string;          // 冲/稳/保
}

/**
 * 目标评估页「单校聚合」卡片：学校共性信息只显示一次，专业组作为子表展示差异化数据。
 *
 * 与 HenanItemCard（多校平铺，每校独立卡片）的区别：本组件面向「单校多专业组」，
 * 把学校名/性质/省市/位次/差比/成功率/语种等共性字段提取到头部，避免重复；
 * 专业组代码/组内专业/计划人数/学费（可能因组而异）作为子表逐行展示。
 *
 * 安全降级：共性字段若组间不一致（如某些校中外合作组位次/学费不同），
 * 该字段自动降级到子表按组显示，不强行合并。
 */
export default function TargetSchoolCard({ items, bucketKey }: Props) {
  const [calcOpen, setCalcOpen] = useState(false);
  if (items.length === 0) return null;
  const head = items[0];

  // —— 共性提取（同校同档位通常一致）——
  const ownership = head.school_ownership || "";
  const detail = head.bucket_detail;
  // 检测共性字段是否组间一致；不一致则降级到子表
  const adjRanks = new Set(items.map((it) => (it.bucket_detail || {}).adjusted_min_rank ?? null));
  const studentRanks = new Set(items.map((it) => (it.bucket_detail || {}).student_rank ?? null));
  const rankCommon = adjRanks.size === 1 && studentRanks.size === 1;
  // 学费/4年费用按组显示（不提取共性——17/35 校同校不同组学费不同）
  const prob = head.admission_probability;
  const lang = head.language_restriction;

  return (
    <div className="glass rounded-xl p-4">
      {/* —— 学校头部（共性信息，显示一次）—— */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`text-xs font-bold px-2 py-0.5 rounded ${BUCKET_STYLE[bucketKey] ?? "bg-white/10 text-white/70"}`}>{head.bucket}</span>
        {typeof prob === "number" && prob > 0 && (
          <span className={`text-xs font-bold px-2 py-0.5 rounded ${
            prob >= 0.9 ? "bg-sky-500/20 text-sky-300"
            : prob >= 0.6 ? "bg-emerald-500/20 text-emerald-300"
            : prob >= 0.4 ? "bg-amber-500/20 text-amber-300"
            : "bg-orange-500/20 text-orange-300"
          }`}>成功率 {Math.round(prob * 100)}%</span>
        )}
        <span className="font-bold text-base truncate">{head.school_name}</span>
      </div>

      {/* 性质 + 省市（共性） */}
      <div className="flex items-center gap-1.5 flex-wrap mt-1.5">
        {ownership && (
          <span className={`text-[11px] px-1.5 py-0.5 rounded ${OWNERSHIP_STYLE[ownership] ?? "bg-white/10 text-white/60"}`}>{ownership}</span>
        )}
        <span className="text-[11px] text-white/55 flex items-center gap-0.5">
          <MapPin className="w-3 h-3" />
          {head.is_henan_local ? "省内" : "省外"}{head.school_province ? `·${head.school_province}` : ""}{head.school_city ? ` ${head.school_city}` : ""}
        </span>
        {(head.school_tags ?? []).map((t) => (
          <span key={t} className="text-[11px] px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-300">{t}</span>
        ))}
      </div>

      {/* 位次/差比（共性，关键数据加粗） */}
      {rankCommon && detail && (
        <div className="mt-2 text-[13px] text-white/70 flex flex-wrap items-center gap-x-3 gap-y-1 tabular-nums">
          <span>考生位次 <b className="text-white/90">{fmtRank(detail.student_rank)}</b></span>
          <span className="text-white/25">·</span>
          <span>{detail.baseline_year ? `${detail.baseline_year}年` : ""}录取位次 <b className="text-white/90">{fmtRank(detail.adjusted_min_rank)}</b></span>
          <span className="text-white/25">·</span>
          <span>位次差比 <b className={bucketKey === "搏" ? "text-rose-300" : bucketKey === "冲" ? "text-orange-300" : bucketKey === "稳" ? "text-emerald-300" : bucketKey === "垫" ? "text-indigo-300" : "text-sky-300"}>
            {detail.rank_gap_ratio !== null && detail.rank_gap_ratio !== undefined ? `${(detail.rank_gap_ratio * 100).toFixed(1)}%` : "—"}
          </b></span>
        </div>
      )}

      {/* 语种提示（共性，日语考生场景） */}
      {lang && lang.level !== "none" && (
        <div className={`mt-1.5 text-[12px] flex items-start gap-1 ${
          lang.level === "hard_blocked" ? "text-red-300/85"
          : lang.level === "soft_warning" ? "text-amber-300/80"
          : "text-white/55"
        }`}>
          <span>⚠ {lang.level === "hard_blocked" ? "不可录取：" : lang.level === "soft_warning" ? "英语适应风险：" : "语种数据缺失："}</span>
          <span>{lang.note}</span>
        </div>
      )}

      {/* 冲稳保计算链（同校同档位计算链一致，放头部） */}
      {rankCommon && detail && (
        <div className="mt-1.5">
          <button type="button" onClick={() => setCalcOpen((v) => !v)}
            className="text-[11px] text-white/45 hover:text-white/70 flex items-center gap-0.5">
            <Calculator className="w-3 h-3" />{calcOpen ? "收起" : "查看"}冲稳保计算
          </button>
          {calcOpen && (
            <div className="text-[11px] text-white/60 mt-1 bg-white/5 rounded-lg p-2 space-y-0.5 font-mono">
              <div>公式：{detail.formula}</div>
              <div>考生位次 <b className="text-white/80">{fmtRank(detail.student_rank)}</b> − 参考位次 <b className="text-white/80">{fmtRank(detail.adjusted_min_rank)}</b>
                {detail.baseline_year ? `（${detail.baseline_year}年${fmtBaselineGranularity(detail.baseline_granularity)}）` : ""}</div>
              <div>位次差比 = <b className={bucketKey === "搏" ? "text-rose-300" : bucketKey === "冲" ? "text-orange-300" : bucketKey === "稳" ? "text-emerald-300" : bucketKey === "垫" ? "text-indigo-300" : "text-sky-300"}>
                {detail.rank_gap_ratio !== null && detail.rank_gap_ratio !== undefined ? `${(detail.rank_gap_ratio * 100).toFixed(1)}%` : "—"}
              </b> → 判定 <b className="text-white/80">{head.bucket}</b> · 投档成功率 <b className="text-emerald-300">
                {typeof detail.admission_probability === "number" && detail.admission_probability > 0 ? `${Math.round(detail.admission_probability * 100)}%` : "—"}
              </b></div>
              <div className="text-white/45">置信度 {detail.confidence?.toFixed?.(2) ?? detail.confidence}{detail.confidence < 0.7 ? "（&lt;0.7，成功率已打折）" : ""}</div>
            </div>
          )}
        </div>
      )}

      {/* —— 专业组子表（差异化数据，逐行显示）—— */}
      <div className="mt-3 pt-3 border-t border-white/10">
        <div className="text-[12px] text-white/55 mb-2">
          专业组明细（{items.length} 个）{!rankCommon && " · 位次因组而异已逐组列出"}
        </div>
        <div className="space-y-2">
          {items.map((it, i) => {
            const itDetail = it.bucket_detail;
            return (
              <div key={`${it.major_group_code}-${i}`} className="bg-white/5 rounded-lg p-2.5">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="min-w-0">
                    <span className="text-[13px] font-semibold text-white/90">{it.major_group_code}</span>
                    <span className="text-[11px] text-white/45 ml-1.5">{it.major_group_name}</span>
                  </div>
                  <div className="text-[12px] text-white/60 tabular-nums">
                    {typeof it.plan_count === "number" && <span>计划 {it.plan_count} 人</span>}
                  </div>
                </div>
                {/* 组内专业 */}
                {it.selected_majors && it.selected_majors.length > 0 && (
                  <div className="text-[12px] text-white/65 mt-1 leading-relaxed">{it.selected_majors.join("、")}</div>
                )}
                {/* 费用（按组，可能不同） */}
                <div className="text-[12px] text-white/60 mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 tabular-nums">
                  <span>学费 <b className="text-white/85">{fmtMoney(it.tuition)}</b>/年</span>
                  <span className="text-white/25">·</span>
                  <span>{it.school_system_years ?? 4}年合计 <b className="text-amber-300/90">{fmtMoney(it.four_year_total)}</b>元</span>
                </div>
                {/* 位次不共性时降级按组显示 */}
                {!rankCommon && itDetail && (
                  <div className="text-[11px] text-white/55 mt-1 tabular-nums">
                    考生位次 {fmtRank(itDetail.student_rank)} · {itDetail.baseline_year ? `${itDetail.baseline_year}年` : ""}录取 {fmtRank(itDetail.adjusted_min_rank)}
                    {itDetail.rank_gap_ratio !== null && itDetail.rank_gap_ratio !== undefined ? ` · 差比 ${(itDetail.rank_gap_ratio * 100).toFixed(1)}%` : ""}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
