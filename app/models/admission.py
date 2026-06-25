from enum import Enum

from app.models.base import SourcedRecord


class Batch(str, Enum):
    FIRST = "一本"
    SECOND = "二本"
    EARLY = "提前批"


class AdmissionRecord(SourcedRecord):
    """高校历年录取数据（仅 schema + 示例，不批量入库）。

    本层只做原始字段匹配查询；按分数筛选/院校推荐归属 decision-engine。
    """

    school: str
    major: str
    province: str
    year: int
    track: str  # 文/理/新高考选科自由字符串
    min_score: int
    min_rank: int
    avg_score: int
    batch: Batch
