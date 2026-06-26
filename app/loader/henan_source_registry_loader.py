"""加载河南数据源登记 YAML（design §2）。

校验每条数据源的 year_type 合法性，拒绝未分类数据集。
"""
from __future__ import annotations

from pathlib import Path

import yaml

from app.models.henan_source_registry import HenanDataSource


def load_henan_source_registry(path: str | Path) -> list[HenanDataSource]:
    source_path = Path(path)
    raw = yaml.safe_load(source_path.read_text(encoding="utf-8")) or []
    sources = [HenanDataSource(**item) for item in raw]
    for source in sources:
        source.validate_year_type()
    return sources
