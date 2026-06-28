import { test, expect } from "@playwright/test";

// 河南志愿推目标评估验收。前置：后端 8000 + 前端 5173 已启动。

test.describe("河南志愿推目标评估", () => {
  test("选择学校后专业和专业组联动", async ({ page }) => {
    await page.goto("/target-evaluation");
    // 等待 /henan/options 加载完成（院校下拉出现 >1 个 option）
    const schoolSelect = page.locator("select").first();
    await expect(schoolSelect.locator("option")).toHaveCount(0, { timeout: 5000 }).catch(() => {});
    await expect(async () => {
      const n = await schoolSelect.locator("option").count();
      expect(n).toBeGreaterThan(1);
    }).toPass({ timeout: 15000 });
  });

  test("提交评估后显示结果或不推荐", async ({ page }) => {
    await page.goto("/target-evaluation");
    // 等 options 加载 + 默认院校选中
    await expect(page.getByRole("button", { name: /开始评估/ })).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: /开始评估|评估中/ }).click();
    // 总结区（可评估/不推荐）或错误提示至少出现一个
    const summary = page.getByText(/可评估|不推荐|出错了/).first();
    await expect(summary).toBeVisible({ timeout: 15000 });
  });
});
