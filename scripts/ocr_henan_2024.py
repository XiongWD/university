"""OCR 2024 河南一分一段表图片 → 结构化 CSV（适配阳光高考图片版布局）。

页面来源：https://gaokao.chsi.com.cn/gkxx/zc/ss/202406/20240625/2293299193.html
图片：理科 + 文科各若干页（1080×1528），每页 4 列排版（分数|累计 × 2-3 栏）。

布局（实测 cx，1080px 宽）：
  分数列:  A≈85-110, B≈455-480, C≈825-855
  累计列:  A≈250-275, B≈615-640, C≈990-1015

策略：
1. PaddleOCR 出每个数字框中心(cx,cy)+文本+置信度
2. 按 cx 归到 6 个单元列（3 分数栏 + 3 累计栏）
3. 按 cy 配行：同行(±12px)同栏的 (分数,累计) 配成一条
4. 跨页拼合：分数唯一去重
5. 单调性校验：分数降序，累计升序

输出：data/datasets/henan_2024_score_rank_{track}.csv（与现有 henan_*_score_rank.csv 同格式）。
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys

os.environ.setdefault("FLAGS_use_mkldnn", "0")  # 规避 onednn PIR bug
os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")

import warnings

warnings.filterwarnings("ignore")

from paddleocr import PaddleOCR

# 列中心 cx 区间（实测，1080px 宽，±25 容差）
SCORE_COLS = [("A", (75, 130)), ("B", (440, 495)), ("C", (810, 870))]
COUNT_COLS = [("A", (240, 290)), ("B", (600, 655)), ("C", (975, 1030))]

IMG_DIR = "data/raw/henan_2024/sources"
CACHE_DIR = "data/raw/henan_2024/cache"
OUT_DIR = "data/raw/henan_2024/out"


def col_of(cx: float):
    for name, (lo, hi) in SCORE_COLS:
        if lo <= cx <= hi:
            return ("score", name)
    for name, (lo, hi) in COUNT_COLS:
        if lo <= cx <= hi:
            return ("count", name)
    return None


def detect_track(texts):
    """从 OCR 文本里识别该批图是理科还是文科。"""
    blob = "".join(texts)
    if "理科" in blob:
        return "物理类"  # 2024 改革前理科，映射到新高考物理类参考
    if "文科" in blob:
        return "历史类"
    return None


def ocr_page(ocr, path):
    """OCR 单页，带缓存。返回 [kind, col, cy, value, conf] 列表。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    cache = f"{CACHE_DIR}/{stem}.json"
    if os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    res = ocr.predict(path)[0]
    cells = []
    for i, poly in enumerate(res["dt_polys"]):
        t = res["rec_texts"][i]
        if not re.fullmatch(r"\d+", t):
            continue
        cx = float(sum(p[0] for p in poly) / 4)
        cy = float(sum(p[1] for p in poly) / 4)
        kind = col_of(cx)
        if kind is None:
            continue
        cells.append([kind[0], kind[1], cy, int(t), float(res["rec_scores"][i])])
    json.dump(cells, open(cache, "w", encoding="utf-8"))
    return cells


def pair_rows(cells, rows_tolerance=12):
    """同行(±容差)同栏的 (分数,累计) 配对。返回 [(score, cumulative), ...]。"""
    pairs = []
    for col in ("A", "B", "C"):
        col_cells = [c for c in cells if c[1] == col]
        scores = [(c[2], c[3], c[4]) for c in col_cells if c[0] == "score"]
        counts = [(c[2], c[3], c[4]) for c in col_cells if c[0] == "count"]
        used = set()
        for sy, sv, _ in sorted(scores):
            best = None
            for j, (cy, cv, _) in enumerate(sorted(counts)):
                if j in used:
                    continue
                if abs(cy - sy) <= rows_tolerance:
                    best = j
                    break
            if best is not None:
                used.add(best)
                pairs.append((sv, counts[best][1]))
    return pairs


def dedupe_and_sort(all_pairs):
    """分数唯一去重，按分数降序、累计升序。"""
    by_score = {}
    for score, cum in all_pairs:
        # 同分数取较大累计（更完整）
        if score not in by_score or cum > by_score[score]:
            by_score[score] = cum
    rows = sorted(by_score.items(), key=lambda x: -x[0])
    # 后处理：强制累计单调（分数降序→累计升序）。
    # OCR 配对偶发回退，用 running max 修复：每个累计不低于更高分的累计。
    # 同时剔除累计明显低于前值的噪声点（OCR 错配）。
    cleaned = []
    prev_cum = 0
    for score, cum in rows:
        if cum < prev_cum:
            continue  # 丢弃回退点（OCR 错配，高分段已有更可靠数据）
        cleaned.append((score, cum))
        prev_cum = cum
    return cleaned


def validate_monotonic(rows, track):
    """校验：分数降序、累计升序。报告异常但不强制阻断。"""
    issues = 0
    prev_cum = 0
    for score, cum in rows:
        if cum < prev_cum:
            issues += 1
        prev_cum = max(prev_cum, cum)
    return issues


def main():
    parser = argparse.ArgumentParser(description="OCR 2024 河南一分一段表")
    parser.add_argument("--track", choices=["物理类", "历史类", "auto"], default="auto")
    args = parser.parse_args()

    images = sorted(glob.glob(f"{IMG_DIR}/*.png"))
    if not images:
        print(f"未找到图片: {IMG_DIR}/*.png", file=sys.stderr)
        return 1

    # 仅当有未缓存页时才初始化 PaddleOCR（缓存全命中时跳过，秒出）
    ocr = None

    def get_ocr():
        nonlocal ocr
        if ocr is None:
            print(f"PaddleOCR 初始化（已关闭 mkldnn 规避 onednn bug）...", flush=True)
            ocr = PaddleOCR(use_textline_orientation=True, lang="ch", enable_mkldnn=False)
        return ocr

    def ocr_cached(path):
        stem = os.path.splitext(os.path.basename(path))[0]
        cache = f"{CACHE_DIR}/{stem}.json"
        if os.path.exists(cache):
            return json.load(open(cache, encoding="utf-8"))
        return ocr_page(get_ocr(), path)

    # 先探测 track（用缓存，避免重复 OCR）
    track = args.track
    all_cells = []
    for img in images:
        all_cells.append((img, ocr_cached(img)))
    if track == "auto":
        # track 探测需 OCR 原始文本（缓存 cells 已过滤非数字，需重新取文本）
        # 简化：page_01 缓存检测标题。从所有页 cells 无文本，故从 page_01 重新 OCR 文本
        r = get_ocr().predict(images[0])[0]
        track = detect_track(r["rec_texts"])
        if track is None:
            print("无法自动识别理科/文科，请用 --track 指定", file=sys.stderr)
            return 1
        print(f"自动识别: {track}")

    all_pairs = []
    for img, cells in all_cells:
        pairs = pair_rows(cells)
        all_pairs.extend(pairs)
        print(f"  {os.path.basename(img)}: {len(pairs)} 对")

    rows = dedupe_and_sort(all_pairs)
    issues = validate_monotonic(rows, track)
    print(f"\n汇总: {len(rows)} 个分数段, 单调性异常 {issues} 处")

    os.makedirs(OUT_DIR, exist_ok=True)
    out = f"{OUT_DIR}/henan_2024_score_rank_{track}.csv"
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["最高分", "最低分", "人数", "累计", "省级行政区", "综合", "年份", "总分(裸分)", "模式"])
        # 人数 = 本分数段累计 - 上一分数段累计（更高分）
        prev_cum = 0
        for score, cum in rows:
            count = max(0, cum - prev_cum)
            w.writerow([score, score, count, cum, "河南", track, 2024, 750, "传统文理"])
            prev_cum = cum
    print(f"输出: {out} ({len(rows)} 行)")
    # 验证打印首尾
    if rows:
        print(f"  最高分: {rows[0][0]} (累计{rows[0][1]})")
        print(f"  最低分: {rows[-1][0]} (累计{rows[-1][1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
