"""外语语种规则解析与聚合（资格链专业级下沉，design §3.4/§8.2）。

核心原则：
  - 语种限制是**专业级**属性（同一专业组内不同专业可能要求不同语种），
    不能简单从专业级"上卷"为专业组级。
  - 三态区分（绝不能混淆）：
      restricted   = 明确核验为限报某语种（如"只招英语语种"）
      unrestricted = 明确核验为不限语种（如"零起点，语种不限"）
      unknown      = 未采集/空 remark（不能当"不限"，保守降级 uncertain）
  - 组级语种字段仅在**组内所有专业规则完全一致**时才生成；
    混合规则组级置空 + has_mixed_language_rules=True，运行时强制走专业级判断。

本模块供 import_henan_2026_catalog（数据导入）和 henan_recommendation（资格引擎）共用，
保证数据层与运行时对语种规则的解析口径一致，避免逻辑漂移。
"""
from __future__ import annotations

import re


# 语种限制解析正则（必须从原始 remark 文本抽取，置信度由原文支持）
# 顺序敏感：先判"明确不限"，再判"明确限报"，最后才是 unknown
_RE_ENGLISH_ONLY = re.compile(r"只招英语语种考生|只招英语|限英语语种|英语语种|应试语种.*英语")
_RE_JAPANESE_ONLY = re.compile(r"只招日语语种考生|只招日语|限日语语种|招日语考生|可招日语")
_RE_UNRESTRICTED = re.compile(r"语种不限|不限语种|不限外语|不限应试语种|零起点")


def normalize_language_rule(remark: str) -> dict:
    """把专业备注文本解析为结构化语种规则（专业级）。

    返回:
        {
            "rule_status": "restricted" | "unrestricted" | "unknown",
            "accepted": list[str],        # restricted 时为限制语种列表；其余为空
            "required": str | None,       # restricted 时为单语种硬要求；其余为 None
        }

    关键：空 remark / 无匹配 → unknown，绝不等于 unrestricted。
    （"没采集到限制"和"明确不限"是两回事，前者保守降级 uncertain。）
    """
    if not remark or not str(remark).strip():
        return {"rule_status": "unknown", "accepted": [], "required": None}
    text = str(remark)

    # 明确限报语种优先级最高：只要出现"只招英语语种/只招英语"等硬限制词，
    # 即便备注里同时有"零起点"（如吉林大学日语"零起点培养；只招英语语种的考生"），
    # 也应判为 restricted —— "只招英语语种"是明确的报考门槛，零起点只指入学后从零教。
    # 这避免了 unrestricted 正则先命中"零起点"而误判为不限。
    if _RE_ENGLISH_ONLY.search(text):
        return {"rule_status": "restricted", "accepted": ["英语"], "required": "英语"}
    if _RE_JAPANESE_ONLY.search(text):
        return {"rule_status": "restricted", "accepted": ["日语"], "required": "日语"}

    # 明确不限语种（零起点/语种不限）—— 仅当没有硬限制词时才生效
    if _RE_UNRESTRICTED.search(text):
        return {"rule_status": "unrestricted", "accepted": [], "required": None}

    # 含"英语"但非明确限报（如"英语适应""英语课程"）→ unknown，不当限制
    return {"rule_status": "unknown", "accepted": [], "required": None}


def aggregate_group_language_rule(major_rules: list[dict]) -> dict:
    """把组内各专业的语种规则聚合为组级规则。

    规则（design：组级字段仅在组内全专业一致时才生成）：
      - 组内所有专业的硬限制签名完全一致（全 restricted 同语种，或全 unrestricted，或全 unknown）
        → 生成组级规则（取该一致值）
      - 否则（混合 restricted+unrestricted/unknown，或不同 restricted 语种）
        → 组级硬限制置空 + has_mixed_language_rules=True，运行时走专业级

    参数:
        major_rules: 组内每个专业的 normalize_language_rule 返回值列表

    返回:
        {
            "accepted_exam_languages": list[str],  # 组级（混合时为空）
            "required_exam_language": str | None,   # 组级（混合时为 None）
            "has_mixed_language_rules": bool,       # 混合规则标记
        }
    """
    if not major_rules:
        return {"accepted_exam_languages": [], "required_exam_language": None,
                "has_mixed_language_rules": False}

    # 硬限制签名：restricted 时按语种集合，unrestricted/unknown 各自一类
    def _sig(rule: dict) -> tuple:
        if rule["rule_status"] == "restricted":
            return ("restricted", tuple(sorted(set(rule["accepted"]))))
        return (rule["rule_status"],)  # unrestricted / unknown

    signatures = {_sig(r) for r in major_rules}

    if len(signatures) == 1:
        # 组内全专业规则一致 → 上卷为组级
        only_sig = next(iter(signatures))
        if only_sig[0] == "restricted":
            accepted = list(next(iter(major_rules))["accepted"])
            required = next(iter(major_rules))["required"]
            return {"accepted_exam_languages": accepted, "required_exam_language": required,
                    "has_mixed_language_rules": False}
        # 全 unrestricted / 全 unknown → 组级无硬限制
        return {"accepted_exam_languages": [], "required_exam_language": None,
                "has_mixed_language_rules": False}

    # 混合规则 → 组级置空，强制专业级判断
    return {"accepted_exam_languages": [], "required_exam_language": None,
            "has_mixed_language_rules": True}
