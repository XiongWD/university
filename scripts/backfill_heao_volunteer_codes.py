"""
把 heao 缓存里的真实志愿填报代码补进 seed YAML：
  - program_groups_2026.yaml: 每个 major_group 补 volunteer_group_code（heao zyzh 专业组号）
  - universities.yaml:        每个学校补 henan_school_code（heao yxdh 河南院校代码）

桥接方式：heao 与系统用不同代码体系（heao yxdh/国标 vs gaokao.cn school_id），
只能靠**campus-aware 校名校名归一化**匹配（与 import_heao_admission_to_history.py 同一逻辑）。
专业组号 zyzh 按"专业名重合度"在命中校的多个组里挑最接近的。

幂等：重复运行只更新 volunteer_group_code / henan_school_code 两列，保留其他字段。
"""
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 复用 matcher 的 campus-aware 校名归一化（单一来源，含更名白名单）
from import_heao_admission_to_history import school_key  # noqa: E402

HEAO = Path("data/raw/henan_2026/heao_admission/all_schools.json")
PROGRAM_GROUPS = Path("data/seed/henan/program_groups_2026.yaml")
UNIVERSITIES = Path("data/seed/henan/universities.yaml")


def norm_major(name: str) -> str:
    if not name:
        return ""
    return re.sub(r"[（(].*?[)）]", "", name).strip()


def best_zyzh(heao_groups: list[dict], sys_majors: list[str]) -> str:
    """在命中校的多个 heao 专业组里，按专业名重合度挑 zyzh。

    heao 有合成组 zyzh='2024年招生专业'/'2025年招生专业'（聚合全年专业的占位组，非真实填报号），
    必须排除——只接受纯数字的真实专业组号。
    """
    sys_set = {norm_major(m) for m in (sys_majors or []) if m}
    if not sys_set:
        return ""
    best_code, best_score = "", 0.0
    for g in heao_groups:
        zyzh = g.get("zyzh", "")
        # 排除合成占位组（"2024年招生专业" 等）——真实专业组号是纯数字
        if not zyzh or not zyzh.isdigit():
            continue
        heao_set = {norm_major(m["major_name"]) for m in g.get("majors", []) if m.get("major_name")}
        if not heao_set:
            continue
        inter = len(heao_set & sys_set)
        if inter == 0:
            continue
        score = inter / len(heao_set | sys_set)
        if score > best_score:
            best_score, best_code = score, zyzh
    return best_code if best_score >= 0.3 else ""


def main() -> int:
    heao = json.loads(HEAO.read_text(encoding="utf-8"))
    # heao 按 school_key 索引（保留所有同 key 的校，取首个有 yxdh 的）
    heao_by_key: dict[str, dict] = {}
    for s in heao:
        heao_by_key.setdefault(school_key(s["school_name"]), s)

    # ── 1) program_groups_2026.yaml：补 volunteer_group_code（zyzh）──
    pg = yaml.safe_load(PROGRAM_GROUPS.read_text(encoding="utf-8"))
    pg = pg if isinstance(pg, list) else (pg.get("program_groups") or pg.get("records") or [])
    n_grp_filled = 0
    n_grp_skip = 0
    for g in pg:
        if not (g.get("track") == "历史类" and g.get("batch") == "本科批"):
            n_grp_skip += 1
            continue
        s = heao_by_key.get(school_key(g.get("school_name", "")))
        # 始终覆盖（清除上一轮可能写入的合成占位值）；heao 无该组则置空
        zyzh = best_zyzh(s.get("groups", []), g.get("included_majors") or []) if s else ""
        if zyzh:
            g["volunteer_group_code"] = zyzh
            n_grp_filled += 1
        elif "volunteer_group_code" in g:
            # 清除历史遗留的非数字占位值（如 '2024年招生专业'）
            g["volunteer_group_code"] = ""
    PROGRAM_GROUPS.write_text(
        yaml.safe_dump(pg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # ── 2) universities.yaml：补 henan_school_code（yxdh）──
    unis = yaml.safe_load(UNIVERSITIES.read_text(encoding="utf-8"))
    unis = unis if isinstance(unis, list) else []
    n_uni_filled = 0
    for u in unis:
        s = heao_by_key.get(school_key(u.get("school_name", "")))
        if s and s.get("yxdh"):
            u["henan_school_code"] = str(s["yxdh"])
            n_uni_filled += 1
    UNIVERSITIES.write_text(
        yaml.safe_dump(unis, allow_unicode=True, sort_keys=False), encoding="utf-8")

    print(f"program_groups: 补 volunteer_group_code（zyzh）= {n_grp_filled} 组（跳过非历史本科 {n_grp_skip}）")
    print(f"universities:   补 henan_school_code（yxdh）= {n_uni_filled} 校")
    return 0


if __name__ == "__main__":
    sys.exit(main())
