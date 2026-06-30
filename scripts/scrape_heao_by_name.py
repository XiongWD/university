"""
按校名增量补抓 heao getSchoolList，把「真缺失」校的专业组录取位次补进 all_schools.json。

读 missing_review_schools.txt（list_missing_review_schools.py 产物），过滤掉已在
all_schools.json 的校（campus-aware 校名桥接），只对真缺失的逐个用 schoolName 查询。
parse_school() 后按 school_code_guobiao 去重合并进 all_schools.json。

接口：GET getSchoolList?schoolName=<urlencoded>&pcdm=1&minWc=1&maxWc=300000&pageSize=20
token 失效（401/空 rows）立即报错提示刷新。
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from heao_client import get_json, load_token  # noqa: E402

# 复用主采集脚本的 parse_school（保持解析逻辑单一来源）
from scrape_heao_admission import parse_school  # noqa: E402
# 复用 matcher 的 campus-aware 校名归一化（单一来源，避免三处漂移）
from import_heao_admission_to_history import school_key as _school_key  # noqa: E402

API = "https://book.heao.com.cn/prod-api/choose/volunteer/getSchoolList"
MISSING_TXT = Path("data/raw/henan_2026/heao_admission/missing_review_schools.txt")
ALL_SCHOOLS = Path("data/raw/henan_2026/heao_admission/all_schools.json")

# 统一用 matcher 的 school_key（含更名白名单）
def _key(name: str) -> str:
    return _school_key(name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=0.5, help="请求间隔秒")
    ap.add_argument("--input", default=str(MISSING_TXT), help="待补校名清单（每行一校）")
    args = ap.parse_args()

    names = [l.strip() for l in Path(args.input).read_text(encoding="utf-8").splitlines() if l.strip()]
    all_schools = json.loads(ALL_SCHOOLS.read_text(encoding="utf-8"))
    have_keys = {_key(s["school_name"]) for s in all_schools}
    # 真缺失：清单里 campus-aware 名不在缓存的
    todo = [n for n in names if _key(n) not in have_keys]
    print(f"清单 {len(names)} 校：已缓存 {len(names)-len(todo)}，真缺失待抓 {len(todo)}")

    token = load_token()
    # token 预检
    probe = get_json(f"{API}?pageNum=1&pageSize=1&pcdm=1&minWc=1&maxWc=300000", token)
    if probe.get("code") not in (None, 200, "200", 0) or not (probe.get("rows") or probe.get("data")):
        raise SystemExit(f"❌ token 预检失败（code={probe.get('code')}），请刷新 cookie 并更新 TOKEN_FILE。")
    print(f"token 有效（total={probe.get('total')}）")

    import urllib.parse
    fetched = {}    # school_code_guobiao -> parsed school
    missed = []     # 查询无结果或名不符的校
    for i, name in enumerate(todo, 1):
        q = urllib.parse.quote(name)
        data = get_json(f"{API}?pageNum=1&pageSize=20&schoolName={q}&pcdm=1&minWc=1&maxWc=300000", token)
        rows = data.get("rows") or data.get("data") or []
        if not rows:
            missed.append(f"{name}\t查询无结果")
            print(f"  [{i}/{len(todo)}] {name}：查询无结果")
            time.sleep(args.delay)
            continue
        # 取校名匹配的那条（避免「湖北」前缀命中多校时取错）
        nk = _key(name)
        hit = next((r for r in rows if _key(r.get("schoolName", "")) == nk), rows[0])
        parsed = parse_school(hit)
        gc = parsed.get("school_code_guobiao") or ""
        if gc:
            fetched[gc] = parsed
        print(f"  [{i}/{len(todo)}] {name}：命中 {parsed['school_name']}（国标{gc}，"
              f"{len(parsed.get('groups', []))} 组）")
        time.sleep(args.delay)

    # 合并进 all_schools.json（按国标码去重：新抓的覆盖旧的）
    by_gc = {s.get("school_code_guobiao") or s["school_name"]: s for s in all_schools}
    for gc, s in fetched.items():
        by_gc[gc or s["school_name"]] = s
    new_all = list(by_gc.values())
    ALL_SCHOOLS.write_text(json.dumps(new_all, ensure_ascii=False, indent=2), encoding="utf-8")

    if missed:
        mf = ALL_SCHOOLS.parent / "scrape_by_name_missed.txt"
        mf.write_text("\n".join(missed) + "\n", encoding="utf-8")
    print(f"\n完成：新抓 {len(fetched)} 校，合并后 all_schools.json 共 {len(new_all)} 校")
    print(f"  无结果/未命中 {len(missed)} 校（多为 heao 仍未收录的 2025/2026 新设/更名校）")
    print("  下一步：重跑 import_heao_admission_to_history.py --apply 把新数据匹配进 CSV")
    return 0


if __name__ == "__main__":
    sys.exit(main())
