import { useState } from "react";
import { Search, Loader2 } from "lucide-react";
import type { AdvisoryRequest } from "../api/types";

const PROVINCES = ["河南", "广东"];
const TRACKS_BY_PROVINCE: Record<string, { label: string; value: string }[]> = {
  河南: [
    { label: "物理类", value: "物理类" },
    { label: "历史类", value: "历史类" },
    { label: "理科(2024及以前)", value: "理科" },
    { label: "文科(2024及以前)", value: "文科" },
  ],
  广东: [
    { label: "物理类", value: "物理类" },
    { label: "历史类", value: "历史类" },
  ],
};
// 河南志愿推：策略改为 冲/稳/保 + 全部（design §7.2，去掉"中"）。
// 显示档位 display_bucket 作为前端筛选；risk_preference 仍提交后端兼容值。
const BUCKET_OPTIONS: { value: "全部" | "冲" | "稳" | "保"; label: string; desc: string }[] = [
  { value: "全部", label: "全部", desc: "48志愿布局" },
  { value: "冲", label: "冲", desc: "只看冲刺志愿" },
  { value: "稳", label: "稳", desc: "只看稳妥志愿" },
  { value: "保", label: "保", desc: "只看保底志愿" },
];
const YEARS = [2026, 2025, 2024];  // 2026优先（当年最新一分一段表）

interface Props {
  loading: boolean;
  onSubmit: (req: AdvisoryRequest) => void;
}

const FOREIGN_LANGS = ["英语", "日语", "俄语", "德语", "法语", "西班牙语"];
const ELECTIVES = ["物理", "化学", "生物", "政治", "历史", "地理"];

export default function ScoreForm({ loading, onSubmit }: Props) {
  const [province, setProvince] = useState("河南");
  const [totalScore, setTotalScore] = useState(480);
  const [track, setTrack] = useState("历史类");
  const [dataYear, setDataYear] = useState(2026);  // 默认当年最新
  const [displayBucket, setDisplayBucket] = useState<"全部" | "冲" | "稳" | "保">("全部");
  // 选科/外语/单科（填报硬门槛）
  const [foreignLang, setForeignLang] = useState("日语");  // 默认日语(用户弟弟场景)
  const [electives, setElectives] = useState<string[]>(["政治", "地理"]);
  const [mathScore, setMathScore] = useState(64);
  const [foreignScore, setForeignScore] = useState(98);
  // 河南志愿推新增：关注院校 / 兴趣专业（design §7.3）
  const [focusedSchoolsText, setFocusedSchoolsText] = useState("");
  const [interestMajorsText, setInterestMajorsText] = useState("");

  const tracks = TRACKS_BY_PROVINCE[province] || [];

  function toggleElective(s: string) {
    setElectives((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : prev.length < 2 ? [...prev, s] : prev
    );
  }

  function splitWords(text: string): string[] {
    return text.split(/[、,，\s]+/).map((s) => s.trim()).filter(Boolean);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      province,
      total_score: totalScore,
      data_year: dataYear,
      // 仍提交后端兼容的 risk_preference（冲/稳），新增 display_bucket 做前端筛选
      risk_preference: displayBucket === "冲" ? "冲" : displayBucket === "保" ? "稳" : "中",
      primary_subject: track.includes("历史") ? "历史" : "物理",
      math_score: mathScore,
      exam_foreign_language: foreignLang,
      foreign_language_score: foreignScore,
      english_actual_level: foreignLang === "英语" && foreignScore >= 120 ? "advanced" : "intermediate",
      elective_subjects: electives,
      accept_private_school: true,
      focused_schools: splitWords(focusedSchoolsText),
      interest_majors: splitWords(interestMajorsText),
      display_bucket: displayBucket,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="glass rounded-3xl p-6 sm:p-8 shadow-2xl animate-slide-up">
      <h2 className="text-xl font-bold mb-1 flex items-center gap-2">
        <Search className="w-5 h-5 text-pink-400" />
        输入考生信息
      </h2>
      <p className="text-sm text-white/50 mb-6">填写分数与偏好，一键生成冲稳保志愿表</p>

      <div className="grid grid-cols-2 gap-4">
        {/* 省份 */}
        <label className="block">
          <span className="text-xs text-white/60 mb-1.5 block">省份</span>
          <select
            value={province}
            onChange={(e) => {
              setProvince(e.target.value);
              const t = TRACKS_BY_PROVINCE[e.target.value];
              if (t && !t.find((x) => x.value === track)) setTrack(t[0].value);
            }}
            className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400"
          >
            {PROVINCES.map((p) => (
              <option key={p} value={p} className="bg-slate-800">
                {p}
              </option>
            ))}
          </select>
        </label>

        {/* 高考总分 */}
        <label className="block">
          <span className="text-xs text-white/60 mb-1.5 block">高考总分</span>
          <input
            type="number"
            min={0}
            max={750}
            value={totalScore}
            onChange={(e) => setTotalScore(Number(e.target.value))}
            className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400"
          />
        </label>

        {/* 科类 */}
        <label className="block">
          <span className="text-xs text-white/60 mb-1.5 block">科类</span>
          <select
            value={track}
            onChange={(e) => setTrack(e.target.value)}
            className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400"
          >
            {tracks.map((t) => (
              <option key={t.value} value={t.value} className="bg-slate-800">
                {t.label}
              </option>
            ))}
          </select>
        </label>

        {/* 数据年份 */}
        <label className="block">
          <span className="text-xs text-white/60 mb-1.5 block">参考数据年份</span>
          <select
            value={dataYear}
            onChange={(e) => setDataYear(Number(e.target.value))}
            className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400"
          >
            {YEARS.map((y) => (
              <option key={y} value={y} className="bg-slate-800">
                {y} 年
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* 选科 / 外语 / 单科（填报硬门槛）*/}
      <div className="mt-5 pt-5 border-t border-white/10">
        <span className="text-xs text-white/60 mb-2 block">外语语种</span>
        <div className="flex flex-wrap gap-1.5 mb-4">
          {FOREIGN_LANGS.map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => setForeignLang(l)}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition ${
                foreignLang === l
                  ? "bg-gradient-to-r from-pink-500 to-indigo-500 text-white"
                  : "bg-white/5 text-white/50 hover:bg-white/10"
              }`}
            >
              {l}
            </button>
          ))}
        </div>

        <span className="text-xs text-white/60 mb-2 block">
          再选科目（3+1+2 的"2"，选2门）<span className="text-white/30 ml-1">已选 {electives.length}/2</span>
        </span>
        <div className="flex flex-wrap gap-1.5 mb-4">
          {ELECTIVES.filter((s) => s !== "物理" && s !== "历史").map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => toggleElective(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                electives.includes(s)
                  ? "bg-gradient-to-r from-emerald-500 to-teal-500 text-white"
                  : "bg-white/5 text-white/50 hover:bg-white/10"
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-xs text-white/60 mb-1.5 block">数学单科分</span>
            <input
              type="number" min={0} max={150} value={mathScore}
              onChange={(e) => setMathScore(Number(e.target.value))}
              className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400"
            />
          </label>
          <label className="block">
            <span className="text-xs text-white/60 mb-1.5 block">{foreignLang}单科分</span>
            <input
              type="number" min={0} max={150} value={foreignScore}
              onChange={(e) => setForeignScore(Number(e.target.value))}
              className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400"
            />
          </label>
        </div>
        <p className="text-[10px] text-white/30 mt-2">部分专业对数学/外语单科有门槛，系统自动剔除不达标的专业</p>
      </div>

      {/* 关注院校 / 兴趣专业（河南志愿推 design §7.3） */}
      <div className="mt-5 pt-5 border-t border-white/10 grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label className="block">
          <span className="text-xs text-white/60 mb-1.5 block">关注院校（可选，逗号/空格分隔）</span>
          <input
            value={focusedSchoolsText}
            onChange={(e) => setFocusedSchoolsText(e.target.value)}
            placeholder="如 郑州大学 河南大学"
            className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400"
          />
        </label>
        <label className="block">
          <span className="text-xs text-white/60 mb-1.5 block">兴趣专业（可选，逗号/空格分隔）</span>
          <input
            value={interestMajorsText}
            onChange={(e) => setInterestMajorsText(e.target.value)}
            placeholder="如 会计学 法学"
            className="w-full bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400"
          />
        </label>
      </div>

      {/* 冲稳保档位筛选（design §7.2，去掉"中"） */}
      <div className="mt-5">
        <span className="text-xs text-white/60 mb-2 block">查看档位</span>
        <div className="grid grid-cols-4 gap-2">
          {BUCKET_OPTIONS.map((b) => (
            <button
              key={b.value}
              type="button"
              onClick={() => setDisplayBucket(b.value)}
              className={`py-3 rounded-xl text-sm font-bold transition border ${
                displayBucket === b.value
                  ? "bg-gradient-to-br from-pink-500 to-indigo-500 border-transparent text-white shadow-lg"
                  : "bg-white/5 border-white/15 text-white/60 hover:bg-white/10"
              }`}
            >
              <div className="text-lg">{b.label}</div>
              <div className="text-[10px] font-normal opacity-70 mt-0.5">{b.desc}</div>
            </button>
          ))}
        </div>
        <p className="text-[10px] text-white/30 mt-2">"冲/稳/保"是产品辅助填报策略，非河南省教育考试院官方比例</p>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="mt-6 w-full py-3.5 rounded-xl bg-gradient-to-r from-pink-500 via-fuchsia-500 to-indigo-500 font-bold text-white shadow-lg hover:shadow-pink-500/30 hover:scale-[1.01] active:scale-[0.99] transition disabled:opacity-50 disabled:hover:scale-100 flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" /> 生成中...
          </>
        ) : (
          <>生成志愿表</>
        )}
      </button>
    </form>
  );
}
