"""种子加载器：YAML → Domain（校验来源字段）→ Table Row（幂等 upsert）。

校验失败（含缺 source 字段）由 Pydantic ValidationError 捕获并包装为 SeedLoadError，
报告文件名与记录标识，不静默跳过。
"""

from pathlib import Path

import yaml
from pydantic import ValidationError
from sqlmodel import Session, select

from app.models.admission import AdmissionRecord
from app.models.career import Career
from app.models.city import CityCost
from app.models.insurance import SocialInsurance
from app.models.major import Major
from app.models.tables import (
    AdmissionRow, CareerRow, CityCostRow, MajorRow,
    SocialInsuranceRow, UniversityRow,
)
from app.models.university import University
from app.repositories.mappers import (
    admission_to_row, career_to_row, city_to_row,
    insurance_to_row, major_to_row, university_to_row, _check_sourced,
)


class SeedLoadError(Exception):
    """种子加载校验失败。"""


# (相对路径, Domain类, Row类, to_row函数, 业务主键字段列表)
SEED_SPECS = [
    ("careers/careers.yaml", Career, CareerRow, career_to_row, ["name"]),
    ("cities/cities.yaml", CityCost, CityCostRow, city_to_row, ["city"]),
    ("universities/universities.yaml", University, UniversityRow, university_to_row, ["name"]),
    ("majors/majors.yaml", Major, MajorRow, major_to_row, ["name"]),
    ("insurance/insurance.yaml", SocialInsurance, SocialInsuranceRow, insurance_to_row, ["city"]),
    ("admissions/admissions.yaml", AdmissionRecord, AdmissionRow, admission_to_row,
     ["school", "major", "province", "year"]),
]


def is_db_empty(session: Session) -> bool:
    """DB 是否无任何核心数据（检查全部 6 张核心数据表）。

    覆盖 careers/cities/universities/majors/social_insurance/admissions，
    避免部分加载场景误判为空触发全量重载。
    """
    row_classes = (CareerRow, CityCostRow, UniversityRow, MajorRow,
                   SocialInsuranceRow, AdmissionRow)
    return all(session.exec(select(cls)).first() is None for cls in row_classes)


def _find_existing(session: Session, row_cls, match_keys: dict):
    stmt = select(row_cls)
    for k, v in match_keys.items():
        stmt = stmt.where(getattr(row_cls, k) == v)
    return session.exec(stmt).first()


def load_all_seeds(seed_dir: Path, session: Session) -> dict:
    """加载 seed_dir 下全部种子 YAML。返回 {entity: (count, rejected)}。

    幂等：按业务主键 upsert，重复执行不产生重复记录。
    缺来源字段或校验失败 → 抛 SeedLoadError（不静默跳过）。
    """
    seed_dir = Path(seed_dir)
    report: dict[str, tuple[int, int]] = {}
    for rel, domain_cls, row_cls, to_row, match_keys in SEED_SPECS:
        path = seed_dir / rel
        entity = rel.split("/")[0]
        if not path.exists():
            report[entity] = (0, 0)
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        count = 0
        for idx, rec in enumerate(data):
            try:
                dom = domain_cls.model_validate(rec)
            except ValidationError as e:
                ident = {k: rec.get(k) for k in match_keys} if isinstance(rec, dict) else {}
                raise SeedLoadError(
                    f"{path.name}[{idx}] 校验失败 {ident} —— {e}"
                ) from e
            row = to_row(dom)
            _check_sourced(row)  # 写回前校验来源不变量（confidence 范围）
            key = {k: getattr(row, k) for k in match_keys}
            existing = _find_existing(session, row_cls, key)
            if existing:
                # upsert：更新已有记录的全部字段（除 id）
                for field in row.model_dump():
                    if field != "id":
                        setattr(existing, field, getattr(row, field))
            else:
                session.add(row)
            count += 1
        session.commit()
        report[entity] = (count, 0)
    return report
