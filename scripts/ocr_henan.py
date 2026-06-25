"""OCR 河南 2026 一分一段表 PDF（渲染图片）→ 结构化 CSV。

表布局（每页）：3 列 × (分数, 考生人数)，各列独立按分数降序、人数（累计）升序。
列中心 x（1400px 宽图）：
  Col A: 分数≈126, 人数≈330   （高分段起点）
  Col B: 分数≈590, 人数≈805
  Col C: 分数≈1087,人数≈1298
同一行(相同 y)的三对单元分别属 A/B/C 三列。

策略：
1. PaddleOCR 出每个数字框中心(cx,cy)+文本+置信度
2. 按 cx 归到 6 个单元列之一（3 分数列 + 3 人数列）
3. 按行(y)配对：同行同列的 (分数,人数) 配成一条记录
4. 跨页拼合：分数唯一，去重取最高置信
5. 单调性校验 + 锚点校验
"""
from __future__ import annotations

import json
import os
import re
import sys

os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
os.environ.setdefault("FLAGS_use_mkldnn", "0")

from paddleocr import PaddleOCR

IMG_DIR = "data/raw/henan_2026/ocr"
OUT_DIR = "data/raw/henan_2026/out"
CACHE_DIR = "data/raw/henan_2026/cache"
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# (分数列cx, 人数列cx) —— 用区间判定，兼容轻微抖动
# 区间基于实测直方图：100-150,300-350,550-650,750-850,1050-1100,1250-1350
SCORE_COLS = [("A", (100, 180)), ("B", (540, 660)), ("C", (1040, 1110))]
COUNT_COLS = [("A", (290, 360)), ("B", (770, 870)), ("C", (1270, 1360))]

TRACKS = {
    "物理类": [f"wuli_p{i}" for i in range(1, 9)],
    "历史类": [f"lishi_p{i}" for i in range(1, 9)],
}


def col_of(cx):
    """返回 ('score'|'count', 列名 'A'/'B'/'C') 或 None。"""
    for name, (lo, hi) in SCORE_COLS:
        if lo <= cx <= hi:
            return ("score", name)
    for name, (lo, hi) in COUNT_COLS:
        if lo <= cx <= hi:
            return ("count", name)
    return None


def ocr_page(ocr, path):
    """OCR 单页，带磁盘缓存（避免重跑）。"""
    stem = os.path.splitext(os.path.basename(path))[0]
    cache = f"{CACHE_DIR}/{stem}.json"
    if os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    res = ocr.predict(path)[0]
    polys = res["dt_polys"]
    texts = res["rec_texts"]
    scores = res["rec_scores"]
    cells = []
    for i, p in enumerate(polys):
        t = texts[i]
        if not re.fullmatch(r"\d+", t):
            continue
        cx = float(sum(pt[0] for pt in p) / 4)
        cy = float(pt[1] for pt in p) / 4 if False else float(sum(pt[1] for pt in p) / 4)
        kind = col_of(cx)
        if kind is None:
            continue
        cells.append([kind[0], kind[1], cy, int(t), float(scores[i])])
    json.dump(cells, open(cache, "w", encoding="utf-8"))
    return cells


def pair_rows(cells):
    """同行(同 y±10)同列的 (score,count) 配对。

    返回 [(col, score, count, min_score), ...]。
    """
    cells.sort(key=lambda c: (c[1], c[2]))
    pairs = []
    for col in ("A", "B", "C"):
        col_cells = [c for c in cells if c[1] == col]
        col_cells.sort(key=lambda c: c[2])  # 按 y
        scores = [(c[2], c[3], c[4]) for c in col_cells if c[0] == "score"]
        counts = [(c[2], c[3], c[4]) for c in col_cells if c[0] == "count"]
        # 贪心配对：分数与最近的 count（同 y）
        used = set()
        for sy, sv, ss in scores:
            best = None
            for j, (cy, cv, cs) in enumerate(counts):
                if j in used:
                    continue
                if abs(cy - sy) <= 12:
                    best = (j, cy, cv, cs)
                    break
            if best is not None:
                j, cy, cv, cs = best
                used.add(j)
                pairs.append((col, sv, cv, min(ss, cs)))
    return pairs


def extract_track(ocr, track, stems):
    print(f"\n===== {track} =====", flush=True)
    records = []  # (score, count, page, col, min_conf)
    for stem in stems:
        path = f"{IMG_DIR}/{stem}.png"
        if not os.path.exists(path):
            print(f"  [skip] {path}", file=sys.stderr); continue
        cells = ocr_page(ocr, path)
        pairs = pair_rows(cells)
        for col, sc, cnt, conf in pairs:
            if 0 <= sc <= 750 and 0 <= cnt <= 600000:
                records.append((sc, cnt, stem, col, round(conf, 3)))
        print(f"  {stem}: {len(pairs)} 条", flush=True)
    return records


def merge(records):
    by_score = {}
    for sc, cnt, page, col, conf in records:
        if sc not in by_score or conf > by_score[sc][4]:
            by_score[sc] = (sc, cnt, page, col, conf)
    return sorted(by_score.values(), key=lambda r: -r[0])


def validate(rows):
    issues = []
    for i in range(1, len(rows)):
        sp, cp = rows[i - 1][0], rows[i - 1][1]
        sc, cc, page, col, conf = rows[i]
        if sc >= sp:
            issues.append({"kind": "SCORE_NOT_DESC", "score": sc, "prev": sp, "page": page, "col": col})
        if cc < cp:
            issues.append({"kind": "COUNT_NOT_ASC", "score": sc, "prev": cp, "cur": cc, "page": page, "col": col})
    return issues


def anchor_check(rows, track):
    """锚点：600分累计应≈37544（物理类全省，非单表，仅量级参考）。
    本表"考生人数"是累计。本科线 419 物理类累计应≈359972。"""
    anchors = {}
    by = {r[0]: r[1] for r in rows}
    for sc in (700, 650, 600, 550, 513, 500, 419, 400):
        if sc in by:
            anchors[sc] = by[sc]
    return anchors


def main():
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    ocr = PaddleOCR(use_textline_orientation=False, lang="ch", enable_mkldnn=False)
    summary = {}
    for track, stems in TRACKS.items():
        if only and track not in only and not any(s.split("_")[0] in only[0] for s in stems):
            continue
        recs = extract_track(ocr, track, stems)
        rows = merge(recs)
        issues = validate(rows)
        anchors = anchor_check(rows, track)
        csv_path = f"{OUT_DIR}/henan_2026_{track}.csv"
        with open(csv_path, "w", encoding="utf-8-sig") as f:
            f.write("score,count_at,page,col,min_confidence\n")
            for sc, cnt, page, col, conf in rows:
                f.write(f"{sc},{cnt},{page},{col},{conf}\n")
        with open(f"{OUT_DIR}/henan_2026_{track}_issues.json", "w", encoding="utf-8") as f:
            json.dump({"issues": issues, "anchors": anchors, "row_count": len(rows)}, f, ensure_ascii=False, indent=2)
        summary[track] = {"rows": len(rows), "issues": len(issues), "anchors": anchors}
        print(f"  -> {csv_path} ({len(rows)} 行, {len(issues)} 异常)")
        print(f"     锚点: {anchors}")
    print("\n摘要:", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
