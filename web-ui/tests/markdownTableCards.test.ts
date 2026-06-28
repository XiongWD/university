import assert from "node:assert/strict";
import {
  parseMarkdownTable,
  sanitizeMarkdownTableLines,
  splitMarkdownIntoBlocks,
} from "../src/components/markdownTableCards.ts";

const messyRiskTable =
  "| 专业组代码 | 风险类型 | 具体描述 | 核实建议 | | ----------- | --------- | --------- | --------- | | 756600 | 语种限制 | 外国语言文学类通常默认以英语为教学语种，日语考生可能无法选读日语方向 | 致电招生办确认公共外语是否开设日语班 | | 756598 | 数学要求 | 财务管理、互联网金融专业对数学基础要求较高 | 查询该校该专业历年挂科率 |";

const normalized = sanitizeMarkdownTableLines(messyRiskTable).join("\n");

assert.equal(
  normalized,
  [
    "| 专业组代码 | 风险类型 | 具体描述 | 核实建议 |",
    "| ----------- | --------- | --------- | --------- |",
    "| 756600 | 语种限制 | 外国语言文学类通常默认以英语为教学语种，日语考生可能无法选读日语方向 | 致电招生办确认公共外语是否开设日语班 |",
    "| 756598 | 数学要求 | 财务管理、互联网金融专业对数学基础要求较高 | 查询该校该专业历年挂科率 |",
  ].join("\n"),
);

const parsed = parseMarkdownTable(normalized);

assert.deepEqual(parsed, {
  headers: ["专业组代码", "风险类型", "具体描述", "核实建议"],
  rows: [
    {
      title: "756600",
      fields: [
        { label: "风险类型", value: "语种限制" },
        {
          label: "具体描述",
          value: "外国语言文学类通常默认以英语为教学语种，日语考生可能无法选读日语方向",
        },
        { label: "核实建议", value: "致电招生办确认公共外语是否开设日语班" },
      ],
    },
    {
      title: "756598",
      fields: [
        { label: "风险类型", value: "数学要求" },
        { label: "具体描述", value: "财务管理、互联网金融专业对数学基础要求较高" },
        { label: "核实建议", value: "查询该校该专业历年挂科率" },
      ],
    },
  ],
});

const reportBlocks = splitMarkdownIntoBlocks(`## 薪资曲线对比
以下数据基于估算。
${messyRiskTable}
结论：需要核实风险。`);

assert.equal(reportBlocks.length, 3);
assert.equal(reportBlocks[0].type, "markdown");
assert.equal(reportBlocks[1].type, "table");
assert.equal(reportBlocks[2].type, "markdown");
if (reportBlocks[1].type === "table") {
  assert.equal(reportBlocks[1].table.rows.length, 2);
  assert.equal(reportBlocks[1].table.rows[0].title, "756600");
}

const compactNoSpaceBlocks = splitMarkdownIntoBlocks(
  "| 选择（专业组） | ROI | 主要风险 ||:---|:---|:---||756600（外语类）|3.4-5.3倍|语种限制风险||756599（商科类）|2.4-4.0倍|AI替代基础岗位|",
);

assert.equal(compactNoSpaceBlocks.length, 1);
assert.equal(compactNoSpaceBlocks[0].type, "table");
if (compactNoSpaceBlocks[0].type === "table") {
  assert.equal(compactNoSpaceBlocks[0].table.headers[0], "选择（专业组）");
  assert.equal(compactNoSpaceBlocks[0].table.rows[1].title, "756599（商科类）");
  assert.equal(compactNoSpaceBlocks[0].table.rows[1].fields[1].value, "AI替代基础岗位");
}
