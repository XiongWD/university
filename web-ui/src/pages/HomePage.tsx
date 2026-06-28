import { useEffect, useState } from "react";
import { AlertCircle, Rocket, ShieldCheck, Anchor, HelpCircle, Calculator, MapPin, Wallet } from "lucide-react";
import ScoreForm from "../components/ScoreForm";
import { henanRecommendation, ApiError } from "../api/client";
import type { AdvisoryRequest, HenanRecommendationResult, HenanTargetItem } from "../api/types";

// 5 档 bucket 渲染配置（design D2，去掉"中"，新增需人工复核）
const BUCKETS = [
  { key: "冲" as const, label: "冲", icon: Rocket, color: "text-orange-300", desc: "有希望但冒险" },
  { key: "稳" as const, label: "稳", icon: ShieldCheck, color: "text-emerald-300", desc: "匹配度较高" },
  { key: "保" as const, label: "保", icon: Anchor, color: "text-sky-300", desc: "稳妥兜底" },
  { key: "不推荐" as const, label: "不推荐", icon: AlertCircle, color: "text-red-300", desc: "资格不符或位次差距过大" },
  { key: "需人工复核" as const, label: "需人工复核", icon: HelpCircle, color: "text-amber-300", desc: "数据待核验" },
];

type StatFilter = "local" | "nonLocal" | "public" | "private" | "joint" | "langWarning";

const STAT_FILTERS: { key: StatFilter; label: string; group: "location" | "ownership" | "risk" }[] = [
  { key: "local", label: "省内", group: "location" },
  { key: "nonLocal", label: "省外", group: "location" },
  { key: "public", label: "公办", group: "ownership" },
  { key: "private", label: "民办", group: "ownership" },
  { key: "joint", label: "中外", group: "ownership" },
  { key: "langWarning", label: "日语风险", group: "risk" },
];

// 费用格式化（元 → 千/万可读）
function fmtMoney(v?: number | null): string {
  if (v === undefined || v === null) return "—";
  if (v >= 10000) return `${(v / 10000).toFixed(v % 10000 === 0 ? 0 : 1)}万`;
  return `${v}`;
}

function fmtRank(v?: number | null): string {
  return typeof v === "number" && v > 0 ? v.toLocaleString("zh-CN") : "—";
}

function fmtBaselineGranularity(v?: string | null): string {
  if (!v) return "";
  if (v === "major") return "专业";
  if (v === "major_group") return "专业组";
  if (v === "major_group_trend") return "专业组趋势";
  if (v === "school") return "学校";
  if (v === "school_inferred") return "同校推断";
  return v;
}

function buildStats(items: HenanTargetItem[]) {
  const count = items.length;
  const local = items.filter((s) => s.is_henan_local).length;
  const publicCount = items.filter((s) => s.school_ownership === "公办").length;
  const privateCount = items.filter((s) => s.school_ownership === "民办").length;
  const jointCount = items.filter((s) => s.school_ownership === "中外合作").length;
  const langWarning = items.filter((s) => s.language_restriction?.level === "soft_warning").length;
  return {
    count,
    local,
    publicCount,
    privateCount,
    jointCount,
    langWarning,
  };
}

function filterStatItems(items: HenanTargetItem[], filters: StatFilter[]) {
  return items.filter((s) => {
    if (filters.includes("local") && !s.is_henan_local) return false;
    if (filters.includes("nonLocal") && s.is_henan_local) return false;
    if (filters.includes("public") && s.school_ownership !== "公办") return false;
    if (filters.includes("private") && s.school_ownership !== "民办") return false;
    if (filters.includes("joint") && s.school_ownership !== "中外合作") return false;
    if (filters.includes("langWarning") && s.language_restriction?.level !== "soft_warning") return false;
    return true;
  });
}

function toggleStatFilter(filters: StatFilter[], next: StatFilter): StatFilter[] {
  const def = STAT_FILTERS.find((f) => f.key === next);
  if (!def) return filters;
  if (filters.includes(next)) {
    return filters.filter((f) => f !== next);
  }
  const withoutSameGroup = filters.filter((f) => {
    const existing = STAT_FILTERS.find((item) => item.key === f);
    return !existing || existing.group !== def.group;
  });
  return [...withoutSameGroup, next];
}

function filterTitle(filters: StatFilter[]) {
  if (filters.length === 0) return "当前可见全部";
  return filters
    .map((key) => STAT_FILTERS.find((f) => f.key === key)?.label ?? key)
    .join(" + ");
}

// 学校性质徽章色
const OWNERSHIP_STYLE: Record<string, string> = {
  公办: "bg-sky-500/20 text-sky-300",
  民办: "bg-amber-500/20 text-amber-300",
  中外合作: "bg-fuchsia-500/20 text-fuchsia-300",
  独立学院: "bg-purple-500/20 text-purple-300",
};

// 学校卡片：费用 + 学校性质 + 冲稳保计算链（问题2/3/4）
function SchoolCard({ s, bucketKey, index, showCalc }: {
  s: HenanTargetItem;
  bucketKey: string;
  index: number;
  showCalc?: boolean;
}) {
  const [calcOpen, setCalcOpen] = useState(false);
  const ownership = s.school_ownership || "";
  const detail = s.bucket_detail;
  return (
    <div key={`${s.school_name}-${index}`} className="glass rounded-xl p-3 text-sm">
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div className="w-9 h-9 rounded-lg bg-white/10 text-white/70 font-mono text-sm tabular-nums flex items-center justify-center shrink-0">
          #{index + 1}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
              bucketKey === "冲" ? "bg-orange-500/20 text-orange-300"
              : bucketKey === "稳" ? "bg-emerald-500/20 text-emerald-300"
              : bucketKey === "保" ? "bg-sky-500/20 text-sky-300"
              : "bg-amber-500/20 text-amber-300"
            }`}>{s.bucket}</span>
            {/* 投档成功率徽章（problem1）：可达档位才显示 */}
            {typeof s.admission_probability === "number" && s.admission_probability > 0 && (
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                s.admission_probability >= 0.9 ? "bg-sky-500/20 text-sky-300"
                : s.admission_probability >= 0.6 ? "bg-emerald-500/20 text-emerald-300"
                : s.admission_probability >= 0.4 ? "bg-amber-500/20 text-amber-300"
                : "bg-orange-500/20 text-orange-300"
              }`}>成功率 {Math.round(s.admission_probability * 100)}%</span>
            )}
            <span className="font-bold truncate">{s.school_name}</span>
            <span className="text-[10px] text-white/50">{s.major_group_code} · {s.major_group_name}</span>
          </div>
          {/* 学校性质（问题4）：公办/民办/中外 + 省内/省外 + 985/211 */}
          <div className="flex items-center gap-1.5 flex-wrap mt-1">
            {ownership && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${OWNERSHIP_STYLE[ownership] ?? "bg-white/10 text-white/60"}`}>{ownership}</span>
            )}
            <span className="text-[10px] text-white/45 flex items-center gap-0.5">
              <MapPin className="w-2.5 h-2.5" />
              {s.is_henan_local ? "省内" : "省外"}{s.school_province ? `·${s.school_province}` : ""}{s.school_city ? ` ${s.school_city}` : ""}
            </span>
            {(s.school_tags ?? []).map((t) => (
              <span key={t} className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-300">{t}</span>
            ))}
            {/* 语种限制标签（日语考生场景）：hard_blocked 不可录取 / soft_warning 英语适应风险 */}
            {s.language_restriction && s.language_restriction.level === "hard_blocked" && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-300" title={s.language_restriction.note}>
                英语限·不可录取
              </span>
            )}
            {s.language_restriction && s.language_restriction.level === "soft_warning" && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300" title={s.language_restriction.note}>
                公共外语仅英语
              </span>
            )}
            {s.language_restriction && s.language_restriction.level === "missing_data" && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-white/55" title={s.language_restriction.note}>
                语种数据缺失
              </span>
            )}
          </div>
          {s.selected_majors && s.selected_majors.length > 0 && (
            <div className="text-xs text-white/50 mt-0.5">组内专业：{s.selected_majors.join("、")}</div>
          )}
          {/* 费用（问题3）：学费/住宿费/生活费 + 4年合计 */}
          <div className="text-[11px] text-white/55 mt-1 flex items-center gap-1 flex-wrap">
            <Wallet className="w-3 h-3 text-emerald-300/70" />
            <span>学费 {fmtMoney(s.tuition)}/年</span>
            <span className="text-white/25">·</span>
            <span>住宿 {fmtMoney(s.accommodation)}/年{s.accommodation_is_estimate ? <span className="text-white/30">（估）</span> : null}</span>
            <span className="text-white/25">·</span>
            <span>生活费 {fmtMoney(s.living_cost_per_year)}/年</span>
            <span className="text-white/25">·</span>
            <span className="text-amber-300/80">{s.school_system_years ?? 4}年合计 ≈ {fmtMoney(s.four_year_total)}元</span>
          </div>
          {typeof s.plan_count === "number" && (
            <div className="text-[11px] text-white/40 mt-0.5">2026河南计划 {s.plan_count} 人</div>
          )}
          {detail && (
            <div className="text-[11px] text-white/45 mt-0.5 flex flex-wrap gap-1.5 tabular-nums">
              <span>考生位次 {fmtRank(detail.student_rank)}</span>
              <span className="text-white/25">·</span>
              <span>
                {detail.baseline_year ? `${detail.baseline_year}年录取位次` : "去年录取位次"} {fmtRank(detail.adjusted_min_rank)}
              </span>
            </div>
          )}
        </div>
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
              <div>考生位次 <b className="text-white/70">{detail.student_rank ?? "—"}</b> − 参考位次 <b className="text-white/70">{detail.adjusted_min_rank ?? "—"}</b>
                {detail.baseline_year ? `（${detail.baseline_year}年${fmtBaselineGranularity(detail.baseline_granularity)}）` : ""}</div>
              <div>位次差比 = <b className={bucketKey === "冲" ? "text-orange-300" : bucketKey === "稳" ? "text-emerald-300" : "text-sky-300"}>
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

export default function HomePage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<HenanRecommendationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [displayBucket, setDisplayBucket] = useState<"全部" | "冲" | "稳" | "保">("全部");
  // design D1：不推荐院校默认折叠，避免硬塞用户未关注的不可达院校
  const [showRejected, setShowRejected] = useState(false);
  const [showAlgorithm, setShowAlgorithm] = useState(false);
  const [statFilters, setStatFilters] = useState<StatFilter[] | null>(null);
  const [statPage, setStatPage] = useState(0);

  useEffect(() => {
    if (!result || displayBucket === "全部") return;
    window.requestAnimationFrame(() => {
      document.getElementById(`bucket-${displayBucket}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [result, displayBucket]);

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
        track: "历史类",
        source_province: "河南",
        primary_subject: "历史",
        elective_subjects: req.elective_subjects,
        exam_foreign_language: req.exam_foreign_language || "英语",
        subject_scores_detail: {
          数学: req.math_score ?? 0,
          外语: req.foreign_language_score ?? 0,
        },
        strategy: strategyMap[req.display_bucket ?? "全部"] ?? "自动",
        sort_mode: req.sort_mode ?? "rank",
        prefer_local: req.prefer_local ?? false,
        prefer_public: req.prefer_public ?? false,
        interest_majors: req.interest_majors ?? [],
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
  const visibleItems = result
    ? visibleBuckets
        .filter((b) => b.key !== "不推荐")
        .flatMap((b) => result.buckets[b.key] ?? [])
    : [];
  const visibleStats = buildStats(visibleItems);
  const rankedVisibleItems = visibleItems.map((item, index) => ({ item, rank: index + 1 }));
  const statFilteredItems = statFilters === null
    ? []
    : filterStatItems(visibleItems, statFilters).map((item) => ({
        item,
        rank: rankedVisibleItems.find((entry) => entry.item === item)?.rank ?? 0,
      }));
  const statPageSize = 20;
  const statPageCount = Math.max(1, Math.ceil(statFilteredItems.length / statPageSize));
  const statPageItems = statFilteredItems.slice(statPage * statPageSize, (statPage + 1) * statPageSize);
  function openStats(filters: StatFilter[]) {
    setStatFilters(filters);
    setStatPage(0);
  }
  function toggleModalFilter(filter: StatFilter) {
    setStatFilters((current) => {
      const next = toggleStatFilter(current ?? [], filter);
      setStatPage(0);
      return next;
    });
  }

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
          <div className="fixed right-3 top-24 z-30 w-44 rounded-xl bg-slate-950/85 shadow-2xl shadow-black/30 ring-1 ring-white/10 backdrop-blur-md p-3 text-xs text-white/70">
            <div className="font-bold text-white/85 mb-2 flex items-center justify-between">
              <span>当前统计</span>
              <button type="button" onClick={() => openStats([])} className="font-mono tabular-nums text-white/55 hover:text-white">
                {visibleStats.count}
              </button>
            </div>
            <div className="grid grid-cols-2 gap-1.5 tabular-nums">
              <button type="button" onClick={() => openStats(["local"])} className="rounded-md bg-white/5 px-2 py-1 text-left hover:bg-white/10">省内 {visibleStats.local}</button>
              <button type="button" onClick={() => openStats(["nonLocal"])} className="rounded-md bg-white/5 px-2 py-1 text-left hover:bg-white/10">省外 {Math.max(0, visibleStats.count - visibleStats.local)}</button>
              <button type="button" onClick={() => openStats(["public"])} className="rounded-md bg-sky-500/10 px-2 py-1 text-left text-sky-200 hover:bg-sky-500/20">公办 {visibleStats.publicCount}</button>
              <button type="button" onClick={() => openStats(["private"])} className="rounded-md bg-amber-500/10 px-2 py-1 text-left text-amber-200 hover:bg-amber-500/20">民办 {visibleStats.privateCount}</button>
              <button type="button" onClick={() => openStats(["joint"])} className="rounded-md bg-fuchsia-500/10 px-2 py-1 text-left text-fuchsia-200 hover:bg-fuchsia-500/20">中外 {visibleStats.jointCount}</button>
              <button type="button" onClick={() => openStats(["langWarning"])} className="rounded-md bg-orange-500/10 px-2 py-1 text-left text-orange-200 hover:bg-orange-500/20">日语风险 {visibleStats.langWarning}</button>
            </div>
          </div>

          {statFilters !== null && (
            <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="w-full max-w-5xl max-h-[82vh] rounded-2xl bg-slate-950 shadow-2xl ring-1 ring-white/10 overflow-hidden flex flex-col">
                <div className="p-4 border-b border-white/10">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-bold text-white">{filterTitle(statFilters)}</h3>
                      <p className="text-xs text-white/45 mt-0.5">
                        共 {statFilteredItems.length} 个，按当前页面排序列出；可组合筛选条件。
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setStatFilters(null)}
                      className="min-w-10 h-10 rounded-lg bg-white/5 text-white/60 hover:bg-white/10 hover:text-white active:scale-[0.96] transition-transform"
                    >
                      ×
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2 mt-3">
                    {STAT_FILTERS.map((filter) => {
                      const active = statFilters.includes(filter.key);
                      return (
                        <button
                          key={filter.key}
                          type="button"
                          onClick={() => toggleModalFilter(filter.key)}
                          className={`min-h-10 px-3 rounded-lg text-xs font-bold transition-colors ${
                            active ? "bg-emerald-500 text-white" : "bg-white/5 text-white/55 hover:bg-white/10"
                          }`}
                        >
                          {filter.label}
                        </button>
                      );
                    })}
                    <button
                      type="button"
                      onClick={() => { setStatFilters([]); setStatPage(0); }}
                      className="min-h-10 px-3 rounded-lg text-xs font-bold bg-white/5 text-white/55 hover:bg-white/10"
                    >
                      清空
                    </button>
                  </div>
                </div>

                <div className="overflow-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="sticky top-0 bg-slate-950 text-white/45 border-b border-white/10">
                      <tr>
                        <th className="px-3 py-2 font-medium">排序</th>
                        <th className="px-3 py-2 font-medium">档位</th>
                        <th className="px-3 py-2 font-medium">学校</th>
                        <th className="px-3 py-2 font-medium">专业组</th>
                        <th className="px-3 py-2 font-medium">组内专业</th>
                        <th className="px-3 py-2 font-medium">属性</th>
                        <th className="px-3 py-2 font-medium">考生位次</th>
                        <th className="px-3 py-2 font-medium">去年录取位次</th>
                        <th className="px-3 py-2 font-medium">成功率</th>
                        <th className="px-3 py-2 font-medium">四年费用</th>
                        <th className="px-3 py-2 font-medium">日语</th>
                        <th className="px-3 py-2 font-medium">欠缺数据</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {statPageItems.map(({ item, rank }) => (
                        <tr key={`${item.school_name}-${item.major_group_code}-${rank}`} className="text-white/70">
                          <td className="px-3 py-2 font-mono tabular-nums text-white/45">#{rank}</td>
                          <td className="px-3 py-2">{item.bucket}</td>
                          <td className="px-3 py-2 font-bold text-white/85">{item.school_name}</td>
                          <td className="px-3 py-2 text-white/55">{item.major_group_code} · {item.major_group_name}</td>
                          <td className="px-3 py-2 max-w-xs text-white/55">{item.selected_majors?.join("、") || "—"}</td>
                          <td className="px-3 py-2 text-white/55">{item.is_henan_local ? "省内" : "省外"} · {item.school_ownership || "—"}</td>
                          <td className="px-3 py-2 tabular-nums">{fmtRank(item.bucket_detail?.student_rank)}</td>
                          <td className="px-3 py-2 tabular-nums">
                            {fmtRank(item.bucket_detail?.adjusted_min_rank)}
                            {item.bucket_detail?.baseline_year ? <span className="text-white/35 ml-1">({item.bucket_detail.baseline_year})</span> : null}
                          </td>
                          <td className="px-3 py-2 tabular-nums">{typeof item.admission_probability === "number" && item.admission_probability > 0 ? `${Math.round(item.admission_probability * 100)}%` : "—"}</td>
                          <td className="px-3 py-2 tabular-nums">{fmtMoney(item.four_year_total)}</td>
                          <td className="px-3 py-2">
                            {item.language_restriction?.level === "soft_warning"
                              ? "风险"
                              : item.language_restriction?.level === "missing_data"
                                ? "未知"
                                : "—"}
                          </td>
                          <td className="px-3 py-2 max-w-sm text-white/50">{item.missing_data_items?.join("；") || "—"}</td>
                        </tr>
                      ))}
                      {statPageItems.length === 0 && (
                        <tr>
                          <td colSpan={12} className="px-3 py-8 text-center text-white/45">没有符合当前复合条件的院校专业组</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="p-3 border-t border-white/10 flex items-center justify-between text-xs text-white/55">
                  <span className="tabular-nums">第 {statPage + 1} / {statPageCount} 页，每页 {statPageSize} 条</span>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={statPage === 0}
                      onClick={() => setStatPage((p) => Math.max(0, p - 1))}
                      className="min-h-10 px-3 rounded-lg bg-white/5 disabled:opacity-35 hover:bg-white/10"
                    >
                      上一页
                    </button>
                    <button
                      type="button"
                      disabled={statPage >= statPageCount - 1}
                      onClick={() => setStatPage((p) => Math.min(statPageCount - 1, p + 1))}
                      className="min-h-10 px-3 rounded-lg bg-white/5 disabled:opacity-35 hover:bg-white/10"
                    >
                      下一页
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 数据就绪状态 banner */}
          {(!result.production_ready || result.readiness_errors.length > 0 || (result.coverage_notes?.length ?? 0) > 0) && (
            <div className="glass rounded-2xl p-4 border border-amber-400/30 flex items-start gap-2 text-sm text-amber-200">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <div>
                <p className="font-medium">
                  {result.production_ready ? "推荐数据存在额外风险提示" : "推荐数据未完全就绪"}
                </p>
                <p className="text-amber-200/70 text-xs mt-0.5">
                  {result.readiness_errors.join("；") || "部分数据待核验，冲稳保结果仅供参考"}
                </p>
                {(result.coverage_notes?.length ?? 0) > 0 && (
                  <div className="text-amber-200/60 text-[11px] mt-1 space-y-0.5">
                    {result.coverage_notes.map((note, index) => <div key={index}>• {note}</div>)}
                  </div>
                )}
                <p className="text-amber-200/50 text-[11px] mt-1">
                  以下结果中「需人工复核」档位表示数据不足，不作可信推荐依据。
                </p>
              </div>
            </div>
          )}

          {/* 语种限制提示（日语考生场景）：顶部明确标注英语限制概况 */}
          {result.language_restriction_summary && (() => {
            const ls = result.language_restriction_summary;
            return (
              <div className="glass rounded-2xl p-4 border border-fuchsia-400/30 flex items-start gap-2 text-sm text-fuchsia-200">
                <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">⚠ {ls.exam_foreign_language}考生 · 语种提示</p>
                  <p className="text-fuchsia-200/80 text-xs mt-1 leading-relaxed">{ls.note}</p>
                  <div className="text-[11px] mt-1.5 flex flex-wrap gap-3">
                    <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-300">不可录取 {ls.hard_blocked_count} 个（要求英语，已置「不推荐」）</span>
                    <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">可录取但英语适应风险 {ls.soft_warning_count} 个</span>
                    <span className="px-1.5 py-0.5 rounded bg-white/10 text-white/60">语种数据缺失 {ls.missing_data_count} 个</span>
                  </div>
                  {ls.reachable_same_language_major_group_count === 0 && (
                    <div className="text-[11px] mt-1.5 text-white/70">
                      当前分数条件下未检出可达的{ls.exam_foreign_language}专业组；全量数据中检出 {ls.same_language_major_group_count} 个同语种专业组。
                    </div>
                  )}
                </div>
              </div>
            );
          })()}

          {/* 档位筛选提示 */}
          <div className="text-xs text-white/40 px-1">
            共 {Object.values(result.buckets).reduce((s, l) => s + l.length, 0)} 个院校专业组候选 ·
            当前显示「{displayBucket}」档位
          </div>

          {/* 可达 buckets（冲/稳/保/需人工复核）：始终展示。选档位时锚定到对应区 */}
          {visibleBuckets.filter((b) => b.key !== "不推荐").map((b) => {
            const list = result.buckets[b.key] ?? [];
            if (list.length === 0 && displayBucket === "全部") return null;
            return (
              <div key={b.key} id={`bucket-${b.key}`} className="mb-6 scroll-mt-4">
                <div className="flex items-center gap-2 mb-3 px-1">
                  <b.icon className={`w-5 h-5 ${b.color}`} />
                  <h3 className="font-bold text-lg">{b.label}</h3>
                  <span className="text-xs text-white/40">{b.desc}</span>
                  <span className="ml-auto text-xs text-white/40">{list.length} 个专业组</span>
                </div>
                {list.length > 0 ? (
                  <div className="space-y-2">
                    {list.map((s, i) => (
                      <SchoolCard key={`${s.school_name}-${i}`} s={s} bucketKey={b.key} index={i} showCalc />
                    ))}
                  </div>
                ) : (
                  <div className="glass rounded-xl p-4 text-sm text-white/45">
                    当前条件下暂无「{b.label}」档候选，可切换到“全部”查看其它档位。
                  </div>
                )}
              </div>
            );
          })}

          {/* 不推荐院校：默认折叠（design D1），避免硬塞用户未关注的不可达院校 */}
          {(() => {
            const rejected = result.buckets["不推荐"] ?? [];
            if (rejected.length === 0) return null;
            return (
              <div className="mb-6">
                <button
                  type="button"
                  onClick={() => setShowRejected((v) => !v)}
                  className="flex items-center gap-2 mb-3 px-1 text-sm text-white/50 hover:text-white/70 transition"
                >
                  <AlertCircle className="w-4 h-4 text-red-300/70" />
                  <span>{showRejected ? "收起" : "查看"}不可达院校（不推荐）</span>
                  <span className="text-xs text-white/35">{rejected.length} 个 · 资格不符或位次差距过大</span>
                </button>
                {showRejected && (
                  <div className="space-y-2">
                    {rejected.map((s, i) => (
                      <SchoolCard key={`${s.school_name}-${i}`} s={s} bucketKey="不推荐" index={i} showCalc />
                    ))}
                  </div>
                )}
              </div>
            );
          })()}

          {/* 48 志愿草案（问题1）：策略感知的配额与排序，选档位即生成对应策略志愿表 */}
          {result.volunteer_table && result.volunteer_table.items.length > 0 && (() => {
            const vt = result.volunteer_table;
            const stratLabel: Record<string, string> = { 自动: "自动（均衡）", 积极: "积极（多冲）", 保守: "保守（多保）", 均衡: "均衡" };
            return (
              <div className="mb-6">
                <div className="flex items-center gap-2 mb-1 px-1">
                  <Rocket className="w-5 h-5 text-pink-300" />
                  <h3 className="font-bold text-lg">48 志愿草案</h3>
                  <span className="text-xs text-white/40">共 {vt.total} 个志愿 · {stratLabel[vt.strategy_used] ?? vt.strategy_used} · 排序：{vt.sort_mode === "probability" ? "成功率优先" : "位次匹配度"}{vt.prefer_local ? " · 省内优先" : ""}{vt.prefer_public ? " · 公办优先" : ""}</span>
                </div>
                <div className="text-[11px] text-white/45 px-1 mb-2 flex flex-wrap gap-2">
                  {(["冲", "稳", "保"] as const).map((bk) => (
                    <span key={bk} className={`px-1.5 py-0.5 rounded ${
                      bk === "冲" ? "bg-orange-500/15 text-orange-300"
                      : bk === "稳" ? "bg-emerald-500/15 text-emerald-300"
                      : "bg-sky-500/15 text-sky-300"
                    }`}>
                      {bk}：{vt.used[bk]}/{vt.quota[bk][1]}（配额 {vt.quota[bk][0]}-{vt.quota[bk][1]}）
                    </span>
                  ))}
                </div>
                <div className="space-y-1.5">
                  {vt.items.map((s, i) => (
                    <div key={`${s.school_name}-${i}`} className="glass rounded-lg p-2.5 text-xs flex items-center gap-2">
                      <span className="text-white/30 font-mono w-6 shrink-0">{i + 1}</span>
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        s.bucket === "冲" ? "bg-orange-500/20 text-orange-300"
                        : s.bucket === "稳" ? "bg-emerald-500/20 text-emerald-300"
                        : "bg-sky-500/20 text-sky-300"
                      }`}>{s.bucket}</span>
                      {typeof s.admission_probability === "number" && s.admission_probability > 0 && (
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                          s.admission_probability >= 0.9 ? "bg-sky-500/20 text-sky-300"
                          : s.admission_probability >= 0.6 ? "bg-emerald-500/20 text-emerald-300"
                          : s.admission_probability >= 0.4 ? "bg-amber-500/20 text-amber-300"
                          : "bg-orange-500/20 text-orange-300"
                        }`}>{Math.round(s.admission_probability * 100)}%</span>
                      )}
                      <span className="font-bold truncate">{s.school_name}</span>
                      <span className="text-[10px] text-white/40 truncate">{s.major_group_name}</span>
                      <span className="ml-auto text-[10px] text-white/35 shrink-0">{s.school_ownership} · {s.is_henan_local ? "省内" : "省外"} · 4年≈{fmtMoney(s.four_year_total)}</span>
                    </div>
                  ))}
                </div>
                <p className="text-[10px] text-white/30 mt-1.5 px-1">配额随档位选择策略变化：积极→多冲少保，保守→多保少冲，均衡→标准比例。非河南省教育考试院官方比例。</p>
              </div>
            );
          })()}

          {/* 冲稳保算法说明（问题2）：可折叠展示计算公式与阈值 */}
          <div className="mb-6">
            <button type="button" onClick={() => setShowAlgorithm((v) => !v)}
              className="flex items-center gap-2 mb-2 px-1 text-sm text-white/50 hover:text-white/70 transition">
              <Calculator className="w-4 h-4 text-emerald-300/70" />
              <span>{showAlgorithm ? "收起" : "查看"}冲稳保怎么算的</span>
            </button>
            {showAlgorithm && (
              <div className="glass rounded-2xl p-4 text-xs text-white/55 space-y-2">
                <div><b className="text-white/70">核心公式：</b>rank_gap_ratio = (考生位次 − 参考位次) / 参考位次</div>
                <div className="text-white/40">参考位次取该专业组 2025/2024 已核验的最低录取位次（adjusted_min_rank）。差比为正表示考生位次更靠后、风险更高。</div>
                <div className="bg-white/5 rounded-lg p-2 space-y-1">
                  <div className="flex items-center gap-2"><span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-300">冲</span> 位次差比 &gt; 3%（有希望但冒险）</div>
                  <div className="flex items-center gap-2"><span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">稳</span> 位次差比 ∈ [−10%, 3%]（匹配度较高）</div>
                  <div className="flex items-center gap-2"><span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300">保</span> 位次差比 &lt; −10%（且需 2025 verified 历史 + 置信度 ≥ 0.7）</div>
                  <div className="flex items-center gap-2"><span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-red-700/30 text-red-200">不推荐</span> 位次差比 &gt; 15% 或资格层未通过（选科/语种/单科/体检/专项）</div>
                </div>
                <div className="text-white/40">资格层先行：首选科目 → 再选科目 → 语种硬限 → 单科门槛 → 体检 → 专项资格，任一不通过直接「不推荐」，不进入位次风险层。</div>
                <div className="text-white/40">点击下方任意院校专业组卡片的「查看本组冲稳保计算」可看该组的实际位次差比计算链。</div>
              </div>
            )}
          </div>

          {/* 覆盖报告 */}
          {result.coverage && (
            <div className="glass rounded-2xl p-4 text-xs text-white/45 space-y-1">
              <div className="font-bold text-white/60 mb-1">数据覆盖</div>
              {(() => {
                const actual = (result.coverage.actual ?? {}) as Record<string, number>;
                const uniCount = actual.universities_2026 ?? 0;
                return (
                  <div className="text-amber-300/70 mb-1">
                    ⚠ 已覆盖 {uniCount} 所可追溯院校，河南全量（~1500所）待官方源导入后补齐
                  </div>
                );
              })()}
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
