"""用 heao 真实志愿组的专业清单，补全系统 program_groups 缺失的专业。

【背景】系统 program_groups 来自 gaokao.cn，建组时常漏建部分专业（如丽江文化旅游
组101 heao 有 10 个专业，系统只建了 4 个）。heao 的专业组是河南考试院权威数据，
专业完整且带国标专业码（majorCode，如 020101=经济学）。

【补全规则】对每个历史类本科批系统组：
  - 按志愿组号(volunteer_group_code=zyzh) + 校名桥接定位 heao 真实组
  - 一切以 heao 为准（gaokao.cn 数据不全/有误）：heao 有的专业系统必须有，
    缺失的从 heao 补进 included_majors + major_codes（用 heao 国标 majorCode）
  - 系统原有但 heao 没有的专业保留（不丢信息），heao 多出的补上
  - 不做子集判断——只要志愿组号对齐就补（heao 是权威源）

幂等：重复运行只追加缺失专业，已补全的不重复加（按规范化名去重）。
"""
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_heao_admission_to_history import school_key  # noqa: E402

HEAO = Path("data/raw/henan_2026/heao_admission/all_schools.json")
PROGRAM_GROUPS = Path("data/seed/henan/program_groups_2026.yaml")


def norm_major(name: str) -> str:
    if not name:
        return ""
    return re.sub(r"[（(].*?[)）]", "", name).strip()


def build_heao_majors(heao: list[dict]) -> dict:
    """{(school_key, zyzh): [(major_name, major_code), ...]} 按专业名规范化去重保序。"""
    idx: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for s in heao:
        k = school_key(s["school_name"])
        for g in s.get("groups", []):
            zyzh = str(g.get("zyzh") or "")
            if not zyzh.isdigit():
                continue
            key = (k, zyzh)
            seen_norm: set[str] = set()
            for m in g.get("majors", []):
                mname = m.get("major_name", "")
                mcode = str(m.get("major_code") or "")
                nm = norm_major(mname)
                if not nm or nm in seen_norm:
                    continue
                seen_norm.add(nm)
                idx.setdefault(key, []).append((mname, mcode))
    return idx


def main() -> int:
    heao = json.loads(HEAO.read_text(encoding="utf-8"))
    heao_idx = build_heao_majors(heao)

    pg = yaml.safe_load(PROGRAM_GROUPS.read_text(encoding="utf-8"))
    pg = pg if isinstance(pg, list) else (pg.get("program_groups") or pg.get("records") or [])

    filled = 0
    no_match = 0
    samples = []

    for g in pg:
        if not (g.get("track") == "历史类" and g.get("batch") == "本科批"):
            continue
        k = school_key(g.get("school_name", ""))
        vgc = str(g.get("volunteer_group_code") or "")
        if not vgc or (k, vgc) not in heao_idx:
            no_match += 1
            continue

        sys_majors = list(g.get("included_majors") or [])
        sys_codes = list(g.get("major_codes") or [])
        sys_norm_set = {norm_major(m) for m in sys_majors}

        heao_majors = heao_idx[(k, vgc)]

        # 一切以 heao 为准：找出 heao 有、系统没有的专业（按规范化名去重）
        missing = [(mn, mc) for mn, mc in heao_majors if norm_major(mn) not in sys_norm_set]
        if not missing:
            continue  # heao 专业系统已全部包含

        # 追加缺失专业（保持 heao 顺序），major_codes 同步追加国标码
        g["included_majors"] = sys_majors + [mn for mn, _ in missing]
        # major_codes 长度对齐：系统原码 + 补全专业的国标码
        g["major_codes"] = sys_codes + [mc for _, mc in missing]
        filled += 1
        if len(samples) < 6:
            samples.append(
                f"{g['school_name']} 组{g['major_group_code']}(志愿{vgc}): "
                f"{len(sys_majors)}→{len(g['included_majors'])} 补{[mn for mn,_ in missing]}"
            )

    PROGRAM_GROUPS.write_text(
        yaml.safe_dump(pg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    print(f"=== 专业组补全结果（历史类本科批，以 heao 为准）===")
    print(f"  补全专业组: {filled}")
    print(f"  无法对齐(无vgc/heao无此校组): {no_match}")
    print(f"\n样本:")
    for s in samples:
        print(f"  {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
