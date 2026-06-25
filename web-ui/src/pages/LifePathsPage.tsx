import { useState } from "react";
import {
  Compass, Loader2, AlertCircle, TrendingUp, Wallet, Target,
  Shield, Scale, Rocket, ChevronDown, ChevronRight,
} from "lucide-react";
import { lifePaths, ApiError } from "../api/client";
import type { LifePathResult } from "../api/types";

const FOREIGN_LANGS = ["日语", "英语", "俄语", "德语", "法语", "西班牙语"];
const ENGLISH_LEVELS = [
  { value: "none", label: "几乎不会" },
  { value: "basic", label: "基础" },
  { value: "intermediate", label: "中等(四级)" },
  { value: "advanced", label: "高级(六级+)" },
];
const ELECTIVES = ["政治", "地理", "化学", "生物"];
const PATH_STYLE: Record<string, { color: string; icon: typeof Shield; bg: string }> = {
  稳健: { color: "text-emerald-300", icon: Shield, bg: "from-emerald-500/20 to-green-500/20 border-emerald-400/30" },
  均衡: { color: "text-amber-300", icon: Scale, bg: "from-amber-500/20 to-yellow-500/20 border-amber-400/30" },
  进取: { color: "text-rose-300", icon: Rocket, bg: "from-rose-500/20 to-red-500/20 border-rose-400/30" },
};
const fmt = (n: number) => n.toLocaleString();
const wan = (n: number) => (n >= 10000 ? `${(n / 10000).toFixed(1)}万` : fmt(n));

export default function LifePathsPage() {
  const [score, setScore] = useState(480);
  const [primary, setPrimary] = useState("历史");
  const [math, setMath] = useState(75);
  const [foreignLang, setForeignLang] = useState("日语");
  const [foreignScore, setForeignScore] = useState(120);
  const [engLevel, setEngLevel] = useState("basic");
  const [electives, setElectives] = useState<string[]>(["政治", "地理"]);
  const [income, setIncome] = useState(80000);
  const [savings, setSavings] = useState(20000);
  const [annEdu, setAnnEdu] = useState(25000);
  const [result, setResult] = useState<LifePathResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedPath, setExpandedPath] = useState<number | null>(null);

  function toggleElect(s: string) {
    setElectives((p) => p.includes(s) ? p.filter(x => x !== s) : p.length < 2 ? [...p, s] : p);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setError(null);
    try {
      const r = await lifePaths({
        total_score: score, primary_subject: primary, math_score: math,
        exam_foreign_language: foreignLang, foreign_language_score: foreignScore,
        english_actual_level: engLevel, elective_subjects: electives,
        family_annual_income: income, family_savings: savings, max_annual_education_budget: annEdu,
      });
      setResult(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "请求失败，请确认后端已启动");
      setResult(null);
    } finally { setLoading(false); }
  }

  return (
    <div className="space-y-6">
      <div className="text-center py-4">
        <h1 className="text-3xl sm:text-4xl font-extrabold">
          <span className="bg-gradient-to-r from-emerald-400 via-amber-400 to-rose-400 bg-clip-text text-transparent">
            三条人生路径
          </span>
        </h1>
        <p className="text-white/50 text-sm mt-2">资格链 → 录取预测 → 就业市场 → 家庭预算 → 稳健/均衡/进取</p>
      </div>

      {/* 输入表单 */}
      <form onSubmit={handleSubmit} className="glass rounded-3xl p-6 shadow-xl space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <label className="block">
            <span className="text-xs text-white/60 mb-1 block">高考总分</span>
            <input type="number" value={score} onChange={e => setScore(+e.target.value)}
              className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2 text-sm" />
          </label>
          <label className="block">
            <span className="text-xs text-white/60 mb-1 block">首选科目</span>
            <select value={primary} onChange={e => setPrimary(e.target.value)}
              className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2 text-sm">
              <option className="bg-slate-800">历史</option>
              <option className="bg-slate-800">物理</option>
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-white/60 mb-1 block">数学</span>
            <input type="number" value={math} onChange={e => setMath(+e.target.value)}
              className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2 text-sm" />
          </label>
          <label className="block">
            <span className="text-xs text-white/60 mb-1 block">外语语种</span>
            <select value={foreignLang} onChange={e => setForeignLang(e.target.value)}
              className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2 text-sm">
              {FOREIGN_LANGS.map(l => <option key={l} className="bg-slate-800">{l}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-white/60 mb-1 block">外语分数</span>
            <input type="number" value={foreignScore} onChange={e => setForeignScore(+e.target.value)}
              className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2 text-sm" />
          </label>
          <label className="block">
            <span className="text-xs text-white/60 mb-1 block">实际英语能力</span>
            <select value={engLevel} onChange={e => setEngLevel(e.target.value)}
              className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2 text-sm">
              {ENGLISH_LEVELS.map(l => <option key={l.value} value={l.value} className="bg-slate-800">{l.label}</option>)}
            </select>
          </label>
          <label className="block col-span-2">
            <span className="text-xs text-white/60 mb-1 block">家庭年收入</span>
            <input type="number" value={income} onChange={e => setIncome(+e.target.value)}
              className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2 text-sm" />
          </label>
        </div>

        {/* 再选科目 */}
        <div>
          <span className="text-xs text-white/60 mb-1.5 block">再选科目（选2门）</span>
          <div className="flex gap-1.5">
            {ELECTIVES.map(s => (
              <button key={s} type="button" onClick={() => toggleElect(s)}
                className={`px-3 py-1 rounded-lg text-xs ${electives.includes(s) ? "bg-emerald-500 text-white" : "bg-white/5 text-white/50"}`}>{s}</button>
            ))}
          </div>
        </div>

        {/* 家庭预算 */}
        <div className="grid grid-cols-2 gap-3 pt-2 border-t border-white/10">
          <label className="block">
            <span className="text-xs text-white/60 mb-1 block">可投入储蓄</span>
            <input type="number" value={savings} onChange={e => setSavings(+e.target.value)}
              className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2 text-sm" />
          </label>
          <label className="block">
            <span className="text-xs text-white/60 mb-1 block">每年教育预算</span>
            <input type="number" value={annEdu} onChange={e => setAnnEdu(+e.target.value)}
              className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2 text-sm" />
          </label>
        </div>

        <button type="submit" disabled={loading}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-emerald-500 via-amber-500 to-rose-500 font-bold disabled:opacity-50 flex items-center justify-center gap-2">
          {loading ? <><Loader2 className="w-4 h-4 animate-spin" />生成中</> : <><Compass className="w-4 h-4" />生成三条人生路径</>}
        </button>
      </form>

      {error && <div className="glass rounded-xl p-3 border border-red-400/30 text-red-200 text-sm flex gap-2"><AlertCircle className="w-4 h-4 shrink-0" />{error}</div>}

      {/* 三路径结果 */}
      {result && (
        <div className="space-y-4 animate-slide-up">
          {result.paths.map((path, i) => {
            const st = PATH_STYLE[path.path_type] || PATH_STYLE["均衡"];
            const Icon = st.icon;
            const expanded = expandedPath === i;
            const buckets = path.school_buckets;
            const totalSchools = buckets.reach.length + buckets.match.length + buckets.safe.length;
            return (
              <div key={i} className={`glass rounded-2xl p-5 border bg-gradient-to-br ${st.bg}`}>
                <div className="flex items-center gap-3 cursor-pointer" onClick={() => setExpandedPath(expanded ? null : i)}>
                  {expanded ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
                  <Icon className={`w-6 h-6 ${st.color}`} />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-bold text-lg">{path.path_type}路径</h3>
                      <span className={`text-xs px-2 py-0.5 rounded ${st.color} bg-white/10`}>{path.major_direction}</span>
                      <span className="text-xs text-white/40">风险: {path.risk_level}</span>
                    </div>
                    <p className="text-xs text-white/50 mt-0.5">{path.summary || `${path.major_direction}方向，${totalSchools}所学校可选`}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold">{wan(path.university_cost_4y)}</div>
                    <div className="text-[10px] text-white/40">4年费用·压力{path.pressure_coefficient}</div>
                  </div>
                </div>

                {/* 路径详情 */}
                <div className="grid grid-cols-3 gap-2 mt-3">
                  <div className="bg-white/5 rounded-lg p-2">
                    <div className="text-[10px] text-white/50 flex items-center gap-1"><Wallet className="w-3 h-3" />起薪中位</div>
                    <div className="text-sm font-bold">¥{fmt(path.expected_start_salary_p50)}</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-2">
                    <div className="text-[10px] text-white/50 flex items-center gap-1"><TrendingUp className="w-3 h-3" />专业价值</div>
                    <div className="text-sm font-bold">{(path.major_value_score * 100).toFixed(0)}%</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-2">
                    <div className="text-[10px] text-white/50 flex items-center gap-1"><Target className="w-3 h-3" />综合分</div>
                    <div className="text-sm font-bold">{(path.overall_score * 100).toFixed(0)}%</div>
                  </div>
                </div>

                {/* 目标职业 */}
                {path.target_careers.length > 0 && (
                  <div className="mt-2 flex gap-1 flex-wrap">
                    {path.target_careers.map(c => <span key={c} className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-white/60">{c}</span>)}
                  </div>
                )}

                {/* 展开：冲稳保学校 */}
                {expanded && totalSchools > 0 && (
                  <div className="mt-4 pt-3 border-t border-white/10 space-y-3">
                    {[
                      { label: "冲", items: buckets.reach, color: "text-orange-300" },
                      { label: "稳", items: buckets.match, color: "text-emerald-300" },
                      { label: "保", items: buckets.safe, color: "text-sky-300" },
                    ].map(b => b.items.length > 0 && (
                      <div key={b.label}>
                        <div className={`text-xs font-bold ${b.color} mb-1`}>{b.label}（{b.items.length}）</div>
                        {b.items.map((s, j) => (
                          <div key={j} className="bg-white/5 rounded-lg px-3 py-2 mb-1.5 text-sm">
                            <div className="flex items-center justify-between">
                              <div>
                                <span className="font-medium">{s.school}</span>
                                <span className="text-xs text-white/40 ml-2">{s.matched_major}</span>
                                <span className={`text-[10px] ml-2 px-1.5 py-0.5 rounded ${s.ownership === "民办" ? "bg-orange-500/20 text-orange-300" : "bg-emerald-500/20 text-emerald-300"}`}>{s.ownership}</span>
                              </div>
                              <div className="text-right text-xs">
                                <div>{wan(s.total_cost_4y)}</div>
                                <div className={s.affordability_status === "超预算" ? "text-red-300" : "text-white/40"}>{s.affordability_status}</div>
                              </div>
                            </div>
                            {s.warnings && s.warnings.length > 0 && (
                              <div className="mt-1.5 space-y-0.5">
                                {s.warnings.map((w, k) => (
                                  <div key={k} className={`text-[10px] leading-tight ${
                                    w.startsWith("⚠") ? "text-amber-300/80" : w.startsWith("✓") ? "text-emerald-300/70" : "text-white/40"
                                  }`}>{w}</div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}

          {/* 系统说明 */}
          {result.notes.length > 0 && (
            <div className="glass rounded-xl p-3 text-xs text-white/40 space-y-1">
              {result.notes.map((n, i) => <div key={i}>· {n}</div>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
