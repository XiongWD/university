"""资格链引擎测试（V2.2 Phase 1 核心——定义可行解空间）。

验证四类规则ABCD + 弟弟场景（480+日语）：
A语种(硬) B单科(硬,区分外语/英语) C选科(硬) D数学(仅章程明确硬)
关键：日语考生被英语限定专业过滤；数学弱不擅自门槛。
"""
import pytest

from app.engine.eligibility import check_eligibility, filter_eligible
from app.models.eligibility import (
    AdmissionOfferingRule, BlockedField, EnglishLevel,
    StudentAcademicProfile, SubjectScoreRule,
)


def _student(
    lang="日语", fl_score=120, math=75, primary="历史",
    electives=None, english_level=EnglishLevel.BASIC,
):
    return StudentAcademicProfile(
        province="河南", admission_year=2026, total_score=480,
        primary_subject=primary,
        chinese_score=100, math_score=math,
        exam_foreign_language=lang, foreign_language_score=fl_score,
        english_actual_level=english_level,
        elective_subjects=electives or ["政治", "地理"],
    )


def _rule(
    school="测试大学", required_lang=None, accepted=None,
    score_rules=None, primary_req=None, elective_rule=None,
    english_dep="low", instruction_langs=None, public_langs=None,
    oral_required=False,
):
    return AdmissionOfferingRule(
        school=school, major_group_code="101", province="河南",
        required_exam_language=required_lang,
        accepted_exam_languages=accepted or [],
        subject_score_rules=score_rules or [],
        primary_subject_requirement=primary_req,
        elective_subject_rule=elective_rule or {},
        english_dependency_level=english_dep,
        major_instruction_languages=instruction_langs or [],
        public_foreign_languages=public_langs or [],
        oral_test_required=oral_required,
        source="test", as_of="2026-06-01", confidence=0.8,
    )


# ===== A类：高考应试语种（硬约束）=====
def test_japanese_blocked_from_english_required_major():
    """日语考生+要求英语语种专业→INELIGIBLE（核心：弟弟场景）。"""
    student = _student(lang="日语")
    rule = _rule(required_lang="英语")
    result = check_eligibility(student, rule)
    assert not result.eligible
    assert BlockedField.EXAM_LANGUAGE in result.blocked_fields
    # reasons 含具体语种说明（可解释）
    assert any("英语" in r for r in result.reasons)


def test_japanese_allowed_when_no_language_restriction():
    """日语考生+无语种限制→eligible。"""
    student = _student(lang="日语")
    rule = _rule(required_lang=None, accepted=[])  # 不限
    result = check_eligibility(student, rule)
    assert result.eligible


def test_japanese_allowed_in_accepted_list():
    """日语考生+接受英语/日语→eligible。"""
    student = _student(lang="日语")
    rule = _rule(accepted=["英语", "日语"])
    assert check_eligibility(student, rule).eligible


def test_english_student_passes_english_required():
    """英语考生+要求英语→eligible。"""
    student = _student(lang="英语")
    rule = _rule(required_lang="英语")
    assert check_eligibility(student, rule).eligible


# ===== B类：单科门槛（区分外语/英语）=====
def test_foreign_language_threshold_uses_exam_language_score():
    """'外语≥110'不限语种→日语考生用日语分(120)判断→通过。"""
    student = _student(lang="日语", fl_score=120)
    rule = _rule(score_rules=[
        SubjectScoreRule(subject="foreign_language", threshold=110, source_text="外语≥110")
    ])
    assert check_eligibility(student, rule).eligible


def test_foreign_language_threshold_fails_low_score():
    """'外语≥110'+日语分100→不符。"""
    student = _student(lang="日语", fl_score=100)
    rule = _rule(score_rules=[
        SubjectScoreRule(subject="foreign_language", threshold=110)
    ])
    result = check_eligibility(student, rule)
    assert not result.eligible
    assert BlockedField.FOREIGN_SCORE in result.blocked_fields


def test_english_threshold_blocks_japanese_student():
    """'英语≥110'→日语考生无英语单科成绩→不符（关键区分外语vs英语）。"""
    student = _student(lang="日语", fl_score=140)  # 日语140分很高
    rule = _rule(score_rules=[
        SubjectScoreRule(subject="english", threshold=110, source_text="英语单科≥110")
    ])
    result = check_eligibility(student, rule)
    assert not result.eligible
    assert BlockedField.ENGLISH_SCORE in result.blocked_fields


def test_math_threshold_only_when_charter_specifies():
    """章程明确数学≥95→不达标不符。"""
    student = _student(math=75)
    rule = _rule(score_rules=[
        SubjectScoreRule(subject="math", threshold=95, source_text="数学≥95")
    ])
    result = check_eligibility(student, rule)
    assert not result.eligible
    assert BlockedField.MATH_SCORE in result.blocked_fields


def test_no_math_threshold_means_no_block():
    """章程无数学门槛→数学75也不挡（不擅自创造门槛）。"""
    student = _student(math=75)
    rule = _rule(score_rules=[])  # 无单科规则
    result = check_eligibility(student, rule)
    assert result.eligible  # 数学弱但不挡资格


# ===== C类：3+1+2 选科 =====
def test_primary_subject_history_required():
    """要求历史+考生历史→通过；考生物理→不符。"""
    rule = _rule(primary_req="历史")
    assert check_eligibility(_student(primary="历史"), rule).eligible
    result = check_eligibility(_student(primary="物理"), rule)
    assert not result.eligible
    assert BlockedField.PRIMARY_SUBJECT in result.blocked_fields


def test_elective_require_specific():
    """再选要求含政治+考生无政治→不符。"""
    rule = _rule(elective_rule={"require": ["政治"]})
    student = _student(electives=["地理", "生物"])  # 无政治
    result = check_eligibility(student, rule)
    assert not result.eligible
    assert BlockedField.ELECTIVE_SUBJECT in result.blocked_fields


def test_elective_any_of():
    """再选至少含化学/生物之一+考生有生物→通过。"""
    rule = _rule(elective_rule={"any_of": ["化学", "生物"]})
    student = _student(electives=["政治", "生物"])
    assert check_eligibility(student, rule).eligible


def test_brother_electives_match():
    """弟弟政治+地理→符合不限/要求政治的组。"""
    rule = _rule(elective_rule={"require": ["政治"]})
    student = _student(electives=["政治", "地理"])
    assert check_eligibility(student, rule).eligible


# ===== D类：口试 =====
def test_oral_test_required_blocks_if_not_taken():
    rule = _rule(oral_required=True)
    student = _student()
    student.oral_test_taken = False
    result = check_eligibility(student, rule)
    assert not result.eligible
    assert BlockedField.ORAL_TEST in result.blocked_fields


# ===== 软风险：语言适应（不挡资格）=====
def test_language_risk_for_japanese_in_english_taught():
    """日语考生+入学后英语教学为主→eligible但language_risk高。"""
    student = _student(lang="日语", english_level=EnglishLevel.BASIC)
    rule = _rule(
        required_lang=None,  # 不限语种，可报
        english_dep="high",
        instruction_langs=["英语"],
        public_langs=["英语"],  # 无日语公共外语
    )
    result = check_eligibility(student, rule)
    assert result.eligible  # 可报
    assert result.language_risk in ("medium", "high")  # 但有软风险


def test_no_language_risk_when_japanese_supported():
    """日语考生+学校开日语公共外语→低风险。"""
    student = _student(lang="日语")
    rule = _rule(public_langs=["英语", "日语"], english_dep="low")
    result = check_eligibility(student, rule)
    assert result.language_risk == "low"


# ===== 可解释性 =====
def test_blocked_summary_human_readable():
    """阻挡原因人类可读。"""
    student = _student(lang="日语")
    rule = _rule(required_lang="英语")
    result = check_eligibility(student, rule)
    assert "英语" in result.blocked_summary or "语种" in result.blocked_summary


def test_eligible_has_positive_reason():
    """通过时有正面原因。"""
    result = check_eligibility(_student(), _rule())
    assert result.eligible
    assert len(result.reasons) > 0


# ===== 批量过滤（可行解空间定义）=====
def test_filter_eligible_partitions():
    """filter_eligible正确划分可行/不可行。"""
    student = _student(lang="日语", math=75)
    offerings = [
        _rule(school="A大学"),  # 无限制→eligible
        _rule(school="B大学", required_lang="英语"),  # 限英语→ineligible
        _rule(school="C大学", score_rules=[  # 数学≥90→ineligible(75)
            SubjectScoreRule(subject="math", threshold=90)
        ]),
        _rule(school="D大学", accepted=["英语", "日语"]),  # 接受日语→eligible
    ]
    eligible, ineligible = filter_eligible(student, offerings)
    assert len(eligible) == 2  # A, D
    assert len(ineligible) == 2  # B, C
    eligible_schools = [o.school for o, _ in eligible]
    assert "A大学" in eligible_schools
    assert "D大学" in eligible_schools


def test_filter_eligible_keeps_block_reasons():
    """不可行列表保留阻挡原因（可解释）。"""
    student = _student(lang="日语")
    offerings = [_rule(school="英语专业校", required_lang="英语")]
    _, ineligible = filter_eligible(student, offerings)
    assert len(ineligible) == 1
    off, result = ineligible[0]
    assert not result.eligible
    assert any("英语" in r or "语种" in r for r in result.reasons)
