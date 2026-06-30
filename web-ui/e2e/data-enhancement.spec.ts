import { test, expect, type Page } from "@playwright/test";
import { createHash } from "node:crypto";

// 本次数据增强（yxdh/zyzh 真实志愿填报代码 + 官网/招生网 + 复核文案 + 校园误并修复）端到端验收。
// 前置：后端 8000 + 前端 5173 已启动。

const BACKEND = "http://127.0.0.1:8000/api/v1";
const VOLUNTEER = `${BACKEND}/my-volunteers`;
const OWNER_HEADER = "X-Owner-Key";
// 用一个能覆盖五档 + 需复核的 profile（历史类，rank 居中）
const PROFILE = {
  source_province: "河南", score: 520, rank: 28000, track: "历史类",
  primary_subject: "历史", elective_subjects: ["政治", "地理"], exam_foreign_language: "英语",
};

function ownerFor(testInfo: { workerIndex: number; testId: string }) {
  const id = createHash("sha1").update(testInfo.testId).digest("hex").slice(0, 12);
  return `de-${testInfo.workerIndex}-${id}`;
}

async function getRecommendation() {
  const res = await fetch(`${BACKEND}/henan/recommendation`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(PROFILE),
  });
  return res.json();
}

test.describe("数据增强：yxdh/zyzh + 官网 + 复核文案 + 校园区分", () => {
  // 注：无 beforeEach clearGroup——每个 UI 测试用唯一 owner 隔离（见下），无需清理。

  // ── 后端 API 层断言（最稳）──
  test("API: candidate 含 yxdh/zyzh/官网，且校园不串户", async () => {
    const data = await getRecommendation();
    // 所有 buckets 展开成候选列表
    const all: any[] = [];
    for (const b of ["搏", "冲", "稳", "保", "垫", "需人工复核"]) {
      all.push(...(data.buckets?.[b] ?? []));
    }
    expect(all.length).toBeGreaterThan(100);
    // 至少有候选带 yxdh 和 zyzh
    const withYxdh = all.filter((c) => c.yxdh);
    const withZyzh = all.filter((c) => c.zyzh);
    expect(withYxdh.length, "应有候选带 yxdh 河南院校代码").toBeGreaterThan(50);
    expect(withZyzh.length, "应有候选带 zyzh 专业组号").toBeGreaterThan(20);
    // 至少有候选带官网或招生网
    const withWeb = all.filter((c) => c.official_website || c.enrollment_website);
    expect(withWeb.length, "应有候选带官网/招生网").toBeGreaterThan(50);
    // 校园误并修复核验：同校不同校区 school_code 必须不同
    const byName: Record<string, string[]> = {};
    for (const c of all) {
      const n = c.school_name;
      if (n.includes("中国地质大学") || n.includes("中国石油大学") || n.includes("哈尔滨工业大学")) {
        (byName[n] ??= []).push(c.school_code);
      }
    }
    const diZhi = Object.keys(byName).filter((n) => n.includes("中国地质大学"));
    if (diZhi.length >= 2) {
      const codes = new Set(diZhi.map((n) => byName[n][0]));
      expect(codes.size, "中国地质大学(北京)≠(武汉)，school_code 不能相同").toBe(diZhi.length);
    }
  });

  test("API: 复核原因文案含「查官网」指引", async () => {
    const data = await getRecommendation();
    const rs = data.review_summary;
    // 该 profile 下应有需复核项
    expect(rs?.total, "应有需人工复核项").toBeGreaterThan(0);
    // 标签或文案应含官网指引
    const label = rs?.labels?.missing_verified_2025_rank ?? "";
    expect(label).toContain("官网");
  });

  // ── 前端 UI 层断言 ──
  test("UI: 志愿推荐卡片校名内联 yxdh + 组内专业内联 zyzh + 官网链接", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /生成志愿表|生成中/ }).click();
    await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 20000 });
    // 校名后内联 yxdh（全角括号包裹的纯数字），如「贵州商学院（7279）」
    await expect(page.getByText(/（\d+）/, { exact: false }).first()).toBeVisible({ timeout: 10000 });
    // 组内专业内联 zyzh，如「组内专业（203）：...」
    await expect(page.getByText(/组内专业（\d+）：/).first()).toBeVisible({ timeout: 10000 });
    // 官网或招生网链接出现（取第一个）
    await expect(page.getByRole("link", { name: /^(官网|招生网)$/ }).first()).toBeVisible({ timeout: 10000 });
  });

  test("UI: 需复核原因汇总展示更新文案", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /生成志愿表|生成中/ }).click();
    await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 20000 });
    // 复核汇总区出现（含「官网」指引文字）
    await expect(page.getByText(/官网/).first()).toBeVisible({ timeout: 10000 });
  });

  test("UI: 加入志愿组后，我的志愿也内联 yxdh/zyzh", async ({ page }, testInfo) => {
    const owner = ownerFor(testInfo);
    // setExtraHTTPHeaders：稳定注入 X-Owner-Key 到该 page 所有浏览器请求（隔离志愿组）
    await page.context().setExtraHTTPHeaders({ [OWNER_HEADER]: owner });
    await page.goto("/");
    await page.getByRole("button", { name: /生成志愿表|生成中/ }).click();
    await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 20000 });
    // 等 store 初始化完成（data-ready=ready）再操作，避免竞态
    await expect(page.getByTestId("volunteer-dock")).toHaveAttribute("data-ready", "ready", { timeout: 10000 });

    // 加入第一张可加入的卡片（首页靠前院校均带 yxdh 真实填报代码）
    await page.getByTestId("add-volunteer").first().click();
    await expect(page.getByTestId("added-badge").first()).toBeVisible({ timeout: 5000 });

    // 我的志愿组（悬浮窗始终展示在 md+ 视口）里校名后内联 yxdh（全角括号数字）
    const dock = page.getByTestId("volunteer-dock");
    await expect(dock.getByText(/（\d+）/, { exact: false }).first()).toBeVisible({ timeout: 8000 });
  });
});
