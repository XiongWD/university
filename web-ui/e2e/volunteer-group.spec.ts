import { test, expect, type Page } from "@playwright/test";

// 我的志愿组（志愿编排工作台）端到端验收。
// 前置：后端 8000（含 my-volunteers 路由）+ 前端 5173 已启动。
// UI 元素用 data-testid 定位（稳定），关键状态用 API 验证。

const BACKEND = "http://127.0.0.1:8000/api/v1/my-volunteers";
const PROFILE = {
  source_province: "河南", score: 480, rank: 60000, track: "历史类",
  primary_subject: "历史", elective_subjects: ["政治", "地理"], exam_foreign_language: "日语",
};

async function clearGroup() {
  // 清空志愿组。clear 受 version 乐观锁保护，若上个测试的延迟删除/写入导致版本漂移，
  // 后端返回 409（不清空）→ 重取最新 version 重试，直到确认清空，杜绝测试间数据污染。
  for (let attempt = 0; attempt < 5; attempt++) {
    const g = await (await fetch(`${BACKEND}`)).json();
    const res = await fetch(`${BACKEND}/clear`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true, version: g.version }),
    });
    if (res.ok) {
      // 确认后端已清空（应对延迟删除窗口）
      await expect.poll(async () => await getItemCount(), { timeout: 5000, intervals: [200] }).toBe(0);
      return;
    }
    // 409 冲突 → 短暂等待后重试（取最新 version）
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error("clearGroup: 5 次重试仍未清空（后端持续冲突）");
}

async function getItemCount(): Promise<number> {
  const res = await fetch(`${BACKEND}`);
  const g = await res.json();
  return g.items?.length ?? 0;
}

async function submitRecommendation(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /生成志愿表|生成中/ }).click();
  await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 20000 });
  // 等 dock-count 渲染（App.useEffect 的 loadGroup 已触发并完成首屏渲染）。
  // beforeAll 的 clearGroup 已确保后端为空且 version 最新，此处前端 store 加载到的即为干净状态。
  await expect(page.getByTestId("dock-count")).toBeVisible({ timeout: 5000 });
  // 等至少一张「加入志愿组」按钮就绪（推荐卡片已完整渲染、可点击），
  // 避免在卡片异步渲染/排序过程中点击导致「已加入志愿组」toast 不触发。
  await expect(page.getByTestId("add-volunteer").first()).toBeVisible({ timeout: 10000 });
}

/** dock 数量（testid 定位，唯一稳定） */
const dockCount = (page: Page) => page.getByTestId("dock-count");

test.describe("我的志愿组（志愿编排工作台）", () => {
  test.beforeEach(async () => { await clearGroup(); });

  test("提交推荐后显示志愿组悬浮窗", async ({ page }) => {
    await submitRecommendation(page);
    await expect(page.getByText("我的志愿组").first()).toBeVisible();
    await expect(dockCount(page)).toContainText("0/48");
  });

  test("点击「加入志愿组」加入第一个志愿", async ({ page }) => {
    const vBefore = (await (await fetch(`${BACKEND}`)).json()).version;
    await submitRecommendation(page);
    await page.getByTestId("add-volunteer").first().click();
    await expect(page.getByText("已加入志愿组")).toBeVisible({ timeout: 5000 });
    await expect(dockCount(page)).toContainText("1/48", { timeout: 5000 });
    await expect.poll(() => getItemCount(), { timeout: 5000 }).toBe(1);
    const vAfter = (await (await fetch(`${BACKEND}`)).json()).version;
    // version 应严格递增（本次 addItem 写入成功）。不绑定精确 +1：套件中其他
    // 测试的延迟删除/写入若恰好落在本测试窗口内会使 version 多跳一格，属正常并发。
    expect(vAfter).toBeGreaterThan(vBefore);
  });

  test("已加入的志愿显示「已加入」标记", async ({ page }) => {
    await submitRecommendation(page);
    await page.getByTestId("add-volunteer").first().click();
    await expect(page.getByText("已加入志愿组")).toBeVisible();
    await expect(page.getByTestId("added-badge").first()).toBeVisible({ timeout: 5000 });
  });

  test("同一院校专业组不重复添加", async ({ page }) => {
    await submitRecommendation(page);
    await page.getByTestId("add-volunteer").first().click();
    await expect(page.getByText("已加入志愿组")).toBeVisible();
    await expect.poll(() => getItemCount(), { timeout: 5000 }).toBe(1);
    const res = await fetch(`${BACKEND}`);
    const g = await res.json();
    const codes = g.items.map((it: { school_code: string; major_group_code: string }) =>
      `${it.school_code}-${it.major_group_code}`);
    expect(new Set(codes).size).toBe(codes.length);
  });

  test("资格不符的卡片显示「不可加入」（ineligible 不可加入志愿组）", async ({ page }) => {
    await submitRecommendation(page);
    // 展开「不推荐」折叠区
    await page.getByRole("button", { name: /查看不可达院校/ }).click();
    // ineligible 卡片显示「不可加入」标记（非按钮）
    await expect(page.getByTestId("add-disabled").first()).toBeVisible({ timeout: 8000 });
    // API 层双重验证：ineligible 院校专业组加入被服务端拒绝
    const res = await fetch(`${BACKEND}/items`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ school_code: "NOTEXIST", major_group_code: "999", profile: PROFILE }),
    });
    expect(res.status).toBe(400);
  });

  test("悬浮窗志愿项显示中等密度信息（专业组+学费+4年合计）", async ({ page }) => {
    await fetch(`${BACKEND}/items`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    await submitRecommendation(page);
    await expect(dockCount(page)).toContainText("1/48", { timeout: 10000 });
    // 校名（内联 yxdh 河南院校代码，如「哈尔滨石油学院（xxxx）」）
    await expect(page.getByTestId("volunteer-dock").getByText(/哈尔滨石油学院（\d+）/)).toBeVisible({ timeout: 10000 });
    // 学费/年 + 4年合计
    await expect(page.getByTestId("volunteer-dock").getByText(/\/年/)).toBeVisible();
    await expect(page.getByTestId("volunteer-dock").getByText(/4年≈/)).toBeVisible();
    expect(await getItemCount()).toBe(1);
  });

  test("悬浮窗志愿项可展开查看位次对比+计算公式", async ({ page }) => {
    await fetch(`${BACKEND}/items`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    await submitRecommendation(page);
    await expect(dockCount(page)).toContainText("1/48", { timeout: 10000 });
    // 点击展开按钮（ChevronRight → 展开）
    await page.getByTestId("volunteer-dock").getByRole("button", { name: "展开详情" }).first().click();
    // 展开后显示位次对比 + 计算公式
    await expect(page.getByTestId("volunteer-dock").getByText(/位次优势/)).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId("volunteer-dock").getByText(/考生位次/)).toBeVisible();
  });

  test("加入 2 个志愿后悬浮窗显示数量", async ({ page }) => {
    await fetch(`${BACKEND}/items`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    const rec = await fetch("http://127.0.0.1:8000/api/v1/henan/recommendation", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(PROFILE),
    });
    const recData = await rec.json();
    const second = recData.buckets["垫"]?.find(
      (it: { school_code: string; major_group_code: string }) => it.school_code !== "2535",
    );
    if (second) {
      await fetch(`${BACKEND}/items`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ school_code: second.school_code, major_group_code: second.major_group_code, profile: PROFILE }),
      });
    }
    await submitRecommendation(page);
    await expect(dockCount(page)).toContainText("2/48", { timeout: 10000 });
    expect(await getItemCount()).toBe(2);
  });

  test("清空志愿组（悬浮窗）", async ({ page }) => {
    await fetch(`${BACKEND}/items`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    await submitRecommendation(page);
    await expect(dockCount(page)).toContainText("1/48", { timeout: 10000 });
    await page.locator('button[aria-label="清空"]').click();
    await page.waitForTimeout(300);
    await page.getByTestId("confirm-clear").click();
    await expect(page.getByText("已清空志愿组")).toBeVisible({ timeout: 5000 });
    await expect.poll(() => getItemCount(), { timeout: 5000 }).toBe(0);
  });

  test("移出志愿组后显示撤销，点击撤销恢复", async ({ page }) => {
    await fetch(`${BACKEND}/items`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    await submitRecommendation(page);
    await expect(dockCount(page)).toContainText("1/48", { timeout: 10000 });
    await page.getByTestId("item-menu").first().click();
    await page.waitForTimeout(300);
    await page.getByTestId("remove-item").click();
    await expect(page.getByTestId("undo-delete")).toBeVisible({ timeout: 5000 });
    await expect(dockCount(page)).toContainText("0/48", { timeout: 5000 });
    await page.getByTestId("undo-delete").click();
    await expect(page.getByText("已撤销删除")).toBeVisible({ timeout: 5000 });
    await expect(dockCount(page)).toContainText("1/48", { timeout: 5000 });
  });

  test("移出志愿组 5 秒后真正删除（API 验证）", async ({ page }) => {
    test.setTimeout(20000);
    await fetch(`${BACKEND}/items`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    await submitRecommendation(page);
    await page.getByTestId("item-menu").first().click();
    await page.waitForTimeout(300);
    await page.getByTestId("remove-item").click();
    await expect(page.getByTestId("undo-delete")).toBeVisible({ timeout: 5000 });
    await expect(dockCount(page)).toContainText("0/48", { timeout: 5000 });
    await expect.poll(() => getItemCount(), { timeout: 9000 }).toBe(0);
  });

  test("刷新页面后志愿组数据恢复（服务端持久化）", async ({ page }) => {
    await fetch(`${BACKEND}/items`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    await submitRecommendation(page);
    await expect(dockCount(page)).toContainText("1/48", { timeout: 10000 });
    await expect(page.getByText(/哈尔滨石油学院（\d+）/).first()).toBeVisible({ timeout: 10000 });
    await page.reload();
    await submitRecommendation(page);
    await expect(page.getByText(/哈尔滨石油学院（\d+）/).first()).toBeVisible({ timeout: 10000 });
    await expect(dockCount(page)).toContainText("1/48", { timeout: 10000 });
  });

  test("导航栏无独立编排页（志愿组是临时笔记本，不单独成页）", async ({ page }) => {
    await page.goto("/");
    // 不应有「志愿编排」导航项（已删除独立编排页）
    await expect(page.getByRole("link", { name: /志愿编排/ })).toHaveCount(0);
  });

  test("切换页面后悬浮窗仍常驻", async ({ page }) => {
    await fetch(`${BACKEND}/items`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    await submitRecommendation(page);
    await expect(dockCount(page)).toContainText("1/48", { timeout: 10000 });
    await page.getByRole("link", { name: /位次工具/ }).click();
    await expect(page.getByText("我的志愿组").first()).toBeVisible({ timeout: 5000 });
  });
});
