import { beforeEach, describe, expect, it, vi } from "vitest";
import { useVolunteerStore } from "./volunteerStore";
import type { HenanTargetItem, UserVolunteerGroup, UserVolunteerItem } from "../api/types";

// mock client API（store 单测不依赖真实网络，专注数据一致性逻辑）
vi.mock("../api/client", () => ({
  getMyVolunteers: vi.fn(),
  addVolunteerItem: vi.fn(),
  applyVolunteerLayout: vi.fn(),
  updateVolunteerTier: vi.fn(),
  deleteVolunteerItem: vi.fn(),
  clearVolunteers: vi.fn(),
}));

import {
  addVolunteerItem, applyVolunteerLayout, clearVolunteers, deleteVolunteerItem,
  getMyVolunteers, updateVolunteerTier,
} from "../api/client";

const mockItem = (over: Partial<UserVolunteerItem> = {}): UserVolunteerItem => ({
  id: 1, group_id: 1, school_code: "2535", school_name: "测试大学",
  major_group_code: "G1", major_group_name: "测试大学-G1",
  algorithm_tier_at_add: "稳", latest_algorithm_tier: "稳",
  algorithm_changed: false, planned_tier: null, effective_tier: "稳",
  sort_order: 0, eligibility_status: "eligible",
  is_henan_local: false, school_ownership: "公办", four_year_total: 40000,
  ...over,
});

const mockGroup = (items: UserVolunteerItem[] = []): UserVolunteerGroup => ({
  id: 1, owner_key: "default", name: "我的志愿组", version: 1,
  manually_reordered: false, profile_snapshot: {}, items,
  stats: {
    total: items.length,
    by_effective_tier: {}, by_algorithm_tier: {},
    local_count: 0, out_of_province_count: 0,
    public_count: 0, private_count: 0, structure_hints: [],
  },
});

const targetItem: HenanTargetItem = {
  school_name: "测试大学", school_code: "2535", major_group_code: "G1",
  major_name: "测试专业", major_group_name: "测试大学-G1", bucket: "稳",
  group_eligibility_status: "eligible",
  is_henan_local: false, school_ownership: "公办", four_year_total: 40000,
};

beforeEach(() => {
  vi.clearAllMocks();
  useVolunteerStore.setState({
    group: null, loading: false, initializationStatus: "idle", saving: false, pendingLayout: false,
    pendingDeletes: {}, toasts: [],
  });
});

describe("volunteerStore", () => {
  it("loadGroup 成功加载", async () => {
    vi.mocked(getMyVolunteers).mockResolvedValue(mockGroup([mockItem()]));
    await useVolunteerStore.getState().loadGroup();
    expect(useVolunteerStore.getState().group?.items.length).toBe(1);
    expect(useVolunteerStore.getState().loading).toBe(false);
  });

  it("addItem 成功：乐观加入后替换为服务端结果", async () => {
    // 初始有1个，加第2个
    const g0 = mockGroup([mockItem({ id: 1 })]);
    vi.mocked(getMyVolunteers).mockResolvedValue(g0);
    await useVolunteerStore.getState().loadGroup();

    const g1 = mockGroup([mockItem({ id: 1 }), mockItem({ id: 2, sort_order: 1 })]);
    vi.mocked(addVolunteerItem).mockResolvedValue({ ok: true, group: g1 });

    const ok = await useVolunteerStore.getState().addItem(targetItem, { score: 480 });
    expect(ok).toBe(true);
    expect(useVolunteerStore.getState().group?.items.length).toBe(2);
  });

  it("addItem 失败：回滚到添加前状态", async () => {
    const g0 = mockGroup([mockItem({ id: 1 })]);
    vi.mocked(getMyVolunteers).mockResolvedValue(g0);
    await useVolunteerStore.getState().loadGroup();

    vi.mocked(addVolunteerItem).mockRejectedValue(new Error("资格不符"));
    const ok = await useVolunteerStore.getState().addItem(targetItem, {});
    expect(ok).toBe(false);
    // 回滚：仍是1个
    expect(useVolunteerStore.getState().group?.items.length).toBe(1);
  });

  it("addItem 409 冲突：加载最新 + 不静默", async () => {
    vi.mocked(getMyVolunteers).mockResolvedValue(mockGroup([]));
    await useVolunteerStore.getState().loadGroup();

    const latest = mockGroup([mockItem({ id: 9 })]);
    vi.mocked(addVolunteerItem).mockResolvedValue({
      ok: false, conflict: { error: "version_conflict", message: "已更新", latest_group: latest },
    });
    await useVolunteerStore.getState().addItem(targetItem, {});
    // 加载了最新 group
    expect(useVolunteerStore.getState().group?.items[0]?.id).toBe(9);
  });

  it("isAdded：去重判断（同校同组视为已加入）", async () => {
    vi.mocked(getMyVolunteers).mockResolvedValue(mockGroup([mockItem({ school_code: "2535", major_group_code: "G1" })]));
    await useVolunteerStore.getState().loadGroup();
    expect(useVolunteerStore.getState().isAdded("2535", "G1")).toBe(true);
    expect(useVolunteerStore.getState().isAdded("2535", "G2")).toBe(false);
    expect(useVolunteerStore.getState().isAdded("9999", "G1")).toBe(false);
  });

  it("updateTier：乐观更新 planned_tier，effective_tier 跟随", async () => {
    vi.mocked(getMyVolunteers).mockResolvedValue(mockGroup([mockItem({ id: 1, latest_algorithm_tier: "稳" })]));
    await useVolunteerStore.getState().loadGroup();

    const updated = mockGroup([mockItem({ id: 1, planned_tier: "冲", effective_tier: "冲" })]);
    vi.mocked(updateVolunteerTier).mockResolvedValue({ ok: true, group: updated });

    await useVolunteerStore.getState().updateTier(1, "冲");
    // 乐观：立即看到冲档
    expect(useVolunteerStore.getState().group?.items[0].planned_tier).toBe("冲");
    expect(useVolunteerStore.getState().group?.items[0].effective_tier).toBe("冲");
  });

  it("requestDelete + undoDelete：乐观移除 + 撤销恢复", async () => {
    vi.useFakeTimers();
    vi.mocked(getMyVolunteers).mockResolvedValue(mockGroup([mockItem({ id: 1 })]));
    await useVolunteerStore.getState().loadGroup();

    useVolunteerStore.getState().requestDelete(1);
    // 乐观：立即移除
    expect(useVolunteerStore.getState().group?.items.length).toBe(0);
    expect(useVolunteerStore.getState().pendingDeletes[1]).toBeDefined();

    // 撤销：恢复
    useVolunteerStore.getState().undoDelete(1);
    expect(useVolunteerStore.getState().group?.items.length).toBe(1);
    expect(useVolunteerStore.getState().pendingDeletes[1]).toBeUndefined();

    vi.useRealTimers();
  });

  it("requestDelete 延迟后真删（flushPendingDeletes）", async () => {
    vi.mocked(getMyVolunteers).mockResolvedValue(mockGroup([mockItem({ id: 1 })]));
    await useVolunteerStore.getState().loadGroup();

    vi.mocked(deleteVolunteerItem).mockResolvedValue({ ok: true, group: mockGroup([]) });
    useVolunteerStore.getState().requestDelete(1);
    expect(useVolunteerStore.getState().pendingDeletes[1]).toBeDefined();

    // flush 立即触发真删
    await useVolunteerStore.getState().flushPendingDeletes();
    expect(deleteVolunteerItem).toHaveBeenCalledWith(1, 1);
    expect(useVolunteerStore.getState().pendingDeletes[1]).toBeUndefined();
  });

  it("clearAll：不乐观，等服务端成功", async () => {
    vi.mocked(getMyVolunteers).mockResolvedValue(mockGroup([mockItem({ id: 1 })]));
    await useVolunteerStore.getState().loadGroup();

    vi.mocked(clearVolunteers).mockResolvedValue({ ok: true, group: mockGroup([]) });
    await useVolunteerStore.getState().clearAll();
    // 服务端成功后才清空
    expect(useVolunteerStore.getState().group?.items.length).toBe(0);
  });

  it("applyLayout：乐观重排 + 提交", async () => {
    vi.mocked(getMyVolunteers).mockResolvedValue(mockGroup([
      mockItem({ id: 1, sort_order: 0 }), mockItem({ id: 2, sort_order: 1, school_name: "B大学" }),
    ]));
    await useVolunteerStore.getState().loadGroup();

    const reordered = mockGroup([
      mockItem({ id: 2, sort_order: 0, school_name: "B大学" }), mockItem({ id: 1, sort_order: 1 }),
    ]);
    vi.mocked(applyVolunteerLayout).mockResolvedValue({ ok: true, group: reordered });

    await useVolunteerStore.getState().applyLayout([
      { item_id: 2, planned_tier: null, sort_order: 0 },
      { item_id: 1, planned_tier: null, sort_order: 1 },
    ]);
    // 乐观：立即看到顺序交换
    expect(useVolunteerStore.getState().group?.items[0].id).toBe(2);
    expect(applyVolunteerLayout).toHaveBeenCalled();
  });
});
