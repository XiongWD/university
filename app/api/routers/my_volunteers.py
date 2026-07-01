"""我的志愿组 API（design：志愿编排工作台）。

单用户 MVP：owner_key 固定 "default"。服务端用 group.profile_snapshot 重新校验资格/档位，
不信任前端传的任何展示字段（前端只传 school_code+major_group_code）。

端点：
  GET    /my-volunteers                         获取志愿组（重算 latest_algorithm_tier + stats）
  GET    /my-volunteers/heao-assessment         heao 权威评估（2025 历年专业组录取数据）
  POST   /my-volunteers/items                   添加志愿（服务端重新校验）
  PATCH  /my-volunteers/layout                  原子布局更新（跨档拖拽专用）
  PATCH  /my-volunteers/items/{id}/tier         单改规划档位
  DELETE /my-volunteers/items/{id}              删除单个
  POST   /my-volunteers/clear                   清空全部
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session_dep
from app.models.volunteer import UserVolunteerGroup, VolunteerConflictError
from app.repositories import volunteer_repo

router = APIRouter(prefix="/my-volunteers", tags=["my-volunteers"])

DEFAULT_OWNER = "default"

# 测试隔离：当 VOLUNTEER_OWNER_ISOLATION=1 时，允许请求通过 X-Owner-Key header
# 选择独立 owner_key（每个 E2E 测试用唯一 owner，彻底隔离志愿组，杜绝测试间污染）。
# 生产环境默认关闭，保持单用户 MVP 的 "default" owner。
_OWNER_ISOLATION = os.getenv("VOLUNTEER_OWNER_ISOLATION", "") == "1"
_OWNER_HEADER = "X-Owner-Key"


def _resolve_owner(request: Request) -> str:
    """解析当前请求的 owner_key：隔离开启时读 header，否则固定 default。"""
    if not _OWNER_ISOLATION:
        return DEFAULT_OWNER
    owner = request.headers.get(_OWNER_HEADER) or DEFAULT_OWNER
    # 仅允许字母数字/下划线/连字符，避免注入或路径穿越
    if owner != DEFAULT_OWNER and not owner.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="非法 owner_key")
    return owner


class AddItemRequest(BaseModel):
    school_code: str
    major_group_code: str
    # 考生档案（首次添加时绑定，后续重算依据）。前端从当前推荐表单传入。
    profile: dict


class LayoutItem(BaseModel):
    item_id: int
    planned_tier: str | None = None
    sort_order: int


class LayoutRequest(BaseModel):
    items: list[LayoutItem]
    version: int


class TierRequest(BaseModel):
    planned_tier: str | None = None
    version: int


class ClearRequest(BaseModel):
    confirm: bool
    version: int


def _conflict_response(exc: VolunteerConflictError) -> JSONResponse:
    """乐观锁冲突 → 409，返回最新 group 供前端加载。"""
    body: dict = {"error": "version_conflict", "message": str(exc)}
    if exc.latest_group is not None:
        body["latest_group"] = exc.latest_group.model_dump(mode="json")
    return JSONResponse(status_code=409, content=body)


@router.get("")
def get_my_volunteers(request: Request, session: Session = Depends(get_session_dep)):
    """获取志愿组（GET 重算 latest_algorithm_tier + stats）。"""
    group = volunteer_repo.get_group(session, _resolve_owner(request))
    return group.model_dump(mode="json")


# heao 权威评估数据文件（由 scripts/dump_heao_assessment.py 生成）
_HEAO_ASSESSMENT_FILE = Path("data/seed/henan/heao_assessment_2025.yaml")


@lru_cache(maxsize=1)
def _load_university_meta() -> dict[str, dict]:
    """加载院校元数据索引：{校名(短): {ownership, province, city, school_code}}。"""
    p = Path("data/seed/henan/universities.yaml")
    if not p.exists():
        return {}
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    data = yaml.load(p.read_text(encoding="utf-8"), Loader=loader) or []
    idx: dict[str, dict] = {}
    for u in data:
        name = str(u.get("school_name", "")).split("(")[0].strip()
        if name:
            idx[name] = {
                "ownership": u.get("ownership", ""),
                "province": u.get("province", ""),
                "city": u.get("city", ""),
                "school_code": str(u.get("school_code", "")),
            }
    return idx


@lru_cache(maxsize=1)
def _load_tuition_index() -> dict[str, int]:
    """加载学费索引：{校名(短): 最低学费}。从 enrollment_plans 取每校最低学费。"""
    return _load_plan_costs()["tuition"]


@lru_cache(maxsize=1)
def _load_accommodation_index() -> dict[str, int]:
    """加载住宿费索引：{校名(短): 住宿费}。"""
    return _load_plan_costs()["accomm"]


@lru_cache(maxsize=1)
def _load_plan_costs() -> dict[str, dict]:
    """一次性加载学费+住宿费索引（enrollment_plans 8MB，用 CSafeLoader 加速）。

    enrollment_plans_2026.yaml 有 8266 行，默认 SafeLoader 要 19 秒，
    CSafeLoader 只要 3 秒。学费取每校最低值，住宿费取首个有效值。
    """
    p = Path("data/seed/henan/enrollment_plans_2026.yaml")
    if not p.exists():
        return {"tuition": {}, "accomm": {}}
    # CSafeLoader 比 SafeLoader 快 6 倍（8MB 文件 3s vs 19s）
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    data = yaml.load(p.read_text(encoding="utf-8"), Loader=loader) or []
    tuition: dict[str, int] = {}
    accomm: dict[str, int] = {}
    for plan in data:
        name = str(plan.get("school_name", "")).split("(")[0].strip()
        if not name:
            continue
        t = plan.get("tuition")
        if isinstance(t, int) and t > 0:
            if name not in tuition or t < tuition[name]:
                tuition[name] = t
        a = plan.get("accommodation")
        if isinstance(a, int) and a > 0 and name not in accomm:
            accomm[name] = a
    return {"tuition": tuition, "accomm": accomm}


def _enrich_school(record: dict, school_name: str) -> dict:
    """给记录补齐 ownership/province/city/tuition（从种子库查）。"""
    short = school_name.split("(")[0].strip()
    meta = _load_university_meta().get(short, {})
    tuition = _load_tuition_index().get(short)
    record["ownership"] = meta.get("ownership", "")
    record["province"] = meta.get("province", "")
    record["city"] = meta.get("city", "")
    record["tuition"] = tuition
    return record


@lru_cache(maxsize=1)
def _load_heao_assessment() -> dict[str, dict]:
    """加载 heao 评估 YAML，返回 {校名(短): 学校评估数据} 索引。

    校名取括号前的简称（yaml 里"中原科技学院(原...)"→"中原科技学院"），
    与 db school_name 对齐。补齐 ownership/province/city/tuition。
    """
    if not _HEAO_ASSESSMENT_FILE.exists():
        return {}
    data = yaml.safe_load(_HEAO_ASSESSMENT_FILE.read_text(encoding="utf-8")) or {}
    index: dict[str, dict] = {}
    for school in data.get("schools", []):
        name = str(school.get("school_name", "")).split("(")[0].strip()
        _enrich_school(school, name)
        index[name] = school
    return index


@router.get("/heao-assessment")
def get_heao_assessment():
    """返回志愿组各校的 heao 权威评估数据（2025 历年专业组录取）。

    数据源：河南志愿填报系统 book.heao.com.cn，结构化落盘于
    data/seed/henan/heao_assessment_2025.yaml。按校名索引，每校含
    各专业组(zyzh)的 2025 录取分数/位次/等位分换算/判档。
    """
    return _load_heao_assessment()


@lru_cache(maxsize=1)
def _load_biz_recommendations() -> list[dict]:
    """加载国贸/商务类专业组推荐（heao 验证），补齐性质/省份/学费。"""
    p = Path("data/evaluate/biz_verified_correct.json")
    if not p.exists():
        return []
    import json
    rows = json.loads(p.read_text(encoding="utf-8"))
    for r in rows:
        school = r.get("school", "")
        _enrich_school(r, school)
    return rows


@lru_cache(maxsize=1)
def _load_recommendation_text() -> str:
    """加载志愿组调整建议（markdown）。"""
    p = Path("data/evaluate/recommendation.md")
    return p.read_text(encoding="utf-8") if p.exists() else ""


@router.get("/full-assessment")
def get_full_assessment():
    """完整评估报告：13所志愿组评估 + 国贸/商务推荐 + 调整建议。

    聚合三个数据源，供「评估报告」页面一次性渲染：
    - heao_assessment: 13所各专业组 heao 权威评估
    - biz_recommendations: heao 验证通过的国贸核心专业候选
    - recommendation: 志愿组调整建议文本
    """
    return {
        "heao_assessment": _load_heao_assessment(),
        "biz_recommendations": _load_biz_recommendations(),
        "recommendation_text": _load_recommendation_text(),
    }


# 弟弟档案（生成志愿建议用）
_BROTHER_SCORE = 480
_BROTHER_RANK = 73822


@lru_cache(maxsize=1)
def _load_city_cost() -> dict[str, int]:
    """加载城市月生活费索引：{城市名: 月综合中位}。"""
    p = Path("data/seed/cities/cities.yaml")
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    idx: dict[str, int] = {}
    for c in data:
        mt = c.get("monthly_total")
        if isinstance(mt, dict) and c.get("city"):
            # 取 low/high 中位
            lo, hi = mt.get("low", 0), mt.get("high", 0)
            idx[str(c["city"])] = (lo + hi) // 2
    return idx


def _classify_by_gap(gap: int) -> str:
    """按位次差判档。gap = 录取位次 - 弟弟位次。"""
    if gap < -3000:
        return "冲"
    elif gap < 2000:
        return "冲"
    elif gap < 9000:
        return "稳"
    elif gap < 18000:
        return "保"
    else:
        return "保"  # 超保底归保


@router.get("/volunteer-suggestion")
def get_volunteer_suggestion(
    rush: int = 3, steady: int = 5, safe: int = 8,
    prefer_local: bool = True, prefer_public: bool = True,
):
    """生成最终志愿建议（弟弟可直接参考填报版）。

    弟弟画像：480分/历史类/政治+地理/日语/数学64/河南。
    兴趣：贸易类 > 商务类 > 日语类。
    偏好：省内 > 公办 > 低费。

    默认配额：冲3 / 稳5 / 保8（共16，确保不掉档且优先心仪学校）。
    候选池 = 弟弟13所(heao评估) + 国贸推荐12个，**按专业组去重**（同校多组各自独立）。
    每项标注 source：brother(弟弟选) / recommended(推荐补充)。
    每项含 yxdh(院校代码)、planned_tier(弟弟原设定档位)、eligibility(选科/外语匹配)。
    """
    assessment = _load_heao_assessment()
    biz_recs = _load_biz_recommendations()
    uni_meta = _load_university_meta()
    tuition_idx = _load_tuition_index()
    accomm = _load_accommodation_index()
    city_cost = _load_city_cost()

    # 弟弟兴趣专业关键词（优先级：贸易 > 商务 > 日语）
    INTEREST_PRIORITY = [
        ("国际经济与贸易", 10), ("国际商务", 9), ("跨境电子商务", 9),
        ("贸易经济", 8), ("电子商务", 5), ("商务英语", 4),
        ("日语", 8), ("应用日语", 8), ("商务日语", 7),
        ("市场营销", 3), ("工商管理", 2), ("物流管理", 1),
    ]

    # 弟弟档案（从 db profile_snapshot 读取真实数据）
    import sqlite3
    brother_profile = {
        "score": _BROTHER_SCORE, "rank": _BROTHER_RANK, "track": "历史类",
        "primary_subject": "历史", "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "日语",
    }
    brother_schools: set[str] = set()
    brother_planned: dict[str, str] = {}
    db_path = Path("data/llm_sim.db")
    if db_path.exists():
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
        # 读真实档案
        try:
            g = con.execute(
                "SELECT profile_snapshot FROM user_volunteer_groups WHERE owner_key='default' LIMIT 1"
            ).fetchone()
            if g and g["profile_snapshot"]:
                snap = g["profile_snapshot"]
                if isinstance(snap, str):
                    import json as _json
                    snap = _json.loads(snap)
                if isinstance(snap, dict):
                    brother_profile.update({
                        "score": snap.get("score", brother_profile["score"]),
                        "rank": snap.get("rank", brother_profile["rank"]),
                        "track": snap.get("track", brother_profile["track"]),
                        "primary_subject": snap.get("primary_subject", brother_profile["primary_subject"]),
                        "elective_subjects": snap.get("elective_subjects", brother_profile["elective_subjects"]),
                        "exam_foreign_language": snap.get("exam_foreign_language", brother_profile["exam_foreign_language"]),
                    })
        except Exception:
            pass
        # 读弟弟选的学校 + planned_tier
        rows = con.execute(
            "SELECT school_name, planned_tier FROM user_volunteer_items WHERE group_id="
            "(SELECT id FROM user_volunteer_groups WHERE owner_key='default')"
        ).fetchall()
        for r in rows:
            name = str(r["school_name"]).split("(")[0].strip()
            brother_schools.add(name)
            if r["planned_tier"]:
                brother_planned[name] = r["planned_tier"]
        con.close()

    # 选科匹配检查函数
    def check_eligibility(item: dict) -> dict:
        """根据弟弟选科+外语，检查专业组能否填。返回 {eligible, status, reasons[]}"""
        reasons = []
        req = (item.get("requirement", "") or "").strip()
        brother_subjects = set()
        if brother_profile.get("primary_subject"):
            brother_subjects.add(brother_profile["primary_subject"])
        for s in (brother_profile.get("elective_subjects") or []):
            brother_subjects.add(s)
        # 1. 科目要求（硬性：选科不符 = 不可填）
        if req and req != "不限":
            required = [s.strip() for s in req.replace("+", ",").replace("（", "(").split("(")[0].split(",") if s.strip()]
            missing = [s for s in required if s not in brother_subjects]
            if missing:
                reasons.append(f"科目不符: 需{req}，弟弟选[{'+'.join(sorted(brother_subjects))}]")
        # 2. 外语启发式：含"英语(师范)""翻译"等专业，弟弟日语风险
        # "商务英语"通常可招日语，不算风险
        risk_majors = {"英语(师范)", "英语教育", "翻译"}
        for m in (item.get("majors") or []):
            mn = m.get("major_name", "")
            if mn in risk_majors and brother_profile.get("exam_foreign_language") == "日语":
                reasons.append(f"含「{mn}」专业（日语生录取受限）")
                break
        # 状态判定
        if not reasons:
            status = "可填"
            eligible = True
        else:
            # 有"科目不符"= 不可填；其他 = 有风险但可填
            if any("科目不符" in r for r in reasons):
                status = "不可填"
                eligible = False
            else:
                status = "有风险"
                eligible = True
        return {"eligible": eligible, "status": status, "reasons": reasons}

    # 收集候选池（每个专业组一条，按 school_zyzh 去重，同校多组各自独立保留）
    pool: list[dict] = []
    seen_keys: set[str] = set()

    # 从 heao 评估取（弟弟13所各专业组）
    for name, school in assessment.items():
        meta = uni_meta.get(name, {})
        is_brother = name in brother_schools
        for g in school.get("groups", []):
            zyzh = str(g.get("zyzh", ""))
            if not zyzh:
                continue
            key = f"{name}_{zyzh}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            rank = g.get("min_rank_2025")
            gap = (rank - _BROTHER_RANK) if rank else None
            tier = _classify_by_gap(gap) if gap is not None else "稳"
            pool.append({
                "school": name,
                "yxdh": school.get("yxdh", ""),  # 院校代码
                "ownership": meta.get("ownership", ""),
                "province": meta.get("province", ""),
                "city": meta.get("city", ""),
                "zyzh": zyzh,
                "requirement": g.get("requirement", ""),
                "min_score_2025": g.get("min_score_2025"),
                "min_rank_2025": rank,
                "equiv_score_2026": g.get("equiv_score_2026"),
                "gap": gap,
                "tier": tier,
                "majors": [
                    {"major_code": m.get("major_code", ""), "major_name": m.get("major_name", "")}
                    for m in g.get("majors", [])
                ],
                "tuition": tuition_idx.get(name),
                "accommodation": accomm.get(name, 1500),
                "source": "brother" if is_brother else "recommended",
                "planned_tier": brother_planned.get(name),  # 弟弟原设定档位
            })
            # 选科/外语匹配检查
            elig = check_eligibility(pool[-1])
            pool[-1].update({"eligible": elig["eligible"], "eligibility_status": elig["status"], "eligibility_reasons": elig["reasons"]})

    # 从国贸推荐取（12个，补充弟弟没选的校/组）
    for r in biz_recs:
        name = r.get("school", "")
        zyzh = str(r.get("zyzh", ""))
        key = f"{name}_{zyzh}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        meta = uni_meta.get(name, {})
        is_brother = name in brother_schools
        rank = r.get("rank")
        gap = r.get("gap")
        tier = _classify_by_gap(gap) if gap is not None else "冲"
        pool.append({
            "school": name,
            "yxdh": meta.get("school_code", ""),  # 院校代码（国贸推荐从 uni_meta 取）
            "ownership": r.get("ownership", meta.get("ownership", "")),
            "province": r.get("province", meta.get("province", "")),
            "city": meta.get("city", ""),
            "zyzh": zyzh,
            "requirement": r.get("req", ""),
            "min_score_2025": r.get("score"),
            "min_rank_2025": rank,
            "equiv_score_2026": None,
            "gap": gap,
            "tier": tier,
            "majors": [{"major_code": "", "major_name": m} for m in r.get("majors", [])],
            "tuition": r.get("tuition") or tuition_idx.get(name),
            "accommodation": accomm.get(name, 1500),
            "source": "brother" if is_brother else "recommended",
            "planned_tier": brother_planned.get(name),
        })
        # 选科/外语匹配检查
        elig = check_eligibility(pool[-1])
        pool[-1].update({"eligible": elig["eligible"], "eligibility_status": elig["status"], "eligibility_reasons": elig["reasons"]})

    # 计算生活费（城市匹配，默认郑州）
    def city_monthly(city: str) -> int:
        if city in city_cost:
            return city_cost[city]
        for k, v in city_cost.items():
            if k in city or city in k:
                return v
        return 2000

    for item in pool:
        m_cost = city_monthly(item.get("city", ""))
        tuition = item.get("tuition") or 0
        accomm_cost = item.get("accommodation", 1500)
        item["monthly_cost"] = m_cost
        item["four_year_total"] = tuition * 4 + accomm_cost * 4 + m_cost * 10 * 4

    # 按配额选校：每档按综合分数排序
    # 综合分 = -位次差（保稳档越大越好=录取优势大；冲档负差越接近0=越有戏）
    #          + 兴趣专业匹配加权（贸易 > 商务 > 日语，匹配加 10/9/8 分）
    #          + 省内偏好（+5）+ 公办偏好（+3）+ 低费偏好（学费<15000 +2）
    def interest_score(item: dict) -> int:
        s = 0
        majors = [m.get("major_name", "") for m in item.get("majors", [])]
        for kw, w in INTEREST_PRIORITY:
            if any(kw in m for m in majors):
                s += w
        return s

    def sort_key(item):
        gap = item.get("gap")
        if gap is None:
            gap = 999999
        # 基础分：保稳档 gap 大优先（录取把握大），冲档 gap 接近 0 优先
        if item["tier"] == "冲":
            base = -abs(gap)  # 越接近 0 越前
        else:
            base = gap  # 越大越前
        # 加成
        bonus = interest_score(item)
        if prefer_local and item.get("province") == "河南":
            bonus += 5
        if prefer_public and item.get("ownership") == "公办":
            bonus += 3
        tuition = item.get("tuition") or 999999
        if tuition <= 15000:
            bonus += 2
        # 综合：基础分是位次差（数量级大），bonus 拉开同 gap 内的偏好
        return (-base, -bonus)  # 升序：base 大→-base 小，bonus 大→-bonus 小

    pool.sort(key=sort_key)
    by_tier: dict[str, list[dict]] = {"冲": [], "稳": [], "保": []}
    for item in pool:
        by_tier[item["tier"]].append(item)

    # 配额选校时**跳过选科不符的组**（硬性不能填）
    quota = {"冲": rush, "稳": steady, "保": safe}
    selected: list[dict] = []
    skipped_ineligible: list[dict] = []  # 记录被跳过的，回报给用户
    for t in ["冲", "稳", "保"]:
        for it in by_tier[t]:
            if not it.get("eligible", True):
                skipped_ineligible.append(it)
                continue
            if len([x for x in selected if x["tier"] == t]) >= quota[t]:
                continue
            selected.append(it)

    for i, item in enumerate(selected):
        item["index"] = i + 1

    # 统计（费用用最高/最低范围，不汇总）
    four_year_costs = [s.get("four_year_total", 0) for s in selected if s.get("four_year_total")]
    tuitions = [s.get("tuition", 0) for s in selected if s.get("tuition")]
    stats = {
        "total": len(selected),
        "by_tier": {t: sum(1 for s in selected if s["tier"] == t) for t in ["冲", "稳", "保"]},
        "by_source": {
            "brother": sum(1 for s in selected if s.get("source") == "brother"),
            "recommended": sum(1 for s in selected if s.get("source") == "recommended"),
        },
        "by_ownership": {},
        "by_province": {},
        "tuition_min": min(tuitions) if tuitions else 0,
        "tuition_max": max(tuitions) if tuitions else 0,
        "four_year_min": min(four_year_costs) if four_year_costs else 0,
        "four_year_max": max(four_year_costs) if four_year_costs else 0,
        "local_count": sum(1 for s in selected if s.get("province") == "河南"),
    }
    for s in selected:
        own = s.get("ownership", "?")
        stats["by_ownership"][own] = stats["by_ownership"].get(own, 0) + 1
        prov = s.get("province", "?")
        stats["by_province"][prov] = stats["by_province"].get(prov, 0) + 1

    return {
        "items": selected,
        "stats": stats,
        "pool_total": len(pool),
        "skipped_ineligible": skipped_ineligible,  # 选科/外语不能填被跳过的
        "brother_profile": brother_profile,  # 实际评估用的弟弟档案
    }


@router.post("/items")
def add_item(req: AddItemRequest, request: Request, session: Session = Depends(get_session_dep)):
    """添加志愿（服务端用 profile 重新校验资格/档位，不信任前端展示字段）。"""
    try:
        group = volunteer_repo.add_item(
            session, _resolve_owner(request), req.school_code, req.major_group_code, req.profile
        )
    except VolunteerConflictError as exc:
        return _conflict_response(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return group.model_dump(mode="json")


@router.patch("/layout")
def apply_layout(req: LayoutRequest, request: Request, session: Session = Depends(get_session_dep)):
    """原子布局更新（跨档拖拽专用）：单事务改 planned_tier+全局sort_order+version。"""
    owner = _resolve_owner(request)
    group_row = volunteer_repo.get_or_create_group(session, owner)
    try:
        group = volunteer_repo.apply_layout(
            session, group_row,
            [li.model_dump() for li in req.items], req.version,
        )
    except VolunteerConflictError as exc:
        return _conflict_response(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return group.model_dump(mode="json")


@router.patch("/items/{item_id}/tier")
def update_tier(item_id: int, req: TierRequest, request: Request, session: Session = Depends(get_session_dep)):
    """菜单内单改规划档位（null=恢复用算法档位）。"""
    owner = _resolve_owner(request)
    group_row = volunteer_repo.get_or_create_group(session, owner)
    try:
        group = volunteer_repo.update_planned_tier(
            session, group_row, item_id, req.planned_tier, req.version
        )
    except VolunteerConflictError as exc:
        return _conflict_response(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return group.model_dump(mode="json")


@router.delete("/items/{item_id}")
def delete_item(item_id: int, request: Request, version: int, session: Session = Depends(get_session_dep)):
    """删除单个志愿 + 重排 sort_order + version+1。

    version 走 query 参数（DELETE 带 body 兼容性差）。
    """
    owner = _resolve_owner(request)
    group_row = volunteer_repo.get_or_create_group(session, owner)
    try:
        group = volunteer_repo.delete_item(session, group_row, item_id, version)
    except VolunteerConflictError as exc:
        return _conflict_response(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return group.model_dump(mode="json")


@router.post("/clear")
def clear_group(req: ClearRequest, request: Request, session: Session = Depends(get_session_dep)):
    """清空全部志愿（单条 SQL 删全组 items，事务化）。"""
    if not req.confirm:
        raise HTTPException(status_code=400, detail="需 confirm=true 才能清空")
    owner = _resolve_owner(request)
    group_row = volunteer_repo.get_or_create_group(session, owner)
    try:
        group = volunteer_repo.clear_group(session, group_row, req.version)
    except VolunteerConflictError as exc:
        return _conflict_response(exc)
    return group.model_dump(mode="json")
