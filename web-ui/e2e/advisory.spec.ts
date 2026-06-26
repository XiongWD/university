import { test, expect } from "@playwright/test";

// 真实流程测试：HomePage 主流程走 /api/v1/volunteer/advisory。
// 前置：后端 8000 + 前端 5173 已启动。

// 禁止叙事词（narrative-policy）：结果区不得出现这些作为功能名或结果。
const FORBIDDEN = ["人生路径", "人生轨迹", "回本", "ROI", "投资回报", "15年净收益", "命运", "赛道"];

test.describe("志愿推荐 advisory 真实流程", () => {
  test("首页加载并显示主标题", async ({ page }) => {
    await page.goto("/");
    // Hero 主标题（提交前可见）
    await expect(page.getByRole("heading", { name: "高考志愿专业推荐" })).toBeVisible();
  });

  test("提交后渲染专业方向建议与冲稳保院校", async ({ page }) => {
    await page.goto("/");

    // 默认表单已预填（480/历史类/日语 等），直接提交
    await page.getByRole("button", { name: /生成志愿表|生成中/ }).click();

    // 专业方向建议区（advisory 主输出）
    await expect(page.getByRole("heading", { name: "专业方向建议" })).toBeVisible({ timeout: 15000 });

    // 冲稳保至少出现一个档位标题（冲 / 稳 / 保）
    const bucketHeadings = await page.locator("h3", { hasText: /^(冲|稳|保)$/ }).count();
    // 若该分数段无可推荐院校，则会出现空态提示；两者择一即可
    const emptyState = await page.getByText("该分数段暂无匹配院校数据").count();
    expect(bucketHeadings > 0 || emptyState > 0).toBeTruthy();

    // 考生摘要含全省位次
    await expect(page.getByText("全省位次")).toBeVisible();
  });

  test("结果区不含禁止叙事词", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /生成志愿表|生成中/ }).click();
    await expect(page.getByRole("heading", { name: "专业方向建议" })).toBeVisible({ timeout: 15000 });

    const body = await page.locator("body").innerText();
    for (const w of FORBIDDEN) {
      expect(body, `结果区出现禁止词：${w}`).not.toContain(w);
    }
  });

  test("资格限制与数据说明区在结果存在时可见", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /生成志愿表|生成中/ }).click();
    await expect(page.getByRole("heading", { name: "专业方向建议" })).toBeVisible({ timeout: 15000 });

    // 数据说明区始终存在（advisory notes）
    await expect(page.getByText("数据说明").or(page.getByText(/录取数据基于/))).toBeVisible();
  });
});
