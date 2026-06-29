import { useState } from "react";
import { Calculator, MapPin, Wallet } from "lucide-react";
import type { HenanTargetItem } from "../api/types";

// 费用格式化（元 → 千/万可读）
export function fmtMoney(v?: number | null): string {
  if (v === undefined || v === null) return "—";
  if (v >= 10000) return `${(v / 10000).toFixed(v % 10000 === 0 ? 0 : 1)}万`;
  return `${v}`;
}

// 位次千分位格式化
export function fmtRank(v?: number | null): string {
  return typeof v === "number" && v > 0 ? v.toLocaleString("zh-CN") : "—";
}

// 历史基线粒度中文化
export function fmtBaselineGranularity(v?: string | null): string {
  if (!v) return "";
  if (v === "major") return "专业";
  if (v === "major_group") return "专业组";
  if (v === "major_group_trend") return "专业组趋势";
  if (v === "school") return "学校";
  if (v === "school_inferred") return "同校推断";
  return v;
}

// 学校性质徽章色
export const OWNERSHIP_STYLE: Record<string, string> = {
  公办: "bg-sky-500/20 text-sky-300",
  民办: "bg-amber-500/20 text-amber-300",
  中外合作: "bg-fuchsia-500/20 text-fuchsia-300",
  独立学院: "bg-purple-500/20 text-purple-300",
};

interface Props {
  s: HenanTargetItem;
  bucketKey: string;
  index?: number;
  // 是否展示可展开的冲稳保计算链（首页与目标评估均开启）
  showCalc?: boolean;
}

/**
 * 河南志愿推的院校专业组卡片（冲稳保 + 成功率 + 学校性质 + 费用 + 可展开计算链）。
 * 首页志愿推荐与目标评估共用此组件，保证两处信息一致。
 */
export default function HenanItemCard({ s, bucketKey, index, showCalc }: Props) {
  const [calcOpen, setCalcOpen] = useState(false);
  const ownership = s.school_ownership || "";
  const detail = s.bucket_detail;
  return (
    <div className="glass rounded-xl p-3 text-sm">
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded ${
              bucketKey === "搏" ? "bg-rose-500/20 text-rose-300"
              : bucketKey === "冲" ? "bg-orange-500/20 text-orange-300"
              : bucketKey === "稳" ? "bg-emerald-500/20 text-emerald-300"
              : bucketKey === "保" ? "bg-sky-500/20 text-sky-300"
              : bucketKey === "垫" ? "bg-indigo-500/20 text-indigo-300"
              : "bg-amber-500/20 text-amber-300"
            }`}>{s.bucket}</span>
            {/* 投档成功率徽章（problem1）：可达档位才显示 */}
            {typeof s.admission_probability === "number" && s.admission_probability > 0 && (
              <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded ${
                s.admission_probability >= 0.9 ? "bg-sky-500/20 text-sky-300"
                : s.admission_probability >= 0.6 ? "bg-emerald-500/20 text-emerald-300"
                : s.admission_probability >= 0.4 ? "bg-amber-500/20 text-amber-300"
                : "bg-orange-500/20 text-orange-300"
              }`}>成功率 {Math.round(s.admission_probability * 100)}%</span>
            )}
            <span className="font-bold truncate">{s.school_name}</span>
            <span className="text-[11px] text-white/50">{s.major_group_code} · {s.major_group_name}</span>
          </div>
          {/* 学校性质（问题4）：公办/民办/中外 + 省内/省外 + 985/211 */}
          <div className="flex items-center gap-1.5 flex-wrap mt-1">
            {ownership && (
              <span className={`text-[11px] px-1.5 py-0.5 rounded ${OWNERSHIP_STYLE[ownership] ?? "bg-white/10 text-white/60"}`}>{ownership}</span>
            )}
            <span className="text-[11px] text-white/55 flex items-center gap-0.5">
              <MapPin className="w-3 h-3" />
              {s.is_henan_local ? "省内" : "省外"}{s.school_province ? `·${s.school_province}` : ""}{s.school_city ? ` ${s.school_city}` : ""}
            </span>
            {(s.school_tags ?? []).map((t) => (
              <span key={t} className="text-[11px] px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-300">{t}</span>
            ))}
            {/* 语种限制标签（日语考生场景）：hard_blocked 不可录取 / soft_warning 英语适应风险 */}
            {s.language_restriction && s.language_restriction.level === "hard_blocked" && (
              <span className="text-[11px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-300" title={s.language_restriction.note}>
                英语限·不可录取
              </span>
            )}
            {s.language_restriction && s.language_restriction.level === "soft_warning" && (
              <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300" title={s.language_restriction.note}>
                公共外语仅英语
              </span>
            )}
            {s.language_restriction && s.language_restriction.level === "missing_data" && (
              <span className="text-[11px] px-1.5 py-0.5 rounded bg-white/10 text-white/55" title={s.language_restriction.note}>
                语种数据缺失
              </span>
            )}
          </div>
          {s.selected_majors && s.selected_majors.length > 0 && (
            <div className="text-xs text-white/50 mt-0.5">组内专业：{s.selected_majors.join("、")}</div>
          )}
          {/* 费用（问题3）：学费/住宿费/生活费 + 4年合计 */}
          <div className="text-[13px] text-white/60 mt-1 flex items-center gap-1 flex-wrap">
            <Wallet className="w-3.5 h-3.5 text-emerald-300/70" />
            <span>学费 <b className="text-white/85">{fmtMoney(s.tuition)}</b>/年</span>
            <span className="text-white/25">·</span>
            <span>住宿 <b className="text-white/85">{fmtMoney(s.accommodation)}</b>/年{s.accommodation_is_estimate ? <span className="text-white/30">（估）</span> : null}</span>
            <span className="text-white/25">·</span>
            <span>{s.school_system_years ?? 4}年合计 ≈ <b className="text-amber-300/90">{fmtMoney(s.four_year_total)}</b>元</span>
          </div>
          {typeof s.plan_count === "number" && (
            <div className="text-[13px] text-white/50 mt-0.5">2026河南计划 <b className="text-white/80">{s.plan_count}</b> 人</div>
          )}
          {detail && (
            <div className="text-[13px] text-white/60 mt-0.5 flex flex-wrap gap-1.5 tabular-nums">
              <span>考生位次 <b className="text-white/90">{fmtRank(detail.student_rank)}</b></span>
              <span className="text-white/25">·</span>
              <span>
                {detail.baseline_year ? `${detail.baseline_year}年录取位次` : "去年录取位次"} <b className="text-white/90">{fmtRank(detail.adjusted_min_rank)}</b>
              </span>
            </div>
          )}
        </div>
        {typeof index === "number" && (
          <div className="w-9 h-9 rounded-lg bg-white/10 text-white/70 font-mono text-sm tabular-nums flex items-center justify-center shrink-0">
            #{index + 1}
          </div>
        )}
      </div>
      {/* 冲稳保计算链（问题2）：可展开查看本组位次差比计算 */}
      {showCalc && detail && (
        <div className="mt-1.5">
          <button type="button" onClick={() => setCalcOpen((v) => !v)}
            className="text-[10px] text-white/40 hover:text-white/60 flex items-center gap-0.5">
            <Calculator className="w-3 h-3" />{calcOpen ? "收起" : "查看"}本组冲稳保计算
          </button>
          {calcOpen && (
            <div className="text-[10px] text-white/50 mt-1 bg-white/5 rounded-lg p-2 space-y-0.5 font-mono">
              <div>公式：{detail.formula}</div>
              <div>考生位次 <b className="text-white/70">{fmtRank(detail.student_rank)}</b> − 参考位次 <b className="text-white/70">{fmtRank(detail.adjusted_min_rank)}</b>
                {detail.baseline_year ? `（${detail.baseline_year}年${fmtBaselineGranularity(detail.baseline_granularity)}）` : ""}</div>
              <div>位次差比 = <b className={bucketKey === "搏" ? "text-rose-300" : bucketKey === "冲" ? "text-orange-300" : bucketKey === "稳" ? "text-emerald-300" : bucketKey === "垫" ? "text-indigo-300" : "text-sky-300"}>
                {detail.rank_gap_ratio !== null && detail.rank_gap_ratio !== undefined ? `${(detail.rank_gap_ratio * 100).toFixed(1)}%` : "—"}
              </b> → 判定 <b className="text-white/70">{s.bucket}</b> · 投档成功率 <b className="text-emerald-300">
                {typeof detail.admission_probability === "number" && detail.admission_probability > 0 ? `${Math.round(detail.admission_probability * 100)}%` : "—"}
              </b></div>
              <div className="text-white/35">置信度 {detail.confidence?.toFixed?.(2) ?? detail.confidence}{detail.confidence < 0.7 ? "（&lt;0.7，成功率已打折）" : ""}</div>
            </div>
          )}
        </div>
      )}
      {s.blocked_reasons && s.blocked_reasons.length > 0 && (
        <div className="text-[11px] text-red-300/80 mt-1.5 space-y-0.5">
          {s.blocked_reasons.map((r, j) => <div key={j}>⚠ {r}</div>)}
        </div>
      )}
      {s.warnings && s.warnings.length > 0 && (
        <div className="text-[11px] text-amber-300/70 mt-1 space-y-0.5">
          {s.warnings.map((w, j) => <div key={j}>⚠ {w}</div>)}
        </div>
      )}
      {s.missing_data_items && s.missing_data_items.length > 0 && (
        <div className="text-[11px] text-amber-200/80 mt-1 space-y-0.5">
          {s.missing_data_items.map((item, j) => <div key={j}>缺：{item}</div>)}
        </div>
      )}
    </div>
  );
}
