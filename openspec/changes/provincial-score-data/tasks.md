## 1. 数据模型层（app/models）

- [ ] 1.1 实现 `app/models/provincial.py`：`ProvincialControlLine` 模型（省份/年份/科类 track + 批次线集合 special_line/first_batch/second_batch/undergrad_batch/junior_college，各批次可选），继承 SourcedRecord，校验分数非负、必填字段
- [ ] 1.2 实现 `ScoreRankTable`（表头：省份/年份/科类 + 来源）与 `ScoreRankEntry`（score/count_at/cumulative_rank），含累计位次单调性校验（高分位次小）
- [ ] 1.3 扩展 `app/models/tables.py`：新增 `ProvincialControlLineRow`、`ScoreRankTableRow`、`ScoreRankEntryRow`（SQLModel 拍平，含来源字段 + _check_sourced 校验）

## 2. Repository 映射

- [ ] 2.1 在 `app/repositories/mappers.py` 新增省级数据的 `*_to_row` / `*_to_domain` 映射（provincial_control_line、score_rank_table、score_rank_entry 三类）
- [ ] 2.2 测试映射往返（roundtrip）不丢字段、来源完整

## 3. 数据查询逻辑（位次法双向查询）

- [ ] 3.1 实现分数→累计位次查询（按省/年/科类 + 分数精确匹配）
- [ ] 3.2 实现位次→分数查询（就近匹配：精确位次不存在时取最接近的分数段）
- [ ] 3.3 单元测试双向查询（含就近匹配场景）

## 4. 数据集导入器（app/loader/dataset_importer.py）

- [ ] 4.1 实现公开数据集（CSV/JSON）解析省控线与一分一段表
- [ ] 4.2 实现数据清洗（类型转换、去重、缺失剔除）
- [ ] 4.3 实现幂等导入（复用 Repository upsert）+ 来源标注（数据集名/年份/confidence）
- [ ] 4.4 实现合理性校验（省控线分数非负、一分一段表位次单调性），校验失败拒绝并报告
- [ ] 4.5 测试导入（合法导入、脏数据拒绝、增量更新、幂等）

## 5. 种子数据（data/seed/provincial/）

- [ ] 5.1 编写河南近3年（如2022-2024）省控线种子（文科+理科，一本/二本/专科线）
- [ ] 5.2 编写广东近3年省控线种子（物理类+历史类，特殊类型招生线+本科批）
- [ ] 5.3 编写河南近3年一分一段表种子（文科+理科，每省每年≥100分数段，位次单调）
- [ ] 5.4 编写广东近3年一分一段表种子（物理类+历史类，位次单调）
- [ ] 5.5 扩展 seed_loader 注册省级数据 SEED_SPECS + 加载校验测试（规模达标、位次单调性、来源完整、官方数据 confidence≥0.8）

## 6. FastAPI 端点（app/api/routers/provincial.py）

- [ ] 6.1 实现 `GET /api/v1/provincial/control-line`（省控线查询，含来源字段）
- [ ] 6.2 实现 `GET /api/v1/provincial/score-rank`（一分一段表查询）
- [ ] 6.3 实现 `GET /api/v1/provincial/score-rank/rank`（分数查累计位次）
- [ ] 6.4 实现 `GET /api/v1/provincial/score-rank/score`（位次查分数就近匹配）
- [ ] 6.5 注册 router 到 main.py + 启动加载省级种子
- [ ] 6.6 API 端点测试（各查询返回来源字段、空结果不报错）

## 7. 验证与文档

- [ ] 7.1 单元测试：模型校验（省控线批次可选/一分一段表位次单调性）、双向查询、导入清洗
- [ ] 7.2 端到端验证：河南690分查位次、广东本科批查询、来源字段全链路
- [ ] 7.3 更新 README 增加省级数据端点说明 + 合规检查（无预测措辞，标注历史数据）
