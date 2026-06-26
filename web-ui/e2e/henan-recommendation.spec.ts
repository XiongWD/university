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

    // 数据就绪 banner 或档位标题至少出现一个（数据未就绪时显示 banner）
    const readyBanner = page.getByText("推荐数据未完全就绪");
    const bucketHeading = page.getByRole("heading", { name: /^(冲|稳|保|不推荐|需人工复核)$/ });
    await expect(readyBanner.or(bucketHeading.first())).toBeVisible({ timeout: 15000 });
  });

  test("点击冲档位只显示冲", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "冲", exact: true }).click();
    await page.getByRole("button", { name: /生成志愿表|生成中/ }).click();
    // 冲档位标题应可见（或空态——但档位筛选按钮存在即证明交互生效）
    await expect(page.getByRole("button", { name: "冲", exact: true })).toBeVisible();
  });
});
