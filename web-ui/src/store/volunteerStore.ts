/**
 * 我的志愿组 Zustand store（志愿编排工作台）。
 *
 * 数据一致性策略（design）：
 *  - 乐观更新收紧：加入/单改档/layout 乐观（失败回滚）；清空不乐观（等服务端）
 *  - 409 不静默：冲突时 toast 提示 + 加载最新 group
 *  - layout 串行队列：applyLayout 一次只一个 pending，连续拖动排队（不用防抖）
 *  - 延迟删除撤销：requestDelete 立即隐藏(乐观)+5秒后真DELETE，可撤销；离开页面前 flush
 */
import { create } from "zustand";
import {
  addVolunteerItem, applyVolunteerLayout, clearVolunteers, deleteVolunteerItem,
  getMyVolunteers, updateVolunteerTier,
} from "../api/client";
import type {
  ApplyLayoutRequest, HenanTargetItem, LayoutItem, UserVolunteerGroup, UserVolunteerItem,
} from "../api/types";

export interface Toast {
  id: number;
  message: string;
  type: "success" | "error" | "info";
}

const DELETE_DELAY_MS = 5000;
let _toastId = 0;
let _pendingLayoutQueue: Array<() => Promise<void>> = [];
let _loadGeneration = 0;  // loadGroup 世代令牌，防旧 GET 覆盖新写入

/**
 * 志愿组初始化状态机（生产真实竞态修复）：
 *  - idle：尚未加载（页面未挂载或刚创建 store）
 *  - loading：loadGroup 进行中（此期间禁止添加/改档，避免基于空 store 误判 isAdded）
 *  - ready：已加载最新 group，可安全写操作
 *  - error：加载失败（按钮禁用，避免在未知状态下写入）
 * 测试通过 data-ready="ready" 等待业务就绪，而非依赖元素可见。
 */
export type InitializationStatus = "idle" | "loading" | "ready" | "error";

interface VolunteerState {
  group: UserVolunteerGroup | null;
  loading: boolean;
  initializationStatus: InitializationStatus;
  saving: boolean;
  pendingLayout: boolean;
  pendingDeletes: Record<number, { item: UserVolunteerItem; timer: ReturnType<typeof setTimeout> }>;
  toasts: Toast[];

  // 操作
  loadGroup: () => Promise<void>;
  addItem: (s: HenanTargetItem, profile: Record<string, unknown>) => Promise<boolean>;
  applyLayout: (layoutItems: LayoutItem[]) => Promise<void>;
  updateTier: (itemId: number, tier: string | null) => Promise<void>;
  requestDelete: (itemId: number) => void;
  undoDelete: (itemId: number) => void;
  flushPendingDeletes: () => Promise<void>;
  clearAll: () => Promise<void>;
  isAdded: (schoolCode: string, groupCode: string) => boolean;
  /** 初始化是否完成（ready 才允许写操作） */
  isReady: () => boolean;

  // toast
  addToast: (message: string, type?: Toast["type"]) => void;
  dismissToast: (id: number) => void;

  // 内部：真正发送 DELETE（被 requestDelete 延迟调用）
  _reallyDelete: (itemId: number) => Promise<void>;
}

export const useVolunteerStore = create<VolunteerState>((set, get) => ({
  group: null,
  loading: false,
  initializationStatus: "idle",
  saving: false,
  pendingLayout: false,
  pendingDeletes: {},
  toasts: [],

  addToast: (message, type = "info") => {
    const id = ++_toastId;
    set((st) => ({ toasts: [...st.toasts, { id, message, type }] }));
    setTimeout(() => get().dismissToast(id), 3000);
  },
  dismissToast: (id) => set((st) => ({ toasts: st.toasts.filter((t) => t.id !== id) })),

  loadGroup: async () => {
    // 世代令牌：防止「旧 loadGroup 返回」覆盖「期间发生的新写入」。
    // 场景：用户网络慢，loadGroup A 在途 → 用户点 addItem B 成功（store 已更新）→
    //       A 才返回，若直接 set 会用旧 group 覆盖 B 的结果。令牌确保只有最新一次 load 生效。
    const token = ++_loadGeneration;
    set({ loading: true, initializationStatus: "loading" });
    try {
      const group = await getMyVolunteers();
      if (token !== _loadGeneration) return;  // 已被更新的 load/write 取代，丢弃
      set({ group, loading: false, initializationStatus: "ready" });
    } catch (e) {
      if (token !== _loadGeneration) return;
      set({ loading: false, initializationStatus: "error" });
      get().addToast("加载志愿组失败", "error");
    }
  },

  isReady: () => get().initializationStatus === "ready",

  addItem: async (s, profile) => {
    // 乐观更新：先在前端临时加（无 id），成功替换，失败回滚
    const prev = get().group;
    const schoolCode = s.school_code ?? "";
    const optimisticItem: UserVolunteerItem = {
      id: -1, group_id: prev?.id ?? 0,
      school_code: schoolCode, school_name: s.school_name,
      major_group_code: s.major_group_code, major_group_name: s.major_group_name ?? "",
      algorithm_tier_at_add: s.bucket ?? "需复核",
      latest_algorithm_tier: s.bucket ?? "需复核",
      algorithm_changed: false,
      planned_tier: null,
      effective_tier: s.bucket ?? "需复核",
      sort_order: prev ? prev.items.length : 0,
      eligibility_status: (s.group_eligibility_status ?? "eligible") as UserVolunteerItem["eligibility_status"],
      is_henan_local: s.is_henan_local ?? null,
      school_ownership: s.school_ownership ?? null,
      four_year_total: s.four_year_total ?? null,
    };
    if (prev) {
      set({ group: { ...prev, items: [...prev.items, optimisticItem] } });
    }
    set({ saving: true });
    try {
      const result = await addVolunteerItem({
        school_code: schoolCode, major_group_code: s.major_group_code, profile,
      });
      if (result.ok) {
        _loadGeneration++;  // 本次写入已更新 store，使任何在途的旧 loadGroup 失效（防覆盖）
        set({ group: result.group, saving: false, initializationStatus: "ready" });
        get().addToast("已加入志愿组", "success");
        return true;
      }
      // 409 冲突：加载最新 + 提示（不静默）
      set({ group: prev, saving: false });
      if (result.conflict.latest_group) {
        _loadGeneration++;
        set({ group: result.conflict.latest_group, initializationStatus: "ready" });
      }
      get().addToast("志愿组已在其他页面更新，已加载最新版本", "info");
      return false;
    } catch (e) {
      set({ group: prev, saving: false });  // 回滚
      get().addToast(e instanceof Error ? e.message : "加入失败", "error");
      return false;
    }
  },

  applyLayout: async (layoutItems) => {
    const cur = get().group;
    if (!cur) return;
    // 乐观更新：立即按 layout 重排前端
    const byId = new Map(cur.items.map((it) => [it.id, it]));
    const reordered = layoutItems
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((li) => {
        const it = byId.get(li.item_id);
        if (!it) return null;
        return { ...it, planned_tier: li.planned_tier, effective_tier: li.planned_tier ?? it.latest_algorithm_tier, sort_order: li.sort_order };
      })
      .filter((x): x is UserVolunteerItem => x !== null);
    set({ group: { ...cur, items: reordered } });

    // 串行队列：一次只一个 pending layout 提交
    const submit = async () => {
      const g = get().group;
      if (!g) return;
      const req: ApplyLayoutRequest = { items: layoutItems, version: g.version };
      const result = await applyVolunteerLayout(req);
      if (result.ok) {
        _loadGeneration++;
        set({ group: result.group, initializationStatus: "ready" });
      } else {
        if (result.conflict.latest_group) {
          _loadGeneration++;
          set({ group: result.conflict.latest_group, initializationStatus: "ready" });
        }
        get().addToast("志愿组已在其他页面更新，已加载最新版本", "info");
      }
    };
    _pendingLayoutQueue.push(submit);
    if (!get().pendingLayout) {
      set({ pendingLayout: true });
      while (_pendingLayoutQueue.length > 0) {
        const task = _pendingLayoutQueue.shift()!;
        try {
          await task();
        } catch {
          // 单个失败不阻塞队列
        }
      }
      set({ pendingLayout: false });
    }
  },

  updateTier: async (itemId, tier) => {
    const cur = get().group;
    if (!cur) return;
    const prev = cur;
    // 乐观更新
    const items = cur.items.map((it) =>
      it.id === itemId
        ? { ...it, planned_tier: tier, effective_tier: tier ?? it.latest_algorithm_tier }
        : it,
    );
    set({ group: { ...cur, items } });
    try {
      const result = await updateVolunteerTier(itemId, tier, prev.version);
      if (result.ok) {
        _loadGeneration++;
        set({ group: result.group, initializationStatus: "ready" });
      } else {
        if (result.conflict.latest_group) {
          _loadGeneration++;
          set({ group: result.conflict.latest_group, initializationStatus: "ready" });
        }
        get().addToast("志愿组已在其他页面更新，已加载最新版本", "info");
      }
    } catch (e) {
      set({ group: prev });  // 回滚
      get().addToast(e instanceof Error ? e.message : "调整失败", "error");
    }
  },

  requestDelete: (itemId) => {
    const cur = get().group;
    if (!cur) return;
    const item = cur.items.find((it) => it.id === itemId);
    if (!item) return;
    // 乐观：立即从前端移除
    set({ group: { ...cur, items: cur.items.filter((it) => it.id !== itemId) } });
    // 延迟真删 + 撤销窗口
    const timer = setTimeout(() => {
      void get()._reallyDelete(itemId);
    }, DELETE_DELAY_MS);
    set((st) => ({
      pendingDeletes: { ...st.pendingDeletes, [itemId]: { item, timer } },
    }));
    get().addToast("已移出志愿组", "info");
  },

  undoDelete: (itemId) => {
    const { pendingDeletes, group } = get();
    const entry = pendingDeletes[itemId];
    if (!entry || !group) return;
    clearTimeout(entry.timer);
    // 恢复到原位置（按 sort_order）
    const items = [...group.items, entry.item].sort((a, b) => a.sort_order - b.sort_order);
    const newPending = { ...pendingDeletes };
    delete newPending[itemId];
    set({ group: { ...group, items }, pendingDeletes: newPending });
    get().addToast("已撤销删除", "success");
  },

  flushPendingDeletes: async () => {
    const ids = Object.keys(get().pendingDeletes).map(Number);
    await Promise.all(ids.map((id) => get()._reallyDelete(id)));
  },

  clearAll: async () => {
    // 不乐观更新：等服务端成功
    const cur = get().group;
    if (!cur) return;
    set({ saving: true });
    try {
      const result = await clearVolunteers(cur.version);
      if (result.ok) {
        _loadGeneration++;
        set({ group: result.group, saving: false, initializationStatus: "ready" });
        get().addToast("已清空志愿组", "success");
      } else {
        if (result.conflict.latest_group) {
          _loadGeneration++;
          set({ group: result.conflict.latest_group, initializationStatus: "ready" });
        }
        set({ saving: false });
        get().addToast("志愿组已在其他页面更新，已加载最新版本", "info");
      }
    } catch (e) {
      set({ saving: false });
      get().addToast(e instanceof Error ? e.message : "清空失败", "error");
    }
  },

  isAdded: (schoolCode, groupCode) => {
    const g = get().group;
    if (!g) return false;
    return g.items.some(
      (it) => it.school_code === schoolCode && it.major_group_code === groupCode,
    );
  },

  // 内部：真正发送 DELETE（被 requestDelete 延迟调用）
  _reallyDelete: async (itemId: number) => {
    const cur = get().group;
    const entry = get().pendingDeletes[itemId];
    if (!cur || !entry) return;
    // 用乐观移除前的 version（移除是乐观的，服务端 version 还没变）
    try {
      const result = await deleteVolunteerItem(itemId, cur.version);
      if (result.ok) {
        _loadGeneration++;
        set({ group: result.group, initializationStatus: "ready" });
      } else {
        if (result.conflict.latest_group) {
          _loadGeneration++;
          set({ group: result.conflict.latest_group, initializationStatus: "ready" });
        }
        get().addToast("志愿组已在其他页面更新，已加载最新版本", "info");
      }
    } catch {
      get().addToast("删除失败", "error");
    } finally {
      set((st) => {
        const np = { ...st.pendingDeletes };
        delete np[itemId];
        return { pendingDeletes: np };
      });
    }
  },
}));
