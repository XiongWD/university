import { useState } from "react";
import { AlertCircle, Rocket, ShieldCheck, Anchor, HelpCircle } from "lucide-react";
import ScoreForm from "../components/ScoreForm";
import { henanRecommendation, ApiError } from "../api/client";
import type { AdvisoryRequest, HenanRecommendationResult } from "../api/types";

// 5 档 bucket 渲染配置（design D2，去掉"中"，新增需人工复核）
const BUCKETS = [
  { key: "冲" as const, label: "冲", icon: Rocket, color: "text-orange-300", desc: "有希望但冒险" },
  { key: "稳" as const, label: "稳", icon: ShieldCheck, color: "text-emerald-300", desc: "匹配度较高" },
  { key: "保" as const, label: "保", icon: Anchor, color: "text-sky-300", desc: "稳妥兜底" },
  { key: "不推荐" as const, label: "不推荐", icon: AlertCircle, color: "text-red-300", desc: "资格不符或位次差距过大" },
  { key: "需人工复核" as const, label: "需人工复核", icon: HelpCircle, color: "text-amber-300", desc: "数据待核验" },
];

export default function HomePage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<HenanRecommendationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [displayBucket, setDisplayBucket] = useState<"全部" | "冲" | "稳" | "保">("全部");

  async function handleSubmit(req: AdvisoryRequest) {
    setLoading(true);
    setError(null);
    setDisplayBucket(req.display_bucket ?? "全部");
    try {
      // 映射档位选择到推荐策略：冲→积极，保→保守，稳/全部→自动（design §8.4）
      const strategyMap: Record<string, "自动" | "保守" | "积极" | "均衡"> = {
        "冲": "积极", "保": "保守", "稳": "均衡", "全部": "自动",
      };
      const response = await henanRecommendation({
        score: req.total_score,
        rank: null,
        track: (req.primary_subject === "历史" ? "历史类" : "物理类"),
        source_province: req.province || "河南",
        primary_subject: req.primary_subject,
        elective_subjects: req.elective_subjects,
        exam_foreign_language: req.exam_foreign_language || "英语",
        strategy: strategyMap[req.display_bucket ?? "全部"] ?? "自动",
      });
      setResult(response);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "请求失败，请确认后端服务已启动");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const visibleBuckets = displayBucket === "全部"
    ? BUCKETS
    : BUCKETS.filter((b) => b.label === displayBucket);

  return (
    <div className="space-y-6">
      {!result && (
        <div className="text-center py-6 animate-fade-in">
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight">
            <span className="bg-gradient-to-r from-pink-400 via-fuchsia-400 to-indigo-400 bg-clip-text text-transparent">
              河南志愿推
            </span>
          </h1>
          <p className="text-white/60 mt-3 text-sm sm:text-base">
            河南高考志愿推荐 · 院校专业组 · 冲稳保
          </p>
        </div>
      )}

      <ScoreForm loading={loading} onSubmit={handleSubmit} />

      {error && (
        <div className="glass rounded-2xl p-4 border border-red-400/30 flex items-start gap-2 text-sm text-red-200">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <div>
            <p className="font-medium">出错了</p>
            <p className="text-red-200/70 text-xs mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {result && (
        <div className="animate-slide-up space-y-5">
          {/* 数据就绪状态 banner */}
          {!result.data_ready && (
            <div className="glass rounded-2xl p-4 border border-amber-400/30 flex items-start gap-2 text-sm text-amber-200">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <div>
                <p className="font-medium">推荐数据未完全就绪</p>
                <p className="text-amber-200/70 text-xs mt-0.5">
                  {result.readiness_errors.join("；") || "部分数据待核验，冲稳保结果仅供参考"}
                </p>
                <p className="text-amber-200/50 text-[11px] mt-1">
                  以下结果中「需人工复核」档位表示数据不足，不作可信推荐依据。
                </p>
              </div>
            </div>
          )}

          {/* 档位筛选提示 */}
          <div className="text-xs text-white/40 px-1">
            共 {Object.values(result.buckets).reduce((s, l) => s + l.length, 0)} 个院校专业组候选 ·
            当前显示「{displayBucket}」档位
          </div>

          {/* 5 档 buckets */}
          {visibleBuckets.map((b) => {
            const list = result.buckets[b.key] ?? [];
            if (list.length === 0) return null;
            return (
              <div key={b.key} className="mb-6">
                <div className="flex items-center gap-2 mb-3 px-1">
                  <b.icon className={`w-5 h-5 ${b.color}`} />
                  <h3 className="font-bold text-lg">{b.label}</h3>
                  <span className="text-xs text-white/40">{b.desc}</span>
                  <span className="ml-auto text-xs text-white/40">{list.length} 个专业组</span>
                </div>
                <div className="space-y-2">
                  {list.map((s, i) => (
                    <div key={`${s.school_name}-${i}`} className="glass rounded-xl p-3 text-sm">
                      <div className="flex items-start justify-between gap-2 flex-wrap">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                              b.key === "冲" ? "bg-orange-500/20 text-orange-300"
                              : b.key === "稳" ? "bg-emerald-500/20 text-emerald-300"
                              : b.key === "保" ? "bg-sky-500/20 text-sky-300"
                              : b.key === "不推荐" ? "bg-red-700/30 text-red-200"
                              : "bg-amber-500/20 text-amber-300"
                            }`}>{s.bucket}</span>
                            <span className="font-bold truncate">{s.school_name}</span>
                            <span className="text-[10px] text-white/50">{s.major_group_code} · {s.major_group_name}</span>
                          </div>
                          {s.selected_majors && s.selected_majors.length > 0 && (
                            <div className="text-xs text-white/50 mt-0.5">组内专业：{s.selected_majors.join("、")}</div>
                          )}
                          {typeof s.plan_count === "number" && (
                            <div className="text-[11px] text-white/40 mt-0.5">2026河南计划 {s.plan_count} 人</div>
                          )}
                        </div>
                      </div>
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
                    </div>
                  ))}
                </div>
              </div>
            );
          })}

          {/* 覆盖报告 */}
          {result.coverage && (
            <div className="glass rounded-2xl p-4 text-xs text-white/45 space-y-1">
              <div className="font-bold text-white/60 mb-1">数据覆盖</div>
              {Object.entries((result.coverage.quality ?? {}) as Record<string, number>).map(([k, v]) => (
                <div key={k}>· {k}: {String(v)}</div>
              ))}
            </div>
          )}

          <div className="text-[11px] text-white/35 leading-relaxed px-1">
            冲稳保是产品辅助填报策略，非河南省教育考试院官方比例。录取风险仅供参考，正式填报以省考试院公布为准。
          </div>
        </div>
      )}
    </div>
  );
}
