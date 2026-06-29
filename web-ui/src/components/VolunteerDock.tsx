import { useMemo, useState, type CSSProperties } from "react";
import {
  DndContext, PointerSensor, useSensor, useSensors, closestCenter, type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext, useSortable, verticalListSortingStrategy, arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ChevronRight, Trash2, Layers, MapPin, Building2 } from "lucide-react";
import { useVolunteerStore } from "../store/volunteerStore";
import VolunteerItemRow from "./VolunteerItemRow";
import type { LayoutItem, UserVolunteerItem } from "../api/types";

/**
 * 右侧悬浮志愿组（桌面端）。
 * - 顶部统计（总数/档位分布/地域性质）
 * - 志愿项列表（@dnd-kit 单容器全局排序，onDragEnd 提交，串行队列）
 * - 折叠/展开胶囊态
 * - 清空、跳转编排页
 * - 空状态
 * 移动端：本组件 hidden md:block，移动端用底部抽屉（MyGroupsPage 或独立组件）
 */

/** 可拖拽包装行（dnd-kit useSortable）。拖拽中浮起高亮，不变透明（防看不见） */
function SortableRow({ item, index }: { item: UserVolunteerItem; index: number }) {
  const { setNodeRef, attributes, listeners, transform, transition, isDragging } = useSortable({ id: item.id });
  // 拖拽视觉：提升层级 + 阴影浮起 + 略放大，保持完全可见（不用透明度，避免看不见）
  const style: CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: 1,
    zIndex: isDragging ? 50 : "auto",
    position: isDragging ? "relative" : "static",
    boxShadow: isDragging ? "0 8px 24px rgba(0,0,0,0.4)" : "none",
    scale: isDragging ? "1.02" : "1",
  };
  return (
    <div ref={setNodeRef} style={style} className={isDragging ? "rounded-lg ring-2 ring-indigo-400/50" : ""}>
      <VolunteerItemRow item={item} index={index} dragHandleProps={{ ...attributes, ...listeners }} />
    </div>
  );
}

export default function VolunteerDock() {
  const group = useVolunteerStore((s) => s.group);
  const loading = useVolunteerStore((s) => s.loading);
  const applyLayout = useVolunteerStore((s) => s.applyLayout);
  const clearAll = useVolunteerStore((s) => s.clearAll);
  const pendingDeletes = useVolunteerStore((s) => s.pendingDeletes);
  const [collapsed, setCollapsed] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  const items = group?.items ?? [];
  const stats = group?.stats;

  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const oldIndex = items.findIndex((it) => it.id === active.id);
    const newIndex = items.findIndex((it) => it.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = arrayMove(items, oldIndex, newIndex);
    const layout: LayoutItem[] = reordered.map((it, i) => ({
      item_id: it.id, planned_tier: it.planned_tier, sort_order: i,
    }));
    void applyLayout(layout);
  };

  // 撤销提示
  const undoEntries = useMemo(
    () => Object.entries(pendingDeletes) as [string, { item: UserVolunteerItem }][],
    [pendingDeletes],
  );

  if (loading || !group) return null;

  // 折叠态：小型胶囊
  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => setCollapsed(false)}
        className="hidden md:flex fixed right-3 top-24 z-30 w-12 h-12 rounded-full bg-indigo-500/30 backdrop-blur-md ring-1 ring-white/15 items-center justify-center shadow-xl hover:bg-indigo-500/40 transition"
        title="展开志愿组"
      >
        <Layers className="w-5 h-5 text-white/80" />
        {items.length > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-pink-500 text-white text-[10px] font-bold flex items-center justify-center">
            {items.length}
          </span>
        )}
      </button>
    );
  }

  return (
    <div data-testid="volunteer-dock" className="hidden md:flex fixed right-3 top-24 z-30 w-[380px] max-w-[calc(100vw-1.5rem)] max-h-[75vh] flex-col rounded-2xl bg-slate-950/85 shadow-2xl shadow-black/30 ring-1 ring-white/10 backdrop-blur-md">
      {/* 顶部标题 + 折叠 */}
      <div className="flex items-center gap-2 p-3 border-b border-white/10">
        <Layers className="w-4 h-4 text-indigo-300 shrink-0" />
        <span className="font-bold text-sm text-white/90">我的志愿组</span>
        <span data-testid="dock-count" className="text-[11px] text-white/40">{items.length}/48</span>
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          className="ml-auto text-white/30 hover:text-white/60 p-0.5"
          aria-label="折叠"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* 统计区 */}
      {stats && items.length > 0 && (
        <div className="p-3 border-b border-white/10 space-y-1.5">
          {/* 第一行：档位分布 */}
          <div className="flex flex-wrap gap-1.5">
            {(["搏", "冲", "稳", "保", "垫"] as const).map((t) => {
              const n = stats.by_effective_tier[t] ?? 0;
              if (n === 0) return null;
              const colors: Record<string, string> = {
                搏: "bg-orange-500/20 text-orange-300",
                冲: "bg-amber-500/20 text-amber-300",
                稳: "bg-emerald-500/20 text-emerald-300",
                保: "bg-sky-500/20 text-sky-300",
                垫: "bg-indigo-500/20 text-indigo-300",
              };
              return (
                <span key={t} className={`text-[10px] px-1.5 py-0.5 rounded ${colors[t]}`}>
                  {t} {n}
                </span>
              );
            })}
          </div>
          {/* 第二行：地域性质 */}
          <div className="flex flex-wrap gap-3 text-[11px] text-white/50">
            <span className="flex items-center gap-0.5">
              <MapPin className="w-3 h-3" />省内 {stats.local_count} · 省外 {stats.out_of_province_count}
            </span>
            <span className="flex items-center gap-0.5">
              <Building2 className="w-3 h-3" />公办 {stats.public_count} · 民办 {stats.private_count}
            </span>
          </div>
          {/* 结构提示（温和） */}
          {stats.structure_hints.filter((h) => h.severity === "warning").map((h) => (
            <div key={h.code} className="text-[10px] text-amber-200/80 leading-snug">
              ⚠ {h.message}
            </div>
          ))}
        </div>
      )}

      {/* 列表区（滚动） */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5 min-h-0">
        {items.length === 0 ? (
          <div className="text-center text-xs text-white/40 py-8 px-3 leading-relaxed">
            还没有加入志愿。<br />在推荐列表点击「加入志愿组」开始编排。
          </div>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
            <SortableContext items={items.map((it) => it.id)} strategy={verticalListSortingStrategy}>
              {items.map((it, i) => (
                <SortableRow key={it.id} item={it} index={i} />
              ))}
            </SortableContext>
          </DndContext>
        )}
      </div>

      {/* 撤销删除提示 */}
      {undoEntries.length > 0 && (
        <div className="px-3 py-1.5 border-t border-white/10 space-y-1">
          {undoEntries.map(([id, entry]) => (
            <button
              key={id}
              type="button"
              data-testid="undo-delete"
              onClick={() => useVolunteerStore.getState().undoDelete(Number(id))}
              className="w-full text-[11px] text-sky-300/80 hover:text-sky-200 text-left truncate"
            >
              ↩ 撤销移出「{entry.item.school_name}」
            </button>
          ))}
        </div>
      )}

      {/* 底部操作 */}
      {items.length > 0 && (
        <div className="p-2.5 border-t border-white/10 flex items-center gap-2">
          <span className="text-[10px] text-white/30 flex-1">点击项展开位次对比 · 拖动手柄排序</span>
          {confirmClear ? (
            <>
              <button
                type="button"
                data-testid="confirm-clear"
                onClick={() => { void clearAll(); setConfirmClear(false); }}
                className="text-[11px] px-2 py-2 rounded-lg bg-red-500/25 text-red-200 hover:bg-red-500/35"
              >
                确认清空
              </button>
              <button
                type="button"
                onClick={() => setConfirmClear(false)}
                className="text-[11px] px-2 py-2 rounded-lg bg-white/10 text-white/60"
              >
                取消
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmClear(true)}
              className="text-white/30 hover:text-red-300 p-1.5"
              aria-label="清空"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
