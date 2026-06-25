import { useEffect, useState } from "react";
import { Wallet, Loader2, GraduationCap, Home, UtensilsCrossed, TrendingUp } from "lucide-react";
import { listUniversities, estimateCost, ApiError } from "../api/client";
import type { University, CostEstimate, SchoolNature } from "../api/types";

const NATURES: { value: SchoolNature | ""; label: string }[] = [
  { value: "", label: "全部" },
  { value: "公立", label: "公立" },
  { value: "民办", label: "民办" },
  { value: "中外合作", label: "中外合作" },
];

// 办学性质配色
const NATURE_STYLE: Record<string, string> = {
  公立: "bg-emerald-500/20 text-emerald-300 border-emerald-400/30",
  民办: "bg-orange-500/20 text-orange-300 border-orange-400/30",
  中外合作: "bg-fuchsia-500/20 text-fuchsia-300 border-fuchsia-400/30",
};

const fmt = (n: number) => n.toLocaleString();

export default function UniversityCostPage() {
  const [nature, setNature] = useState<SchoolNature | "">("");
  const [schools, setSchools] = useState<University[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [years, setYears] = useState(4);
  const [cost, setCost] = useState<CostEstimate | null>(null);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingCost, setLoadingCost] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载院校列表
  useEffect(() => {
    setLoadingList(true);
    listUniversities(nature || undefined)
      .then((r) => {
        setSchools(r);
        if (r.length && !r.find((s) => s.name === selected)) setSelected(r[0].name);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "加载失败"))
      .finally(() => setLoadingList(false));
  }, [nature]);

  // 查询费用
  useEffect(() => {
    if (!selected) return;
    setLoadingCost(true);
    setError(null);
    estimateCost(selected, years)
      .then(setCost)
      .catch((e) => {
        setError(e instanceof ApiError ? e.message : "查询失败");
        setCost(null);
      })
      .finally(() => setLoadingCost(false));
  }, [selected, years]);

  return (
    <div className="max-w-3xl mx-auto">
      <div className="text-center mb-6">
        <h1 className="text-3xl font-bold flex items-center justify-center gap-2">
          <Wallet className="w-7 h-7 text-pink-400" />
          大学费用估算
        </h1>
        <p className="text-white/50 text-sm mt-1">学费 + 住宿费 + 生活费 · 公立/民办/中外合作对比</p>
      </div>

      {/* 筛选 + 选校 */}
      <div className="glass rounded-3xl p-5 shadow-xl space-y-4 mb-6">
        <div className="flex flex-wrap gap-2">
          {NATURES.map((n) => (
            <button
              key={n.label}
              onClick={() => setNature(n.value)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                nature === n.value
                  ? "bg-gradient-to-r from-pink-500 to-indigo-500 text-white"
                  : "bg-white/5 text-white/60 hover:bg-white/10"
              }`}
            >
              {n.label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-3 gap-3">
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="col-span-2 bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm"
          >
            {loadingList && <option>加载中...</option>}
            {schools.map((s) => (
              <option key={s.id} value={s.name} className="bg-slate-800">
                {s.name}（{s.nature}·{s.city || s.province}）
              </option>
            ))}
          </select>
          <select
            value={years}
            onChange={(e) => setYears(Number(e.target.value))}
            className="bg-white/10 border border-white/15 rounded-xl px-3 py-2.5 text-sm"
          >
            <option value={3} className="bg-slate-800">3年(专科)</option>
            <option value={4} className="bg-slate-800">4年(本科)</option>
            <option value={5} className="bg-slate-800">5年(医学等)</option>
          </select>
        </div>
      </div>

      {error && <p className="text-red-300 text-sm text-center mb-4">{error}</p>}

      {/* 费用明细 */}
      {loadingCost && (
        <div className="text-center py-10">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-pink-400" />
        </div>
      )}

      {cost && !loadingCost && (
        <div className="space-y-4 animate-slide-up">
          {/* 总开销大数字 */}
          <div className="glass rounded-3xl p-8 text-center shadow-xl">
            <div className="text-xs text-white/50 mb-2">{cost.years}年大学期间总开销</div>
            <div className="text-5xl font-extrabold bg-gradient-to-r from-pink-400 via-fuchsia-400 to-indigo-400 bg-clip-text text-transparent">
              ¥{fmt(cost.grand_total)}
            </div>
            <div className="mt-3 flex items-center justify-center gap-2 flex-wrap">
              <span className={`text-xs px-2 py-0.5 rounded-md border ${NATURE_STYLE[cost.nature] || ""}`}>
                {cost.nature}
              </span>
              {cost.city && <span className="text-xs text-white/50">{cost.city}</span>}
              <span className="text-xs text-white/40">年均 ¥{fmt(cost.annual_total)}</span>
            </div>
          </div>

          {/* 费用构成 */}
          <div className="grid sm:grid-cols-3 gap-3">
            <CostItem
              icon={GraduationCap}
              label="学费"
              sub={`${cost.years}年`}
              value={cost.tuition_per_year * cost.years}
              color="from-pink-500/20 to-rose-500/20 border-pink-400/30"
              iconColor="text-pink-400"
              perYear={`¥${fmt(cost.tuition_per_year)}/年`}
            />
            <CostItem
              icon={Home}
              label="住宿费"
              sub={`${cost.years}年`}
              value={cost.accommodation_per_year * cost.years}
              color="from-indigo-500/20 to-blue-500/20 border-indigo-400/30"
              iconColor="text-indigo-400"
              perYear={`¥${fmt(cost.accommodation_per_year)}/年`}
            />
            <CostItem
              icon={UtensilsCrossed}
              label="生活费"
              sub={`${cost.years}年`}
              value={cost.living_cost_per_year * cost.years}
              color="from-emerald-500/20 to-green-500/20 border-emerald-400/30"
              iconColor="text-emerald-400"
              perYear={`¥${fmt(cost.living_cost_per_year)}/年`}
            />
          </div>

          {/* 来源说明 */}
          <div className="glass rounded-2xl p-4 flex items-start gap-2 text-xs text-white/50">
            <TrendingUp className="w-4 h-4 mt-0.5 shrink-0" />
            <div>
              <p>生活费来源：{cost.city_cost_source}</p>
              <p className="mt-1 text-white/30">
                年成本 = 12 × 月生活费中位 + 学费 + 住宿费。生活费因城市差异大（如北京≈深圳&gt;郑州），
                学费因办学性质差异大（公立5千 / 民办1.5-3万 / 中外合作4-10万）。
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CostItem({
  icon: Icon, label, sub, value, color, iconColor, perYear,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string; sub: string; value: number; color: string; iconColor: string; perYear: string;
}) {
  return (
    <div className={`glass rounded-2xl p-4 border bg-gradient-to-br ${color} animate-fade-in`}>
      <Icon className={`w-5 h-5 ${iconColor} mb-2`} />
      <div className="text-xs text-white/60">{label}({sub})</div>
      <div className="text-2xl font-bold mt-1">¥{fmt(value)}</div>
      <div className="text-xs text-white/40 mt-0.5">{perYear}</div>
    </div>
  );
}
