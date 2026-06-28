"""Markdown 表格修复器

LLM 流式输出时常把整个表格（表头 + 分隔行 + 数据行）挤在一行里：
    | col1 | col2 | | :--- | :--- | | data1 | data2 | | data3 | data4 |

本模块在 SSE 流式输出前对文本做规范化，将合并行重新拆分为标准 Markdown 表格。

流式处理策略：
- 维护一个行缓冲区，按换行符切片
- 只有完整的行（以 \\n 结尾）才送修复器，未完成的片段累积
- 修复器仅处理表格行（以 | 开头并以 | 结尾）
"""

import re
from typing import AsyncGenerator

# 匹配分隔单元格（:---  /  ---  /  :---:  /  ---:）
_SEP_CELL_RE = re.compile(r"^\s*:?-{3,}:?\s*$")
# 匹配表格行（首尾都是竖线，允许首尾有空白）
_TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")


def _normalize_table_line(line: str) -> str:
    """将一行内挤在一起的多个表格行拆分为标准多行 Markdown 表格。

    算法：
    1. split('|') 得到所有单元格（含首尾空串）
    2. 去掉首尾空串
    3. 用最长连续分隔单元格序列推断列数 N
    4. 过滤掉行间边界的纯空白占位格
    5. 按每 N 个单元格为一行重新组装
    """
    if not _TABLE_LINE_RE.match(line):
        return line

    # 只处理单行内含分隔符（说明多行被合并）的表格行
    raw_cells = line.split("|")
    cells = raw_cells[1:-1]  # 去掉首尾空串

    # 找最长连续分隔单元格序列 → 列数 N
    col_count = 0
    run = 0
    for c in cells:
        if _SEP_CELL_RE.match(c):
            run += 1
            if run > col_count:
                col_count = run
        else:
            run = 0

    if col_count < 2:
        # 没有合并行，可能只是普通表格行（含分隔符的）或非表格文本
        # 对普通表格行也做一次"去除多余尾部竖线"的规整
        trimmed = [c.strip() for c in cells]
        # 去掉尾部空白单元格
        while trimmed and trimmed[-1] == "":
            trimmed.pop()
        if len(trimmed) < 2:
            return line
        return "| " + " | ".join(trimmed) + " |"

    # 有合并行的情况：按 N 列重新分组
    # 先过滤掉所有纯空白占位格（行边界 | | 的产物），保留有内容的和分隔格
    meaningful = [c.strip() for c in cells if c.strip() != ""]

    # 分隔格在 meaningful 中仍然连续，重新确认 N
    sep_run = 0
    max_sep_run = 0
    for c in meaningful:
        if _SEP_CELL_RE.match(c):
            sep_run += 1
            if sep_run > max_sep_run:
                max_sep_run = sep_run
        else:
            sep_run = 0
    n = max_sep_run if max_sep_run >= 2 else col_count

    if n < 2:
        return line

    rows: list[list[str]] = []
    for i in range(0, len(meaningful), n):
        chunk = meaningful[i : i + n]
        rows.append(chunk)

    return "\n".join("| " + " | ".join(r) + " |" for r in rows)


def fix_markdown_tables(text: str) -> str:
    """对完整文本做表格修复（批量版本，用于测试和整段处理）。"""
    lines = text.split("\n")
    fixed = []
    for line in lines:
        if _TABLE_LINE_RE.match(line):
            fixed.append(_normalize_table_line(line))
        else:
            fixed.append(line)
    return "\n".join(fixed)


class StreamingTableFixer:
    """流式表格修复器：在 SSE 流式输出过程中按行缓冲并修复表格。

    使用方式：
        fixer = StreamingTableFixer()
        async for delta in upstream:
            async for piece in fixer.feed(delta):
                yield piece
        async for piece in fixer.flush():
            yield piece
    """

    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, delta: str) -> list[str]:
        """喂入一段流式文本，返回可立即输出的已修复完整片段列表。

        策略：累积到 buffer，遇到 \\n 就切出一行，若是表格行则修复。
        为保证表格行修复正确，需 peek 下一行是否仍属同一表格块——
        但合并行的本质是"整块表格只有一行"，所以行内修复即可，无需跨行。
        """
        out: list[str] = []
        self._buffer += delta

        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            # line 是一个完整的行（不含换行符）
            if _TABLE_LINE_RE.match(line):
                fixed = _normalize_table_line(line)
                out.append(fixed + "\n")
            else:
                out.append(line + "\n")

        return out

    def flush(self) -> str:
        """流结束时输出缓冲区剩余内容。"""
        remaining = self._buffer
        self._buffer = ""
        if not remaining:
            return ""
        if _TABLE_LINE_RE.match(remaining):
            return _normalize_table_line(remaining)
        return remaining


async def wrap_stream_with_table_fix(
    upstream: AsyncGenerator[str, None],
) -> AsyncGenerator[str, None]:
    """包裹一个异步文本流，输出经过表格修复的文本流。

    Args:
        upstream: 原始 LLM 流式生成器

    Yields:
        str: 修复后的文本片段
    """
    fixer = StreamingTableFixer()
    try:
        async for delta in upstream:
            pieces = fixer.feed(delta)
            for piece in pieces:
                if piece:
                    yield piece
        tail = fixer.flush()
        if tail:
            yield tail
    except Exception:
        # 出错时也把缓冲区冲刷出去
        tail = fixer.flush()
        if tail:
            yield tail
        raise
