"""河南志愿推数据源登记模型（design §2、§2.1）。

每个数据集必须登记权威主来源、所需字段、验真规则和缺失降级行为，
不允许只靠手工伪造种子。year_type 区分历史基准层 / 2026 政策招生层 / 当前信号层。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

# 允许的数据版本分层（design §2.2）
_ALLOWED_YEAR_TYPES = {"historical", "latest_2026", "historical_and_latest", "current_signal"}


class HenanDataSource(BaseModel):
    """一条河南数据集的来源与约束登记。"""

    dataset_key: str
    display_name: str
    year_type: str
    years: list[int] = Field(default_factory=list)
    primary_source_name: str
    # 用 str 而非 HttpUrl：来源链接需可追溯（design §2 字段列表），
    # 且便于做 startswith 校验，避免 HttpUrl 序列化差异。
    primary_source_url: str
    auxiliary_source_names: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    verification_rules: list[str] = Field(default_factory=list)
    missing_data_behavior: str = ""
    blocks_recommendation_when_missing: bool = False

    def validate_year_type(self) -> None:
        if self.year_type not in _ALLOWED_YEAR_TYPES:
            raise ValueError(
                f"year_type must be one of {sorted(_ALLOWED_YEAR_TYPES)} (got {self.year_type!r})"
            )
