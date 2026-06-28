export interface MarkdownTableField {
  label: string;
  value: string;
}

export interface MarkdownTableRowCard {
  title: string;
  fields: MarkdownTableField[];
}

export interface MarkdownTableModel {
  headers: string[];
  rows: MarkdownTableRowCard[];
}

export type MarkdownContentBlock =
  | { type: "markdown"; text: string }
  | { type: "table"; table: MarkdownTableModel };

function isMarkdownTableLine(line: string): boolean {
  return line.trimStart().startsWith("|") && line.trimEnd().endsWith("|");
}

function splitMarkdownTableCells(line: string): string[] {
  return line
    .trim()
    .split("|")
    .slice(1, -1)
    .map((cell) => cell.trim());
}

function isSeparatorCell(cell: string): boolean {
  return /^[\s]*:?-{3,}:?[\s]*$/.test(cell);
}

function isSeparatorRow(cells: string[]): boolean {
  const nonEmpty = cells.filter((cell) => cell !== "");
  return nonEmpty.length > 0 && nonEmpty.every(isSeparatorCell);
}

function inferColumnCount(cells: string[]): number {
  let colCount = 0;
  let run = 0;

  for (const cell of cells) {
    if (isSeparatorCell(cell)) {
      run += 1;
      colCount = Math.max(colCount, run);
    } else {
      run = 0;
    }
  }

  if (colCount < 2) {
    colCount = cells.filter((cell) => cell !== "").length;
  }

  return colCount;
}

export function sanitizeMarkdownTableLines(raw: string): string[] {
  const result: string[] = [];

  for (const line of raw.split("\n")) {
    if (!isMarkdownTableLine(line)) {
      result.push(line);
      continue;
    }

    const cells = splitMarkdownTableCells(line);
    const colCount = inferColumnCount(cells);

    if (colCount < 2) {
      result.push(line);
      continue;
    }

    const meaningful = cells.filter((cell) => cell !== "");
    for (let i = 0; i < meaningful.length; i += colCount) {
      const row = meaningful.slice(i, i + colCount);
      result.push("| " + row.join(" | ") + " |");
    }
  }

  return result;
}

export function parseMarkdownTable(markdown: string): MarkdownTableModel | null {
  const tableRows = markdown
    .split("\n")
    .filter(isMarkdownTableLine)
    .map(splitMarkdownTableCells)
    .filter((cells) => cells.some((cell) => cell !== ""));

  const headers = tableRows.find((cells) => !isSeparatorRow(cells));
  if (!headers || headers.length < 2) {
    return null;
  }

  const bodyRows = tableRows
    .slice(tableRows.indexOf(headers) + 1)
    .filter((cells) => !isSeparatorRow(cells));

  return {
    headers,
    rows: bodyRows.map((cells) => {
      const title = cells[0] || "项目";
      const fields = headers.slice(1).map((label, index) => ({
        label,
        value: cells[index + 1] || "-",
      }));

      return { title, fields };
    }),
  };
}

export function splitMarkdownIntoBlocks(raw: string): MarkdownContentBlock[] {
  const lines = sanitizeMarkdownTableLines(raw);
  const blocks: MarkdownContentBlock[] = [];
  let markdownLines: string[] = [];
  let tableLines: string[] = [];

  const flushMarkdown = () => {
    const text = markdownLines.join("\n").trim();
    if (text) blocks.push({ type: "markdown", text });
    markdownLines = [];
  };

  const flushTable = () => {
    if (tableLines.length === 0) return;
    const table = parseMarkdownTable(tableLines.join("\n"));
    if (table) {
      blocks.push({ type: "table", table });
    } else {
      markdownLines.push(...tableLines);
    }
    tableLines = [];
  };

  for (const line of lines) {
    if (isMarkdownTableLine(line)) {
      flushMarkdown();
      tableLines.push(line);
    } else {
      flushTable();
      markdownLines.push(line);
    }
  }

  flushTable();
  flushMarkdown();

  return blocks;
}
