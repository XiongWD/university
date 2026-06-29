"""导入 2026 河南招生目录 normalized CSV → YAML（design Task 2）。

接受从官方目录人工/OCR 标准化的 CSV，产 universities/program_groups/enrollment_plans。
保留 source_url/as_of/review_status 每行可追溯。供后续全量增量导入用。
当前 seed 用方案 A 已核实的核心校真实数据手工构造。

语种规则专业级聚合（资格链 P0 修复）：
  语种限制是专业级属性，不能从首个专业"上卷"为整组级。
  本导入器逐专业收集语种规则，全部专业读完后调用 aggregate_group_language_rule
  聚合——仅当组内全专业规则一致才生成组级硬限制，混合规则组级置空 +
  has_mixed_language_rules=True（运行时走专业级判断）。避免再次制造污染数据。
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import yaml

# 统一的专业级语种规则聚合（数据层与运行时共用同一套口径，避免漂移）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.loader.henan_language_rule import aggregate_group_language_rule, normalize_language_rule


def split_pipe(value: str) -> list[str]:
    return [x.strip() for x in (value or "").split("|") if x.strip()]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/import_henan_2026_catalog.py <normalized_catalog.csv>")
    source = Path(sys.argv[1])
    rows = list(csv.DictReader(source.read_text(encoding="utf-8-sig").splitlines()))

    universities: dict[str, dict] = {}
    groups: dict[tuple, dict] = {}
    # 每个专业组内各专业的语种规则（专业级收集，最后统一聚合，避免 setdefault 首条污染）
    group_major_rules: dict[tuple, list[dict]] = defaultdict(list)
    plans: list[dict] = []

    for row in rows:
        school_code = row["school_code"]
        universities[school_code] = {
            "school_code": school_code,
            "school_name": row["school_name"],
            "province": row["school_origin_province"],
            "city": row.get("city", ""),
            "ownership": row.get("ownership", ""),
            "school_level": row.get("school_level", ""),
            "strong_majors": [],
            "tags": [t.strip() for t in (row.get("school_tags", "") or "").split("、") if t.strip()],
            "source_name": row["source_name"],
            "source_url": row["source_url"],
            "source_api_endpoint": row.get("source_api_endpoint", ""),
            "source_params": row.get("source_params", ""),
            "source_page": row.get("source_page", ""),
            "source_response_checksum": row.get("source_response_checksum", ""),
            "as_of": row["as_of"],
            "confidence": 0.9 if row["review_status"] == "verified" else 0.5,
            "review_status": row["review_status"],
        }
        key = (row["year"], row["track"], school_code, row["major_group_code"])
        # 专业级语种规则收集（不在此处决定组级，避免首条污染）
        major_lang_raw = row.get("accepted_exam_languages", "") or ""
        major_lang = split_pipe(major_lang_raw)
        if major_lang:
            # CSV 已核验的硬限制语种（如"英语"）→ restricted
            group_major_rules[key].append(
                {"rule_status": "restricted", "accepted": major_lang, "required": major_lang[0]}
            )
        else:
            # 用 remark 重新解析（区分 unrestricted / unknown）
            group_major_rules[key].append(normalize_language_rule(row.get("remarks", "")))

        group = groups.setdefault(key, {
            "year": int(row["year"]),
            "track": row["track"],
            "batch": row["batch"],
            "school_code": school_code,
            "school_name": row["school_name"],
            "major_group_code": row["major_group_code"],
            "major_group_name": row["major_group_name"],
            "included_majors": [],
            "major_codes": [],
            "primary_subject_requirement": row["primary_subject_requirement"],
            "elective_subject_requirement": yaml.safe_load(row["elective_subject_requirement"] or "{}") or {},
            # 组级语种字段留空，待全部专业收集后统一聚合（见循环后聚合块）
            "accepted_exam_languages": [],
            "required_exam_language": None,
            "public_foreign_languages": split_pipe(row["public_foreign_languages"]),
            "single_subject_requirements": [],
            "adjustment_scope": "组内专业",
            "physical_restrictions": row.get("physical_restrictions", ""),
            "special_qualification_type": row.get("special_qualification_type", ""),
            "source_name": row["source_name"],
            "source_url": row["source_url"],
            "source_api_endpoint": row.get("source_api_endpoint", ""),
            "source_params": row.get("source_params", ""),
            "source_page": row.get("source_page", ""),
            "source_response_checksum": row.get("source_response_checksum", ""),
            "as_of": row["as_of"],
            "confidence": 0.9 if row["review_status"] == "verified" else 0.5,
            "review_status": row["review_status"],
        })
        if row["major_name"] not in group["included_majors"]:
            group["included_majors"].append(row["major_name"])
        if row.get("major_code") and row["major_code"] not in group["major_codes"]:
            group["major_codes"].append(row["major_code"])

        plans.append({
            "year": int(row["year"]),
            "source_province": row["source_province"],
            "school_origin_province": row["school_origin_province"],
            "is_henan_local_school": row["school_origin_province"] == "河南",
            "school_code": school_code,
            "school_name": row["school_name"],
            "major_group_code": row["major_group_code"],
            "major_name": row["major_name"],
            "plan_count": int(row["plan_count"]),
            "school_system_years": 4,
            "tuition": int(row["tuition"] or 0) or None,
            "accommodation": int(row["accommodation"] or 0) or None,
            "batch": row["batch"],
            "track": row["track"],
            "campus": row.get("campus", ""),
            "remarks": row.get("remarks", ""),
            "physical_restrictions": row.get("physical_restrictions", ""),
            "special_qualification_type": row.get("special_qualification_type", ""),
            "accepted_exam_languages": row.get("accepted_exam_languages", ""),
            "source_name": row["source_name"],
            "source_url": row["source_url"],
            "source_api_endpoint": row.get("source_api_endpoint", ""),
            "source_params": row.get("source_params", ""),
            "source_page": row.get("source_page", ""),
            "source_response_checksum": row.get("source_response_checksum", ""),
            "as_of": row["as_of"],
            "confidence": 0.9 if row["review_status"] == "verified" else 0.5,
            "review_status": row["review_status"],
        })

    # 专业级语种规则聚合（资格链 P0 修复）：全部专业读完后，按组聚合语种规则。
    # 仅当组内全专业规则一致才生成组级硬限制；混合规则组级置空 + has_mixed_language_rules。
    mixed_count = 0
    restricted_count = 0
    for key, group in groups.items():
        major_rules = group_major_rules.get(key, [])
        agg = aggregate_group_language_rule(major_rules)
        group["accepted_exam_languages"] = agg["accepted_exam_languages"]
        group["required_exam_language"] = agg["required_exam_language"]
        group["has_mixed_language_rules"] = agg["has_mixed_language_rules"]
        if agg["has_mixed_language_rules"]:
            mixed_count += 1
        if agg["accepted_exam_languages"]:
            restricted_count += 1

    out_dir = Path("data/seed/henan")
    (out_dir / "universities.yaml").write_text(
        yaml.safe_dump(list(universities.values()), allow_unicode=True, sort_keys=False), encoding="utf-8")
    (out_dir / "program_groups_2026.yaml").write_text(
        yaml.safe_dump(list(groups.values()), allow_unicode=True, sort_keys=False), encoding="utf-8")
    (out_dir / "enrollment_plans_2026.yaml").write_text(
        yaml.safe_dump(plans, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"imported {len(universities)} universities, {len(groups)} groups, {len(plans)} plans")
    print(f"  语种规则聚合：组级硬限制 {restricted_count} 组（全专业一致），"
          f"混合规则（组级置空+走专业级）{mixed_count} 组")


if __name__ == "__main__":
    main()
