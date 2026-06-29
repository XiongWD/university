import { useRef, useState } from "react";
import { GripVertical, MoreVertical, Trash2, RefreshCw, ChevronDown, ChevronRight, Wallet } from "lucide-react";
import type { UserVolunteerItem } from "../api/types";
import { useVolunteerStore } from "../store/volunteerStore";
import { fmtMoney, fmtRank } from "./HenanItemCard";
import { OWNERSHIP_STYLE, PLANNABLE_TIERS, TIER_STYLE } from "./volunteerTier";

interface Props {
  item: UserVolunteerItem;
  index: number;
  /** 是否启用 @dnd-kit 拖拽（Dock 用；非拖拽模式不渲染手柄） */
  dragHandleProps?: Record<string, unknown>;
}

/** 志愿项行（中等密度 + 可展开详情）。支持对比决策（学费/位次/计算公式）。 */
export default function VolunteerItemRow({ item, index, dragHandleProps }: Props) {
  const updateTier = useVolunteerStore((s) => s.updateTier);
  const requestDelete = useVolunteerStore((s) => s.requestDelete);
  const [menuOpen, setMenuOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  // 菜单 fixed 定位（脱离 Dock overflow 容器，防裁剪看不见）
  const menuBtnRef = useRef<HTMLButtonElement>(null);
  const [menuPos, setMenuPos] = useState<{ top: number; right: number } | null>(null);

  const openMenu = () => {
    const rect = menuBtnRef.current?.getBoundingClientRect();
    if (rect) {
      // 菜单宽 176px(w-44)，右对齐按钮右边缘，顶部在按钮下方
      setMenuPos({ top: rect.bottom + 4, right: window.innerWidth - rect.right });
    }
    setMenuOpen((v) => !v);
  };

  const tierStyle = TIER_STYLE[item.effective_tier] ?? "bg-white/10 text-white/50";
  const ownership = item.school_ownership ?? "";
  const needReview = item.eligibility_status === "uncertain";
  const partialElig = item.eligibility_status === "partially_eligible";
  const algoChanged = item.algorithm_changed;
  const majors = item.selected_majors ?? [];

  return (
    <div className="glass rounded-lg p-2.5 text-xs group">
      <div className="flex items-center gap-2">
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
        {/* 展开切换 */}
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-white/30 hover:text-white/60 shrink-0"
          aria-label={expanded ? "收起详情" : "展开详情"}
        >
          {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </button>
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
          <span className="text-[10px] px-1 py-0.5 rounded bg-amber-500/15 text-amber-200/80 shrink-0">部分可报</span>
        )}
        {/* 更多菜单（fixed 定位，脱离 Dock overflow 容器，防裁剪看不见） */}
        <div className="relative ml-auto shrink-0">
          <button
            type="button"
            data-testid="item-menu"
            ref={menuBtnRef}
            onClick={openMenu}
            className="text-white/30 hover:text-white/60 p-0.5"
            aria-label="更多操作"
          >
            <MoreVertical className="w-3.5 h-3.5" />
          </button>
          {menuOpen && menuPos && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
              <div
                data-testid="item-menu-panel"
                className="fixed z-50 w-44 glass rounded-lg p-1 shadow-xl text-[12px]"
                style={{ top: menuPos.top, right: menuPos.right }}
              >
                <div className="px-2 py-1 text-white/40 text-[10px]">规划档位</div>
                {PLANNABLE_TIERS.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => { void updateTier(item.id, t); setMenuOpen(false); }}
                    className={`w-full text-left px-2 py-1 rounded hover:bg-white/10 ${
                      item.planned_tier === t ? "text-white/90 bg-white/5" : "text-white/60"
                    }`}
                  >
                    {t}{item.planned_tier === t ? " ✓" : ""}
                  </button>
                ))}
                {item.planned_tier && (
                  <button
                    type="button"
                    onClick={() => { void updateTier(item.id, null); setMenuOpen(false); }}
                    className="w-full text-left px-2 py-1 rounded hover:bg-white/10 text-white/60 flex items-center gap-1"
                  >
                    <RefreshCw className="w-3 h-3" />恢复算法档位
                  </button>
                )}
                <div className="border-t border-white/10 my-1" />
                <button
                  type="button"
                  data-testid="remove-item"
                  onClick={() => { requestDelete(item.id); setMenuOpen(false); }}
                  className="w-full text-left px-2 py-1 rounded hover:bg-red-500/15 text-red-300/80 flex items-center gap-1"
                >
                  <Trash2 className="w-3 h-3" />移出志愿组
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* 主信息行：校名 + 专业组代码 */}
      <div className="mt-1 flex items-baseline gap-1.5 flex-wrap">
        <span className="font-bold text-white/90">{item.school_name}</span>
        <span className="text-white/40">{item.major_group_code}</span>
        {item.school_city && <span className="text-white/35 text-[10px]">{item.school_city}</span>}
      </div>

      {/* 费用 + 性质（对比核心信息，始终显示） */}
      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-white/50">
        {ownership && (
          <span className={`px-1 py-0.5 rounded ${OWNERSHIP_STYLE[ownership] ?? "bg-white/10 text-white/50"}`}>{ownership}</span>
        )}
        <span>{item.is_henan_local ? "省内" : "省外"}</span>
        {typeof item.tuition_per_year === "number" && (
          <span className="flex items-center gap-0.5">
            <Wallet className="w-3 h-3 text-emerald-300/60" />
            {fmtMoney(item.tuition_per_year)}/年
          </span>
        )}
        {typeof item.four_year_total === "number" && (
          <span>4年≈<b className="text-amber-300/90">{fmtMoney(item.four_year_total)}</b></span>
        )}
        {typeof item.plan_count === "number" && <span>计划{item.plan_count}人</span>}
      </div>

      {/* 组内专业（始终显示，截断） */}
      {majors.length > 0 && (
        <div className="mt-0.5 text-white/40 truncate">组内专业：{majors.join("、")}</div>
      )}

      {/* 算法档位变化提示 */}
      {algoChanged && (
        <div className="mt-0.5 text-[10px] text-amber-200/70">
          算法参考档位：{item.latest_algorithm_tier}（添加时为{item.algorithm_tier_at_add}）
        </div>
      )}

      {/* 展开详情：位次对比 + 计算公式 */}
      {expanded && (typeof item.student_rank === "number" || typeof item.reference_rank === "number") && (
        <div className="mt-1.5 pt-1.5 border-t border-white/10 text-[10px] text-white/50 space-y-0.5 font-mono">
          <div>
            考生位次 <b className="text-white/80">{fmtRank(item.student_rank)}</b>
            {typeof item.reference_rank === "number" && (
              <>
                {" "}· {item.baseline_year ?? ""}年录取位次 <b className="text-white/80">{fmtRank(item.reference_rank)}</b>
              </>
            )}
          </div>
          {typeof item.advantage === "number" && (
            <div>
              位次优势 = {item.reference_rank ?? "?"} − {item.student_rank ?? "?"} =
              <b className={item.advantage >= 0 ? "text-sky-300" : "text-orange-300"}>
                {" "}{item.advantage >= 0 ? "+" : ""}{item.advantage.toLocaleString("zh-CN")}
              </b>
              {typeof item.advantage_ratio === "number" && (
                <span className="text-white/40">（{(item.advantage_ratio * 100).toFixed(1)}%，负=目标更难）</span>
              )}
            </div>
          )}
          {item.risk_level && <div className="text-white/40">风险等级：{item.risk_level}</div>}
        </div>
      )}
    </div>
  );
}
