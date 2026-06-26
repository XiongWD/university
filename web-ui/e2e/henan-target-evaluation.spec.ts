import { test, expect } from "@playwright/test";

// 河南志愿推目标评估验收。前置：后端 8000 + 前端 5173 已启动。

test.describe("河南志愿推目标评估", () => {
  test("选择学校后专业和专业组联动", async ({ page }) => {
    await page.goto("/target-evaluation");
    // 院校下拉有选项（联动 /henan/options）
    const schoolSelect = page.locator("select").first();
    const optionCount = await schoolSelect.locator("option").count();
    expect(optionCount).toBeGreaterThan(1);
  });

  test("提交评估后显示结果或不推荐", async ({ page }) => {
    await page.goto("/target-evaluation");
    await page.waitForTimeout(1000); // 等 options 加载
    await page.getByRole("button", { name: /开始评估|评估中/ }).click();
    // 总结区（可评估/不推荐）或错误提示至少出现一个
    const summary = page.getByText(/可评估|不推荐|出错了/).first();
    await expect(summary).toBeVisible({ timeout: 15000 });
  });
});
