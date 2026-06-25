from enum import Enum

from app.models.base import SourcedRecord


class Batch(str, Enum):
    FIRST = "一本"
    SECOND = "二本"
    EARLY = "提前批"
    UNDERGRAD = "本科批"  # 新高考合并批次（河南2025+/广东）
    JUNIOR = "专科"


class AdmissionRecord(SourcedRecord):
    """高校历年录取数据。

    老高考(2023-2024河南文/理科)：major_group=None，按"学校+专业"粒度。
    新高考(2025+河南 物理类/历史类)：major_group 标注院校专业组，
    subject_requirement 标注选科要求(如"物理+化学")。
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
    major_group: str | None = None  # 院校专业组代码(新高考)，老高考为空
    subject_requirement: str | None = None  # 选科要求(如"物理+化学")，无要求为空
    foreign_language_required: str = "不限"  # 外语要求：不限/英语/可日语等，多数"不限"
    single_subject_requirements: dict[str, int] = {}  # 单科分数门槛，如{"数学":90,"外语":105}，空=无门槛
