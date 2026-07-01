/**
 * 评估报告页：13所志愿组 heao 评估 + 国贸/商务推荐 + 调整建议。
 *
 * 数据源：GET /my-volunteers/full-assessment（聚合 heao_assessment + biz_recommendations + recommendation_text）
 */
import { useEffect, useState } from "react";
import { ClipboardCheck, TrendingUp, Lightbulb, AlertTriangle, ListChecks } from "lucide-react";
import { getFullAssessment, type FullAssessment } from "../api/client";
import { useVolunteerStore } from "../store/volunteerStore";
import { TIER_STYLE } from "../components/volunteerTier";
import VolunteerSuggestion from "../components/VolunteerSuggestion";

const TIER_ORDER: Record<string, number> = { "超冲": 0, "搏": 1, "冲": 2, "稳": 3, "保": 4, "垫": 5 };

export default function AssessmentPage() {
  const [data, setData] = useState<FullAssessment | null>(null);
  const [loading, setLoading] = useState(true);
  const group = useVolunteerStore((s) => s.group);

  useEffect(() => {
    getFullAssessment()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-white/10 animate-pulse" />
          <div>
            <div className="h-7 w-32 bg-white/10 rounded animate-pulse mb-2" />
            <div className="h-4 w-64 bg-white/5 rounded animate-pulse" />
          </div>
        </div>
        <div className="glass rounded-2xl p-8 text-center">
          <div className="inline-block w-6 h-6 border-2 border-emerald-400/30 border-t-emerald-400 rounded-full animate-spin mb-3" />
          <div className="text-sm text-white/60">正在加载评估数据（首次约5秒，加载 heao 历年录取 + 学费 + 专业组）…</div>
        </div>
        {[1, 2, 3].map((i) => (
          <div key={i} className="glass rounded-2xl p-5 space-y-3">
            <div className="h-5 w-48 bg-white/10 rounded animate-pulse" />
            {[1, 2, 3].map((j) => (
              <div key={j} className="h-16 bg-white/5 rounded-lg animate-pulse" />
            ))}
          </div>
        ))}
      </div>
    );
  }
  if (!data) {
    return <div className="text-center text-rose-300 py-20">评估数据加载失败，请确认后端服务已启动</div>;
  }

  const items = group?.items ?? [];
  const assessment = data.heao_assessment;
  const bizRecs = data.biz_recommendations;

  // 志愿组评估：每校设定 tier vs heao 最优组实际 tier
  const evaluations = items.map((it) => {
    const key = it.school_name.split("(")[0];
    const schoolData = assessment[key];
    const schoolMeta = {
      ownership: schoolData?.ownership ?? "",
      province: schoolData?.province ?? "",
      city: schoolData?.city ?? "",
      tuition: schoolData?.tuition ?? null,
    };
    if (!schoolData?.groups?.length) {
      return { item: it, groups: [], best: null, planned: it.planned_tier ?? it.effective_tier, status: "no_data" as const, schoolMeta };
    }
    const groups = [...schoolData.groups].sort((a, b) => (b.advantage ?? -Infinity) - (a.advantage ?? -Infinity));
    const best = groups[0];
    const planned = it.planned_tier ?? it.effective_tier;
    let status: "match" | "conservative" | "optimistic" | "no_data" = "no_data";
    if (best) {
      if (planned === best.tier) status = "match";
      else if ((TIER_ORDER[best.tier] ?? 9) < (TIER_ORDER[planned] ?? 9)) status = "optimistic";
      else status = "conservative";
    }
    return { item: it, groups, best, planned, status, schoolMeta };
  });

  // 汇总统计
  const stats = {
    match: evaluations.filter((e) => e.status === "match").length,
    conservative: evaluations.filter((e) => e.status === "conservative").length,
    optimistic: evaluations.filter((e) => e.status === "optimistic").length,
    no_data: evaluations.filter((e) => e.status === "no_data").length,
  };

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-sky-500 flex items-center justify-center">
          <ClipboardCheck className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">评估报告</h1>
          <p className="text-sm text-white/50">
            考生 480分 / 位次73822 / 历史类 · heao 权威数据 · {new Date().toLocaleDateString("zh-CN")}
          </p>
        </div>
      </div>

      {/* 汇总卡 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <SummaryCard label="设定一致" value={stats.match} color="emerald" />
        <SummaryCard label="偏保守" value={stats.conservative} color="amber" />
        <SummaryCard label="偏乐观⚠" value={stats.optimistic} color="rose" />
        <SummaryCard label="国贸推荐" value={bizRecs.length} color="sky" />
      </div>

      {/* Part 1: 13所志愿组评估 */}
      <Section icon={<TrendingUp className="w-5 h-5" />} title="志愿组 heao 评估（13所）">
        <div className="space-y-2">
          {evaluations.map((e) => (
            <SchoolEvalCard key={e.item.id} evaluation={e} />
          ))}
        </div>
      </Section>

      {/* Part 2: 国贸/商务推荐 */}
      <Section icon={<Lightbulb className="w-5 h-5" />} title={`国贸/商务类专业组推荐（${bizRecs.length}个，heao验证）`}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-white/50 border-b border-white/10">
                <th className="text-left py-2 px-2">学校</th>
                <th className="text-center">性质</th>
                <th className="text-center">省</th>
                <th className="text-center">档</th>
                <th className="text-center">组</th>
                <th className="text-center">2025分</th>
                <th className="text-center">位次</th>
                <th className="text-center">差</th>
                <th className="text-center">学费</th>
                <th className="text-left px-2">国贸对口</th>
                <th className="text-center">专业明细</th>
              </tr>
            </thead>
            <tbody>
              {[...bizRecs]
                .sort((a, b) => {
                  const ta = TIER_ORDER[a.tier ?? ""] ?? 9;
                  const tb = TIER_ORDER[b.tier ?? ""] ?? 9;
                  if (ta !== tb) return ta - tb;
                  return (a.province === "河南" ? 0 : 1) - (b.province === "河南" ? 0 : 1);
                })
                .map((r, i) => (
                  <BizRow key={i} rec={r} />
                ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-200/80 leading-relaxed">
          <AlertTriangle className="w-4 h-4 inline mr-1" />
          公办本科弟弟能录的=0（212所含国贸公办 heao 全部查不到，录取位次远高于弟弟）。以上推荐全是民办/独立学院，但学费 1.1-2.6万，国贸直接对口。
        </div>
      </Section>

      {/* 最终志愿建议（可配置配额 + 可拖动 + 统计盘） */}
      <Section icon={<ListChecks className="w-5 h-5" />} title="最终志愿建议（冲稳保可配置 · 拖拽调整序号）">
        <VolunteerSuggestion brotherScore={480} brotherRank={73822} />
      </Section>

      {/* Part 3: 调整建议 */}
      {data.recommendation_text && (
        <Section icon={<ClipboardCheck className="w-5 h-5" />} title="志愿组调整建议">
          <div className="prose prose-invert max-w-none text-sm">
            <MarkdownRender text={data.recommendation_text} />
          </div>
        </Section>
      )}
    </div>
  );
}

/** 国贸推荐行（点击展开专业明细） */
function BizRow({ rec }: { rec: { school: string; zyzh: string; req: string; score: number; rank: number; gap: number; biz: string[]; majors?: string[]; ownership?: string; province?: string; tuition?: number; tier?: string } }) {
  const [expanded, setExpanded] = useState(false);
  const tier = rec.tier ?? (rec.gap < 2000 ? "冲" : rec.gap < 9000 ? "稳" : rec.gap < 18000 ? "保" : "垫");
  return (
    <>
      <tr className="border-b border-white/5 hover:bg-white/5 cursor-pointer" onClick={() => setExpanded((v) => !v)}>
        <td className="py-2 px-2 font-medium">{rec.school}</td>
        <td className="text-center text-white/50">{rec.ownership ?? "?"}</td>
        <td className="text-center text-white/50">{rec.province ?? "?"}</td>
        <td className="text-center">
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${TIER_STYLE[tier] ?? ""}`}>{tier}</span>
        </td>
        <td className="text-center text-white/50 font-mono">{rec.zyzh}</td>
        <td className="text-center">{rec.score}</td>
        <td className="text-center text-white/60 font-mono">{rec.rank.toLocaleString("zh-CN")}</td>
        <td className={`text-center font-mono ${rec.gap >= 0 ? "text-sky-300" : "text-orange-300"}`}>
          {rec.gap >= 0 ? "+" : ""}{rec.gap.toLocaleString("zh-CN")}
        </td>
        <td className="text-center text-white/50">{rec.tuition ? `${rec.tuition.toLocaleString()}` : "?"}</td>
        <td className="px-2 text-emerald-300/80">{rec.biz.slice(0, 2).join("、")}</td>
        <td className="text-center text-white/40 text-[10px]">{expanded ? "收起▲" : "展开▼"}</td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={11} className="px-4 py-2 bg-white/[0.03]">
            <div className="text-[10px] text-white/50 mb-1">组{rec.zyzh}（{rec.req || "不限"}）组内专业：</div>
            <div className="flex flex-wrap gap-1.5">
              {(rec.majors ?? []).map((m, j) => {
                const isBiz = rec.biz.some((b) => m.includes(b) || b.includes(m));
                return (
                  <span key={j} className={`text-[10px] px-1.5 py-0.5 rounded ${isBiz ? "bg-emerald-500/20 text-emerald-300" : "bg-white/5 text-white/50"}`}>
                    {m}
                  </span>
                );
              })}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function SummaryCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colors: Record<string, string> = {
    emerald: "from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 text-emerald-300",
    amber: "from-amber-500/20 to-amber-600/10 border-amber-500/30 text-amber-300",
    rose: "from-rose-500/20 to-rose-600/10 border-rose-500/30 text-rose-300",
    sky: "from-sky-500/20 to-sky-600/10 border-sky-500/30 text-sky-300",
  };
  return (
    <div className={`rounded-xl border bg-gradient-to-br p-4 ${colors[color]}`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-white/60 mt-0.5">{label}</div>
    </div>
  );
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="glass rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <div className="text-emerald-300">{icon}</div>
        <h2 className="text-lg font-bold">{title}</h2>
      </div>
      {children}
    </div>
  );
}

type Evaluation = {
  item: { id: number; school_name: string; planned_tier: string | null; effective_tier: string; major_group_code: string };
  groups: { zyzh: string; requirement: string; min_score_2025: number | null; min_rank_2025: number | null; equiv_score_2026: number | null; advantage: number | null; tier: string; majors?: { major_name: string; major_code: string }[] }[];
  best: { zyzh: string; tier: string; min_score_2025: number | null; min_rank_2025: number | null; advantage: number | null } | null;
  planned: string;
  status: "match" | "conservative" | "optimistic" | "no_data";
  schoolMeta: { ownership: string; province: string; city: string; tuition: number | null };
};

const OWNERSHIP_BADGE: Record<string, string> = {
  公办: "bg-sky-500/20 text-sky-300",
  民办: "bg-amber-500/20 text-amber-300",
  独立学院: "bg-purple-500/20 text-purple-300",
  中外合作办学: "bg-fuchsia-500/20 text-fuchsia-300",
};

function SchoolEvalCard({ evaluation }: { evaluation: Evaluation }) {
  const { item, groups, best, planned, status, schoolMeta } = evaluation;
  const [showDetail, setShowDetail] = useState<string | null>(null);
  const statusMap = {
    match: { icon: "✅", text: "设定一致", color: "text-emerald-300" },
    conservative: { icon: "⚠", text: "偏保守", color: "text-amber-300" },
    optimistic: { icon: "🔺", text: "偏乐观", color: "text-rose-300" },
    no_data: { icon: "❓", text: "无数据", color: "text-white/40" },
  };
  const s = statusMap[status];

  return (
    <div className="rounded-lg border border-white/10 p-3 bg-white/[0.02]">
      {/* 第一行：校名 + 性质/省/学费 + 设定状态 */}
      <div className="flex items-center justify-between mb-2 flex-wrap gap-1">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="font-medium text-sm">{item.school_name}</span>
          {schoolMeta.ownership && (
            <span className={`text-[9px] px-1 py-0.5 rounded ${OWNERSHIP_BADGE[schoolMeta.ownership] ?? "bg-white/10 text-white/50"}`}>
              {schoolMeta.ownership}
            </span>
          )}
          {schoolMeta.province && (
            <span className="text-[10px] text-white/40">{schoolMeta.province}{schoolMeta.city && `·${schoolMeta.city}`}</span>
          )}
          {schoolMeta.tuition && (
            <span className="text-[10px] text-white/50">学费{schoolMeta.tuition.toLocaleString("zh-CN")}/年</span>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-white/40">设定</span>
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${TIER_STYLE[planned] ?? ""}`}>{planned}</span>
          <span className={s.color}>{s.icon} {s.text}</span>
        </div>
      </div>

      {/* heao 最优组摘要 */}
      {best && (
        <div className="text-xs text-white/60 mb-2">
          heao最优组 {best.zyzh}：<span className={`font-bold px-1 rounded ${TIER_STYLE[best.tier] ?? ""}`}>{best.tier}</span>
          {" "}
          {best.min_score_2025 && <span>{best.min_score_2025}分</span>}
          {best.min_rank_2025 && <span className="text-white/40">/{best.min_rank_2025.toLocaleString("zh-CN")}位</span>}
          {best.advantage != null && (
            <span className={best.advantage >= 0 ? "text-sky-300" : "text-orange-300"}>
              {" "}差{best.advantage >= 0 ? "+" : ""}{best.advantage.toLocaleString("zh-CN")}
            </span>
          )}
        </div>
      )}

      {/* 各专业组标签（含代码） */}
      {groups.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1">
          {groups.map((g) => (
            <button
              key={g.zyzh}
              onClick={() => setShowDetail((v) => (v === g.zyzh ? null : g.zyzh))}
              className={`text-[9px] px-1.5 py-0.5 rounded transition ${TIER_STYLE[g.tier] ?? "bg-white/10"} ${showDetail === g.zyzh ? "ring-1 ring-white/40" : "opacity-80 hover:opacity-100"}`}
              title="点击展开专业明细"
            >
              {g.zyzh}组·{g.tier}{g.requirement && g.requirement !== "不限" ? `·${g.requirement}` : ""}
            </button>
          ))}
        </div>
      )}

      {/* 专业组明细（点击组标签展开） */}
      {showDetail && (() => {
        const g = groups.find((x) => x.zyzh === showDetail);
        if (!g) return null;
        return (
          <div className="mt-1.5 pt-1.5 border-t border-white/10 text-[10px] space-y-0.5">
            <div className="text-white/50 mb-1">
              组{g.zyzh}（{g.requirement || "不限"}）
              {g.min_score_2025 && ` · 2025最低${g.min_score_2025}分`}
              {g.min_rank_2025 && `/${g.min_rank_2025.toLocaleString("zh-CN")}位`}
              {g.equiv_score_2026 && ` · 2026等位分${g.equiv_score_2026}`}
            </div>
            {(g.majors ?? []).map((m) => (
              <div key={m.major_code} className="flex items-center gap-1.5 text-white/60">
                <span className="font-mono text-white/30 w-7">{m.major_code}</span>
                <span>{m.major_name}</span>
              </div>
            ))}
          </div>
        );
      })()}

      {status === "no_data" && <div className="text-xs text-white/30">heao 无该校评估数据</div>}
    </div>
  );
}

/** 极简 markdown 渲染（表格/标题/列表/段落） */
function MarkdownRender({ text }: { text: string }) {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    // 标题
    if (line.startsWith("### ")) {
      elements.push(<h3 key={key++} className="text-base font-bold mt-4 mb-2 text-emerald-300">{line.slice(4)}</h3>);
    } else if (line.startsWith("## ")) {
      elements.push(<h2 key={key++} className="text-lg font-bold mt-4 mb-2">{line.slice(3)}</h2>);
    } else if (line.startsWith("# ")) {
      elements.push(<h1 key={key++} className="text-xl font-bold mt-2 mb-3">{line.slice(2)}</h1>);
    }
    // 表格
    else if (line.startsWith("|") && i + 1 < lines.length && lines[i + 1].includes("---")) {
      const headers = line.split("|").map((s) => s.trim()).filter(Boolean);
      const rows: string[][] = [];
      i += 2; // 跳过表头和分隔行
      while (i < lines.length && lines[i].startsWith("|")) {
        rows.push(lines[i].split("|").map((s) => s.trim()).filter(Boolean));
        i++;
      }
      elements.push(
        <div key={key++} className="overflow-x-auto my-3">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr>{headers.map((h, j) => <th key={j} className="border border-white/10 px-2 py-1 text-left text-white/60 bg-white/5">{h}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri}>{r.map((c, ci) => <td key={ci} className="border border-white/10 px-2 py-1" dangerouslySetInnerHTML={{ __html: c.replace(/\*\*(.+?)\*\*/g, '<b class="text-white">$1</b>') }} />)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }
    // 引用块
    else if (line.startsWith("> ")) {
      elements.push(<blockquote key={key++} className="border-l-2 border-amber-400/50 pl-3 my-2 text-white/60 text-xs">{line.slice(2)}</blockquote>);
    }
    // 列表项
    else if (line.startsWith("- ") || /^\d+\./.test(line)) {
      elements.push(<div key={key++} className="ml-4 text-white/70 my-0.5" dangerouslySetInnerHTML={{ __html: "• " + line.replace(/^(- |\d+\.\s)/, "").replace(/\*\*(.+?)\*\*/g, '<b class="text-white">$1</b>') }} />);
    }
    // 空行
    else if (line.trim() === "") {
      elements.push(<div key={key++} className="h-2" />);
    }
    // 段落
    else {
      elements.push(<p key={key++} className="text-white/70 my-1" dangerouslySetInnerHTML={{ __html: line.replace(/\*\*(.+?)\*\*/g, '<b class="text-white">$1</b>') }} />);
    }
    i++;
  }

  return <>{elements}</>;
}
