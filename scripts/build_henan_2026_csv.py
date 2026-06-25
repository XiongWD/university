"""把 OCR 输出转换为 dataset_importer 能直接导入的 CSV 格式。

河南一分一段表"考生人数"列实为【累计位次】（表脚注已说明）。
importer 需要: 最高分(score), 人数(count_at本段), 累计(cumulative_rank).
本段人数 = cumu[score] - cumu[score+1]（相邻高分累计之差）。

支持 2025/2026 两年。输出 data/datasets/henan_{YEAR}_score_rank.csv。
importer 白名单(省/年)需包含对应年份。
"""
import sys
import csv
from pathlib import Path

YEAR = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].isdigit() else "2026"
OCR_DIR = Path(f"data/raw/henan_{YEAR}/out")
OUT = Path(f"data/datasets/henan_{YEAR}_score_rank.csv")


def load_cumulative(track):
    """读 OCR，返回 {score: cumulative_rank}。"""
    d = {}
    with open(OCR_DIR / f"henan_{YEAR}_{track}.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            d[int(r["score"])] = int(r["count_at"])
    return d


def build_track(track):
    cumu = load_cumulative(track)
    scores = sorted(cumu.keys(), reverse=True)
    rows = []
    missing_diff = []
    for i, sc in enumerate(scores):
        cumulative = cumu[sc]
        # 本段人数 = 本分累计 - 上一高分(相邻更小累计之外的那个)累计
        # 分数降序：scores[0]最高。本段人数 = cumu[sc] - cumu[sc_next_higher]
        # sc_next_higher = scores[i-1] (i>0)
        if i == 0:
            count_at = cumulative  # 最高分段，本段=累计
        else:
            higher = scores[i - 1]
            if higher == sc + 1:
                count_at = cumulative - cumu[higher]
            else:
                # 有间隔（缺行），本段人数无法精确算，标记
                count_at = cumulative - cumu[higher]  # 仍用差，可能含多段
                missing_diff.append((sc, higher))
        rows.append({
            "最高分": sc, "最低分": sc,
            "人数": count_at, "累计": cumulative,
            "省级行政区": "河南", "综合": track,
            "年份": YEAR, "总分(裸分)": "750", "模式": "3+1+2",
        })
    return rows, missing_diff


def main():
    all_rows = []
    total_missing = 0
    for track in ["物理类", "历史类"]:
        rows, miss = build_track(track)
        all_rows.extend(rows)
        total_missing += len(miss)
        print(f"{track}: {len(rows)} 行, 缺行(本段差不精确) {len(miss)} 处")
        if miss:
            print(f"  例: {miss[:5]}")
    # 合并到主 CSV（追加；若文件存在且含2026则先剔除旧2026）
    fields = ["最高分", "最低分", "人数", "累计", "省级行政区", "综合",
              "年份", "总分(裸分)", "模式"]
    if OUT.exists():
        # 读已有，剔除河南该年避免重复
        kept = []
        with open(OUT, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if not (r["省级行政区"] == "河南" and r["年份"] == YEAR):
                    kept.append(r)
        with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(kept + all_rows)
        print(f"合并: 保留旧 {len(kept)} 行 + 新增 {len(all_rows)} 行 → {OUT}")
    else:
        with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(all_rows)
        print(f"新建: {len(all_rows)} 行 → {OUT}")
    print(f"总缺行处: {total_missing}（本段人数可能不精确，但累计位次精确）")


if __name__ == "__main__":
    main()
