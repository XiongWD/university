import { useEffect, useMemo, useRef, useState } from "react";
import { Search, Loader2 } from "lucide-react";

// 院校联想下拉的候选项（与 HenanOptions.schools 同构）
export interface SchoolOption {
  code: string;
  name: string;
}

interface Props {
  options: SchoolOption[];
  value: string;
  onChange: (name: string) => void;
  disabled?: boolean;
  placeholder?: string;
  // 最多展示多少条候选，避免长列表卡顿
  maxVisible?: number;
}

/**
 * 可输入 + 联想过滤的院校选择器。
 * - 输入时按 name 子串（大小写不敏感）过滤
 * - ↑/↓ 移动高亮、Enter 选中、Esc 关闭、点击外部关闭
 * - 选中后回填院校名，并清空输入框的临时文本，保证 value 与 options 一致
 */
export default function SchoolCombobox({
  options,
  value,
  onChange,
  disabled = false,
  placeholder = "输入院校名称，如 郑州大学",
  maxVisible = 15,
}: Props) {
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // 外部 value 变化（如联动重置）时同步输入框
  useEffect(() => {
    setQuery(value);
  }, [value]);

  // 点击外部关闭浮层
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
        // 关闭时回填为当前已选院校，丢弃未确认的临时输入
        setQuery(value);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open, value]);

  // 联想过滤：仅当浮层打开且输入内容与当前已选值不同时才过滤
  const filtered = useMemo(() => {
    if (!open) return [];
    const q = query.trim().toLowerCase();
    if (!q) return options.slice(0, maxVisible);
    const matched = options.filter((o) => o.name.toLowerCase().includes(q));
    return matched.slice(0, maxVisible);
  }, [open, query, options, maxVisible]);

  // 过滤结果变化时，把高亮项钳制到合法范围
  useEffect(() => {
    setActive((a) => Math.min(a, Math.max(0, filtered.length - 1)));
  }, [filtered.length]);

  function pick(name: string) {
    onChange(name);
    setQuery(name);
    setOpen(false);
    setActive(0);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      if (!open) { setOpen(true); return; }
      e.preventDefault();
      setActive((a) => Math.min(a + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      if (!open) return;
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      if (open && filtered.length > 0) {
        e.preventDefault();
        pick(filtered[active].name);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      setQuery(value);
    }
  }

  // 高亮项滚动到可视区
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${active}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const showEmpty = open && query.trim() !== "" && filtered.length === 0;

  return (
    <div ref={wrapRef} className="relative">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40 pointer-events-none" />
        <input
          type="text"
          value={query}
          disabled={disabled}
          placeholder={placeholder}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); setActive(0); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          className="w-full bg-white/10 rounded-xl pl-8 pr-8 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-pink-400/50 disabled:opacity-50"
          autoComplete="off"
        />
        {disabled && (
          <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40 animate-spin" />
        )}
      </div>

      {open && !disabled && (
        <ul
          ref={listRef}
          className="absolute z-20 mt-1 w-full max-h-60 overflow-auto rounded-xl bg-slate-800 ring-1 ring-white/10 shadow-2xl"
        >
          {filtered.map((o, i) => (
            <li key={o.code}>
              <button
                type="button"
                data-idx={i}
                onClick={() => pick(o.name)}
                onMouseEnter={() => setActive(i)}
                className={`w-full text-left px-3 py-2 text-sm transition ${
                  i === active ? "bg-pink-500/20 text-white" : "text-white/70 hover:bg-white/5"
                }`}
              >
                <span className="font-medium">{o.name}</span>
                <span className="text-[10px] text-white/35 ml-2">{o.code}</span>
              </button>
            </li>
          ))}
          {showEmpty && (
            <li className="px-3 py-2 text-xs text-white/40">无匹配院校</li>
          )}
        </ul>
      )}
    </div>
  );
}
