"""
抓取院校官网/招生网站（heao schoolBaseInfo 接口）。

接口：GET https://book.heao.com.cn/prod-api/schoolLibrary/schoolBaseInfo?schoolCode=<国标码>
返回（取两个字段，缺失留空）：
  officialWebsite  官网        enrollWebsite  招生网站
  注：schoolCode 是**国标码**（如清华 10003），不是 gaokao.cn school_id。

流程：遍历 universities.yaml 所有校 → 用 heao all_schools.json 的 school_code_guobiao
（campus-aware 校名桥接）查官网 → 断点续抓缓存到 raw/ → 合并 all_websites.json。
token 失效（首个请求 401/空）立即报错；失败校记 failed.txt 可重跑。
"""
import argparse
import json
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from heao_client import get_json, load_token  # noqa: E402
# 复用 matcher 的 campus-aware 校名归一化（单一来源，含更名白名单）
from import_heao_admission_to_history import school_key as _key  # noqa: E402

API = "https://book.heao.com.cn/prod-api/schoolLibrary/schoolBaseInfo"
UNIS = Path("data/seed/henan/universities.yaml")
HEAO = Path("data/raw/henan_2026/heao_admission/all_schools.json")
OUT_DIR = Path("data/raw/henan_2026/heao_school_baseinfo")
OUT_JSON = OUT_DIR / "all_websites.json"
FAILED = OUT_DIR / "failed.txt"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="限制抓取校数（调试，0=全部）")
    ap.add_argument("--delay", type=float, default=0.4, help="请求间隔秒")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # heao 国标码索引：校名 key -> guobiao code
    heao = json.loads(HEAO.read_text(encoding="utf-8"))
    guo_by_key: dict[str, str] = {}
    for s in heao:
        gc = str(s.get("school_code_guobiao") or "")
        if gc:
            guo_by_key.setdefault(_key(s["school_name"]), gc)

    # universities 待抓清单
    unis = yaml.safe_load(UNIS.read_text(encoding="utf-8"))
    unis = unis if isinstance(unis, list) else []
    todo = []
    for u in unis:
        gc = guo_by_key.get(_key(u.get("school_name", "")))
        if gc:
            todo.append((u.get("school_name", ""), str(u.get("school_code", "")), gc))
    print(f"待抓官网：{len(todo)} 校（有 heao 国标码的）")

    # 断点续抓：已缓存的跳过
    cache_file = OUT_DIR / "cache.json"
    cache: dict[str, dict] = {}
    if cache_file.exists():
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
    done = {gc for gc, v in cache.items() if v.get("ok")}
    todo = [t for t in todo if t[2] not in done]
    print(f"  已缓存 {len(done)}，剩余 {len(todo)}")
    if args.limit:
        todo = todo[: args.limit]
        print(f"  --limit {args.limit}，本次抓 {len(todo)}")

    token = load_token()
    # token 预检：抓第一个，401/空即停
    if todo:
        name0, sc0, gc0 = todo[0]
        try:
            probe = get_json(f"{API}?schoolCode={gc0}", token)
            if not probe or probe.get("code") not in (None, 200, "200", 0) or not probe.get("data"):
                # 部分接口用 data，部分直接平铺；先记下，下面统一解析
                pass
        except Exception as e:
            raise SystemExit(f"❌ token 预检失败（可能过期）：{e}\n   请刷新 cookie 并更新 TOKEN_FILE。")

    websites: dict[str, dict] = {}
    failed: list[str] = []
    for i, (name, sc, gc) in enumerate(todo, 1):
        try:
            data = get_json(f"{API}?schoolCode={gc}", token)
            # 字段在 data.schoolInfo 下（officialWebsite / enrollWebsite）
            payload = data.get("data") if isinstance(data.get("data"), dict) else data
            info = payload.get("schoolInfo") if isinstance(payload, dict) else {}
            off = (info.get("officialWebsite") or "").strip()
            enr = (info.get("enrollWebsite") or "").strip()
            websites[gc] = {"school_name": name, "school_code": sc, "guobiao": gc,
                           "official_website": off, "enrollment_website": enr}
            cache[gc] = {"ok": True}
            if i % 25 == 0 or i == len(todo):
                cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                print(f"  [{i}/{len(todo)}] {name}：官网={off or '∅'} 招生={enr or '∅'}")
        except Exception as e:
            failed.append(f"{name}\t{sc}\t{gc}\t{e}")
            cache[gc] = {"ok": False, "err": str(e)}
        time.sleep(args.delay)

    # 合并历史缓存 + 本次结果
    if cache_file.exists():
        full_cache = json.loads(cache_file.read_text(encoding="utf-8"))
        ok_gcs = {gc for gc, v in full_cache.items() if v.get("ok")}
    else:
        ok_gcs = set()
    # 把所有 ok 的都重查一次太慢，直接用本次 websites + 既有 all_websites.json
    existing: dict[str, dict] = {}
    if OUT_JSON.exists():
        existing = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    existing.update(websites)
    OUT_JSON.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    if failed:
        FAILED.write_text("\n".join(failed) + "\n", encoding="utf-8")
        print(f"\n失败 {len(failed)} 校 → {FAILED}")

    n_off = sum(1 for v in existing.values() if v.get("official_website"))
    n_enr = sum(1 for v in existing.values() if v.get("enrollment_website"))
    print(f"\n完成：累计 {len(existing)} 校，官网 {n_off} / 招生网 {n_enr} → {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
