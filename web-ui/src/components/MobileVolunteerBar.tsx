import { useState } from "react";
import { Layers, X, ChevronRight } from "lucide-react";
import { useVolunteerStore } from "../store/volunteerStore";
import { TIER_STYLE } from "./volunteerTier";

/**
 * 移动端底部志愿栏（< md 显示）。
 * 固定底部栏显示数量+档位，点击弹全屏抽屉（查看 + 跳转编排页，不做复杂拖拽）。
 * 桌面端由 VolunteerDock 接管，本组件 md:hidden。
 */
export default function MobileVolunteerBar() {
  const group = useVolunteerStore((s) => s.group);
  const [open, setOpen] = useState(false);

  const items = group?.items ?? [];
  const stats = group?.stats;
  if (!group || items.length === 0) return null;

  return (
    <>
      {/* 底部固定栏 */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="md:hidden fixed bottom-0 inset-x-0 z-30 h-14 glass border-t border-white/15 flex items-center gap-2 px-4"
      >
        <Layers className="w-4 h-4 text-indigo-300" />
        <span className="text-sm font-bold text-white/90">我的志愿组</span>
        <span className="text-xs text-white/40">{items.length}/48</span>
        {/* 档位紧凑统计 */}
        <div className="ml-auto flex items-center gap-1">
          {(["搏", "冲", "稳", "保", "垫"] as const).map((t) => {
            const n = (stats?.by_effective_tier[t] ?? 0);
            if (n === 0) return null;
            return (
              <span key={t} className={`text-[10px] px-1 py-0.5 rounded ${TIER_STYLE[t]}`}>{t}{n}</span>
            );
          })}
          <ChevronRight className="w-4 h-4 text-white/40" />
        </div>
      </button>

      {/* 全屏抽屉 */}
      {open && (
        <div className="md:hidden fixed inset-0 z-50 flex flex-col bg-slate-950/95 backdrop-blur-md">
          <div className="flex items-center gap-2 p-4 border-b border-white/10">
            <Layers className="w-4 h-4 text-indigo-300" />
            <span className="font-bold text-white/90">我的志愿组</span>
            <span className="text-xs text-white/40">{items.length}/48</span>
            <button type="button" onClick={() => setOpen(false)} className="ml-auto text-white/40 hover:text-white/70 p-1">
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
            {items.map((it, i) => (
              <div key={it.id} className="glass rounded-lg p-2.5 text-xs flex items-center gap-2">
                <span className="w-5 h-5 rounded bg-white/10 text-white/60 font-mono text-[11px] flex items-center justify-center shrink-0">{i + 1}</span>
                <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded shrink-0 ${TIER_STYLE[it.effective_tier] ?? "bg-white/10 text-white/50"}`}>
                  {it.effective_tier}
                </span>
                <span className="font-bold text-white/90 truncate flex-1">{it.school_name}</span>
                <span className="text-white/40 shrink-0">{it.school_ownership}</span>
              </div>
            ))}
          </div>
          <div className="p-3 border-t border-white/10">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="w-full text-sm py-2.5 rounded-lg bg-indigo-500/25 text-indigo-200 hover:bg-indigo-500/35 font-medium"
            >
              完成
            </button>
          </div>
        </div>
      )}
    </>
  );
}
