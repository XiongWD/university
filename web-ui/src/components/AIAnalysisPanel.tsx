import { useState, useRef, useCallback, useEffect, isValidElement } from "react";
import type { ReactNode } from "react";
import { Sparkles, X, Loader2, Square } from "lucide-react";
import ReactMarkdown from "react-markdown";
import type { SSEChunk } from "../api/types";
import { sanitizeMarkdownTableLines, splitMarkdownIntoBlocks } from "./markdownTableCards";
import type { MarkdownTableModel } from "./markdownTableCards";

export interface AIAnalysisPanelProps {
  title: string;
  buttonLabel?: string;
  streamFactory: (
    signal: AbortSignal,
  ) => AsyncGenerator<SSEChunk, void, undefined>;
  defaultOpen?: boolean;
}

/** 格式化耗时 */
function fmtElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(0);
  return `${m}m ${s}s`;
}

/** 预处理 Markdown：修复 LLM 的表格格式错误（多行合并 + 多余空列） */
function sanitizeMarkdown(raw: string): string {
  return sanitizeMarkdownTableLines(raw).join("\n");

  const lines = raw.split("\n");
  const result: string[] = [];

  for (const line of lines) {
    // 只处理表格行
    if (!line.trimStart().startsWith("|") || !line.trimEnd().endsWith("|")) {
      result.push(line);
      continue;
    }

    // 提取所有单元格
    const rawCells = line.split("|");
    const cells = rawCells.slice(1, -1); // 去掉首尾空串

    // 找到分隔行的列数 N（最长连续 |:---| 序列）
    let colCount = 0;
    let run = 0;
    for (const c of cells) {
      if (/^[\s]*:?-{3,}:?[\s]*$/.test(c)) {
        run++;
        if (run > colCount) colCount = run;
      } else {
        run = 0;
      }
    }
    if (colCount < 2) {
      colCount = cells.filter(c => c.trim() !== "").length;
    }
    if (colCount < 2) {
      result.push(line);
      continue;
    }

    // 过滤掉行间边界的纯空白单元格（| | 产物），保留有内容的
    const meaningful = cells.filter(c => c.trim() !== "");

    // 按 N 列分组为行
    const rows: string[][] = [];
    for (let i = 0; i < meaningful.length; i += colCount) {
      rows.push(meaningful.slice(i, i + colCount).map(c => c.trim()));
    }

    for (const row of rows) {
      result.push("| " + row.join(" | ") + " |");
    }
  }
  return result.join("\n");
}

function extractPlainText(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractPlainText).join("").trim();
  if (isValidElement<{ children?: ReactNode }>(node)) return extractPlainText(node.props.children);
  return "";
}

function extractTableRows(node: ReactNode): string[][] {
  if (node === null || node === undefined || typeof node === "boolean") return [];
  if (Array.isArray(node)) return node.flatMap(extractTableRows);
  if (!isValidElement<{ children?: ReactNode }>(node)) return [];

  if (node.type === "tr") {
    const children = node.props.children;
    const cells = Array.isArray(children)
      ? children.map(extractPlainText).map((cell) => cell.trim())
      : [extractPlainText(children).trim()];
    return [cells];
  }

  return extractTableRows(node.props.children);
}

function MarkdownTableCards({ children }: { children: ReactNode }) {
  const rows = extractTableRows(children).filter((row) => row.some(Boolean));
  const headers = rows[0] ?? [];
  const bodyRows = rows.slice(1);

  if (headers.length < 2 || bodyRows.length === 0) {
    return (
      <div className="my-4 rounded-xl bg-white/[0.04] px-4 py-3 text-sm text-white/60">
        {extractPlainText(children)}
      </div>
    );
  }

  const titleLabel = headers[0] || "项目";

  return (
    <div className="my-4 space-y-3">
      {bodyRows.map((row, rowIndex) => {
        const title = row[0] || `${titleLabel} ${rowIndex + 1}`;
        const fields = headers.slice(1).map((label, index) => ({
          label: label || `字段 ${index + 1}`,
          value: row[index + 1] || "-",
        }));
        const leadField = fields[0];

        return (
          <article
            key={`${title}-${rowIndex}`}
            className="rounded-xl bg-white/[0.045] px-4 py-3 shadow-[0_1px_0_rgba(255,255,255,0.08)_inset] transition-colors hover:bg-white/[0.065]"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-medium text-white/40">{titleLabel}</span>
              <h4 className="text-sm font-semibold text-white/90">{title}</h4>
              {leadField && (
                <span className="rounded-md bg-pink-500/15 px-2 py-0.5 text-[11px] font-medium text-pink-200">
                  {leadField.value}
                </span>
              )}
            </div>
            <dl className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {fields.slice(leadField ? 1 : 0).map((field, fieldIndex) => (
                <div
                  key={`${field.label}-${fieldIndex}`}
                  className="rounded-lg bg-black/10 px-3 py-2"
                >
                  <dt className="text-[11px] font-medium text-white/40">{field.label}</dt>
                  <dd className="mt-1 text-[13px] leading-relaxed text-white/75 [text-wrap:pretty]">
                    {field.value}
                  </dd>
                </div>
              ))}
            </dl>
          </article>
        );
      })}
    </div>
  );
}

function MarkdownTableModelCards({ table }: { table: MarkdownTableModel }) {
  const titleLabel = table.headers[0] || "项目";

  return (
    <div className="my-4 space-y-3">
      {table.rows.map((row, rowIndex) => {
        const leadField = row.fields[0];

        return (
          <article
            key={`${row.title}-${rowIndex}`}
            className="rounded-xl bg-white/[0.055] px-4 py-3 shadow-[0_1px_0_rgba(255,255,255,0.09)_inset] transition-colors hover:bg-white/[0.075]"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-medium text-white/40">{titleLabel}</span>
              <h4 className="text-sm font-semibold text-white/90">{row.title}</h4>
              {leadField && (
                <span className="rounded-md bg-pink-500/15 px-2 py-0.5 text-[11px] font-medium text-pink-200">
                  {leadField.value}
                </span>
              )}
            </div>
            <dl className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {row.fields.slice(leadField ? 1 : 0).map((field, fieldIndex) => (
                <div
                  key={`${field.label}-${fieldIndex}`}
                  className="rounded-lg bg-black/10 px-3 py-2"
                >
                  <dt className="text-[11px] font-medium text-white/40">{field.label}</dt>
                  <dd className="mt-1 text-[13px] leading-relaxed text-white/75 [text-wrap:pretty]">
                    {field.value}
                  </dd>
                </div>
              ))}
            </dl>
          </article>
        );
      })}
    </div>
  );
}

export default function AIAnalysisPanel({
  title,
  buttonLabel = "✨ AI 分析",
  streamFactory,
  defaultOpen = false,
}: AIAnalysisPanelProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [status, setStatus] = useState<"idle" | "loading" | "streaming" | "done" | "error">("idle");
  const [content, setContent] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 自动滚动到底部
  useEffect(() => {
    if (status === "streaming" && contentRef.current) {
      contentRef.current.scrollTo({
        top: contentRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [content, status]);

  // 清理定时器和请求
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      abortRef.current?.abort();
    };
  }, []);

  const startStream = useCallback(async () => {
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("loading");
    setContent("");
    setErrorMsg("");
    setElapsed(0);
    setOpen(true);

    // 启动计时器
    timerRef.current = setInterval(() => {
      setElapsed((prev) => prev + 0.1);
    }, 100);

    try {
      const stream = streamFactory(controller.signal);
      setStatus("streaming");

      for await (const chunk of stream) {
        if (chunk.error) {
          setErrorMsg(chunk.error);
          setStatus("error");
          return;
        }
        if (chunk.delta) {
          setContent((prev) => prev + chunk.delta);
        }
      }
      setStatus("done");
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setStatus(content ? "done" : "idle");
        return;
      }
      const msg = err instanceof Error ? err.message : "AI 服务请求失败";
      setErrorMsg(msg);
      setStatus("error");
    } finally {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  }, [streamFactory, content]);

  const stopStream = useCallback(() => {
    abortRef.current?.abort();
    if (content) {
      setStatus("done");
    } else {
      setStatus("idle");
      setOpen(false);
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, [content]);

  // ---- 未展开：显示触发按钮 ----
  if (!open) {
    return (
      <button
        type="button"
        onClick={startStream}
        className="w-full py-3 rounded-xl border border-dashed border-pink-400/30
                   bg-gradient-to-r from-pink-500/10 via-fuchsia-500/10 to-indigo-500/10
                   hover:from-pink-500/20 hover:to-indigo-500/20
                   text-pink-200 text-sm font-medium
                   flex items-center justify-center gap-2
                   transition-all duration-300"
      >
        <Sparkles className="w-4 h-4" />
        {buttonLabel}
      </button>
    );
  }

  // ---- 已展开 ----
  return (
    <div className="glass rounded-3xl p-5 sm:p-6 shadow-2xl animate-slide-up">
      {/* ── 头部 ── */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 min-w-0">
          <Sparkles className="w-5 h-5 text-pink-400 shrink-0" />
          <h2 className="font-bold text-base sm:text-lg text-white/90 truncate">{title}</h2>

          {status === "loading" && (
            <span className="flex items-center gap-1 text-xs text-amber-300/80 shrink-0">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              准备中...
            </span>
          )}
          {status === "streaming" && (
            <span className="flex items-center gap-1 text-xs text-emerald-300/80 shrink-0">
              <span className="inline-block w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
              生成中 {fmtElapsed(elapsed)}
            </span>
          )}
          {status === "done" && (
            <span className="text-[10px] text-emerald-400/80 font-medium bg-emerald-500/10 px-2 py-0.5 rounded shrink-0">
              完成 · {fmtElapsed(elapsed)}
            </span>
          )}
          {status === "error" && (
            <span className="text-[10px] text-red-400/80 font-medium bg-red-500/10 px-2 py-0.5 rounded shrink-0">
              出错
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {status === "streaming" && (
            <button
              type="button"
              onClick={stopStream}
              className="p-1.5 rounded-lg bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 transition"
              title="停止生成"
            >
              <Square className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="p-1.5 rounded-lg bg-white/5 text-white/40 hover:bg-white/10 hover:text-white/70 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ── 错误 ── */}
      {errorMsg && (
        <div className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-400/20 text-sm text-red-200">
          {errorMsg}
        </div>
      )}

      {/* ── 空状态：等待 LLM 返回第一个字 ── */}
      {(status === "loading" || (status === "streaming" && !content)) && (
        <div className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-pink-400" />
            <span className="text-sm text-white/50">
              AI 正在分析，请稍候...
            </span>
            <span className="text-xs text-white/30">
              已等待 {fmtElapsed(elapsed)}
            </span>
          </div>
        </div>
      )}

      {/* ── 内容区域 ── */}
      {content && (
        <div
          ref={contentRef}
          className="markdown-body max-h-[700px] overflow-y-auto
                     scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent
                     text-sm leading-relaxed text-white/80"
        >
          {splitMarkdownIntoBlocks(sanitizeMarkdown(content)).map((block, blockIndex) => block.type === "table" ? (
            <MarkdownTableModelCards key={`table-${blockIndex}`} table={block.table} />
          ) : (
          <ReactMarkdown
            key={`markdown-${blockIndex}`}
            components={{
              // 表格渲染 — 支持横向滚动，列宽自适应
              table: ({ children }) => (
                <MarkdownTableCards>{children}</MarkdownTableCards>
              ),
              // 标题
              h2: ({ children }) => (
                <h2 className="text-lg font-bold text-white/90 mt-6 mb-3 pb-1.5 border-b border-white/10">
                  {children}
                </h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-base font-semibold text-white/85 mt-4 mb-2">{children}</h3>
              ),
              // 段落
              p: ({ children }) => (
                <p className="my-2 text-white/75 leading-relaxed">{children}</p>
              ),
              // 列表
              ul: ({ children }) => (
                <ul className="my-2 space-y-1 list-disc list-inside text-white/70">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="my-2 space-y-1 list-decimal list-inside text-white/70">{children}</ol>
              ),
              li: ({ children }) => (
                <li className="pl-1 marker:text-pink-400">{children}</li>
              ),
              // 强调
              strong: ({ children }) => (
                <strong className="font-semibold text-white/90">{children}</strong>
              ),
              em: ({ children }) => (
                <em className="italic text-pink-300/80">{children}</em>
              ),
              // 代码
              code: ({ children }) => (
                <code className="text-pink-300 bg-white/5 px-1.5 py-0.5 rounded text-xs font-mono">
                  {children}
                </code>
              ),
              // 引用
              blockquote: ({ children }) => (
                <blockquote className="border-l-3 border-pink-400/40 pl-4 my-3 text-white/55 italic">
                  {children}
                </blockquote>
              ),
              // 链接
              a: ({ children, href }) => (
                <a href={href} className="text-pink-400 hover:underline" target="_blank" rel="noopener">
                  {children}
                </a>
              ),
              // 分割线
              hr: () => <hr className="my-4 border-white/10" />,
            }}
          >
            {block.text}
          </ReactMarkdown>
          ))}
          {status === "streaming" && (
            <span className="inline-block w-2 h-4 ml-0.5 bg-pink-400 animate-pulse rounded-sm align-middle" />
          )}
        </div>
      )}

      {/* ── 底部操作 ── */}
      {status === "done" && (
        <div className="mt-4 pt-3 border-t border-white/10 flex items-center gap-3">
          <button
            type="button"
            onClick={startStream}
            className="text-xs px-3 py-1.5 rounded-lg bg-pink-500/15 text-pink-300 hover:bg-pink-500/25 transition"
          >
            🔄 重新生成
          </button>
          <span className="text-[11px] text-white/30">
            AI 生成内容仅供参考，请以官方招生章程为准。
          </span>
        </div>
      )}

      {status === "error" && (
        <div className="mt-4 pt-3 border-t border-white/10">
          <button
            type="button"
            onClick={startStream}
            className="text-xs px-3 py-1.5 rounded-lg bg-red-500/15 text-red-300 hover:bg-red-500/25 transition"
          >
            🔄 重试
          </button>
        </div>
      )}
    </div>
  );
}
