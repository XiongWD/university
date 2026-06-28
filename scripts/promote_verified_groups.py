"""
将核验通过的 (school_code, major_group_code) 从 needs_review 提升为 verified。

用法：
    python scripts/promote_verified_groups.py
        --verified-groups data/seed/henan/verified_groups.txt
        [--dry-run]

从 verified_groups.txt 逐行读取 "school_code:major_group_code" 键，
在 program_groups_2026.yaml 和 enrollment_plans_2026.yaml 中将对应记录
标记 review_status=verified，confidence=0.9。

dry-run 仅输出变更预览，不写文件。
"""
from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote verified groups from needs_review to verified")
    parser.add_argument("--verified-groups", default="data/seed/henan/verified_groups.txt")
    parser.add_argument("--groups-yaml", default="data/seed/henan/program_groups_2026.yaml")
    parser.add_argument("--plans-yaml", default="data/seed/henan/enrollment_plans_2026.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't write files")
    args = parser.parse_args()

    # Load verified keys
    verified_path = Path(args.verified_groups)
    if not verified_path.exists():
        print(f"[ERROR] Verified groups file not found: {verified_path}")
        sys.exit(1)

    verified_keys = set()
    for line in verified_path.read_text(encoding="utf-8").strip().splitlines():
        line = line.strip()
        if line:
            verified_keys.add(line)
    print(f"Verified keys: {len(verified_keys)}")
    for k in sorted(verified_keys):
        print(f"  {k}")

    # ── Promote program groups ──
    groups_path = Path(args.groups_yaml)
    groups = yaml.safe_load(groups_path.read_text(encoding="utf-8")) or []
    
    group_promotions = 0
    for g in groups:
        key = f"{g['school_code']}:{g['major_group_code']}"
        if key in verified_keys and g.get("review_status") != "verified":
            g["review_status"] = "verified"
            g["confidence"] = 0.9
            group_promotions += 1
    
    print(f"\nProgram groups promoted: {group_promotions}")

    # ── Promote enrollment plans ──
    plans_path = Path(args.plans_yaml)
    plans = yaml.safe_load(plans_path.read_text(encoding="utf-8")) or []
    
    plan_promotions = 0
    for p in plans:
        key = f"{p['school_code']}:{p['major_group_code']}"
        if key in verified_keys and p.get("review_status") != "verified":
            p["review_status"] = "verified"
            p["confidence"] = 0.9
            plan_promotions += 1
    
    print(f"Enrollment plans promoted: {plan_promotions}")

    if group_promotions == 0 and plan_promotions == 0:
        print("\nNothing to promote.")
        return

    if args.dry_run:
        print(f"\n[Dry-run] Would write {group_promotions} groups + {plan_promotions} plans")
        return

    # Write updated YAML
    groups_path.write_text(
        yaml.safe_dump(groups, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    plans_path.write_text(
        yaml.safe_dump(plans, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(f"\nWritten: {groups_path}")
    print(f"Written: {plans_path}")
    print("Done.")


if __name__ == "__main__":
    main()
