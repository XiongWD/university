"""narrative-policy 静态扫描测试。

校验用户可见主流程不出现禁止叙事词：
- 人生固化叙事：人生路径/人生轨迹/赛道/命运/人生经济模型模拟器
- 交易化叙事：回本/ROI/投资回报/15年净收益

扫描范围（用户可见文案）：
- web-ui/src/ 全部 .ts/.tsx
- README.md
- app/api/ 下 Python 文件的 docstring 与字符串字面量（用户可见 API 文案）

豁免：
- app/ 内部算法注释（# 开头的纯注释行，非 docstring）不扫
- 同行含 DEPRECATED 关键字的注释豁免
- 归档目录、openspec/ 规约、设计文档本身不在扫描路径
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# 禁止词（作为功能名/结果呈现时禁止）
FORBIDDEN = [
    "人生路径",
    "人生轨迹",
    "赛道",
    "命运",
    "人生经济模型模拟器",
    "回本",
    "ROI",
    "投资回报",
    "15年净收益",
]

# 扫描的前端源码目录
FRONTEND_SRC = REPO_ROOT / "web-ui" / "src"

# 扫描的后端 API 目录（只扫 docstring 与字符串字面量里的用户可见 API 文案）
BACKEND_API = REPO_ROOT / "app" / "api"

# 扫描的文档
README = REPO_ROOT / "README.md"

# 豁免：路径包含这些片段的不扫
PATH_EXEMPT_FRAGMENTS = (
    "openspec",
    "docs/superpowers/specs",  # 设计文档自身
    "docs/superpowers/plans",
    ".comet",
    "node_modules",
    "dist",
    "archive",
)


def _is_path_exempt(p: Path) -> bool:
    s = str(p).replace("\\", "/")
    return any(frag in s for frag in PATH_EXEMPT_FRAGMENTS)


def _forbidden_in_line(line: str) -> list[str]:
    hits = []
    for w in FORBIDDEN:
        if w in line:
            hits.append(w)
    return hits


def _scan_frontend(root: Path) -> list[tuple[Path, int, str, list[str]]]:
    """前端 src：扫全部行（注释与文案都属用户可见）。DEPRECATED 同行豁免。"""
    out = []
    if not root.exists():
        return out
    for f in root.rglob("*"):
        if not f.is_file() or f.suffix not in {".ts", ".tsx"}:
            continue
        if _is_path_exempt(f):
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "DEPRECATED" in line:
                continue
            hits = _forbidden_in_line(line)
            if hits:
                out.append((f, i, line.strip(), hits))
    return out


def _scan_readme(path: Path) -> list[tuple[Path, int, str, list[str]]]:
    out = []
    if not path.exists():
        return out
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if "DEPRECATED" in line:
            continue
        hits = _forbidden_in_line(line)
        if hits:
            out.append((path, i, line.strip(), hits))
    return out


def _extract_python_visible_lines(text: str) -> list[tuple[int, str]]:
    """从 Python 文件抽取用户可见行：docstring 与字符串字面量。

    纯注释行（# 开头，去掉空格后）不算用户可见，跳过。
    """
    lines = text.splitlines()
    visible: list[tuple[int, str]] = []
    in_docstring = False
    for i, raw in enumerate(lines, 1):
        stripped = raw.strip()
        # docstring 边界（三引号）
        triple_count = raw.count('"""')
        if in_docstring:
            visible.append((i, raw))
            if triple_count % 2 == 1:
                in_docstring = False
            continue
        if triple_count == 1:
            visible.append((i, raw))
            in_docstring = True
            continue
        if triple_count >= 2:
            visible.append((i, raw))
            continue
        # 纯注释行跳过（非 docstring 内）
        if stripped.startswith("#"):
            continue
        # 字符串字面量行视为可见
        if '"""' not in raw and ("\"" in raw or "'" in raw):
            visible.append((i, raw))
    return visible


def _scan_backend_api(root: Path) -> list[tuple[Path, int, str, list[str]]]:
    out = []
    if not root.exists():
        return out
    for f in root.rglob("*.py"):
        if _is_path_exempt(f):
            continue
        text = f.read_text(encoding="utf-8")
        for i, raw in _extract_python_visible_lines(text):
            if "DEPRECATED" in raw:
                continue
            hits = _forbidden_in_line(raw)
            if hits:
                out.append((f, i, raw.strip(), hits))
    return out


def _format(violations: list[tuple[Path, int, str, list[str]]]) -> str:
    return "\n".join(
        f"  {p.relative_to(REPO_ROOT)}:{i} hits={hits} :: {line}"
        for p, i, line, hits in violations
    )


def test_frontend_no_forbidden_narrative():
    violations = _scan_frontend(FRONTEND_SRC)
    assert not violations, f"前端存在禁止叙事词:\n{_format(violations)}"


def test_readme_no_forbidden_narrative():
    violations = _scan_readme(README)
    assert not violations, f"README 存在禁止叙事词:\n{_format(violations)}"


def test_backend_docstrings_no_forbidden_narrative():
    violations = _scan_backend_api(BACKEND_API)
    assert not violations, f"后端 API docstring/字面量存在禁止叙事词:\n{_format(violations)}"
