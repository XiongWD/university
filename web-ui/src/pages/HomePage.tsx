import { useState } from "react";
import { AlertCircle, Rocket, ShieldCheck, Anchor } from "lucide-react";
import ScoreForm from "../components/ScoreForm";
import { advisory, ApiError } from "../api/client";
import type { AdvisoryRequest, VolunteerAdvisoryResult } from "../api/types";

const BUCKETS = [
  { key: "reach" as const, label: "冲", icon: Rocket, color: "text-orange-300", desc: "有希望但冒险" },
  { key: "match" as const, label: "稳", icon: ShieldCheck, color: "text-emerald-300", desc: "匹配度最高" },
  { key: "safe" as const, label: "保", icon: Anchor, color: "text-sky-300", desc: "稳妥兜底" },
];

export default function HomePage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VolunteerAdvisoryResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(req: AdvisoryRequest) {
    setLoading(true);
    setError(null);
    try {
      const response = await advisory(req);
      setResult(response);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "请求失败，请确认后端服务已启动");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const total = result
    ? result.school_options.reach.length + result.school_options.match.length + result.school_options.safe.length
    : 0;

  return (
    <div className="space-y-6">
      {/* Hero */}
      {!result && (
        <div className="text-center py-6 animate-fade-in">
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight">
            <span className="bg-gradient-to-r from-pink-400 via-fuchsia-400 to-indigo-400 bg-clip-text text-transparent">
              高考志愿专业推荐
            </span>
          </h1>
          <p className="text-white/60 mt-3 text-sm sm:text-base">
            输入分数 → 冲稳保志愿 → 大学花费 · 毕业起薪，一目了然
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
        <div className="animate-slide-up">
          {/* 考生摘要 */}
          <div className="glass rounded-3xl p-6 mb-6 shadow-xl">
            <div className="flex flex-wrap items-center justify-around gap-4 text-center">
              <div>
                <div className="text-3xl font-bold text-white">
                  {result.student_rank.toLocaleString()}
                </div>
                <div className="text-xs text-white/50 mt-1">全省位次</div>
              </div>
              <div className="w-px h-12 bg-white/10" />
              <div>
                <div className="text-xl font-bold text-white">{result.track}</div>
                <div className="text-xs text-white/50 mt-1">{result.province} · {result.data_year}年数据</div>
              </div>
              <div className="w-px h-12 bg-white/10" />
              <div>
                <div className="text-xl font-bold text-white">
                  ¥{result.budget_summary.total_4y.toLocaleString()}
                </div>
                <div className="text-xs text-white/50 mt-1">代表院校4年费用 · {result.budget_summary.affordability_status}</div>
              </div>
            </div>
          </div>

          {/* 专业方向建议 */}
          {result.major_directions.length > 0 && (
            <div className="mb-7">
              <h3 className="font-bold text-lg mb-3 px-1">专业方向建议</h3>
              <div className="space-y-2">
                {result.major_directions.slice(0, 5).map((d, i) => (
                  <div key={`${d.direction}-${i}`} className="glass rounded-2xl p-4">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <div className="font-bold text-base">{d.direction}</div>
                      <div className="flex items-center gap-3 text-xs text-white/60">
                        <span>综合匹配 <span className="text-emerald-300 font-mono">{(d.major_value * 100).toFixed(0)}%</span></span>
                        <span>市场 <span className="font-mono">{(d.market_value * 100).toFixed(0)}%</span></span>
                        <span>适配 <span className="font-mono">{(d.student_fit * 100).toFixed(0)}%</span></span>
                      </div>
                    </div>
                    {d.recommended_majors.length > 0 && (
                      <div className="text-xs text-white/50 mt-1">建议专业：{d.recommended_majors.join("、")}</div>
                    )}
                    {d.fit_explanation.length > 0 && (
                      <div className="text-[11px] text-white/40 mt-1.5 space-y-0.5">
                        {d.fit_explanation.map((x, j) => <div key={j}>· {x}</div>)}
                      </div>
                    )}
                    {d.risk_warnings.length > 0 && (
                      <div className="text-[11px] text-amber-300/80 mt-1 space-y-0.5">
                        {d.risk_warnings.map((w, j) => <div key={j}>⚠ {w}</div>)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 冲稳保院校清单 */}
          {total === 0 ? (
            <div className="glass rounded-3xl p-10 text-center text-white/50">
              该分数段暂无匹配院校数据，可尝试切换科类或调整分数。
            </div>
          ) : (
            <>
              {BUCKETS.map((b) => {
                const list = result.school_options[b.key];
                if (list.length === 0) return null;
                return (
                  <div key={b.key} className="mb-7">
                    <div className="flex items-center gap-2 mb-3 px-1">
                      <b.icon className={`w-5 h-5 ${b.color}`} />
                      <h3 className="font-bold text-lg">{b.label}</h3>
                      <span className="text-xs text-white/40">{b.desc}</span>
                      <span className="ml-auto text-xs text-white/40">{list.length} 所</span>
                    </div>
                    <div className="space-y-2">
                      {list.map((s, i) => (
                        <div key={`${s.school}-${i}`} className="glass rounded-xl p-3 text-sm">
                          <div className="flex items-start justify-between gap-2 flex-wrap">
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                  b.key === "reach" ? "bg-orange-500/20 text-orange-300"
                                  : b.key === "match" ? "bg-emerald-500/20 text-emerald-300"
                                  : "bg-sky-500/20 text-sky-300"
                                }`}>{s.admission_level}</span>
                                <span className="font-bold truncate">{s.school}</span>
                                <span className="text-[10px] text-white/50">{s.ownership}</span>
                              </div>
                              {s.matched_major && <div className="text-xs text-white/50 mt-0.5">{s.matched_major}</div>}
                            </div>
                            <div className="text-right text-xs shrink-0">
                              <div className="font-bold text-pink-200">¥{s.total_cost_4y.toLocaleString()}</div>
                              <div className={s.affordability_status === "超预算" ? "text-red-300" : "text-white/40"}>
                                {s.affordability_status} · {s.data_granularity}
                              </div>
                            </div>
                          </div>
                          {s.warnings.length > 0 && (
                            <div className="text-[10px] text-amber-300/70 mt-1.5 space-y-0.5">
                              {s.warnings.map((w, j) => <div key={j}>⚠ {w}</div>)}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </>
          )}

          {/* 资格限制说明 */}
          {result.ineligible_options.length > 0 && (
            <div className="mb-6">
              <h3 className="font-bold text-lg mb-3 px-1">资格限制说明</h3>
              <div className="glass rounded-2xl p-4 space-y-1.5">
                {result.ineligible_options.slice(0, 8).map((r, i) => (
                  <div key={`${r.school}-${i}`} className="text-xs">
                    <span className="text-white/70">{r.school}{r.major_group_name ? `（${r.major_group_name}）` : ""}</span>
                    <span className="text-white/40">：{r.blocked_summary}</span>
                  </div>
                ))}
                {result.ineligible_options.length > 8 && (
                  <div className="text-[11px] text-white/40">还有 {result.ineligible_options.length - 8} 条资格限制未展开</div>
                )}
              </div>
            </div>
          )}

          {/* 数据说明 */}
          <div className="glass rounded-2xl p-4 text-xs text-white/50 leading-relaxed space-y-1">
            {result.notes.map((n, i) => <div key={i}>· {n}</div>)}
          </div>
        </div>
      )}
    </div>
  );
}
