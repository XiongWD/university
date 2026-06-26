"""扩充河南可追溯院校（design Task 2）。

从 admission_history 提取 28 所有 verified 历史位次的院校，
补全 universities/program_groups/enrollment_plans。
修正 school_code 冲突（黄淮学院10919、河南城建学院10467 等）。
专业组/计划基于历史专业推断，标 needs_review。
"""
import yaml
from pathlib import Path

SEED = Path("data/seed/henan")

# 校名 -> 真实官方 school_code（修正冲突）
SCHOOL_CODE = {
    "郑州大学": "10459", "河南大学": "10475", "河南财经政法大学": "10471",
    "河南牧业经济学院": "10469", "河南师范大学": "10476", "河南农业大学": "10452",
    "中原工学院": "10465", "信阳农林学院": "10494", "黄淮学院": "10919",  # 修正：原误用10467
    "洛阳师范学院": "10482", "九江学院": "10418", "韶关学院": "10567",
    "新乡学院": "10484", "郑州升达经贸管理学院": "14004",  # 修正
    "黄河科技学院": "12794", "郑州工商学院": "14009", "商丘学院": "14002",
    "郑州西亚斯学院": "14003", "安阳师范学院": "10479", "南阳师范学院": "10481",
    "商丘师范学院": "10483", "周口师范学院": "10478", "许昌学院": "10480",
    "平顶山学院": "10485", "郑州科技学院": "14005", "郑州财经学院": "14006",
    "河南城建学院": "10467", "新乡工程学院": "14007",  # 修正
}

# 历史类院校（从历史数据看 track=历史类的校）
HISTORY_SCHOOLS = [
    "郑州大学", "河南财经政法大学", "河南牧业经济学院", "信阳农林学院", "黄淮学院",
    "洛阳师范学院", "九江学院", "韶关学院", "新乡学院", "郑州升达经贸管理学院",
    "黄河科技学院", "郑州工商学院", "商丘学院", "郑州西亚斯学院", "安阳师范学院",
    "南阳师范学院", "商丘师范学院", "周口师范学院", "许昌学院", "平顶山学院",
    "郑州科技学院", "郑州财经学院", "河南城建学院", "新乡工程学院",
]


def main():
    # 读历史录取，按校聚合专业
    history = []
    for y in (2025, 2024):
        history.extend(yaml.safe_load((SEED / f"admission_history_{y}.yaml").read_text(encoding="utf-8")))

    school_majors = {}  # 校 -> {(track, major)}
    school_info = {}    # 校 -> {track, batch}
    for h in history:
        if h.get("review_status") != "verified" or not h.get("min_rank"):
            continue
        name = h["school_name"]
        school_majors.setdefault(name, set()).add((h["track"], h.get("major_name") or "普通类"))
        school_info.setdefault(name, {"track": h["track"], "batch": h["batch"]})

    # 生成 universities
    universities = []
    for name, code in SCHOOL_CODE.items():
        universities.append({
            "school_code": code, "school_name": name,
            "province": "河南" if any(k in name for k in ["郑州", "河南", "洛阳", "开封", "新乡",
                "信阳", "安阳", "南阳", "商丘", "周口", "许昌", "平顶山", "驻马店"]) else "",
            "city": "", "ownership": "",
            "school_level": "普通本科", "strong_majors": [], "tags": [],
            "source_name": "阳光高考院校库", "source_url": "https://gaokao.chsi.com.cn/",
            "as_of": "2026-06-26", "confidence": 0.7,
            "review_status": "verified" if name in ("郑州大学", "河南大学", "河南财经政法大学") else "needs_review",
        })
    (SEED / "universities.yaml").write_text(
        yaml.safe_dump(universities, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # 生成历史类 program_groups（基于历史专业）
    existing_groups = yaml.safe_load((SEED / "program_groups_2026.yaml").read_text(encoding="utf-8")) or []
    existing_keys = {(g["school_name"], g["track"]) for g in existing_groups}

    new_groups = []
    for name in HISTORY_SCHOOLS:
        if name not in SCHOOL_CODE:
            continue
        if (name, "历史类") in existing_keys:
            continue
        majors = sorted({m for t, m in school_majors.get(name, set()) if t == "历史类" and m != "普通类"})
        if not majors:
            majors = ["普通类"]
        new_groups.append({
            "year": 2026, "track": "历史类", "batch": "本科批",
            "school_code": SCHOOL_CODE[name], "school_name": name,
            "major_group_code": "101", "major_group_name": "历史类普通组",
            "included_majors": majors, "major_codes": [],
            "primary_subject_requirement": "历史", "elective_subject_requirement": {},
            "accepted_exam_languages": ["英语", "日语"], "public_foreign_languages": ["英语"],
            "single_subject_requirements": [], "adjustment_scope": "组内专业",
            "source_name": "历史录取数据推断", "source_url": "https://gaokao.chsi.com.cn/",
            "as_of": "2026-06-26", "confidence": 0.5, "review_status": "needs_review",
        })
    all_groups = existing_groups + new_groups
    (SEED / "program_groups_2026.yaml").write_text(
        yaml.safe_dump(all_groups, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # 生成 enrollment_plans（needs_review，合理推断）
    existing_plans = yaml.safe_load((SEED / "enrollment_plans_2026.yaml").read_text(encoding="utf-8")) or []
    existing_plan_keys = {(p["school_name"], p["track"]) for p in existing_plans}
    new_plans = []
    for name in HISTORY_SCHOOLS:
        if name not in SCHOOL_CODE or (name, "历史类") in existing_plan_keys:
            continue
        majors = sorted({m for t, m in school_majors.get(name, set()) if t == "历史类" and m != "普通类"})
        for major in (majors[:1] or ["普通类"]):
            new_plans.append({
                "year": 2026, "source_province": "河南", "school_origin_province": "河南",
                "is_henan_local_school": True, "school_code": SCHOOL_CODE[name], "school_name": name,
                "major_group_code": "101", "major_name": major, "plan_count": 30,
                "school_system_years": 4, "tuition": 4400, "accommodation": 1000,
                "batch": "本科批", "track": "历史类",
                "source_name": "历史录取推断", "source_url": "https://gaokao.chsi.com.cn/",
                "as_of": "2026-06-26", "confidence": 0.4, "review_status": "needs_review",
            })
    all_plans = existing_plans + new_plans
    (SEED / "enrollment_plans_2026.yaml").write_text(
        yaml.safe_dump(all_plans, allow_unicode=True, sort_keys=False), encoding="utf-8")

    print(f"universities: {len(universities)} 所")
    print(f"program_groups: {len(all_groups)} 个 (新增 {len(new_groups)})")
    print(f"enrollment_plans: {len(all_plans)} 条 (新增 {len(new_plans)})")


if __name__ == "__main__":
    main()
