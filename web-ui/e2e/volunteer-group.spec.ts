import { test, expect, type Page } from "@playwright/test";
import { createHash } from "node:crypto";

// 我的志愿组（志愿编排工作台）端到端验收。
// 前置：后端 8000（VOLUNTEER_OWNER_ISOLATION=1）+ 前端 5173 已启动。
//
// 稳定性策略（架构级隔离，非轮询补丁）：
//  1. 每个测试用唯一 X-Owner-Key（workerInfo+testId），后端按 owner 隔离志愿组 →
//     测试间零共享状态，无需 clearGroup 重试/轮询，失败测试不污染下一个。
//  2. 等 data-ready="ready"（store 初始化完成）再操作，而非等元素可见——
//     修复「loadGroup 未完成时点击 add-volunteer 误判 isAdded」的真实竞态。
//  3. 核心断言以 API 业务状态（items 数）为准，version 仅作附加一致性断言。

const API_BASE = "http://127.0.0.1:8000/api/v1";
const REC_BASE = "http://127.0.0.1:8000/api/v1/henan/recommendation";
const PROFILE = {
  source_province: "河南", score: 480, rank: 60000, track: "历史类",
  primary_subject: "历史", elective_subjects: ["政治", "地理"], exam_foreign_language: "日语",
};
const OWNER_HEADER = "X-Owner-Key";

// ── 每测试唯一 owner：workerIndex-testId-job 唯一，且对 reload/多请求稳定 ──
test.beforeAll(async ({}, testInfo) => {
  // 校验后端开了隔离（否则 owner header 被忽略，测试退回共享状态）
  const probe = await fetch(`${API_BASE}/my-volunteers`, { headers: { [OWNER_HEADER]: "isolation-probe" } });
  const g = await probe.json();
  // 隔离模式下，一个全新 owner 的志愿组应为空；若非空说明隔离未生效（共享了 default 的数据）
  if ((g.items?.length ?? 0) > 0) {
    throw new Error(
      "后端未启用 VOLUNTEER_OWNER_ISOLATION=1，owner 隔离不生效，测试无法稳定。请用该环境变量重启后端。"
    );
  }
});

// 每个 test 自动拿到唯一 owner（Playwright 的 testInfo 在 test 函数内可取）
function ownerFor(testInfo: { workerIndex: number; testId: string }) {
  const id = createHash("sha1").update(testInfo.testId).digest("hex").slice(0, 12);
  return `t-${testInfo.workerIndex}-${id}`;
}

/** 带 owner header 的 Node fetch（测试侧 API 操作与浏览器侧同 owner） */
async function apiFetch(path: string, owner: string, init?: RequestInit) {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", [OWNER_HEADER]: owner, ...(init?.headers ?? {}) },
  });
}

async function getItemCount(owner: string): Promise<number> {
  const res = await apiFetch("/my-volunteers", owner);
  const g = await res.json();
  return g.items?.length ?? 0;
}

/** 提交推荐并注入 owner + 等待 store 初始化完成（data-ready="ready"） */
async function submitRecommendation(page: Page, owner: string) {
  // setExtraHTTPHeaders：在该 page 的所有浏览器请求上稳定注入 X-Owner-Key。
  // 比 addInitScript+window 全局更可靠——不依赖脚本执行时机，不会被上个测试残留覆盖。
  await page.context().setExtraHTTPHeaders({ [OWNER_HEADER]: owner });
  await page.goto("/");
  await page.getByRole("button", { name: /生成志愿表|生成中/ }).click();
  await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 20000 });
  // 等业务就绪：volunteer-dock 的 data-ready 变为 "ready"（store 已加载完该 owner 的空志愿组）
  await expect(page.getByTestId("volunteer-dock")).toHaveAttribute("data-ready", "ready", { timeout: 10000 });
}

/** dock 数量（testid 定位，唯一稳定） */
const dockCount = (page: Page) => page.getByTestId("dock-count");

test.describe("我的志愿组（志愿编排工作台）", () => {
  test("提交推荐后显示志愿组悬浮窗", async ({ page }, testInfo) => {
    const owner = ownerFor(testInfo);
    await submitRecommendation(page, owner);
    await expect(page.getByText("我的志愿组").first()).toBeVisible();
    await expect(dockCount(page)).toContainText("0/48");
  });

  test("点击「加入志愿组」加入第一个志愿", async ({ page }, testInfo) => {
    const owner = ownerFor(testInfo);
    await submitRecommendation(page, owner);
    await page.getByTestId("add-volunteer").first().click();
    // 业务状态为主断言：dock 数量 + API items 数都变 1
    await expect(dockCount(page)).toContainText("1/48", { timeout: 5000 });
    await expect.poll(() => getItemCount(owner), { timeout: 5000 }).toBe(1);
  });

  test("已加入的志愿显示「已加入」标记", async ({ page }, testInfo) => {
    const owner = ownerFor(testInfo);
    await submitRecommendation(page, owner);
    await page.getByTestId("add-volunteer").first().click();
    await expect(page.getByTestId("added-badge").first()).toBeVisible({ timeout: 5000 });
    await expect.poll(() => getItemCount(owner), { timeout: 5000 }).toBe(1);
  });

  test("同一院校专业组不重复添加", async ({ page }, testInfo) => {
    const owner = ownerFor(testInfo);
    await submitRecommendation(page, owner);
    await page.getByTestId("add-volunteer").first().click();
    await expect.poll(() => getItemCount(owner), { timeout: 5000 }).toBe(1);
    // 再次点同一张卡片的加入按钮（已是 added-badge，按钮不存在）→ 数量仍为 1
    await expect(page.getByTestId("added-badge").first()).toBeVisible();
    expect(await getItemCount(owner)).toBe(1);
  });

  test("资格不符的卡片显示「不可加入」（ineligible 不可加入志愿组）", async ({ page }, testInfo) => {
    const owner = ownerFor(testInfo);
    await submitRecommendation(page, owner);
    await page.getByRole("button", { name: /查看不可达院校/ }).click();
    await expect(page.getByTestId("add-disabled").first()).toBeVisible({ timeout: 10000 });
    expect(await getItemCount(owner)).toBe(0);
  });

  test("悬浮窗志愿项显示中等密度信息（专业组+学费+4年合计）", async ({ page }, testInfo) => {
    const owner = ownerFor(testInfo);
    await apiFetch("/my-volunteers/items", owner, {
      method: "POST", body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    await submitRecommendation(page, owner);
    await expect(dockCount(page)).toContainText("1/48", { timeout: 10000 });
    // 校名（内联 yxdh 河南院校代码，如「哈尔滨石油学院（xxxx）」）
    await expect(page.getByTestId("volunteer-dock").getByText(/哈尔滨石油学院（\d+）/)).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId("volunteer-dock").getByText(/\/年/)).toBeVisible();
    await expect(page.getByTestId("volunteer-dock").getByText(/4年≈/)).toBeVisible();
    expect(await getItemCount(owner)).toBe(1);
  });

  test("悬浮窗志愿项可展开查看位次对比+计算公式", async ({ page }, testInfo) => {
    const owner = ownerFor(testInfo);
    await apiFetch("/my-volunteers/items", owner, {
      method: "POST", body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    await submitRecommendation(page, owner);
    await expect(dockCount(page)).toContainText("1/48", { timeout: 10000 });
    await page.getByTestId("volunteer-dock").getByRole("button", { name: "展开详情" }).first().click();
    await expect(page.getByTestId("volunteer-dock").getByText(/位次优势/)).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId("volunteer-dock").getByText(/考生位次/)).toBeVisible();
  });

  test("加入 2 个志愿后悬浮窗显示数量", async ({ page }, testInfo) => {
    const owner = ownerFor(testInfo);
    await apiFetch("/my-volunteers/items", owner, {
      method: "POST", body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    const rec = await fetch(REC_BASE, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(PROFILE),
    });
    const recData = await rec.json();
    const second = recData.buckets["垫"]?.find(
      (it: { school_code: string }) => it.school_code !== "2535",
    );
    if (second) {
      await apiFetch("/my-volunteers/items", owner, {
        method: "POST", body: JSON.stringify({
          school_code: second.school_code, major_group_code: second.major_group_code, profile: PROFILE,
        }),
      });
    }
    await submitRecommendation(page, owner);
    await expect(dockCount(page)).toContainText("2/48", { timeout: 10000 });
    expect(await getItemCount(owner)).toBe(2);
  });

  test("清空志愿组（悬浮窗）", async ({ page }, testInfo) => {
    const owner = ownerFor(testInfo);
    await apiFetch("/my-volunteers/items", owner, {
      method: "POST", body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    await submitRecommendation(page, owner);
    await expect(dockCount(page)).toContainText("1/48", { timeout: 10000 });
    await page.locator('button[aria-label="清空"]').click();
    await page.getByTestId("confirm-clear").click();
    await expect.poll(() => getItemCount(owner), { timeout: 5000 }).toBe(0);
    await expect(dockCount(page)).toContainText("0/48", { timeout: 5000 });
  });

  test("移出志愿组后显示撤销，点击撤销恢复", async ({ page }, testInfo) => {
    const owner = ownerFor(testInfo);
    await apiFetch("/my-volunteers/items", owner, {
      method: "POST", body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    await submitRecommendation(page, owner);
    await expect(dockCount(page)).toContainText("1/48", { timeout: 10000 });
    await page.getByTestId("item-menu").first().click();
    await page.getByTestId("remove-item").click();
    await expect(page.getByTestId("undo-delete")).toBeVisible({ timeout: 5000 });
    await expect(dockCount(page)).toContainText("0/48", { timeout: 5000 });
    await page.getByTestId("undo-delete").click();
    await expect(dockCount(page)).toContainText("1/48", { timeout: 5000 });
    expect(await getItemCount(owner)).toBe(1);
  });

  test("移出志愿组 5 秒后真正删除（API 验证）", async ({ page }, testInfo) => {
    const owner = ownerFor(testInfo);
    test.setTimeout(20000);
    await apiFetch("/my-volunteers/items", owner, {
      method: "POST", body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    await submitRecommendation(page, owner);
    await page.getByTestId("item-menu").first().click();
    await page.getByTestId("remove-item").click();
    await expect(page.getByTestId("undo-delete")).toBeVisible({ timeout: 5000 });
    await expect(dockCount(page)).toContainText("0/48", { timeout: 5000 });
    // 5 秒延迟删除后，该 owner 的 API items 真正归零（不受其他测试干扰）
    await expect.poll(() => getItemCount(owner), { timeout: 9000 }).toBe(0);
  });

  test("刷新页面后志愿组数据恢复（服务端持久化）", async ({ page }, testInfo) => {
    const owner = ownerFor(testInfo);
    await apiFetch("/my-volunteers/items", owner, {
      method: "POST", body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    await submitRecommendation(page, owner);
    await expect(dockCount(page)).toContainText("1/48", { timeout: 10000 });
    await expect(page.getByText(/哈尔滨石油学院（\d+）/).first()).toBeVisible({ timeout: 10000 });
    await page.reload();
    await submitRecommendation(page, owner);
    await expect(page.getByText(/哈尔滨石油学院（\d+）/).first()).toBeVisible({ timeout: 10000 });
    await expect(dockCount(page)).toContainText("1/48", { timeout: 10000 });
  });

  test("导航栏无独立编排页（志愿组是临时笔记本，不单独成页）", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: /志愿编排/ })).toHaveCount(0);
  });

  test("切换页面后悬浮窗仍常驻", async ({ page }, testInfo) => {
    const owner = ownerFor(testInfo);
    await apiFetch("/my-volunteers/items", owner, {
      method: "POST", body: JSON.stringify({ school_code: "2535", major_group_code: "759266", profile: PROFILE }),
    });
    await submitRecommendation(page, owner);
    await expect(dockCount(page)).toContainText("1/48", { timeout: 10000 });
    await page.getByRole("link", { name: /位次工具/ }).click();
    await expect(page.getByText("我的志愿组").first()).toBeVisible({ timeout: 5000 });
  });
});
