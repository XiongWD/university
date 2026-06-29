import { useEffect, useState } from "react";
import { Target, AlertCircle, Loader2 } from "lucide-react";
import { evaluateHenanTarget, getHenanOptions, streamAiEvaluate, ApiError } from "../api/client";
import type { HenanOptions, HenanTargetEvaluationResult } from "../api/types";
import SchoolCombobox from "../components/SchoolCombobox";
import TargetSchoolCard from "../components/TargetSchoolCard";
import AIAnalysisPanel from "../components/AIAnalysisPanel";

// 与首页一致的外语语种与选科枚举
const FOREIGN_LANGS = ["英语", "日语", "俄语", "德语", "法语", "西班牙语"];
const ELECTIVES = ["物理", "化学", "生物", "政治", "历史", "地理"];

// 冲稳保垫档位配色（与首页一致）
const BUCKET_STYLE: Record<string, string> = {
  超冲: "bg-rose-500/20 text-rose-300",
  搏: "bg-orange-500/20 text-orange-300",
  冲: "bg-amber-500/20 text-amber-300",
  稳: "bg-emerald-500/20 text-emerald-300",
  保: "bg-sky-500/20 text-sky-300",
  垫: "bg-indigo-500/20 text-indigo-300",
  不推荐: "bg-red-700/30 text-red-200",
  可评估: "bg-white/15 text-white/80",
  "可评估（超冲）": "bg-rose-500/15 text-rose-200",
  "部分专业可评估": "bg-amber-500/20 text-amber-300",
};

function BucketBadge({ bucket }: { bucket: string }) {
  return (
    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${BUCKET_STYLE[bucket] ?? BUCKET_STYLE["可评估"]}`}>
      {bucket}
    </span>
  );
}

export default function TargetEvaluationPage() {
  const [loading, setLoading] = useState(false);
  const [optsLoading, setOptsLoading] = useState(true);
  const [result, setResult] = useState<HenanTargetEvaluationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [options, setOptions] = useState<HenanOptions | null>(null);

  // 考生信息（默认值与志愿推荐 ScoreForm 保持一致）
  const [score, setScore] = useState(480);
  const [rank, setRank] = useState<number | "">("");
  const [electives, setElectives] = useState<string[]>(["政治", "地理"]);
  const [foreignLang, setForeignLang] = useState("日语");
  const [foreignScore, setForeignScore] = useState(98);
  const [mathScore, setMathScore] = useState(64);
  const [obeyAdjustment, setObeyAdjustment] = useState(true);

  // 目标选择（联动）
  const [targetSchool, setTargetSchool] = useState("");
  const [targetMajors, setTargetMajors] = useState<string[]>([]);
  const [targetGroup, setTargetGroup] = useState("");

  // 加载联动选项
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const opts = await getHenanOptions();
        if (!alive) return;
        setOptions(opts);
        // 院校选择改为由用户输入搜索（SchoolCombobox），不自动预填第一所
      } catch (e) {
        if (!alive) return;
        setError(e instanceof ApiError ? e.message : "院校选项加载失败");
      } finally {
        if (alive) setOptsLoading(false);
      }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 院校联动：当前院校下的专业与专业组
  const schoolMajors = options ? options.majors.filter((m) => m.school === targetSchool) : [];
  const schoolGroups = options ? options.groups.filter((g) => g.school === targetSchool) : [];

  const electiveOptions = ELECTIVES.filter((s) => s !== "物理" && s !== "历史");
  const effectiveElectives = electives.filter((s) => electiveOptions.includes(s));

  function toggleElective(s: string) {
    setElectives((prev) => {
      const cur = prev.filter((x) => electiveOptions.includes(x));
      return cur.includes(s) ? cur.filter((x) => x !== s) : cur.length < 2 ? [...cur, s] : cur;
    });
  }
  function toggleMajor(m: string) {
    setTargetMajors((prev) => (prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]));
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!targetSchool.trim()) {
      setError("请先输入或选择目标院校");
      setResult(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await evaluateHenanTarget({
        score,
        rank: rank === "" ? null : rank,
        track: "历史类",
        source_province: "河南",
        target_school: targetSchool,
        target_majors: targetMajors,
        target_group: targetGroup || null,
        exam_foreign_language: foreignLang,
        primary_subject: "历史",
        elective_subjects: effectiveElectives,
        subject_scores_detail: {
          数学: mathScore,
          外语: foreignScore,
        },
        obey_adjustment: obeyAdjustment,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "请求失败，请确认后端服务已启动");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const inputCls = "bg-white/10 rounded-xl px-3 py-2 text-sm w-full focus:outline-none focus:ring-1 focus:ring-pink-400/50";
  const selectCls = inputCls;

  return (
    <div className="space-y-6">
      {!result && (
        <div className="text-center py-6 animate-fade-in">
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight flex items-center justify-center gap-2">
            <Target className="w-8 h-8 text-pink-400" />
            <span className="bg-gradient-to-r from-pink-400 via-fuchsia-400 to-indigo-400 bg-clip-text text-transparent">
              目标评估
            </span>
          </h1>
          <p className="text-white/60 mt-3 text-sm">
            选择目标院校与专业 → 复用首页冲稳保逻辑判断可报性与录取风险
          </p>
        </div>
      )}

      <form onSubmit={submit} className="glass rounded-3xl p-6 sm:p-8 shadow-2xl animate-slide-up space-y-5">
        {/* 目标院校 / 专业 / 专业组（联动） */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="block">
            <span className="text-xs text-white/60 mb-1.5 block">目标院校</span>
            <SchoolCombobox
              options={options?.schools ?? []}
              value={targetSchool}
              onChange={(name) => { setTargetSchool(name); setTargetMajors([]); setTargetGroup(""); }}
              disabled={optsLoading}
            />
          </label>
          <label className="block">
            <span className="text-xs text-white/60 mb-1.5 block">指定专业组（可选）</span>
            <select value={targetGroup} onChange={(e) => setTargetGroup(e.target.value)} className={selectCls} disabled={!targetSchool}>
              <option value="">{targetSchool ? "不限（评估全部专业组）" : "请先选择院校"}</option>
              {schoolGroups.map((g) => (
                <option key={g.code + g.track} value={g.code} className="bg-slate-800">
                  {g.code} · {g.name}（{g.track}）
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* 目标专业多选（联动当前院校） */}
        <div>
          <span className="text-xs text-white/60 mb-2 block">
            目标专业（可选，多选；不选则评估该校全部专业）
            <span className="text-white/30 ml-1">已选 {targetMajors.length}</span>
          </span>
          <div className="flex flex-wrap gap-1.5">
            {schoolMajors.length === 0 && (
              <span className="text-xs text-white/30">
                {targetSchool ? "该院校暂无分专业计划数据" : "请先选择目标院校"}
              </span>
            )}
            {schoolMajors.map((m) => (
              <button
                key={m.major} type="button"
                onClick={() => toggleMajor(m.major)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  targetMajors.includes(m.major)
                    ? "bg-gradient-to-r from-emerald-500 to-teal-500 text-white"
                    : "bg-white/5 text-white/50 hover:bg-white/10"
                }`}
              >
                {m.major}
              </button>
            ))}
          </div>
        </div>

        <div className="pt-5 border-t border-white/10 grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="block">
            <span className="text-xs text-white/60 mb-1.5 block">适用范围</span>
            <div className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white/80">
              河南 / 2026 / 历史类 / 普通本科批
            </div>
          </label>
          <label className="block">
            <span className="text-xs text-white/60 mb-1.5 block">高考总分</span>
            <input type="number" min={0} max={750} value={score} onChange={(e) => setScore(Number(e.target.value))} className={inputCls} required />
          </label>
          <label className="block">
            <span className="text-xs text-white/60 mb-1.5 block">位次（可选，填了优先用位次）</span>
            <input type="number" min={0} value={rank} onChange={(e) => setRank(e.target.value === "" ? "" : Number(e.target.value))} placeholder="留空按分数换算" className={inputCls} />
          </label>
          <label className="block">
            <span className="text-xs text-white/60 mb-1.5 block">外语语种</span>
            <select value={foreignLang} onChange={(e) => setForeignLang(e.target.value)} className={selectCls}>
              {FOREIGN_LANGS.map((l) => (
                <option key={l} value={l} className="bg-slate-800">{l}</option>
              ))}
            </select>
          </label>
        </div>

        {/* 再选科目 */}
        <div>
          <span className="text-xs text-white/60 mb-2 block">
            再选科目（3+1+2 的"2"，选2门）
            <span className="text-white/30 ml-1">已选 {effectiveElectives.length}/2</span>
          </span>
          <div className="flex flex-wrap gap-1.5">
            {electiveOptions.map((s) => (
              <button key={s} type="button" onClick={() => toggleElective(s)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  effectiveElectives.includes(s) ? "bg-gradient-to-r from-emerald-500 to-teal-500 text-white" : "bg-white/5 text-white/50 hover:bg-white/10"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-xs text-white/60 mb-1.5 block">数学单科分</span>
            <input type="number" min={0} max={150} value={mathScore} onChange={(e) => setMathScore(Number(e.target.value))} className={inputCls} />
          </label>
          <label className="block">
            <span className="text-xs text-white/60 mb-1.5 block">{foreignLang}单科分</span>
            <input type="number" min={0} max={150} value={foreignScore} onChange={(e) => setForeignScore(Number(e.target.value))} className={inputCls} />
          </label>
        </div>

        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={obeyAdjustment} onChange={(e) => setObeyAdjustment(e.target.checked)} className="w-4 h-4 accent-pink-500" />
          服从专业调剂
        </label>

        <button type="submit" disabled={loading}
          className="w-full py-3.5 rounded-xl bg-gradient-to-r from-pink-500 via-fuchsia-500 to-indigo-500 font-bold text-white shadow-lg hover:scale-[1.01] active:scale-[0.99] transition disabled:opacity-50 disabled:hover:scale-100 flex items-center justify-center gap-2"
        >
          {loading ? <><Loader2 className="w-5 h-5 animate-spin" /> 评估中...</> : <>开始评估</>}
        </button>
      </form>

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
        <div className="animate-slide-up space-y-4">
          {(!result.production_ready || (result.coverage_notes?.length ?? 0) > 0) && (
            <div className="glass rounded-2xl p-4 border border-amber-400/30 flex items-start gap-2 text-sm text-amber-200">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <div>
                <p className="font-medium">
                  {result.production_ready ? "评估数据存在额外风险提示" : "评估数据未达到 production_ready"}
                </p>
                {(result.coverage_notes?.length ?? 0) > 0 && (
                  <div className="text-amber-200/70 text-xs mt-0.5 space-y-0.5">
                    {result.coverage_notes?.map((note, index) => <div key={index}>• {note}</div>)}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* AI 智能评估面板 — 两阶段：合规复核 → 综合评估 */}
          <AIAnalysisPanel
            title="AI 智能评估"
            buttonLabel="✨ AI 智能评估"
            streamFactory={(signal) =>
              streamAiEvaluate(
                {
                  score,
                  rank: rank === "" ? null : rank,
                  track: "历史类",
                  source_province: "河南",
                  target_school: targetSchool,
                  target_majors: targetMajors,
                  target_group: targetGroup || null,
                  primary_subject: "历史",
                  elective_subjects: effectiveElectives,
                  exam_foreign_language: foreignLang,
                  subject_scores_detail: {
                    数学: mathScore,
                    外语: foreignScore,
                  },
                  obey_adjustment: obeyAdjustment,
                },
                signal,
              )
            }
          />

          {/* 总结 */}
          <div className="glass rounded-3xl p-6 shadow-xl">
            <div className="flex items-center gap-2 mb-2">
              <Target className="w-5 h-5 text-pink-400" />
              <h2 className="font-bold text-lg">{result.school_name}</h2>
              <BucketBadge bucket={result.overall_bucket} />
            </div>
            {result.overall_bucket === "不推荐" ? (
              <div className="text-sm space-y-2">
                {/* 首条固定为总述，作为标题 */}
                <div className="text-red-200/90 font-medium">⚠ {result.reasons[0]}</div>
                {/* 后续按内容分类着色：位次差距(橙·主因) / 资格不符(红·硬阻断) / 数据待核验(黄) */}
                {result.reasons.slice(1).map((r, i) => {
                  let cls = "text-white/60";
                  let icon = "•";
                  if (r.startsWith("位次差距")) { cls = "text-orange-300/90"; icon = "⚠"; }
                  else if (r.startsWith("资格不符")) { cls = "text-red-300/85"; icon = "⛔"; }
                  else if (r.startsWith("数据待核验")) { cls = "text-amber-300/80"; icon = "⚠"; }
                  return <div key={i} className={`pl-2 ${cls}`}>{icon} {r}</div>;
                })}
                <p className="text-[11px] text-white/35 pt-1">
                  目标评估与志愿推荐使用相同的冲稳保逻辑。若分数提升后位次接近参考录取位次，"位次差距过大"的院校可能转为可报。
                </p>
              </div>
            ) : (
              <div className="text-sm text-white/70 space-y-1">
                <p>共评估 {result.items.length} 个专业/专业组，按冲稳保垫档位列出。</p>
                {result.reasons && result.reasons.length > 0 && (
                  <p className={`text-[13px] ${
                    result.overall_bucket === "部分专业可评估" ? "text-amber-300/90" : "text-rose-300/80"
                  }`}>⚠ {result.reasons.join("；")}</p>
                )}
              </div>
            )}
          </div>

          {/* 按冲稳保分组：单校聚合卡片（学校共性信息只显示一次，专业组作为子表） */}
          {result.items.length > 0 && (
            <div className="space-y-3">
              {(["超冲", "搏", "冲", "稳", "保", "垫"] as const).map((bucket) => {
                const items = result.items.filter((it) => it.bucket === bucket);
                if (items.length === 0) return null;
                return (
                  <div key={bucket}>
                    <div className="flex items-center gap-2 mb-2 px-1">
                      <BucketBadge bucket={bucket} />
                      <span className="text-xs text-white/50">{items.length} 个专业组</span>
                    </div>
                    <TargetSchoolCard items={items} bucketKey={bucket} />
                  </div>
                );
              })}
            </div>
          )}

          <div className="text-[11px] text-white/35 leading-relaxed px-1">
            目标评估复用首页专业推荐的资格过滤与冲稳保分桶逻辑，不使用更宽松的规则。
            录取风险仅供参考，正式填报以河南省教育考试院公布为准。
          </div>
        </div>
      )}
    </div>
  );
}
