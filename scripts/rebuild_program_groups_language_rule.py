"""重建 program_groups_2026.yaml 的语种规则（资格链专业级下沉，P0 修复）。

背景：
  旧导入器 import_henan_2026_catalog.py 用 setdefault 取首个专业的 accepted_exam_languages
  上卷为整组级，导致组内英语专业的"只招英语"限制污染整个专业组（353 个混合组误判）。

本脚本：
  - 数据源：data/seed/henan/enrollment_plans_2026.yaml（专业级，accepted_exam_languages 已正确）
  - 对每个专业组，用 normalize_language_rule 重新解析各专业 remark + accepted 字段
  - 用 aggregate_group_language_rule 聚合：仅当组内全专业规则一致才生成组级硬限制，
    混合规则组级置空 + has_mixed_language_rules=True
  - 重新生成 program_groups_2026.yaml（其余字段保持不变）

用法：
  python scripts/rebuild_program_groups_language_rule.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.loader.henan_language_rule import aggregate_group_language_rule, normalize_language_rule


def main() -> None:
    seed_dir = Path("data/seed/henan")
    groups_path = seed_dir / "program_groups_2026.yaml"
    plans_path = seed_dir / "enrollment_plans_2026.yaml"

    groups = yaml.safe_load(groups_path.read_text(encoding="utf-8"))
    plans = yaml.safe_load(plans_path.read_text(encoding="utf-8"))

    # 按专业组聚合专业计划（四元组 key，与引擎一致）
    plans_by_key: dict[tuple, list[dict]] = defaultdict(list)
    for p in plans:
        plans_by_key[(
            str(p["school_code"]), str(p["major_group_code"]),
            p["track"], p["batch"],
        )].append(p)

    stats = {"groups": 0, "mixed": 0, "group_lang_set": 0, "group_lang_cleared": 0,
             "english_group_kept": 0}

    for g in groups:
        stats["groups"] += 1
        key = (str(g["school_code"]), str(g["major_group_code"]), g["track"], g.get("batch", "本科批"))
        group_plans = plans_by_key.get(key, [])

        # 各专业的语种规则：优先用 accepted_exam_languages（已核验），remark 兜底解析
        major_rules = []
        for p in group_plans:
            acc = (p.get("accepted_exam_languages") or "").strip()
            if acc:
                # 专业级已核验的硬限制语种（如"英语"）
                major_rules.append({"rule_status": "restricted", "accepted": [acc], "required": acc})
            else:
                # 用 remark 重新解析（区分 unrestricted / unknown）
                major_rules.append(normalize_language_rule(p.get("remarks", "")))

        agg = aggregate_group_language_rule(major_rules)
        old_accepted = g.get("accepted_exam_languages") or []
        g["accepted_exam_languages"] = agg["accepted_exam_languages"]
        g["required_exam_language"] = agg["required_exam_language"]
        g["has_mixed_language_rules"] = agg["has_mixed_language_rules"]

        if agg["has_mixed_language_rules"]:
            stats["mixed"] += 1
        if agg["accepted_exam_languages"]:
            stats["group_lang_set"] += 1
            if "英语" in agg["accepted_exam_languages"]:
                stats["english_group_kept"] += 1
        if old_accepted and not agg["accepted_exam_languages"]:
            stats["group_lang_cleared"] += 1

    # 备份原文件
    backup = groups_path.with_suffix(".yaml.bak-langrule")
    backup.write_text(groups_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"备份原文件 -> {backup}")

    groups_path.write_text(
        yaml.safe_dump(groups, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    print("\n重建完成统计:")
    print(f"  专业组总数: {stats['groups']}")
    print(f"  混合规则组(组级置空): {stats['mixed']}")
    print(f"  组级语种非空(全专业一致): {stats['group_lang_set']}")
    print(f"    其中限英语: {stats['english_group_kept']}")
    print(f"  原组级有语种现被清空: {stats['group_lang_cleared']}")


if __name__ == "__main__":
    main()
