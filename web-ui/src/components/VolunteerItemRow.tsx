import { useState } from "react";
import { GripVertical, MoreVertical, Trash2, RefreshCw } from "lucide-react";
import type { UserVolunteerItem } from "../api/types";
import { useVolunteerStore } from "../store/volunteerStore";
import {
  OWNERSHIP_STYLE, PLANNABLE_TIERS, TIER_STYLE,
} from "./volunteerTier";

interface Props {
  item: UserVolunteerItem;
  index: number;
  /** 是否启用 @dnd-kit 拖拽（Dock 用；非拖拽模式不渲染手柄） */
  dragHandleProps?: Record<string, unknown>;
  compact?: boolean;
}

/**
 * 志愿项行（精简单行，抄 48 志愿草案行风格）。
 * - 档位徽章：effective_tier（规划优先），算法档位小字标注
 * - 待复核/部分可报 特殊标识
 * - 更多菜单：调整规划档位、删除、恢复算法档位
 */
export default function VolunteerItemRow({ item, index, dragHandleProps, compact }: Props) {
  const updateTier = useVolunteerStore((s) => s.updateTier);
  const requestDelete = useVolunteerStore((s) => s.requestDelete);
  const [menuOpen, setMenuOpen] = useState(false);

  const tierStyle = TIER_STYLE[item.effective_tier] ?? "bg-white/10 text-white/50";
  const ownership = item.school_ownership ?? "";
  const needReview = item.eligibility_status === "uncertain";
  const partialElig = item.eligibility_status === "partially_eligible";

  return (
    <div className="glass rounded-lg p-2.5 text-xs flex items-center gap-2 group">
      {/* 拖拽手柄（仅 dnd-kit 模式） */}
      {dragHandleProps && (
        <button
          type="button"
          className="cursor-grab active:cursor-grabbing text-white/30 hover:text-white/60 touch-none shrink-0"
          aria-label="拖动排序"
          {...dragHandleProps}
        >
          <GripVertical className="w-4 h-4" />
        </button>
      )}
      <span className="w-5 h-5 rounded bg-white/10 text-white/60 font-mono text-[11px] tabular-nums flex items-center justify-center shrink-0">
        {index + 1}
      </span>
      <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded shrink-0 ${tierStyle}`}>
        {item.effective_tier}
      </span>
      {/* 待复核/部分可报 标识 */}
      {needReview && (
        <span className="text-[10px] px-1 py-0.5 rounded bg-amber-500/15 text-amber-200/80 shrink-0">待复核</span>
      )}
      {partialElig && (
        <span className="text-[10px] px-1 py-0.5 rounded bg-amber-500/15 text-amber-200/80 shrink-0">部分专业可报</span>
      )}
      <div className="min-w-0 flex-1">
        <div className="font-bold truncate text-white/90">{item.school_name}</div>
        {!compact && (
          <div className="text-white/40 truncate">{item.major_group_name || item.major_group_code}</div>
        )}
      </div>
      {/* 算法档位（小字，规划≠算法时提示） */}
      {item.planned_tier && item.planned_tier !== item.latest_algorithm_tier && (
        <span className="text-[10px] text-white/35 shrink-0">算法{item.latest_algorithm_tier}</span>
      )}
      {/* 学校性质 */}
      {ownership && !compact && (
        <span className={`text-[10px] px-1 py-0.5 rounded shrink-0 ${OWNERSHIP_STYLE[ownership] ?? "bg-white/10 text-white/50"}`}>
          {ownership}
        </span>
      )}
      {!compact && (
        <span className="text-[10px] text-white/40 shrink-0">{item.is_henan_local ? "省内" : "省外"}</span>
      )}
      {/* 更多菜单 */}
      <div className="relative shrink-0">
        <button
          type="button"
          onClick={() => setMenuOpen((v) => !v)}
          className="text-white/30 hover:text-white/60 p-0.5"
          aria-label="更多操作"
        >
          <MoreVertical className="w-3.5 h-3.5" />
        </button>
        {menuOpen && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
            <div className="absolute right-0 top-6 z-50 w-44 glass rounded-lg p-1 shadow-xl text-[12px]">
              {/* 调整规划档位 */}
              <div className="px-2 py-1 text-white/40 text-[10px]">规划档位</div>
              {PLANNABLE_TIERS.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => {
                    void updateTier(item.id, t);
                    setMenuOpen(false);
                  }}
                  className={`w-full text-left px-2 py-1 rounded hover:bg-white/10 ${
                    item.planned_tier === t ? "text-white/90 bg-white/5" : "text-white/60"
                  }`}
                >
                  {t}{item.planned_tier === t ? " ✓" : ""}
                </button>
              ))}
              {/* 恢复算法档位 */}
              {item.planned_tier && (
                <button
                  type="button"
                  onClick={() => {
                    void updateTier(item.id, null);
                    setMenuOpen(false);
                  }}
                  className="w-full text-left px-2 py-1 rounded hover:bg-white/10 text-white/60 flex items-center gap-1"
                >
                  <RefreshCw className="w-3 h-3" />恢复算法档位
                </button>
              )}
              <div className="border-t border-white/10 my-1" />
              <button
                type="button"
                onClick={() => {
                  requestDelete(item.id);
                  setMenuOpen(false);
                }}
                className="w-full text-left px-2 py-1 rounded hover:bg-red-500/15 text-red-300/80 flex items-center gap-1"
              >
                <Trash2 className="w-3 h-3" />移出志愿组
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
