"""合规检查：全代码库与种子不得出现违规措辞。"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ["保证就业", "预测未来收入", "包就业"]


def _scan_files():
    """扫描 app 代码 + 种子数据，排除测试文件自身（其字面量列表会误报）。"""
    py_files = [p for p in ROOT.rglob("*.py") if "tests" not in p.parts]
    yaml_files = list((ROOT / "data").rglob("*.yaml"))
    return py_files + yaml_files


@pytest.mark.parametrize("p", _scan_files())
def test_no_forbidden_phrases(p):
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    for bad in FORBIDDEN:
        assert bad not in text, f"{p} 含违规措辞 {bad}"


def test_seeds_carry_simulation_disclaimer():
    files = list((ROOT / "data" / "seed").rglob("*.yaml"))
    assert files
    blob = "\n".join(f.read_text(encoding="utf-8") for f in files)
    assert "待爬虫校准" in blob
