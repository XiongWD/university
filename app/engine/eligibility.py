"""资格链引擎（V2.2 第0层——定义可行解空间，纯函数）。

系统语义铁律：Eligibility是"门"不是"权重项"。
所有后续优化(Market/Fit/Cost/Path)只能在本引擎输出的eligible_offerings上运行。

四类规则（评审要求逐条实现）：
A. 高考应试语种（硬约束）：required_exam_language不符→INELIGIBLE
B. 外语/英语单科门槛（硬约束，区分"外语"vs"英语"）：
   - "外语≥110"且不限语种→用考生外语分(日语考生用日语分)
   - "英语≥110"或要求英语语种→日语考生不符
C. 3+1+2选科（硬约束）：首选+再选符合
D. 数学/其他（仅章程明确门槛才硬过滤，否则不擅自创造门槛）
"""
from __future__ import annotations

from app.models.eligibility import (
    AdmissionOfferingRule,
    BlockedField,
    EligibilityResult,
    StudentAcademicProfile,
    SubjectScoreRule,
)


def _check_exam_language(
    student: StudentAcademicProfile, rule: AdmissionOfferingRule
) -> tuple[bool, str | None, BlockedField | None]:
    """A类：高考应试语种检查。"""
    # required_exam_language 优先
    if rule.required_exam_language:
        if student.exam_foreign_language != rule.required_exam_language:
            return (
                False,
                f"该专业要求高考外语语种为{rule.required_exam_language}，"
                f"考生为{student.exam_foreign_language}",
                BlockedField.EXAM_LANGUAGE,
            )
        return True, None, None
    # accepted_exam_languages 列表（空=不限）
    if rule.accepted_exam_languages:
        if student.exam_foreign_language not in rule.accepted_exam_languages:
            langs = "/".join(rule.accepted_exam_languages)
            return (
                False,
                f"该专业仅接受{langs}语种考生，考生为{student.exam_foreign_language}",
                BlockedField.EXAM_LANGUAGE,
            )
    return True, None, None


def _check_subject_score(
    student: StudentAcademicProfile, sr: SubjectScoreRule
) -> tuple[bool, str | None, BlockedField | None]:
    """B类：单科门槛检查（区分外语/英语/数学，区分语种适用）。"""
    # applies_to_exam_language：仅对特定语种考生适用
    if sr.applies_to_exam_language:
        if student.exam_foreign_language != sr.applies_to_exam_language:
            return True, None, None  # 不适用该考生，跳过（通过）

    # 取对应分数
    if sr.subject == "math":
        score = student.math_score
        field = BlockedField.MATH_SCORE
        label = "数学"
    elif sr.subject == "english":
        # "英语单科"：仅英语考生有英语分；日语考生无英语高考分→不符
        if student.exam_foreign_language != "英语":
            return (
                False,
                f"该专业要求英语单科{sr.operator}{sr.threshold}，"
                f"考生为{student.exam_foreign_language}语种无英语单科成绩",
                BlockedField.ENGLISH_SCORE,
            )
        score = student.foreign_language_score  # 英语考生的外语分=英语分
        field = BlockedField.ENGLISH_SCORE
        label = "英语"
    elif sr.subject == "foreign_language":
        # "外语单科"：不限语种，用考生的高考外语分（日语考生用日语分）
        score = student.foreign_language_score
        field = BlockedField.FOREIGN_SCORE
        label = "外语"
    else:
        return True, None, None  # 未知科目，跳过

    # 比较门槛
    if sr.operator == ">=":
        passed = score >= sr.threshold
    elif sr.operator == ">":
        passed = score > sr.threshold
    else:
        passed = score >= sr.threshold  # 默认>=

    if not passed:
        return (
            False,
            f"{label}单科{sr.operator}{sr.threshold}（章程：{sr.source_text or '未注明'}），"
            f"考生{label}={score}",
            field,
        )
    return True, None, None


def _check_primary_subject(
    student: StudentAcademicProfile, rule: AdmissionOfferingRule
) -> tuple[bool, str | None, BlockedField | None]:
    """C类：首选科目（历史/物理）。"""
    if rule.primary_subject_requirement:
        if student.primary_subject != rule.primary_subject_requirement:
            return (
                False,
                f"该专业要求首选{rule.primary_subject_requirement}，"
                f"考生首选{student.primary_subject}",
                BlockedField.PRIMARY_SUBJECT,
            )
    return True, None, None


def _check_elective_subjects(
    student: StudentAcademicProfile, rule: AdmissionOfferingRule
) -> tuple[bool, str | None, BlockedField | None]:
    """C类：再选科目（3+1+2的"2"）。"""
    es = rule.elective_subject_rule or {}
    require = es.get("require", [])  # 必须含的科目
    any_of = es.get("any_of", [])  # 至少含其一

    student_set = set(student.elective_subjects)
    for r in require:
        if r not in student_set:
            return (
                False,
                f"该专业要求再选含{r}，考生再选为{'+'.join(student.elective_subjects) or '无'}",
                BlockedField.ELECTIVE_SUBJECT,
            )
    if any_of:
        if not any(a in student_set for a in any_of):
            return (
                False,
                f"该专业要求再选至少含{'/'.join(any_of)}之一，"
                f"考生再选为{'+'.join(student.elective_subjects) or '无'}",
                BlockedField.ELECTIVE_SUBJECT,
            )
    return True, None, None


def _check_oral_test(
    student: StudentAcademicProfile, rule: AdmissionOfferingRule
) -> tuple[bool, str | None, BlockedField | None]:
    """口试要求。"""
    if rule.oral_test_required:
        if not student.oral_test_taken:
            return (
                False,
                "该专业要求参加外语口语测试，考生未参加",
                BlockedField.ORAL_TEST,
            )
    return True, None, None


def check_eligibility(
    student: StudentAcademicProfile, rule: AdmissionOfferingRule
) -> EligibilityResult:
    """完整资格判定（四类规则A/B/C/D，顺序检查，任一不符即INELIGIBLE）。

    返回 EligibilityResult：eligible + reasons + blocked_fields + language_risk。
    language_risk 是软风险（不挡资格但标入学后语言适应难度）。
    """
    reasons: list[str] = []
    blocked: list[BlockedField] = []

    # A类：应试语种
    ok, why, field = _check_exam_language(student, rule)
    if not ok:
        blocked.append(field)
        if why:
            reasons.append(why)

    # B类：单科门槛（逐条）
    for sr in rule.subject_score_rules:
        ok, why, field = _check_subject_score(student, sr)
        if not ok:
            blocked.append(field)
            if why:
                reasons.append(why)

    # C类：首选 + 再选
    ok, why, field = _check_primary_subject(student, rule)
    if not ok:
        blocked.append(field)
        if why:
            reasons.append(why)
    ok, why, field = _check_elective_subjects(student, rule)
    if not ok:
        blocked.append(field)
        if why:
            reasons.append(why)

    # 口试
    ok, why, field = _check_oral_test(student, rule)
    if not ok:
        blocked.append(field)
        if why:
            reasons.append(why)

    eligible = len(blocked) == 0

    # 软风险：入学后语言适应（D类，不挡资格）
    language_risk = "low"
    if eligible:
        if student.exam_foreign_language != "英语":
            # 日语等小语种考生，若入学后英语教学为主
            english_heavy = (
                rule.english_dependency_level in ("medium", "high")
                or "英语" in rule.major_instruction_languages
                or (rule.public_foreign_languages and "日语" not in rule.public_foreign_languages)
            )
            if english_heavy:
                # 风险级别取 english_dependency_level 与 language_transition_risk 较高者
                levels = {"low": 0, "medium": 1, "high": 2}
                dep = levels.get(rule.english_dependency_level, 0)
                trans = levels.get(rule.language_transition_risk, 0)
                risk_level = max(dep, trans, 1)  # 至少medium
                language_risk = {0: "low", 1: "medium", 2: "high"}[risk_level]

    return EligibilityResult(
        eligible=eligible,
        reasons=reasons if reasons else (["符合全部资格要求"] if eligible else ["不符合资格"]),
        blocked_fields=blocked,
        language_risk=language_risk,
    )


def filter_eligible(
    student: StudentAcademicProfile,
    offerings: list[AdmissionOfferingRule],
) -> tuple[list[tuple[AdmissionOfferingRule, EligibilityResult]], list[tuple[AdmissionOfferingRule, EligibilityResult]]]:
    """批量资格过滤，返回 (eligible, ineligible) 两个列表。

    这是可行解空间的定义：eligible 列表是后续所有优化的唯一输入域。
    ineligible 列表保留用于可解释（向用户展示"为何不可报"）。
    """
    eligible_list: list[tuple[AdmissionOfferingRule, EligibilityResult]] = []
    ineligible_list: list[tuple[AdmissionOfferingRule, EligibilityResult]] = []
    for off in offerings:
        result = check_eligibility(student, off)
        if result.eligible:
            eligible_list.append((off, result))
        else:
            ineligible_list.append((off, result))
    return eligible_list, ineligible_list
