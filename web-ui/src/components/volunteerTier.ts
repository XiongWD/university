/**
 * 志愿编排工作台共享：档位样式 + 文案 + 校验。
 * 供 VolunteerItemRow / VolunteerDock / MyGroupsPage 复用，避免配色漂移。
 */

/** 档位徽章配色（与 HenanItemCard 统一，颜色+文字共同表达，色弱友好） */
export const TIER_STYLE: Record<string, string> = {
  超冲: "bg-rose-500/20 text-rose-300",
  搏: "bg-orange-500/20 text-orange-300",
  冲: "bg-amber-500/20 text-amber-300",
  稳: "bg-emerald-500/20 text-emerald-300",
  保: "bg-sky-500/20 text-sky-300",
  垫: "bg-indigo-500/20 text-indigo-300",
  需人工复核: "bg-white/10 text-white/50",
  不推荐: "bg-red-700/30 text-red-200",
};

/** 学校性质徽章色 */
export const OWNERSHIP_STYLE: Record<string, string> = {
  公办: "bg-sky-500/20 text-sky-300",
  民办: "bg-amber-500/20 text-amber-300",
  中外合作: "bg-fuchsia-500/20 text-fuchsia-300",
  独立学院: "bg-purple-500/20 text-purple-300",
};

/** 可设置的规划档位（planned_tier 白名单，不含数据状态） */
export const PLANNABLE_TIERS = ["搏", "冲", "稳", "保", "垫"] as const;

/** 档位排序权重（从难到易，用于分区顺序） */
export const TIER_ORDER: Record<string, number> = {
  搏: 0, 冲: 1, 稳: 2, 保: 3, 垫: 4,
};

/** 判断档位是否属于规划可选项 */
export function isPlannable(tier: string | null | undefined): tier is "搏" | "冲" | "稳" | "保" | "垫" {
  return tier !== null && tier !== undefined && (PLANNABLE_TIERS as readonly string[]).includes(tier);
}
