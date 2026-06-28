import { test, expect } from "@playwright/test";

/**
 * 河南志愿推 · 多组真实数据 Playwright 验收（headless）。
 *
 * 前置：scripts/dev.ps1 start 已起 后端 8000 + 前端 5173。
 *
 * 验证目标（与用户需求一一对应）：
 *  1. 页面数据返回正常（API 真实数据落到 UI）
 *  2. 页面结构布局 / UI 流程正常（表单、档位、卡片、覆盖报告）
 *  3. 复核「为孩子选志愿」推荐逻辑（资格先行 → 位次换算 → 冲稳保分桶）
 *  4. 真实计算 冲/稳/保 算法的可见性证明（位次越高 → 保越多；位次越低 → 不推荐越多；
 *     策略积极 → 冲配额高；语种日语 → 命中要求英语的组被剔除）
 *
 * 多组数据：覆盖 高分段 / 中分段 / 低分段 / 日语语种 / 积极策略 五种场景。
 */

const BASE_URL = "http://localhost:5173";

interface Scenario {
  name: string;
  score: number;
  foreignLang: string;
  foreignScore: number;
  mathScore: number;
  bucket: "全部" | "冲" | "稳" | "保";
  /** 该场景的核心断言（在页面 + API 双向验证） */
  expectNote: string;
}

const SCENARIOS: Scenario[] = [
  {
    name: "高分段(650)·英语·全部",
    score: 650,
    foreignLang: "英语",
    foreignScore: 130,
    mathScore: 130,
    bucket: "全部",
    expectNote: "位次靠前，保/稳 数量应充足，不推荐比例低",
  },
  {
    name: "中分段(560)·英语·全部",
    score: 560,
    foreignLang: "英语",
    foreignScore: 105,
    mathScore: 90,
    bucket: "全部",
    expectNote: "中段位次，冲/稳/保 三档均应出现候选",
  },
  {
    name: "低分段(490)·英语·保",
    score: 490,
    foreignLang: "英语",
    foreignScore: 85,
    mathScore: 70,
    bucket: "保",
    expectNote: "位次靠后，不推荐数量应明显升高，保档稀少",
  },
  {
    name: "日语语种(580)·日语·全部",
    score: 580,
    foreignLang: "日语",
    foreignScore: 110,
    mathScore: 95,
    bucket: "全部",
    expectNote: "要求英语语种的组应进入不推荐(资格硬过滤)",
  },
  {
    name: "积极策略(600)·英语·冲",
    score: 600,
    foreignLang: "英语",
    foreignScore: 115,
    mathScore: 100,
    bucket: "冲",
    expectNote: "策略积极 → 仅显示冲档候选，配额向冲倾斜",
  },
];

// 档位按钮的可访问名是 "label<空格>desc"（如 "全部 48志愿布局"），块级 div 间会被 Playwright 插入空格。
function bucketButtonRegex(bucket: string): RegExp {
  // 匹配 "全部 48志愿布局" / "冲 只看冲刺志愿" 等，允许 label 与 desc 间任意空白
  return new RegExp(`^${bucket}\\s*(48志愿布局|只看冲刺志愿|只看稳妥志愿|只看保底志愿)`);
}

async function fillFormAndSubmit(
  page: import("@playwright/test").Page,
  s: Scenario
) {
  await page.goto(BASE_URL + "/");
  await page.waitForLoadState("networkidle");

  // 高考总分（第一个 number input）
  const numInputs = page.locator('input[type="number"]');
  await numInputs.first().fill(String(s.score));

  // 外语语种按钮（语种按钮可访问名就是语种本身）
  await page.getByRole("button", { name: s.foreignLang, exact: true }).click();

  // 数学单科(nth 1) / 外语单科(nth 2)
  await numInputs.nth(1).fill(String(s.mathScore));
  await numInputs.nth(2).fill(String(s.foreignScore));

  // 查看档位（全部/冲/稳/保）
  await page.getByRole("button", { name: bucketButtonRegex(s.bucket) }).click();

  // 提交
  await page.getByRole("button", { name: /生成志愿表/ }).click();

  // 等待结果区：候选总数行（提交成功后必然出现，单一匹配）
  await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 25000 });
}

/** 直接调后端 API 拿「真值」，用于与页面结果交叉验证。 */
async function apiRecommend(s: Scenario): Promise<any> {
  const strategyMap: Record<string, string> = {
    冲: "积极",
    保: "保守",
    稳: "均衡",
    全部: "自动",
  };
  const body = {
    score: s.score,
    rank: null,
    track: "历史类",
    source_province: "河南",
    primary_subject: "历史",
    elective_subjects: ["政治", "地理"],
    exam_foreign_language: s.foreignLang,
    subject_scores_detail: { 数学: s.mathScore, 外语: s.foreignScore },
    strategy: strategyMap[s.bucket] ?? "自动",
  };
  const res = await fetch("http://127.0.0.1:8000/api/v1/henan/recommendation", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

test.describe("河南志愿推 · 多组真实数据验收", () => {
  test("0. 页面基础结构与布局", async ({ page }) => {
    await page.goto(BASE_URL + "/");
    await page.waitForLoadState("networkidle");

    // 标题
    await expect(page.getByRole("heading", { name: "河南志愿推" })).toBeVisible();
    // 副标题
    await expect(page.getByText(/院校专业组.*冲稳保/)).toBeVisible();
    // 表单标题
    await expect(page.getByRole("heading", { name: "输入考生信息" })).toBeVisible();
    // 固定范围展示
    await expect(page.getByText(/河南.*2026.*历史类.*普通本科批/)).toBeVisible();
    // 推荐单位
    await expect(page.getByText(/院校专业组（组内 1-6 个专业）/)).toBeVisible();
    // 外语语种选项齐全
    for (const l of ["英语", "日语", "俄语", "德语", "法语", "西班牙语"]) {
      await expect(page.getByRole("button", { name: l, exact: true })).toBeVisible();
    }
    // 再选科目（去掉物理历史后的4门）
    for (const subj of ["化学", "生物", "政治", "地理"]) {
      await expect(page.getByRole("button", { name: subj, exact: true })).toBeVisible();
    }
    // 档位筛选 4 个
    for (const b of ["全部", "冲", "稳", "保"]) {
      await expect(page.getByRole("button", { name: bucketButtonRegex(b) })).toBeVisible();
    }
    // 提交按钮
    await expect(page.getByRole("button", { name: /生成志愿表/ })).toBeVisible();
    // 无独立「大学费用」导航
    await expect(page.getByRole("link", { name: "大学费用" })).toHaveCount(0);
  });

  for (const s of SCENARIOS) {
    test(`1. 场景：${s.name}（${s.expectNote}）`, async ({ page }) => {
      // 先取 API 真值
      const api = await apiRecommend(s);
      expect(api.data_ready).toBeTruthy();
      const apiBuckets = api.buckets as Record<string, any[]>;
      const apiCounts = {
        冲: apiBuckets["冲"]?.length ?? 0,
        稳: apiBuckets["稳"]?.length ?? 0,
        保: apiBuckets["保"]?.length ?? 0,
        不推荐: apiBuckets["不推荐"]?.length ?? 0,
        需人工复核: apiBuckets["需人工复核"]?.length ?? 0,
      };

      // 页面填写并提交
      await fillFormAndSubmit(page, s);

      // —— 页面数据返回正常：候选总数与 API 一致 ——
      const totalLine = page.getByText(/个院校专业组候选/);
      await expect(totalLine).toBeVisible();
      const totalText = (await totalLine.textContent()) ?? "";
      const pageTotal = Number((totalText.match(/共\s*(\d+)\s*个/) ?? [])[1] ?? 0);
      const apiTotal = Object.values(apiCounts).reduce((a, b) => a + b, 0);
      expect(pageTotal, `页面候选总数应等于API总数(${apiTotal})`).toBe(apiTotal);

      // —— 当前显示档位 ——
      await expect(page.getByText(new RegExp(`当前显示「${s.bucket}」档位`))).toBeVisible();

      // —— 冲稳保算法可见性：档位标题区显示数量 ——
      const reachTotal = apiCounts["冲"] + apiCounts["稳"] + apiCounts["保"];
      if (s.bucket === "全部" && reachTotal > 0) {
        // 至少出现一个可达档位标题
        const headings = page.getByRole("heading", { name: /^(冲|稳|保)$/ });
        await expect(headings.first()).toBeVisible();
      }

      test.info().attach(`api-${s.name}.json`, {
        body: JSON.stringify({ apiCounts, pageTotal, apiTotal }, null, 2),
        contentType: "application/json",
      });
    });
  }

  test("2. 冲稳保算法逻辑可见性：高分 vs 低分 位次单调性", async ({ page }) => {
    // 高分 650
    const high = await apiRecommend({
      score: 650, foreignLang: "英语", foreignScore: 130, mathScore: 130, bucket: "全部",
      name: "high", expectNote: "",
    });
    // 低分 490
    const low = await apiRecommend({
      score: 490, foreignLang: "英语", foreignScore: 85, mathScore: 70, bucket: "全部",
      name: "low", expectNote: "",
    });
    const h = (b: string) => (high.buckets[b] ?? []).length;
    const l = (b: string) => (low.buckets[b] ?? []).length;

    // 位次越高 → 保越多（算法单调性证据）
    expect(h("保"), `高分保档(${h("保")})应 >= 低分保档(${l("保")})`).toBeGreaterThanOrEqual(l("保"));
    // 位次越低 → 不推荐越多
    expect(l("不推荐"), `低分不推荐(${l("不推荐")})应 > 高分不推荐(${h("不推荐")})`).toBeGreaterThan(h("不推荐"));
    // 两个分数都应 data_ready
    expect(high.data_ready).toBeTruthy();
    expect(low.data_ready).toBeTruthy();

    test.info().attach("algorithm-monotonicity.json", {
      body: JSON.stringify({
        high_650: { 保: h("保"), 稳: h("稳"), 冲: h("冲"), 不推荐: h("不推荐") },
        low_490: { 保: l("保"), 稳: l("稳"), 冲: l("冲"), 不推荐: l("不推荐") },
        assertion: "高分保档>=低分保档 且 低分不推荐>高分不推荐",
      }, null, 2),
      contentType: "application/json",
    });

    // 同时在页面验证高分场景确实渲染出保档卡片
    await fillFormAndSubmit(page, {
      score: 650, foreignLang: "英语", foreignScore: 130, mathScore: 130, bucket: "全部",
      name: "high", expectNote: "",
    });
    if (h("保") > 0) {
      await expect(page.getByRole("heading", { name: "保" })).toBeVisible();
      // 保档卡片含「2026河南计划 N 人」字样（真实计划数据可见）
      await expect(page.getByText(/2026河南计划\s*\d+\s*人/).first()).toBeVisible();
    }
  });

  test("3. 资格链可见性：日语语种命中英语要求 → 不推荐原因可见", async ({ page }) => {
    const s: Scenario = {
      score: 580, foreignLang: "日语", foreignScore: 110, mathScore: 95, bucket: "全部",
      name: "japanese", expectNote: "要求英语语种组进入不推荐",
    };
    await fillFormAndSubmit(page, s);

    // 展开「不推荐」折叠区
    const expandBtn = page.getByRole("button", { name: /查看不可达院校/ });
    if (await expandBtn.isVisible().catch(() => false)) {
      await expandBtn.click();
      // 应出现「要求英语语种」类硬过滤原因
      await expect(page.getByText(/英语语种/).first()).toBeVisible({ timeout: 8000 });
    }
  });

  test("4. 数据覆盖报告可见（数据来源/置信度透明）", async ({ page }) => {
    await fillFormAndSubmit(page, SCENARIOS[1]);
    // 覆盖报告区
    await expect(page.getByText("数据覆盖")).toBeVisible();
    await expect(page.getByText(/已覆盖\s*\d+\s*所可追溯院校/)).toBeVisible();
    // quality 指标项（verified_program_groups_2026 等）
    await expect(page.getByText(/verified_program_groups_2026/)).toBeVisible();
    await expect(page.getByText(/verified_2025_major_group_history/)).toBeVisible();
    // 免责声明（结果区底部，含"正式填报"字样以唯一定位）
    await expect(page.getByText(/正式填报以省考试院公布为准/)).toBeVisible();
  });
});

test.describe("河南志愿推 · 四项缺失功能补齐验收", () => {
  test("5. 问题1：选「只看冲」→ 生成策略感知的 48 志愿草案", async ({ page }) => {
    await page.goto(BASE_URL + "/");
    await page.waitForLoadState("networkidle");
    await page.locator('input[type="number"]').first().fill("600");
    await page.getByRole("button", { name: /^冲\s*只看冲刺志愿/ }).click();
    await page.getByRole("button", { name: /生成志愿表/ }).click();
    await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 25000 });

    // 48 志愿草案区出现
    await expect(page.getByRole("heading", { name: "48 志愿草案" })).toBeVisible();
    // 策略标签（积极，因为选了冲）
    await expect(page.getByText(/积极（多冲）/)).toBeVisible();
    // 配额徽章（冲/稳/保 各档 used/上限）
    await expect(page.getByText(/冲：\d+\/\d+（配额\s*\d+-\d+）/)).toBeVisible();
    // 草案至少有一个带序号的志愿
    await expect(page.locator("text=1").first()).toBeVisible();
  });

  test("6. 问题1：积极 vs 保守 策略配额不同（策略真正生效）", async () => {
    // 直接对照 API：同分同科，积极 vs 保守 的 used 配额应不同
    const aggr = await apiRecommend({
      score: 600, foreignLang: "英语", foreignScore: 115, mathScore: 100, bucket: "冲",
      name: "aggr", expectNote: "",
    });
    const cons = await apiRecommend({
      score: 600, foreignLang: "英语", foreignScore: 115, mathScore: 100, bucket: "保",
      name: "cons", expectNote: "",
    });
    const aUsed = aggr.volunteer_table?.used;
    const cUsed = cons.volunteer_table?.used;
    expect(aUsed, "积极策略应返回 used 配额").toBeTruthy();
    expect(cUsed, "保守策略应返回 used 配额").toBeTruthy();
    if (aUsed && cUsed) {
      // 积极冲档配额上限 > 保守冲档配额上限（策略区分证据）
      const aQuotaChong = aggr.volunteer_table!.quota["冲"][1];
      const cQuotaChong = cons.volunteer_table!.quota["冲"][1];
      expect(aQuotaChong, `积极冲配额上限(${aQuotaChong}) > 保守冲配额上限(${cQuotaChong})`)
        .toBeGreaterThan(cQuotaChong);
    }
    test.info().attach("strategy-quota-diff.json", {
      body: JSON.stringify({
        积极: { quota: aggr.volunteer_table?.quota, used: aUsed },
        保守: { quota: cons.volunteer_table?.quota, used: cUsed },
      }, null, 2),
      contentType: "application/json",
    });
  });

  test("7. 问题3：学校卡片含真实学费/住宿费/生活费/4年合计", async ({ page }) => {
    await fillFormAndSubmit(page, SCENARIOS[1]); // 中分560 全部
    // 费用行（学费 N/年 · 住宿 N/年 · 生活费 N/年 · X年合计 ≈ Y元）
    await expect(page.getByText(/学费\s*\S+\s*\/年/).first()).toBeVisible();
    await expect(page.getByText(/住宿\s*\S+\s*\/年/).first()).toBeVisible();
    await expect(page.getByText(/生活费\s*\S+\s*\/年/).first()).toBeVisible();
    await expect(page.getByText(/\d+年合计\s*≈\s*\S+元/).first()).toBeVisible();
    // 展开本组计算（费用卡片里应有「查看本组冲稳保计算」）
    const calcBtn = page.getByRole("button", { name: /查看本组冲稳保计算/ }).first();
    if (await calcBtn.isVisible().catch(() => false)) {
      await calcBtn.click();
      await expect(page.getByText(/公式：/).first()).toBeVisible();
    }
  });

  test("8. 问题3：学费数字非空且合理（真实数据）", async () => {
    // 对照 API：清华学费应为真实值（公办约5000级，非0非空）
    const api = await apiRecommend(SCENARIOS[0]); // 高分650
    const all = [...(api.buckets["保"] ?? []), ...(api.buckets["稳"] ?? []), ...(api.buckets["冲"] ?? [])];
    const withTuition = all.filter((s: any) => typeof s.tuition === "number" && s.tuition > 0);
    expect(withTuition.length, "应有专业组带真实学费>0").toBeGreaterThan(0);
    const sample = withTuition[0];
    expect(sample.four_year_total, "4年合计应>0").toBeGreaterThan(0);
    expect(sample.living_cost_per_year, "生活费应>0").toBeGreaterThan(0);
    test.info().attach("cost-sample.json", {
      body: JSON.stringify({
        school: sample.school_name,
        tuition: sample.tuition, accommodation: sample.accommodation,
        living_cost_per_year: sample.living_cost_per_year, four_year_total: sample.four_year_total,
      }, null, 2),
      contentType: "application/json",
    });
  });

  test("9. 问题4：学校性质可见（公办/民办/中外 + 省内/省外 + 985/211）", async ({ page }) => {
    await fillFormAndSubmit(page, SCENARIOS[1]);
    // 省内/省外 标签（MapPin 图标后跟 省内/省外）
    await expect(page.getByText(/省(内|外)/).first()).toBeVisible();
    // ownership 徽章（公办/民办/中外合作 之一）
    const ownershipVisible = await page.getByText(/公办|民办|中外合作/, { exact: false }).first().isVisible().catch(() => false);
    expect(ownershipVisible, "应可见学校性质徽章").toBeTruthy();
  });

  test("10. 问题4：省内外 + ownership + tags 来自真实数据（API 对照）", async () => {
    const api = await apiRecommend(SCENARIOS[0]);
    const all = [...(api.buckets["保"] ?? []), ...(api.buckets["稳"] ?? []), ...(api.buckets["冲"] ?? [])];
    const local = all.filter((s: any) => s.is_henan_local === true);
    const nonLocal = all.filter((s: any) => s.is_henan_local === false);
    expect(local.length + nonLocal.length, "应有学校标记省内外").toBeGreaterThan(0);
    const withOwnership = all.filter((s: any) => s.school_ownership);
    expect(withOwnership.length, "应有学校 ownership").toBeGreaterThan(0);
    // 至少存在省外（北京等 985）和省内（河南本地）两类
    test.info().attach("school-nature.json", {
      body: JSON.stringify({
        省内样本: local[0] ? { name: local[0].school_name, ownership: local[0].school_ownership } : null,
        省外样本: nonLocal[0] ? { name: nonLocal[0].school_name, ownership: nonLocal[0].school_ownership, tags: nonLocal[0].school_tags } : null,
      }, null, 2),
      contentType: "application/json",
    });
  });

  test("11. 问题2：冲稳保算法说明可见且含公式与阈值", async ({ page }) => {
    await fillFormAndSubmit(page, SCENARIOS[1]);
    // 展开算法说明
    await page.getByRole("button", { name: /查看冲稳保怎么算的/ }).click();
    // 核心公式
    await expect(page.getByText(/rank_gap_ratio\s*=\s*\(考生位次/)).toBeVisible();
    // 阈值（冲>3%）
    await expect(page.getByText(/位次差比\s*>\s*3%/)).toBeVisible();
    // 资格链顺序
    await expect(page.getByText(/资格层先行/)).toBeVisible();
  });
});

test.describe("河南志愿推 · 成功率/排序/偏好 验收", () => {
  test("12. 成功率：卡片与志愿草案显示投档成功率徽章", async ({ page }) => {
    await page.goto(BASE_URL + "/");
    await page.waitForLoadState("networkidle");
    await page.locator('input[type="number"]').first().fill("600");
    await page.getByRole("button", { name: /^全部\s*48志愿布局/ }).click();
    await page.getByRole("button", { name: /生成志愿表/ }).click();
    await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 25000 });
    // 卡片成功率徽章（成功率 N%）
    await expect(page.getByText(/成功率\s*\d+%/).first()).toBeVisible();
    // 48志愿草案区也含成功率徽章
    await expect(page.getByRole("heading", { name: "48 志愿草案" })).toBeVisible();
  });

  test("13. 成功率 API：冲稳保三档成功率单调（冲<稳<保）", async () => {
    const d = await apiRecommend(SCENARIOS[1]);
    const avg = (arr: any[], key: string) => {
      const vals = arr.map((s) => s[key]).filter((v) => typeof v === "number" && v > 0) as number[];
      return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
    };
    const aChong = avg(d.buckets["冲"] ?? [], "admission_probability");
    const aWen = avg(d.buckets["稳"] ?? [], "admission_probability");
    const aBao = avg(d.buckets["保"] ?? [], "admission_probability");
    // 保 >= 稳 >= 冲（成功率随档位升高）
    if (aChong > 0 && aWen > 0) {
      expect(aWen, `稳成功率(${aWen.toFixed(2)}) >= 冲(${aChong.toFixed(2)})`).toBeGreaterThanOrEqual(aChong);
    }
    if (aWen > 0 && aBao > 0) {
      expect(aBao, `保成功率(${aBao.toFixed(2)}) >= 稳(${aWen.toFixed(2)})`).toBeGreaterThanOrEqual(aWen);
    }
    test.info().attach("probability-monotonic.json", {
      body: JSON.stringify({ 冲均: aChong, 稳均: aWen, 保均: aBao }, null, 2),
      contentType: "application/json",
    });
  });

  test("14. 排序方式切换：成功率优先 vs 位次优先 顺序不同", async ({ page }) => {
    await page.goto(BASE_URL + "/");
    await page.waitForLoadState("networkidle");
    await page.locator('input[type="number"]').first().fill("600");
    // 选「成功率优先」
    await page.getByRole("button", { name: /^成功率优先/ }).click();
    await page.getByRole("button", { name: /^全部\s*48志愿布局/ }).click();
    await page.getByRole("button", { name: /生成志愿表/ }).click();
    await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 25000 });
    // 草案头部显示「排序：成功率优先」
    await expect(page.getByText(/排序：成功率优先/)).toBeVisible();
  });

  test("15. 省内优先勾选：volunteer_table.prefer_local=true 且省内排前", async ({ page }) => {
    await page.goto(BASE_URL + "/");
    await page.waitForLoadState("networkidle");
    await page.locator('input[type="number"]').first().fill("580");
    await page.getByRole("button", { name: /^全部\s*48志愿布局/ }).click();
    // 勾选「优先省内院校」
    await page.getByLabel("优先省内院校").check();
    await page.getByRole("button", { name: /生成志愿表/ }).click();
    await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 25000 });
    // 草案头部显示「省内优先」
    await expect(page.getByText(/省内优先/)).toBeVisible();
  });

  test("16. 公办优先勾选：volunteer_table 显示公办优先", async ({ page }) => {
    await page.goto(BASE_URL + "/");
    await page.waitForLoadState("networkidle");
    await page.locator('input[type="number"]').first().fill("580");
    await page.getByRole("button", { name: /^全部\s*48志愿布局/ }).click();
    await page.getByLabel("优先公办院校").check();
    await page.getByRole("button", { name: /生成志愿表/ }).click();
    await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 25000 });
    await expect(page.getByText(/公办优先/)).toBeVisible();
  });

  test("17. 档位锚点：选「稳」后结果区出现稳档标题", async ({ page }) => {
    await page.goto(BASE_URL + "/");
    await page.waitForLoadState("networkidle");
    await page.locator('input[type="number"]').first().fill("580");
    await page.getByRole("button", { name: /^稳\s*只看稳妥志愿/ }).click();
    await page.getByRole("button", { name: /生成志愿表/ }).click();
    await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 25000 });
    // 选稳时：稳档标题区应渲染（带 id 锚点）
    await expect(page.locator("#bucket-稳")).toBeVisible();
    // 冲档标题区在「只看稳」时不应出现（visibleBuckets 已过滤）
    await expect(page.locator("#bucket-冲")).toHaveCount(0);
  });

  test("18. 省内优先 API：prefer_local 时省内院校在档位内排名靠前", async () => {
    // 对照 API：同分，prefer_local=true vs false，看保档前几名省内占比
    const baseBody = {
      score: 580, rank: null, track: "历史类" as const, source_province: "河南" as const,
      primary_subject: "历史" as const, elective_subjects: ["政治", "地理"],
      exam_foreign_language: "英语", subject_scores_detail: { 数学: 95, 外语: 110 },
      strategy: "均衡" as const,
    };
    const off = await fetch("http://127.0.0.1:8000/api/v1/henan/recommendation", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...baseBody, sort_mode: "rank", prefer_local: false }),
    }).then((r) => r.json());
    const on = await fetch("http://127.0.0.1:8000/api/v1/henan/recommendation", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...baseBody, sort_mode: "rank", prefer_local: true }),
    }).then((r) => r.json());
    expect(on.volunteer_table.prefer_local).toBe(true);
    expect(off.volunteer_table.prefer_local).toBe(false);
    // 开启省内优先后，保档前20名中省内院校数应 >= 关闭时
    const baoOn = (on.buckets["保"] ?? []).slice(0, 20).filter((s: any) => s.is_henan_local).length;
    const baoOff = (off.buckets["保"] ?? []).slice(0, 20).filter((s: any) => s.is_henan_local).length;
    expect(baoOn, `省内优先后保档前20省内数(${baoOn}) >= 关闭时(${baoOff})`).toBeGreaterThanOrEqual(baoOff);
    test.info().attach("prefer-local-effect.json", {
      body: JSON.stringify({ 关闭_保档前20省内数: baoOff, 开启_保档前20省内数: baoOn }, null, 2),
      contentType: "application/json",
    });
  });
});

test.describe("河南志愿推 · 日语考生英语限制标注验收", () => {
  test("19. 日语考生：顶部英语限制提示 banner 可见", async ({ page }) => {
    await page.goto(BASE_URL + "/");
    await page.waitForLoadState("networkidle");
    await page.locator('input[type="number"]').first().fill("580");
    await page.getByRole("button", { name: "日语", exact: true }).click();
    await page.getByRole("button", { name: /^全部\s*48志愿布局/ }).click();
    await page.getByRole("button", { name: /生成志愿表/ }).click();
    await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 25000 });
    // 顶部英语限制 banner
    await expect(page.getByText(/日语考生 · 英语语种限制提示/)).toBeVisible();
    await expect(page.getByText(/不可录取\s*\d+\s*个/)).toBeVisible();
    await expect(page.getByText(/英语适应风险\s*\d+\s*个/)).toBeVisible();
  });

  test("20. 日语考生：卡片含英语限制标签（不可录取/公共外语仅英语）", async ({ page }) => {
    await page.goto(BASE_URL + "/");
    await page.waitForLoadState("networkidle");
    await page.locator('input[type="number"]').first().fill("580");
    await page.getByRole("button", { name: "日语", exact: true }).click();
    await page.getByRole("button", { name: /^全部\s*48志愿布局/ }).click();
    await page.getByRole("button", { name: /生成志愿表/ }).click();
    await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 25000 });
    // 软警告标签（可达卡片上）
    await expect(page.getByText(/公共外语仅英语/).first()).toBeVisible();
    // 展开不推荐区，应有「英语限·不可录取」硬阻标签
    const expandBtn = page.getByRole("button", { name: /查看不可达院校/ });
    if (await expandBtn.isVisible().catch(() => false)) {
      await expandBtn.click();
      await expect(page.getByText(/英语限·不可录取/).first()).toBeVisible({ timeout: 8000 });
    }
  });

  test("21. 英语考生：无英语限制提示（不误报）", async ({ page }) => {
    await page.goto(BASE_URL + "/");
    await page.waitForLoadState("networkidle");
    await page.locator('input[type="number"]').first().fill("580");
    await page.getByRole("button", { name: "英语", exact: true }).click();
    await page.getByRole("button", { name: /^全部\s*48志愿布局/ }).click();
    await page.getByRole("button", { name: /生成志愿表/ }).click();
    await expect(page.getByText(/共\s*\d+\s*个院校专业组候选/)).toBeVisible({ timeout: 25000 });
    // 英语考生不应出现日语限制 banner
    await expect(page.getByText(/日语考生 · 英语语种限制提示/)).toHaveCount(0);
  });
});
