"""
把 scrape_heao_school_baseinfo.py 抓到的官网/招生网站合并进 universities.yaml。

输入 all_websites.json（国标码 -> {official_website, enrollment_website}），
经 campus-aware 校名桥接匹配到 universities.yaml 的学校，补 official_website /
enrollment_website 两列（缺失留空）。幂等：重复运行只更新这两列。
"""
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 复用 matcher 的 campus-aware 校名归一化（单一来源，含更名白名单）
from import_heao_admission_to_history import school_key as _school_key  # noqa: E402

WEBSITES = Path("data/raw/henan_2026/heao_school_baseinfo/all_websites.json")
UNIVERSITIES = Path("data/seed/henan/universities.yaml")


def main() -> int:
    if not WEBSITES.exists():
        raise SystemExit(f"❌ {WEBSITES} 不存在，请先跑 scrape_heao_school_baseinfo.py")
    web = json.loads(WEBSITES.read_text(encoding="utf-8"))
    # 校名key -> websites
    by_key: dict[str, dict] = {}
    for v in web.values():
        by_key[_school_key(v.get("school_name", ""))] = v

    unis = yaml.safe_load(UNIVERSITIES.read_text(encoding="utf-8"))
    unis = unis if isinstance(unis, list) else []
    n_off = n_enr = n_any = 0
    for u in unis:
        v = by_key.get(_school_key(u.get("school_name", "")))
        off = v.get("official_website", "") if v else ""
        enr = v.get("enrollment_website", "") if v else ""
        u["official_website"] = off
        u["enrollment_website"] = enr
        if off:
            n_off += 1
        if enr:
            n_enr += 1
        if off or enr:
            n_any += 1
    UNIVERSITIES.write_text(yaml.safe_dump(unis, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"universities {len(unis)} 校：补官网 {n_off} / 招生网 {n_enr} / 至少一个 {n_any}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
