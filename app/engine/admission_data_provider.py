"""招生数据提供方接口与河南实现（design §4.4 省内外互补、后期外省扩展）。

AdmissionDataProvider 是为外省扩展预留的接口；HenanAdmissionDataProvider 当前
只服务河南考生，只保留 source_province=河南 的招生计划（含省内与省外高校），
绝不把全国计划或外省计划误当作河南计划。
"""
from __future__ import annotations

from typing import Protocol


class AdmissionDataProvider(Protocol):
    """招生数据提供方接口（按考生生源地接入对应省份计划/专业组/志愿规则）。"""

    source_province: str

    def ensure_supported(self, source_province: str) -> None:
        ...

    def filter_plans_for_source_province(self, plans: list[dict], source_province: str) -> list[dict]:
        ...


class HenanAdmissionDataProvider:
    """河南志愿推的招生数据提供方。source_province 固定河南。"""

    source_province = "河南"

    def ensure_supported(self, source_province: str) -> None:
        if source_province != self.source_province:
            raise ValueError("河南志愿推当前仅支持河南考生")

    def filter_plans_for_source_province(self, plans: list[dict], source_province: str) -> list[dict]:
        self.ensure_supported(source_province)
        return [plan for plan in plans if plan.get("source_province") == self.source_province]
