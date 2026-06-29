import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  DndContext, PointerSensor, useSensor, useSensors, closestCorners, type DragEndEvent, type DragStartEvent,
} from "@dnd-kit/core";
import {
  SortableContext, useSortable, verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Layers, Flame, Rocket, ShieldCheck, Anchor, Shield, Trash2, AlertTriangle } from "lucide-react";
import { useVolunteerStore } from "../store/volunteerStore";
import VolunteerItemRow from "../components/VolunteerItemRow";
import { TIER_STYLE } from "../components/volunteerTier";
import type { LayoutItem, UserVolunteerItem } from "../api/types";

/** 可拖拽包装行 */
function SortableRow({ item }: { item: UserVolunteerItem }) {
  const { setNodeRef, attributes, listeners, transform, transition, isDragging } = useSortable({ id: item.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };
  // 计算行内序号（编排页按全局 sort_order 展示，不在这里算 index）
  return (
    <div ref={setNodeRef} style={style}>
      <VolunteerItemRow item={item} index={item.sort_order} dragHandleProps={{ ...attributes, ...listeners }} />
    </div>
  );
}

/** 分区配置（按规划档位分区，视觉组织） */
const TIER_ZONES = [
  { tier: "搏", icon: Flame, label: "搏档" },
  { tier: "冲", icon: Rocket, label: "冲档" },
  { tier: "稳", icon: ShieldCheck, label: "稳档" },
  { tier: "保", icon: Anchor, label: "保档" },
  { tier: "垫", icon: Shield, label: "垫档" },
] as const;

export default function MyGroupsPage() {
  const group = useVolunteerStore((s) => s.group);
  const loadGroup = useVolunteerStore((s) => s.loadGroup);
  const applyLayout = useVolunteerStore((s) => s.applyLayout);
  const clearAll = useVolunteerStore((s) => s.clearAll);
  const flushPendingDeletes = useVolunteerStore((s) => s.flushPendingDeletes);

  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    void loadGroup();
    return () => { void flushPendingDeletes(); };
  }, [loadGroup, flushPendingDeletes]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  const items = group?.items ?? [];
  const stats = group?.stats;

  // 按规划档位（effective_tier）分组
  const byTier = useMemo(() => {
    const m: Record<string, UserVolunteerItem[]> = {};
    for (const it of items) {
      const t = it.effective_tier;
      (m[t] ??= []).push(it);
    }
    return m;
  }, [items]);

  // 拖拽处理：跨档拖拽 → 改 planned_tier + 重排全局 sort_order
  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over) return;
    const activeId = Number(active.id);
    const overId = Number(over.id);
    if (activeId === overId) return;

    const activeItem = items.find((it) => it.id === activeId);
    const overItem = items.find((it) => it.id === overId);
    if (!activeItem) return;

    // 确定目标档位：放到某个分区容器上，或放到某项上（用该项 effective_tier）
    let targetTier = activeItem.effective_tier;
    if (overItem) {
      targetTier = overItem.effective_tier;
    } else {
      // over.id 可能是分区容器 id（如 "zone-冲"）
      const z = String(over.id).replace("zone-", "");
      if (TIER_ZONES.some((tz) => tz.tier === z)) targetTier = z;
    }

    // 重新计算全局顺序：移除 active，插到目标位置
    const withoutActive = items.filter((it) => it.id !== activeId);
    let insertIndex: number;
    if (overItem) {
      insertIndex = withoutActive.findIndex((it) => it.id === overId);
      if (insertIndex < 0) insertIndex = withoutActive.length;
    } else {
      // 放到该档末尾
      const lastInTier = [...withoutActive].reverse().find((it) => it.effective_tier === targetTier);
      insertIndex = lastInTier ? withoutActive.indexOf(lastInTier) + 1 : withoutActive.length;
    }
    const newPlannedTier = targetTier === activeItem.latest_algorithm_tier ? null : targetTier;
    const moved = { ...activeItem, planned_tier: newPlannedTier, effective_tier: targetTier };
    const reordered = [...withoutActive];
    reordered.splice(insertIndex, 0, moved);

    const layout: LayoutItem[] = reordered.map((it, i) => ({
      item_id: it.id,
      planned_tier: it.planned_tier,
      sort_order: i,
    }));
    void applyLayout(layout);
  };

  const onDragStart = (_e: DragStartEvent) => { /* 预留：拖动开始反馈 */ };

  return (
    <div className="space-y-4">
      {/* 标题 */}
      <div className="glass rounded-3xl p-6 shadow-xl">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-indigo-300" />
          <h1 className="text-xl font-bold text-white/90">志愿编排</h1>
          {items.length > 0 && <span className="text-sm text-white/40">{items.length}/48</span>}
        </div>
        <p className="text-sm text-white/50 mt-1.5 leading-relaxed">
          按规划档位编排志愿顺序。拖拽卡片可跨档调整（改规划档位）或同档排序。
          算法档位（<span className="text-white/70">算法参考</span>）不会被覆盖，可随时恢复。
        </p>
        {items.length === 0 && (
          <p className="text-sm text-indigo-200/80 mt-3">
            志愿组为空，去 <Link to="/" className="underline hover:text-indigo-100">志愿推荐</Link> 加入院校专业组。
          </p>
        )}
      </div>

      {/* 结构风险提示 */}
      {stats && stats.structure_hints.length > 0 && (
        <div className="glass rounded-2xl p-4 border border-amber-400/30 space-y-1.5">
          <p className="text-sm font-medium text-amber-200 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4" /> 结构提示（参考，非官方要求）
          </p>
          {stats.structure_hints.map((h) => (
            <div key={h.code} className="text-xs text-amber-200/80 leading-relaxed">
              {h.severity === "warning" ? "⚠ " : "• "}{h.message}
            </div>
          ))}
        </div>
      )}

      {/* 档位统计 */}
      {stats && items.length > 0 && (
        <div className="glass rounded-2xl p-4">
          <div className="flex flex-wrap gap-2">
            {(["搏", "冲", "稳", "保", "垫"] as const).map((t) => {
              const n = stats.by_effective_tier[t] ?? 0;
              return (
                <span key={t} className={`text-[11px] px-2 py-0.5 rounded ${TIER_STYLE[t]}`}>
                  {t}档 {n}
                </span>
              );
            })}
            <span className="text-[11px] text-white/40 ml-auto">
              省内 {stats.local_count} · 省外 {stats.out_of_province_count} · 公办 {stats.public_count} · 民办 {stats.private_count}
            </span>
          </div>
        </div>
      )}

      {/* 分区拖拽区 */}
      {items.length > 0 && (
        <DndContext sensors={sensors} collisionDetection={closestCorners} onDragStart={onDragStart} onDragEnd={onDragEnd}>
          <div className="space-y-3">
            {TIER_ZONES.map((zone) => {
              const zoneItems = (byTier[zone.tier] ?? []).sort((a, b) => a.sort_order - b.sort_order);
              return (
                <div key={zone.tier} className="glass rounded-2xl p-3">
                  <div className="flex items-center gap-2 mb-2 px-1">
                    <zone.icon className={`w-4 h-4 ${
                      zone.tier === "搏" ? "text-orange-300" : zone.tier === "冲" ? "text-amber-300"
                      : zone.tier === "稳" ? "text-emerald-300" : zone.tier === "保" ? "text-sky-300" : "text-indigo-300"
                    }`} />
                    <h3 className="font-bold text-sm text-white/85">{zone.label}</h3>
                    <span className="text-xs text-white/40">{zoneItems.length}</span>
                  </div>
                  <div id={`zone-${zone.tier}`} data-zone={zone.tier} className="space-y-1.5 min-h-[2rem]">
                    {zoneItems.length > 0 ? (
                      <SortableContext items={zoneItems.map((it) => it.id)} strategy={verticalListSortingStrategy}>
                        {zoneItems.map((it) => (
                          <SortableRow key={it.id} item={it} />
                        ))}
                      </SortableContext>
                    ) : (
                      <div className="text-[11px] text-white/25 py-2 px-2 border border-dashed border-white/10 rounded-lg text-center">
                        拖入{zone.tier}档
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </DndContext>
      )}

      {/* 清空 */}
      {items.length > 0 && (
        <div className="flex justify-center pt-2">
          {confirmClear ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-red-200/80">确认清空全部 {items.length} 个志愿？</span>
              <button
                type="button"
                onClick={() => { void clearAll(); setConfirmClear(false); }}
                className="text-xs px-3 py-1.5 rounded-lg bg-red-500/25 text-red-200 hover:bg-red-500/35"
              >
                确认清空
              </button>
              <button
                type="button"
                onClick={() => setConfirmClear(false)}
                className="text-xs px-3 py-1.5 rounded-lg bg-white/10 text-white/60"
              >
                取消
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmClear(true)}
              className="text-xs text-white/30 hover:text-red-300 flex items-center gap-1"
            >
              <Trash2 className="w-3.5 h-3.5" />清空志愿组
            </button>
          )}
        </div>
      )}
    </div>
  );
}
