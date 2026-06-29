import { useEffect } from "react";
import { useVolunteerStore } from "../store/volunteerStore";

/**
 * 志愿编排页（占位，Commit 3 完善 @dnd-kit 多容器拖拽 + 分区 + 风险提示）。
 * 当前仅展示志愿项只读列表 + 统计，供路由联通验证。
 */
export default function MyGroupsPage() {
  const group = useVolunteerStore((s) => s.group);
  const loadGroup = useVolunteerStore((s) => s.loadGroup);
  const flushPendingDeletes = useVolunteerStore((s) => s.flushPendingDeletes);

  useEffect(() => {
    void loadGroup();
    return () => { void flushPendingDeletes(); };
  }, [loadGroup, flushPendingDeletes]);

  const items = group?.items ?? [];
  const stats = group?.stats;

  return (
    <div className="space-y-4">
      <div className="glass rounded-3xl p-6 shadow-xl">
        <h1 className="text-xl font-bold text-white/90">志愿编排</h1>
        <p className="text-sm text-white/50 mt-1">
          按规划档位编排你的志愿顺序。拖拽排序、调整档位、查看结构风险。
          {items.length > 0 && <span className="ml-1">当前 {items.length}/48 个志愿。</span>}
        </p>
      </div>

      {stats && stats.structure_hints.length > 0 && (
        <div className="glass rounded-2xl p-4 border border-amber-400/30 space-y-1.5">
          <p className="text-sm font-medium text-amber-200">📋 结构提示（参考，非官方要求）</p>
          {stats.structure_hints.map((h) => (
            <div key={h.code} className="text-xs text-amber-200/80">
              {h.severity === "warning" ? "⚠ " : "• "}{h.message}
            </div>
          ))}
        </div>
      )}

      {items.length === 0 ? (
        <div className="glass rounded-2xl p-8 text-center text-white/40">
          志愿组为空。去「志愿推荐」页加入院校专业组。
        </div>
      ) : (
        <div className="glass rounded-2xl p-4 space-y-1.5">
          {items.map((it, i) => (
            <div key={it.id} className="text-xs flex items-center gap-2 p-2 rounded-lg bg-white/5">
              <span className="w-5 h-5 rounded bg-white/10 text-white/60 font-mono text-[11px] flex items-center justify-center">{i + 1}</span>
              <span className="font-bold px-1.5 py-0.5 rounded bg-white/10 text-white/70">{it.effective_tier}</span>
              <span className="font-bold text-white/90 truncate flex-1">{it.school_name}</span>
              <span className="text-white/40">{it.major_group_name}</span>
            </div>
          ))}
          <p className="text-[11px] text-white/30 pt-2 text-center">
            完整拖拽编排功能开发中（Commit 3）。
          </p>
        </div>
      )}
    </div>
  );
}
