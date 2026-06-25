"""省级分数数据 Domain 模型：省控线 + 一分一段表。

复用 data-foundation 双模型架构，继承 SourcedRecord 强制来源追溯。
"""

from pydantic import BaseModel, field_validator, model_validator

from app.models.base import SourcedRecord


class BatchLines(BaseModel):
    """批次控制线集合，各省按适用性填写（其余为 None）。"""

    special_line: int | None = None       # 特殊类型招生控制线
    first_batch: int | None = None        # 一本线（河南用）
    second_batch: int | None = None       # 二本线（河南用）
    undergrad_batch: int | None = None    # 本科批（广东新高考合并批次）
    junior_college: int | None = None     # 专科线

    @field_validator("*", mode="before")
    @classmethod
    def _non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("批次线分数不能为负")
        return v


class ProvincialControlLine(SourcedRecord):
    """省控线：某省某年某科类各批次录取控制分数线。"""

    province: str
    year: int
    track: str  # 文/理/物理类/历史类 自由字符串
    batches: BatchLines


class ScoreRankEntry(BaseModel):
    """一分一段表分段记录。

    不变量：score 越高位次越小（cumulative_rank 越小）。
    count_at 用于分析竞争密度，cumulative_rank 用于位次法换算。
    """

    score: int
    count_at: int
    cumulative_rank: int

    @field_validator("score", "count_at", "cumulative_rank")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("score/count_at/cumulative_rank 不能为负")
        return v


class ScoreRankTable(SourcedRecord):
    """一分一段表表头（省/年/科类）+ 分段记录列表。

    校验累计位次单调性：score 降序时 cumulative_rank 严格递增（高分位次小）。
    """

    province: str
    year: int
    track: str
    entries: list[ScoreRankEntry]

    @model_validator(mode="after")
    def _monotonic(self) -> "ScoreRankTable":
        if len(self.entries) < 2:
            return self
        ordered = sorted(self.entries, key=lambda e: -e.score)
        for prev, cur in zip(ordered, ordered[1:]):
            if prev.cumulative_rank >= cur.cumulative_rank:
                raise ValueError(
                    f"累计位次单调性违反：score={prev.score} 位次"
                    f"{prev.cumulative_rank} >= score={cur.score} 位次"
                    f"{cur.cumulative_rank}"
                )
        return self
