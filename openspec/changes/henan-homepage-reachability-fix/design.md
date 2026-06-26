---
comet_change: henan-homepage-reachability-fix
role: technical-design
canonical_spec: openspec
---

## Context

首页推荐把所有 2026 专业组列出（含不推荐），用户未关注时造成干扰。target-evaluation 仅 4 所院校，全量官方源拿不到。现有 28 所可追溯院校可扩充。

## Goals / Non-Goals

**Goals:**
- 首页默认只展示可达候选（冲/稳/保/需人工复核），不推荐折叠
- 扩充 28 所可追溯院校 + 修 school_code 冲突
- UI 诚实标注覆盖比例

**Non-Goals:**
- 不攻克全量院校抓取（用户另行提供源）
- 不改候选生成算法（只改消费层展示）

## Decisions

**D1 不推荐默认折叠**：首页 buckets 渲染时，「不推荐」档位默认 `collapsed`，提供「查看 N 所不可达院校及原因」展开按钮。可达档位（冲/稳/保/需人工复核）始终展示。

**D2 扩充用历史数据推断**：28 所院校从 admission_history 提取，专业组/计划基于历史专业推断（标 needs_review），历史位次直接复用。已有 verified 的核心校保持 verified。

**D3 school_code 去重**：用官方院校代码（黄淮学院 10919、西亚斯 14003 实为独立代码需核实）。冲突的用「校名+代码」双校验。

## Risks / Trade-offs

- 28 所仍非全量 → UI 标注覆盖比例诚实告知
- 推断的专业组 needs_review → 不进稳保，符合门禁
