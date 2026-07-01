/**
 * 志愿建议（可拖动表格 + 详细数据 + 统计盘）。
 *
 * 数据源：GET /my-volunteers/volunteer-suggestion?rush=&steady=&safe=
 * 候选池 = 弟弟13所 + 12国贸推荐去重，按冲稳保配额自动选校。
 * 支持：配额可配置、上下拖动调整序号、每行展开详细数据、左侧统计盘。
 */
import { useEffect, useState } from "react";
import {
  DndContext, PointerSensor, useSensor, useSensors, closestCenter, type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext, useSortable, verticalListSortingStrategy, arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, ChevronDown, ChevronRight, Wallet, MapPin, Building2 } from "lucide-react";
import { getVolunteerSuggestion, type SuggestionItem, type VolunteerSuggestion } from "../api/client";
import { TIER_STYLE } from "./volunteerTier";

const OWNERSHIP_BADGE: Record<string, string> = {
  公办: "bg-sky-500/20 text-sky-300",
  民办: "bg-amber-500/20 text-amber-300",
  独立学院: "bg-purple-500/20 text-purple-300",
};

interface Props {
  brotherScore: number;
  brotherRank: number;
}

export default function VolunteerSuggestion({ brotherScore, brotherRank }: Props) {
  // 默认配额：冲3+稳5+保8（共16，确保不掉档）
  const [quota, setQuota] = useState({ rush: 3, steady: 5, safe: 8 });
  const [data, setData] = useState<VolunteerSuggestion | null>(null);
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<SuggestionItem[]>([]);

  useEffect(() => {
    setLoading(true);
    getVolunteerSuggestion(quota.rush, quota.steady, quota.safe)
      .then((d) => {
        setData(d);
        setItems(d.items.map((it, i) => ({ ...it, index: i + 1 })));
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [quota]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const oldIndex = items.findIndex((it) => `${it.index}` === active.id);
    const newIndex = items.findIndex((it) => `${it.index}` === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = arrayMove(items, oldIndex, newIndex);
    setItems(reordered.map((it, i) => ({ ...it, index: i + 1 })));
  };

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="inline-block w-6 h-6 border-2 border-emerald-400/30 border-t-emerald-400 rounded-full animate-spin mb-3" />
        <div className="text-sm text-white/60">生成志愿建议中（合并候选池 + 计算费用 + 分档 + 选科匹配）…</div>
      </div>
    );
  }
  if (!data) return <div className="text-center text-rose-300 py-8">志愿建议数据加载失败</div>;

  const skipped = data.skipped_ineligible ?? [];
  const profile = data.brother_profile;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
      {/* 左侧统计盘 */}
      <StatsPanel stats={data.stats} brotherScore={brotherScore} brotherRank={brotherRank} />

      {/* 右侧：配额 + 可拖动列表 */}
      <div className="space-y-3">
        {/* 填报说明（弟弟直接参考用） */}
        <div className="rounded-lg bg-emerald-500/5 border border-emerald-500/20 p-2.5 text-[11px] text-emerald-200/80 leading-relaxed">
          <span className="text-emerald-300 font-medium">💡 填报说明：</span>
          弟弟画像 <b className="text-white">480分/历史类/政治+地理/日语</b>，兴趣 <b className="text-white">贸易/商务/日语</b>。
          默认 <b className="text-white">冲3+稳5+保8=16个</b>（保档占50%防掉档）。
          排序优先级：兴趣专业（贸易{'>'}商务{'>'}日语）{'>'} 省内 {'>'} 公办 {'>'} 低费。
          拖动可调整顺序，改配额会即时重排。
        </div>

        {/* 弟弟档案信息条 */}
        <div className="glass rounded-xl p-2 px-3 text-xs flex items-center gap-3 flex-wrap text-white/60">
          <span className="text-white/50">评估档案:</span>
          <span className="text-white/80">{profile?.score ?? "?"}分</span>
          <span className="text-white/40">|</span>
          <span>{profile?.primary_subject}+{profile?.elective_subjects?.join("+")}</span>
          <span className="text-white/40">|</span>
          <span>{profile?.exam_foreign_language}</span>
          {profile?.rank == null && (
            <span className="text-amber-300 ml-auto" title="位次为null，请用位次工具补全">⚠ 位次未填</span>
          )}
        </div>

        {/* 跳过的不可填组（警示） */}
        {skipped.length > 0 && (
          <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 p-3 text-xs">
            <div className="text-rose-300 font-medium mb-1.5 flex items-center gap-1.5">
              <span>❌</span>已跳过 {skipped.length} 个选科/外语不符的组（不会出现在志愿列表中）
            </div>
            <div className="space-y-1">
              {skipped.map((s, i) => (
                <div key={i} className="text-rose-200/80">
                  <b className="text-white">{s.school}</b> 组{s.zyzh}：
                  {(s.eligibility_reasons ?? []).join("；") || "选科不符"}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 配额配置 */}
        <div className="glass rounded-xl p-3 flex items-center gap-4 flex-wrap">
          <span className="text-sm font-medium text-white/70">配额</span>
          {(["rush", "steady", "safe"] as const).map((k) => {
            const label = k === "rush" ? "冲" : k === "steady" ? "稳" : "保";
            return (
              <label key={k} className="flex items-center gap-1.5 text-xs">
                <span className={`px-1.5 py-0.5 rounded ${TIER_STYLE[label] ?? ""}`}>{label}</span>
                <input
                  type="number"
                  min={0}
                  max={20}
                  value={quota[k]}
                  onChange={(e) => setQuota({ ...quota, [k]: Math.max(0, Math.min(20, parseInt(e.target.value) || 0)) })}
                  className="w-12 bg-white/10 rounded px-2 py-1 text-center text-sm"
                />
              </label>
            );
          })}
          <span className="text-xs text-white/40 ml-auto">候选池 {data.pool_total} · 已选 {items.length}</span>
        </div>

        {/* 可拖动志愿列表 */}
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext items={items.map((it) => `${it.index}`)} strategy={verticalListSortingStrategy}>
            <div className="space-y-2">
              {items.map((it) => (
                <SortableRow key={`${it.school}_${it.zyzh}`} item={it} brotherScore={brotherScore} brotherRank={brotherRank} />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      </div>
    </div>
  );
}

/** 可拖动行 */
function SortableRow({ item, brotherScore, brotherRank }: { item: SuggestionItem; brotherScore: number; brotherRank: number }) {
  const { setNodeRef, attributes, listeners, transform, transition, isDragging } = useSortable({ id: `${item.index}` });
  const [expanded, setExpanded] = useState(false);
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 50 : "auto",
  } as const;
  const gap = item.gap;
  const gapColor = gap != null && gap >= 0 ? "text-sky-300" : "text-orange-300";

  return (
    <div ref={setNodeRef} style={style} className={`glass rounded-lg p-3 ${isDragging ? "ring-2 ring-emerald-400 shadow-xl" : ""}`}>
      {/* 第一行：序号+拖拽+校名+核心数据 */}
      <div className="flex items-center gap-2">
        <button {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing text-white/30 hover:text-white/60 shrink-0">
          <GripVertical className="w-4 h-4" />
        </button>
        <span className="w-7 h-7 rounded bg-white/10 text-white/70 font-mono text-xs flex items-center justify-center shrink-0 font-bold">
          {item.index}
        </span>
        <button onClick={() => setExpanded((v) => !v)} className="text-white/30 hover:text-white/60 shrink-0">
          {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
        <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded shrink-0 ${TIER_STYLE[item.tier] ?? ""}`}>{item.tier}</span>
        {/* 资格状态徽章 */}
        {item.eligibility_status && item.eligibility_status !== "可填" && (
          <span className={`text-[9px] px-1 py-0.5 rounded shrink-0 ${
            item.eligibility_status === "不可填" ? "bg-rose-500/20 text-rose-300" :
            "bg-amber-500/20 text-amber-300"
          }`} title={(item.eligibility_reasons ?? []).join("；")}>
            {item.eligibility_status === "不可填" ? "❌不可填" : "⚠有风险"}
          </span>
        )}
        {/* 来源标签：弟弟选(蓝)/推荐(绿) */}
        {item.source === "brother" ? (
          <span className="text-[9px] px-1 py-0.5 rounded bg-sky-500/20 text-sky-300 shrink-0" title="弟弟自己选的">弟弟选</span>
        ) : (
          <span className="text-[9px] px-1 py-0.5 rounded bg-emerald-500/20 text-emerald-300 shrink-0" title="系统推荐补充">推荐</span>
        )}
        <span className="font-medium text-sm shrink-0">{item.school}</span>
        <span className="text-[10px] text-white/30 font-mono shrink-0" title="院校代码">{item.yxdh || "?"}</span>
        <span className="text-[10px] text-white/40 shrink-0">组{item.zyzh}</span>
        {/* planned_tier 与建议 tier 不符时标红 */}
        {item.planned_tier && item.planned_tier !== item.tier && (
          <span className="text-[9px] text-rose-300 shrink-0" title={`弟弟原设定${item.planned_tier}，建议调整为${item.tier}`}>
            原设定{item.planned_tier}→建议{item.tier}
          </span>
        )}
        <div className="ml-auto flex items-center gap-3 text-xs text-white/60 shrink-0">
          <span>{item.min_score_2025 ?? "?"}分</span>
          <span className="font-mono">{item.min_rank_2025?.toLocaleString("zh-CN") ?? "?"}位</span>
          <span className={`font-mono ${gapColor}`}>{gap != null ? `${gap >= 0 ? "+" : ""}${gap.toLocaleString("zh-CN")}` : "?"}</span>
        </div>
      </div>

      {/* 展开详情 */}
      {expanded && (
        <div className="mt-2 pt-2 border-t border-white/10 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          {/* 学校信息 */}
          <div className="space-y-1">
            <div className="text-white/40 font-medium mb-1">学校信息</div>
            <div className="flex items-center gap-2 flex-wrap">
              {item.ownership && <span className={`px-1.5 py-0.5 rounded text-[10px] ${OWNERSHIP_BADGE[item.ownership] ?? "bg-white/10"}`}>{item.ownership}</span>}
              <span className="text-white/50 flex items-center gap-0.5"><MapPin className="w-3 h-3" />{item.province}·{item.city}</span>
              <span className="text-white/50">院校代码 <b className="text-white/80 font-mono">{item.yxdh || "?"}</b></span>
            </div>
            <div className="text-white/50">科目要求：{item.requirement || "不限"}</div>
            {item.planned_tier && (
              <div className="text-white/50">弟弟原设定：<span className={`px-1 rounded text-[10px] ${TIER_STYLE[item.planned_tier] ?? ""}`}>{item.planned_tier}</span>
                {item.planned_tier !== item.tier && <span className="text-rose-300"> → 建议调为{item.tier}</span>}
              </div>
            )}
            {item.equiv_score_2026 && <div className="text-white/50">2026等位分：{item.equiv_score_2026}</div>}
          </div>

          {/* 成本 */}
          <div className="space-y-1">
            <div className="text-white/40 font-medium mb-1 flex items-center gap-1"><Wallet className="w-3 h-3" />费用预估</div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-white/60">
              <span>学费/年：¥{(item.tuition ?? 0).toLocaleString("zh-CN")}</span>
              <span>住宿/年：¥{item.accommodation.toLocaleString("zh-CN")}</span>
              <span>月生活费：¥{item.monthly_cost.toLocaleString("zh-CN")}</span>
              <span className="text-amber-300">4年总计：¥{item.four_year_total.toLocaleString("zh-CN")}</span>
            </div>
          </div>

          {/* 专业组内专业 */}
          <div className="sm:col-span-2">
            <div className="text-white/40 font-medium mb-1">组{item.zyzh}内专业（{item.majors.length}个）</div>
            <div className="flex flex-wrap gap-1">
              {item.majors.map((m, j) => (
                <span key={j} className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-white/60">
                  {m.major_code && <span className="text-white/30 font-mono mr-1">{m.major_code}</span>}
                  {m.major_name}
                </span>
              ))}
            </div>
          </div>

          {/* 与弟弟对比 */}
          <div className="sm:col-span-2 flex items-center gap-4 text-[11px] text-white/50 bg-white/[0.03] rounded p-2">
            <span>弟弟 {brotherScore}分/{brotherRank.toLocaleString("zh-CN")}位</span>
            <span>vs</span>
            <span>该校 {item.min_score_2025 ?? "?"}分/{item.min_rank_2025?.toLocaleString("zh-CN") ?? "?"}位</span>
            {gap != null && (
              <span className={gap >= 0 ? "text-sky-300" : "text-orange-300"}>
                {gap >= 0 ? `弟弟领先${gap.toLocaleString("zh-CN")}位（可录）` : `弟弟落后${Math.abs(gap).toLocaleString("zh-CN")}位（需冲）`}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/** 统计盘 */
function StatsPanel({ stats, brotherScore, brotherRank }: { stats: VolunteerSuggestion["stats"]; brotherScore: number; brotherRank: number }) {
  return (
    <div className="space-y-3">
      {/* 考生信息 */}
      <div className="glass rounded-xl p-4">
        <div className="text-xs text-white/40 mb-1">考生档案</div>
        <div className="text-lg font-bold">{brotherScore}<span className="text-sm text-white/50">分</span></div>
        <div className="text-sm text-white/50">位次 {brotherRank.toLocaleString("zh-CN")} · 历史类</div>
      </div>

      {/* 档位分布 */}
      <div className="glass rounded-xl p-4 space-y-2">
        <div className="text-xs text-white/40">档位分布（共{stats.total}）</div>
        {(["冲", "稳", "保"] as const).map((t) => {
          const n = stats.by_tier[t] ?? 0;
          const pct = stats.total > 0 ? (n / stats.total) * 100 : 0;
          return (
            <div key={t} className="flex items-center gap-2">
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded w-8 text-center ${TIER_STYLE[t] ?? ""}`}>{t}</span>
              <div className="flex-1 h-4 bg-white/5 rounded overflow-hidden">
                <div className={`h-full ${t === "冲" ? "bg-amber-500/50" : t === "稳" ? "bg-emerald-500/50" : "bg-sky-500/50"}`} style={{ width: `${pct}%` }} />
              </div>
              <span className="text-xs text-white/60 w-6 text-right">{n}</span>
            </div>
          );
        })}
      </div>

      {/* 性质/地域 */}
      <div className="glass rounded-xl p-4 space-y-2">
        <div className="text-xs text-white/40 flex items-center gap-1"><Building2 className="w-3 h-3" />性质</div>
        {Object.entries(stats.by_ownership).map(([k, v]) => (
          <div key={k} className="flex justify-between text-xs">
            <span className={`px-1.5 py-0.5 rounded ${OWNERSHIP_BADGE[k] ?? "bg-white/10"}`}>{k}</span>
            <span className="text-white/60">{v}</span>
          </div>
        ))}
        <div className="text-xs text-white/40 flex items-center gap-1 pt-1"><MapPin className="w-3 h-3" />省内 {stats.local_count} · 省外 {stats.total - stats.local_count}</div>
      </div>

      {/* 来源构成 */}
      {stats.by_source && (stats.by_source.brother > 0 || stats.by_source.recommended > 0) && (
        <div className="glass rounded-xl p-4 space-y-1">
          <div className="text-xs text-white/40 mb-1">来源构成</div>
          <div className="flex justify-between text-xs">
            <span className="px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300">弟弟选</span>
            <span className="text-white/60">{stats.by_source.brother ?? 0}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">推荐补充</span>
            <span className="text-white/60">{stats.by_source.recommended ?? 0}</span>
          </div>
        </div>
      )}

      {/* 费用范围（单校，只选一所，故用最高最低） */}
      <div className="glass rounded-xl p-4 space-y-1">
        <div className="text-xs text-white/40 mb-1">费用范围（单校/年）</div>
        <div className="flex justify-between text-xs"><span className="text-white/50">学费</span><span className="font-mono">¥{(stats.tuition_min ?? 0).toLocaleString("zh-CN")} ~ ¥{(stats.tuition_max ?? 0).toLocaleString("zh-CN")}</span></div>
        <div className="flex justify-between text-xs"><span className="text-white/50">4年总成本</span><span className="font-mono text-amber-300">¥{(stats.four_year_min ?? 0).toLocaleString("zh-CN")} ~ ¥{(stats.four_year_max ?? 0).toLocaleString("zh-CN")}</span></div>
      </div>
    </div>
  );
}
