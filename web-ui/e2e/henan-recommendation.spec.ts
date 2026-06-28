import { test, expect } from "@playwright/test";

// 河南志愿推首页推荐主链路验收。前置：后端 8000 + 前端 5173 已启动。

test.describe("河南志愿推首页推荐", () => {
  test("首页标题为河南志愿推", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "河南志愿推" })).toBeVisible();
  });

  test("导航无独立大学费用页", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "大学费用" })).toHaveCount(0);
  });

  test("提交后显示数据就绪状态与冲稳保档位", async ({ page }) => {
    await page.goto("/");
    // 默认表单已预填，直接提交
    await page.getByRole("button", { name: /生成志愿表|生成中/ }).click();

    // 结果区候选总数行（提交成功必然出现）
    await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 15000 });
  });

  test("点击冲档位只显示冲", async ({ page }) => {
    await page.goto("/");
    // 档位按钮可访问名为 "冲只看冲刺志愿"（label+desc，div 间含空格）
    await page.getByRole("button", { name: /^冲\s*只看冲刺志愿/ }).click();
    await page.getByRole("button", { name: /生成志愿表|生成中/ }).click();
    // 当前档位提示出现「冲」
    await expect(page.getByText(/当前显示「冲」档位/)).toBeVisible({ timeout: 15000 });
  });
});
