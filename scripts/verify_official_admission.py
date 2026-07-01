"""
院校官网录取数据交叉验证（河南 2026 历史类普通本科批）。

把"郑州经贸 101 组验证方法"固化为可复用工具：从院校招生网抓 2025 河南
历史类录取分数，用一分一段表换算成权威位次，再比对本地种子
admission_history_2025.yaml 的 min_rank，判定 match / conflict / no_official_data。

判等口径（与郑州经贸验证一致）：
  官网分数 → 一分一段表换算位次 → 比对种子 min_rank，容差 ±500 位。

用法：
  python scripts/verify_official_admission.py --school 郑州经贸学院
  python scripts/verify_official_admission.py --all            # 跑弟弟志愿组 16 所
  python scripts/verify_official_admission.py --all --refresh  # 强制重抓官网

设计原则：
- 坚持 stdlib（urllib + html.parser），不引入 requests/BS4，贴合项目既有风格。
- 复用 app.engine.henan_recommendation 的 _load_score_rank_entries / _score_to_rank。
- 复用 app.loader.henan_data_loader 的 load_henan_admission_history / load_henan_universities。
- 断点续抓：data/verify/cache.json 每校缓存，可重跑；失败记 failed.txt。
- 降级鲁棒：官网数据形态多样（PDF/HTML/图片），逐一处理，找不到则标 no_official_data。

官网是唯一权威源。本地 heao 种子数据（多次出现位次/专业组缺失）可信度低，
conflict 时一律以官网为准。
"""
import argparse
import json
import re
import ssl
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.loader.henan_data_loader import (  # noqa: E402
    load_henan_admission_history,
    load_henan_universities,
)
from app.engine.henan_recommendation import (  # noqa: E402
    _load_score_rank_entries,
    _score_to_rank,
)

# ── 配置 ──────────────────────────────────────────────────────────────
SEED_DIR = PROJECT_ROOT / "data" / "seed"
VERIFY_DIR = PROJECT_ROOT / "data" / "verify"
CACHE_FILE = VERIFY_DIR / "cache.json"
REPORT_FILE = VERIFY_DIR / "report.md"
FAILED_FILE = VERIFY_DIR / "failed.txt"
TARGET_YEAR = 2025  # 验证用 2025 录取数据（最近一年有完整官网公布）
SCORE_TOLERANCE = 500  # 位次容差：±500 视为 match（一分一段档位 + 省控年际浮动）

# 弟弟志愿组（default 组）13 所学校 —— data/llm_sim.db 实际清单（2026-06-30 更新）
BROTHER_SCHOOLS = [
    "安阳学院", "商丘学院", "中原科技学院", "新乡工程学院",
    "郑州经贸学院", "长春财经学院", "西安外事学院", "广东理工学院",
    "陕西服装工程学院", "齐齐哈尔工程学院", "哈尔滨石油学院",
    "信阳学院", "黑龙江外国语学院",
]

# 抓取链接的关键词（2025 河南历史类普通本科录取分数统计）
LINK_KEYWORDS = [
    "2025", "河南省", "河南", "本科", "普通类", "录取分数",
    "分专业录取", "录取分数统计", "历年", "录取情况",
]
# 排除关键词（避免抓到无关页面）
LINK_EXCLUDE = [
    "艺术", "体育", "专科", "高职", "跨省", "省外", "物理类",
    "章程", "计划", "简章", "动态", "通知", "公告", "新闻",
]

# 通用 TLS 上下文（本地 Python 证书链校验失败，统一禁用——与 heao_client.py 一致）。
# SECLEVEL=1 兼容使用旧 cipher 的招生网服务器（部分学校 SSLV3_ALERT_HANDSHAKE_FAILURE）。
_CTX = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
try:
    _CTX.set_ciphers("DEFAULT@SECLEVEL=1")
except Exception:
    pass

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# 完整浏览器请求头 —— 部分招生网（西安外事 412、丽江 503）对缺 Referer/接收语言
# 的 urllib 默认请求会主动拒绝。补全头部让其更像真实浏览器访问。
# 注意：不设 Accept-Encoding=gzip，urllib 不会自动解压，会得到 gzip 二进制乱码。
_BROWSER_HEADERS = {
    "User-Agent": UA,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


# ── 数据结构 ──────────────────────────────────────────────────────────
@dataclass
class OfficialRecord:
    """官网抓取结果（Step ①②）。"""

    school_name: str
    found_url: str = ""          # 命中的录取页 URL
    raw_text: str = ""           # 解析出的正文（分数表内容）
    official_score: int | None = None  # 官网历史类最低录取分
    volunteer_group: str = ""    # 志愿组号（如 101）
    converted_rank: int | None = None  # 一分一段表换算位次
    status: str = "no_official_data"  # found / needs_manual / no_official_data
    note: str = ""               # 说明（找不到链接、需人工 OCR 等）
    candidate_links: list[str] = field(default_factory=list)  # 供人工跟进的候选链接
    fetched_at: str = ""


@dataclass
class Verdict:
    """比对结果（Step ③）。"""

    school_name: str
    verdict: str  # match / conflict / no_official_data
    official_score: int | None
    converted_rank: int | None
    seed_rank: int | None
    seed_score: int | None
    delta: int | None  # 换算位次 - 种子位次（正=种子偏低估）
    note: str = ""


# ── Step ① 抓官网录取表 ──────────────────────────────────────────────
class _LinkParser(HTMLParser):
    """抽取 <a href> + 文本（抄 discover_henan_2026_official_sources.py 范式）。"""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = next((v for k, v in attrs if k.lower() == "href" and v), None)
        if not href:
            return
        self.links.append(("", href))  # 文本稍后在 handle_data 补

    def handle_data(self, data: str) -> None:
        if self.links:
            text, href = self.links[-1]
            self.links[-1] = (text + data, href)


class _TableParser(HTMLParser):
    """抽取 <table> 的 rows（抄 extract_henan_2026_catalog_pdf.py 范式）。"""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._cur: list[str] = []
        self._in_cell = False
        self._cell_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "tr":
            self._cur = []
        elif tag.lower() in ("td", "th"):
            self._in_cell = True
            self._cell_buf = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("td", "th"):
            self._in_cell = False
            self._cur.append("".join(self._cell_buf).strip())
        elif t == "tr":
            if self._cur:
                self.rows.append(self._cur)

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_buf.append(data)


class _PdfImageDetector(HTMLParser):
    """检测正文区是否含 PDF/图片。

    高校站常见 vsb 内容系统把 PDF 藏在 <script>showVsbpdfIframe("xxx.pdf",...)</script>
    里（非标准 embed/object/a 标签），需在 handle_data 扫 <script> 内容。
    """

    def __init__(self) -> None:
        super().__init__()
        self.has_pdf_embed = False
        self.has_image_only = False
        self.pdf_urls: list[str] = []
        self.img_urls: list[str] = []
        self._in_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        ad = dict(attrs)
        if t in ("embed", "object"):
            src = ad.get("src") or ad.get("data") or ""
            if src.lower().endswith(".pdf"):
                self.has_pdf_embed = True
                self.pdf_urls.append(src)
        elif t == "a":
            href = ad.get("href") or ""
            if href.lower().endswith(".pdf"):
                self.has_pdf_embed = True
                self.pdf_urls.append(href)
        elif t == "img":
            src = ad.get("src") or ""
            if src and "logo" not in src.lower() and "banner" not in src.lower():
                self.img_urls.append(src)
        elif t == "script":
            self._in_script = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script":
            self._in_script = False

    def handle_data(self, data: str) -> None:
        # 扫 <script> 内容，捕获 showVsbpdfIframe("xxx.pdf",...) 等 JS 内 PDF URL
        if self._in_script:
            for m in re.finditer(r'["\']([^"\']+\.pdf)["\']', data):
                url = m.group(1)
                if url not in self.pdf_urls:
                    self.has_pdf_embed = True
                    self.pdf_urls.append(url)


def _fetch_bytes(url: str, timeout: int = 15, referer: str = "") -> tuple[bytes, str]:
    """抓 URL 返回 (bytes, content_type)。"""
    headers = dict(_BROWSER_HEADERS)
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
        return resp.read(5_000_000), resp.headers.get("content-type", "")


def _fetch_text(url: str, timeout: int = 12, referer: str = "") -> str:
    """抓 HTML 并按 charset 解码（抄 discover 脚本 fetch_text）。"""
    headers = dict(_BROWSER_HEADERS)
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
        ct = resp.headers.get("content-type", "")
        raw = resp.read(2_000_000)
    if "charset=" in ct:
        enc = ct.split("charset=", 1)[1].split(";", 1)[0].strip()
    else:
        enc = "utf-8"
    try:
        return raw.decode(enc, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _read_pdf_text(path: Path) -> str:
    """PDF 文本提取。

    优先 pdfplumber（本环境已装，能解析表格型 PDF），回退 pypdf/PyPDF2。
    三者都没有时返回空，由调用方降级为 needs_manual。
    """
    # 优先 pdfplumber：表格型 PDF 文本提取最准
    try:
        import pdfplumber

        parts: list[str] = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        text = "\n".join(parts).strip()
        if text:
            return text
    except Exception:
        pass
    # 回退 pypdf → PyPDF2（抄 extract_henan_2026_catalog_pdf.py:89）
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore[no-redef]
        except Exception:
            return ""
    try:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


# ── OCR（图片型分数线，复用 ocr_henan_2024.py 的 PaddleOCR 范式）────────
_OCR_INSTANCE = None


def _get_ocr():
    """延迟初始化 PaddleOCR（仅图片型学校需要，避免无谓加载）。"""
    global _OCR_INSTANCE
    if _OCR_INSTANCE is None:
        import os
        import warnings

        os.environ.setdefault("FLAGS_use_mkldnn", "0")  # 规避 onednn PIR bug
        os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
        warnings.filterwarnings("ignore")
        from paddleocr import PaddleOCR

        _OCR_INSTANCE = PaddleOCR(
            use_textline_orientation=True, lang="ch", enable_mkldnn=False
        )
    return _OCR_INSTANCE


# 2025 河南历史类本科批省控线（用于 OCR 表格定位历史类行）
_HENAN_HISTORY_CONTROL_LINE_2025 = 471


def _ocr_image_for_score(image_url: str, referer: str = "") -> tuple[int | None, str]:
    """OCR 录取分数线图片，提取河南历史类最低录取分。

    复用 ocr_henan_2024.py 的 PaddleOCR 范式（多边形中心点定位）。
    录取表布局多样（非固定列），用稳健策略：
    - 找"省控线"列（出现多次的重复值）→ 值=471 的行即历史类（2025河南历史类本科线）
    - 取这些行的"最低分"列最小值
    - 退化：若定位不到省控线列，找"历史"文字附近的分数

    返回 (score, note)。score=None 表示未提取到。
    """
    import json

    # 下载图片
    try:
        data, _ = _fetch_bytes(image_url, referer=referer)
    except Exception as e:
        return None, f"图片下载失败：{e}"

    tmp = VERIFY_DIR / "_ocr_tmp.png"
    tmp.write_bytes(data)
    try:
        ocr = _get_ocr()
        res = ocr.predict(str(tmp))[0]
    except Exception as e:
        return None, f"OCR 失败：{e}"
    finally:
        tmp.unlink(missing_ok=True)

    # 收集所有 (文本, 中心点xy, 置信度)
    items: list[dict] = []
    for i, poly in enumerate(res["dt_polys"]):
        t = res["rec_texts"][i]
        cx = sum(p[0] for p in poly) / 4
        cy = sum(p[1] for p in poly) / 4
        items.append({"t": t, "cx": cx, "cy": cy})

    if not items:
        return None, "OCR 无输出"

    # 策略1：定位省控线列。表头"省控线"附近的列，其值会重复（471×N=历史类，427×N=物理类）
    # 找所有 3 位数的数值项，按值统计频次
    from collections import Counter

    numeric = [
        it for it in items
        if it["t"].isdigit() and 300 <= int(it["t"]) <= 700
    ]
    value_counts = Counter(it["t"] for it in numeric)
    # 省控线值：出现≥2次，且是频次最高的几个值
    control_candidates = [
        v for v, c in value_counts.most_common(5) if c >= 2
    ]

    history_score = None
    note = ""
    if _HENAN_HISTORY_CONTROL_LINE_2025 in [int(v) for v in control_candidates]:
        # 找省控线=471 的所有项，它们定义历史类行
        control_471 = [
            it for it in numeric
            if int(it["t"]) == _HENAN_HISTORY_CONTROL_LINE_2025
        ]
        # 找最低分列：和省控线列同行但 x 更小（最低分通常在省控线左侧）
        # 用 control_471 的 cx 范围定位省控线列，其左侧最近的数值列即最低分
        ctrl_cx_median = sorted(it["cx"] for it in control_471)[
            len(control_471) // 2
        ]
        # 最低分候选：cx < 省控线列，且与某省控线项 cy 接近（同行）
        row_scores = []
        for ctrl in control_471:
            for s in numeric:
                if (
                    s["cx"] < ctrl_cx_median
                    and abs(s["cy"] - ctrl["cy"]) < 20
                    and int(s["t"]) != _HENAN_HISTORY_CONTROL_LINE_2025
                ):
                    row_scores.append(int(s["t"]))
        if row_scores:
            history_score = min(row_scores)
            note = f"OCR定位省控线471行，历史类最低分={history_score}（共{len(row_scores)}个专业分数）"
    else:
        note = f"OCR未找到省控线471行（候选省控线值: {control_candidates}）"

    # 策略2：省份行标签布局（如安阳"各省份分数表"）。
    # 布局：左侧是省份标签（河南/河北/内蒙），右侧是多行"科类+组号+分数"。
    # 找"河南"标签的 cy，取其到下一个省份标签之间的所有行，找含"历史"的行的分数。
    if history_score is None:
        # 省份标签：左侧（cx 较小），文本是省名简称
        PROVINCE_NAMES = [
            "河南", "河北", "内蒙", "海南", "湖南", "湖北", "广东", "广西",
            "山东", "山西", "四川", "贵州", "云南", "陕西", "甘肃", "青海",
            "辽宁", "吉林", "宁夏", "新疆", "西藏", "重庆", "浙江", "江苏",
            "安徽", "福建", "江西", "黑龙江",
        ]
        province_tags = [
            it for it in items
            if it["t"] in PROVINCE_NAMES or any(it["t"] == p for p in PROVINCE_NAMES)
        ]
        henan_tag = next((it for it in province_tags if it["t"] == "河南"), None)
        if henan_tag:
            # 下一个省份标签的 cy（河南段的下界）
            later_provinces = [
                it for it in province_tags
                if it["cy"] > henan_tag["cy"] + 5
            ]
            end_cy = (
                min(it["cy"] for it in later_provinces)
                if later_provinces
                else float("inf")
            )
            # 河南段内：cy 在 [henan_cy-10, end_cy) 的项
            henan_section = [
                it for it in items
                if henan_tag["cy"] - 10 <= it["cy"] < end_cy
            ]
            # 河南段内找含"历史"的行，取该行分数（同行右侧的数字）
            history_rows = [
                it for it in henan_section if "历史" in it["t"]
            ]
            section_scores = []
            for hrow in history_rows:
                for s in numeric:
                    if abs(s["cy"] - hrow["cy"]) < 20 and s["cx"] > hrow["cx"]:
                        section_scores.append(int(s["t"]))
            if section_scores:
                history_score = min(section_scores)
                note = f"OCR省份段策略（河南段+历史行），最低分={history_score}（{len(section_scores)}个历史类分数）"

    # 策略3退化：找"历史"文字附近的分数（全局，无省份定位）
    if history_score is None:
        history_text = next(
            (it for it in items if "历史" in it["t"]), None
        )
        if history_text:
            nearby = [
                int(it["t"]) for it in numeric
                if abs(it["cy"] - history_text["cy"]) < 30
                and it["cx"] > history_text["cx"]
            ]
            if nearby:
                history_score = min(nearby)
                note = f"OCR退化策略（历史文字定位），最低分={history_score}"

    return history_score, note or "OCR 未匹配到历史类分数"


def _ocr_images_in_page(html: str, page_url: str) -> tuple[int | None, str]:
    """从详情页 HTML 提取所有内容图片 URL，逐个 OCR，返回第一个能识别出历史类分数的。

    过滤掉 logo/banner/二维码等装饰图（按文件名/alt 关键词）。
    """
    # 提取 <img src> + alt
    imgs: list[tuple[str, str]] = []
    for m in re.finditer(
        r'<img[^>]+src="([^"]+)"[^>]*(?:alt="([^"]*)")?', html, re.I
    ):
        src, alt = m.group(1), (m.group(2) or "")
        imgs.append((src, alt))
    # 也补 alt 在 src 前的写法
    for m in re.finditer(
        r'<img[^>]+alt="([^"]*)"[^>]*src="([^"]+)"', html, re.I
    ):
        alt, src = m.group(1), m.group(2)
        if not any(s == src for s, _ in imgs):
            imgs.append((src, alt))

    # 过滤装饰图
    DECOR_KW = [
        "logo", "banner", "wx", "wechat", "qrcode", "二维码", "top-contxt",
        "footer", "nav", "btn", "icon", "dz.png", "dh.png", "yx.png",
    ]

    def is_content(src: str, alt: str) -> bool:
        label = (src + " " + alt).lower()
        return not any(kw in label for kw in DECOR_KW) and src.lower().endswith(
            (".png", ".jpg", ".jpeg")
        )

    content_imgs = [
        (urljoin(page_url, s), a) for s, a in imgs if is_content(s, a)
    ]
    if not content_imgs:
        return None, "页面无内容图片"

    # 逐个 OCR，命中即返回
    last_note = ""
    for img_url, _alt in content_imgs:
        score, note = _ocr_image_for_score(img_url, referer=page_url)
        if score is not None:
            return score, f"{note}（图: {img_url}）"
        last_note = note
    return None, f"已 OCR {len(content_imgs)} 张图均未命中（{last_note}）"


def _find_admission_links(base_url: str, html: str) -> list[tuple[str, str]]:
    """从招生网首页/栏目页找 2025 河南历史类录取分数链接。

    返回 [(链接文本, 绝对URL)]，按匹配度排序。
    """
    parser = _LinkParser()
    parser.feed(html)
    scored: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for text, href in parser.links:
        text = text.strip()
        if not text or not href or href.startswith(("javascript:", "#", "mailto:")):
            continue
        abs_url = urljoin(base_url, href)
        # 去重 + 去锚点
        norm = abs_url.split("#")[0]
        if norm in seen:
            continue
        seen.add(norm)
        label = text + " " + urlparse(abs_url).path
        # 排除项一票否决
        if any(x in label for x in LINK_EXCLUDE):
            continue
        # 计分：命中越多越靠前
        score = sum(1 for kw in LINK_KEYWORDS if kw in label)
        if score == 0:
            continue
        scored.append((score, text[:60], abs_url))
    scored.sort(key=lambda x: -x[0])
    return [(t, u) for _, t, u in scored[:10]]


def _extract_history_score(text: str) -> tuple[int | None, str]:
    """从录取表正文（PDF/HTML 提取的纯文本）抽取**河南**历史类最低录取分 + 志愿组号。

    返回 (score, volunteer_group)。

    关键：必须校验省份是河南。很多高校录取表把各省数据放一起
    （如"湖南历史类426"紧邻"河南历史类xxx"），不校验会把外省分当河南分，污染验证。
    策略：
    - 先定位"河南"上下文段（从出现"河南"到下一个其他省份名/明显分隔之前）。
    - 只在该段内找历史类分数。
    - 单省数据（全文不含其他省名）时退化为全文匹配。
    """
    if not text:
        return None, ""

    # 省份名表（排除河南本身）——用于判断是否多省混合
    OTHER_PROVINCES = [
        "湖南", "湖北", "广东", "广西", "海南", "河北", "山西", "山东",
        "江西", "江苏", "浙江", "福建", "安徽", "四川", "贵州", "云南",
        "陕西", "甘肃", "青海", "辽宁", "吉林", "黑龙江", "新疆", "西藏",
        "内蒙", "内蒙古", "宁夏", "重庆", "天津", "北京", "上海", "黑龙江",
    ]
    has_other_province = any(p in text for p in OTHER_PROVINCES)
    has_henan = "河南" in text

    # 定位河南段：找到"河南"出现的位置，截取到下一个省名或文本末尾
    if has_henan and has_other_province:
        # 多次出现"河南"时逐段尝试，命中即返回
        for seg in _iter_province_segments(text, "河南", OTHER_PROVINCES):
            result = _match_history_score_in_text(seg)
            if result[0] is not None:
                return result
        # 河南段内没找到，但全文有河南，可能是表格列式（河南单独一列）
        return None, ""

    # 多省混合但无河南 —— 此页是外省数据，坚决不匹配，避免污染
    if has_other_province and not has_henan:
        return None, ""

    # 单省或无明确省份（默认当河南处理——仅当全文无其他省名时才安全）
    return _match_history_score_in_text(text)


def _iter_province_segments(text: str, target: str, others: list[str]) -> list[str]:
    """把全文按 target(河南) 出现位置切成段，每段到下一个省名为止。"""
    segments: list[str] = []
    start = 0
    while True:
        idx = text.find(target, start)
        if idx == -1:
            break
        # 找该段结束：下一个其他省名的最早位置
        end = len(text)
        for p in others:
            pidx = text.find(p, idx + len(target))
            if pidx != -1 and pidx < end:
                end = pidx
        segments.append(text[max(0, idx - 30) : end])  # 前 30 字上下文
        start = end
    return segments


def _match_history_score_in_text(text: str) -> tuple[int | None, str]:
    """在给定文本段内匹配历史类分数（不做省份校验，由调用方保证段落正确）。"""
    # 模式1：备注式 "历史类：501（101组）" / "历史类 501 (101组)" / "历史类501分"
    remark_patterns = [
        r"历史类[：:\s]*(\d{3})\s*分?\s*[（(]\s*(\d{2,4})\s*组?\s*[)）]",
        r"历史类[：:\s]*(\d{3})\s*[（(]\s*(\d{2,4})\s*组?\s*[)）]",
        r"历史类[：:\s]*(\d{3})\s*分",
    ]
    for pat in remark_patterns:
        m = re.search(pat, text)
        if m:
            score = int(m.group(1))
            group = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
            if 400 <= score <= 700:  # 合理分数区间
                return score, group

    # 模式2：表格行 "历史类 ... 501"（取历史类所在行的最小分数）
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    history_scores: list[int] = []
    for ln in lines:
        if "历史类" not in ln and "历史" not in ln:
            continue
        nums = re.findall(r"\b(4\d{2}|5\d{2}|6\d{2})\b", ln)
        history_scores.extend(int(n) for n in nums if 400 <= int(n) <= 699)
    if history_scores:
        return min(history_scores), ""

    return None, ""


def _try_parse_page(
    html: str, url: str, rec: OfficialRecord, school_name: str
) -> bool:
    """尝试从单个页面解析出河南历史类分数。成功返回 True。

    处理顺序：PDF 嵌入 → HTML 正文 → 表格 → 图片 OCR。
    """
    # PDF 嵌入（含 vsb 系统的 showVsbpdfIframe JS）
    detector = _PdfImageDetector()
    detector.feed(html)
    if detector.pdf_urls:
        pdf_url = urljoin(url, detector.pdf_urls[0])
        try:
            data, _ = _fetch_bytes(pdf_url, referer=url)
            tmp = VERIFY_DIR / f"_tmp_{school_name}.pdf"
            tmp.write_bytes(data)
            body_text = _read_pdf_text(tmp)
            tmp.unlink(missing_ok=True)
        except Exception:
            body_text = ""
        if body_text:
            score, group = _extract_history_score(body_text)
            if score is not None:
                rec.official_score = score
                rec.volunteer_group = group
                rec.raw_text = body_text[:800]
                rec.found_url = pdf_url
                rec.status = "found"
                return True

    # HTML 正文
    body_text = _strip_html_to_text(html)
    if len(body_text) >= 50:
        score, group = _extract_history_score(body_text)
        if score is not None:
            rec.official_score = score
            rec.volunteer_group = group
            rec.raw_text = body_text[:800]
            rec.found_url = url
            rec.status = "found"
            return True

    # HTML 表格
    tp = _TableParser()
    tp.feed(html)
    if tp.rows:
        table_text = "\n".join(
            " ".join(c for c in row if c) for row in tp.rows
        )
        score, group = _extract_history_score(table_text)
        if score is not None:
            rec.official_score = score
            rec.volunteer_group = group
            rec.raw_text = table_text[:800]
            rec.found_url = url
            rec.status = "found"
            return True

    # 图片型：OCR（正文/表格没匹配到分数时尝试）。
    # 前置检查：只在页面含内容图片时才 OCR，避免对纯文本页浪费 GPU。
    has_content_img = bool(
        re.search(r'<img[^>]+src="[^"]+\.(?:png|jpg|jpeg)"', html, re.I)
    )
    if not has_content_img:
        return False
    ocr_score, ocr_note = _ocr_images_in_page(html, url)
    if ocr_score is not None:
        rec.official_score = ocr_score
        rec.raw_text = f"[OCR] {ocr_note}"
        rec.found_url = url
        rec.status = "found"
        return True
    if ocr_note and "无内容图片" not in ocr_note:
        rec.note = f"图片型 OCR 未提取到（{ocr_note}）：{url}"
        rec.status = "needs_manual"

    return False


# 深度爬取：栏目页关键词（用于 BFS 二次发现详情页）
# 覆盖各高校招生网常见的"往年分数"栏目命名变体
_SECTION_KEYWORDS = [
    "往年录取", "往年分数", "历年分数", "历年录取", "历年情况",
    "录取分数", "录取情况", "录取统计", "分省分数", "分省录取",
    "录取查询", "分数统计", "分数查询", "历年数据", "历年成绩",
]


def _find_section_links(base_url: str, html: str) -> list[tuple[str, str]]:
    """从页面找栏目页链接（往年录取/历年分数等），用于深度爬取二次发现详情页。

    与 _find_admission_links 不同：这里专门找导航类栏目（点击后是列表页），
    不要求命中"2025/河南"，因为这些栏目页才藏真正的详情页链接。
    """
    parser = _LinkParser()
    parser.feed(html)
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for text, href in parser.links:
        text = text.strip()
        if not text or not href or href.startswith(("javascript:", "#", "mailto:")):
            continue
        if not any(kw in text for kw in _SECTION_KEYWORDS):
            continue
        abs_url = urljoin(base_url, href).split("#")[0]
        if abs_url in seen or abs_url == base_url:
            continue
        seen.add(abs_url)
        found.append((text[:40], abs_url))
    return found[:6]  # 栏目页通常就几个


def _playwright_fetch(url: str, referer: str = "", timeout_ms: int = 12000) -> str:
    """playwright 抓取（urllib 失败时的反爬兜底）。

    部分招生网（西安外事 412、丽江 503）对 urllib 主动拒绝，
    用真实浏览器加载绕过。仅在 urllib 失败时调用（playwright 慢）。
    用 domcontentloaded 而非 networkidle（后者对 JS 重的站会等满超时）。
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=UA, locale="zh-CN", ignore_https_errors=True
        )
        page = context.new_page()
        kwargs = {"wait_until": "domcontentloaded", "timeout": timeout_ms}
        if referer:
            kwargs["referer"] = referer
        page.goto(url, **kwargs)
        # 等菜单 DOM 渲染（很多招生网菜单是 JS 动态注入）
        try:
            page.wait_for_timeout(2500)
        except Exception:
            pass
        html = page.content()
        context.close()
        browser.close()
    return html


# playwright 调用计数：限制单次运行最多用 3 次浏览器（启动慢，避免对每个慢链接都回退）
_PLAYWRIGHT_BUDGET = 3
_playwright_used = 0


def _fetch_with_fallback(url: str, referer: str = "") -> str:
    """urllib 抓取，仅对**反爬错误**（412/503/403）回退 playwright。

    关键：超时、连接拒绝、SSL 握手失败等**网络错误不回退**——这些 playwright 也救不了，
    反而会因启动浏览器让整体超时。只有服务器明确返回反爬状态码（urllib 能连上但被拒）
    才值得用真实浏览器绕过。预算 3 次。
    """
    global _playwright_used
    try:
        return _fetch_text(url, referer=referer)
    except urllib.request.HTTPError as http_err:
        # 仅对反爬类 HTTP 状态码回退（412/503/403 等，urllib 能连上但被应用层拒）
        if http_err.code not in (403, 412, 503) or _playwright_used >= _PLAYWRIGHT_BUDGET:
            raise
        _playwright_used += 1
        try:
            return _playwright_fetch(url, referer=referer)
        except Exception:
            raise http_err
    except Exception:
        # 超时/连接错误/SSL 等网络问题：不回退，直接抛（playwright 救不了且拖慢整体）
        raise


def fetch_official_record(school_name: str, universities: list) -> OfficialRecord:
    """Step ① + ②：抓官网录取表 + 换算位次。

    BFS 探索（最多 2 层）：首页 → 栏目页（往年录取/历年分数）→ 详情页。
    复用 load_henan_universities 的结果查招生网 URL（避免重复加载）。
    """
    rec = OfficialRecord(
        school_name=school_name, fetched_at=date.today().isoformat()
    )

    # 查招生网 URL
    uni = next((u for u in universities if u.school_name == school_name), None)
    if not uni:
        rec.note = "universities.yaml 无此校记录"
        return rec
    base_url = uni.enrollment_website or uni.official_website
    if not base_url:
        rec.note = "无官网/招生网 URL"
        return rec

    # urllib 抓首页，失败则 playwright 兜底（_fetch_with_fallback 内置）
    try:
        home_html = _fetch_with_fallback(base_url)
    except Exception as e:
        rec.note = f"抓取招生网失败：{e}"
        return rec

    all_links = _find_admission_links(base_url, home_html)
    section_links = _find_section_links(base_url, home_html)

    # BFS 二次发现：从首页找栏目页链接，进入栏目页找详情页。
    # 限制探索量：栏目页最多取 3 个，每个栏目页的子链接最多 5 个，避免 BFS 爆炸导致超时。
    discovered_sublinks: list[tuple[str, str]] = []
    for s_text, s_url in section_links[:3]:
        try:
            sec_html = _fetch_with_fallback(s_url, referer=base_url)
        except Exception:
            continue
        sub_links = _find_admission_links(s_url, sec_html)[:5]
        for t, u in sub_links:
            if not any(u == x for _, x in all_links + discovered_sublinks):
                discovered_sublinks.append((t, u))
    # 子详情页优先（栏目页发现的，比首页新闻更可能是真分数页）
    all_links = discovered_sublinks + all_links

    rec.candidate_links = [u for _, u in all_links][:12]
    if not all_links:
        rec.note = f"招生网未找到 2025 河南本科录取链接（已扫 {base_url}）"
        return rec

    # BFS 尝试每个候选页：既解析分数，又记录探索。
    # 限制最多探索 8 个候选页（子详情页优先），避免扫太多页导致超时。
    visited: set[str] = set()
    for text, url in all_links[:8]:
        if url in visited:
            continue
        visited.add(url)
        if url == base_url:
            page_html = home_html
        else:
            try:
                page_html = _fetch_with_fallback(url, referer=base_url)
            except Exception:
                continue
        if _try_parse_page(page_html, url, rec, school_name):
            break  # 命中即停

    if rec.official_score is None:
        if rec.status != "needs_manual":
            rec.note = rec.note or "链接已访问但未解析出历史类分数"
        return rec

    # Step ② 换算位次
    entries = _load_score_rank_entries(TARGET_YEAR, "历史类")
    rec.converted_rank = _score_to_rank(entries, rec.official_score)
    return rec


def _strip_html_to_text(html: str) -> str:
    """HTML → 纯文本（去 script/style/标签）。"""
    text = re.sub(r"<script.*?</script>", "", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S | re.I)
    # 优先取 vsb_content / v_news_content 容器（很多高校站用）
    m = re.search(
        r'(id="vsb_content"|class="v365_content"|class="v_news_content")[^>]*>(.*?)(?:</div>\s*</div>|<!--)',
        text,
        re.S | re.I,
    )
    if m:
        text = m.group(2)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


# ── Step ③ 比对种子 ──────────────────────────────────────────────────
def compare_with_seed(
    official: OfficialRecord, seed_records: list
) -> Verdict:
    """比对官网换算位次与种子 min_rank。"""
    v = Verdict(
        school_name=official.school_name,
        verdict="no_official_data",
        official_score=official.official_score,
        converted_rank=official.converted_rank,
        seed_rank=None,
        seed_score=None,
        delta=None,
        note=official.note,
    )
    if official.converted_rank is None:
        v.note = official.note or "官网未提供可换算的分数"
        return v

    # 取该校 2025 历史类种子的最小 min_rank（专业组级优先，退化到 school 级）
    seed_for_school = [
        s
        for s in seed_records
        if s.school_name == official.school_name
        and s.year == TARGET_YEAR
        and s.track == "历史类"
    ]
    if not seed_for_school:
        v.note = "admission_history_2025.yaml 无此校记录"
        return v

    ranks = [s.min_rank for s in seed_for_school if s.min_rank]
    scores = [s.min_score for s in seed_for_school if s.min_score]
    v.seed_rank = min(ranks) if ranks else None  # 录取最低位次=最大的位次值
    v.seed_score = min(scores) if scores else None

    if v.seed_rank is None:
        v.note = "种子 min_rank 缺失"
        return v

    v.delta = official.converted_rank - v.seed_rank
    if abs(v.delta) <= SCORE_TOLERANCE:
        v.verdict = "match"
        v.note = f"官网{official.official_score}分→位次{official.converted_rank}，种子{v.seed_rank}，差{v.delta:+d}位（容差±{SCORE_TOLERANCE}）"
    else:
        v.verdict = "conflict"
        direction = "种子位次偏低估（实际更难考）" if v.delta > 0 else "种子位次偏高估（实际更好考）"
        v.note = f"官网{official.official_score}分→位次{official.converted_rank}，种子{v.seed_rank}，差{v.delta:+d}位 {direction}"
    return v


# ── 缓存 ──────────────────────────────────────────────────────────────
def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── 报告 ──────────────────────────────────────────────────────────────
def render_report(verdicts: list[Verdict], records: list[OfficialRecord]) -> str:
    """生成 Markdown 报告。"""
    today = date.today().isoformat()
    lines = [
        f"# 院校官网录取数据交叉验证报告",
        f"",
        f"**验证日期**：{today}",
        f"**验证对象**：弟弟志愿组 {len(verdicts)} 所学校",
        f"**验证口径**：官网 2025 历史类录取分 → 一分一段表换算位次 → 比对种子 min_rank（容差 ±{SCORE_TOLERANCE} 位）",
        f"**权威源**：各校招生网官方公布的 2025 河南省内本科普通类录取分数（官网是唯一权威源）",
        f"",
        f"## 汇总",
        f"",
    ]

    n_match = sum(1 for v in verdicts if v.verdict == "match")
    n_conflict = sum(1 for v in verdicts if v.verdict == "conflict")
    n_nodata = sum(1 for v in verdicts if v.verdict == "no_official_data")
    lines += [
        f"| 判定 | 数量 | 含义 |",
        f"|------|------|------|",
        f"| ✅ match | {n_match} | 官网与种子一致（差 ≤ {SCORE_TOLERANCE} 位） |",
        f"| ⚠️ conflict | {n_conflict} | 官网与种子冲突，**种子错，需按官网修正** |",
        f"| ❓ no_official_data | {n_nodata} | 官网未找到 2025 数据，需人工另行核实 |",
        f"",
        f"## 明细",
        f"",
        f"| # | 学校 | 判定 | 官网分 | 换算位次 | 种子位次 | 差 | 说明 |",
        f"|---|------|------|--------|----------|----------|----|------|",
    ]

    icon = {"match": "✅", "conflict": "⚠️", "no_official_data": "❓"}
    for i, v in enumerate(verdicts, 1):
        delta = f"{v.delta:+d}" if v.delta is not None else "—"
        lines.append(
            f"| {i} | {v.school_name} | {icon[v.verdict]} {v.verdict} | "
            f"{v.official_score or '—'} | {v.converted_rank or '—'} | "
            f"{v.seed_rank or '—'} | {delta} | {v.note} |"
        )

    # conflict 与 needs_manual 单列，便于跟进
    conflicts = [v for v in verdicts if v.verdict == "conflict"]
    needs = [r for r in records if r.status == "needs_manual"]
    if conflicts or needs:
        lines += ["", f"## 待处理", ""]
        if conflicts:
            lines += [
                f"### ⚠️ 冲突（{len(conflicts)} 所，按官网修正种子）",
                f"",
            ]
            for v in conflicts:
                rec = next((r for r in records if r.school_name == v.school_name), None)
                lines += [
                    f"- **{v.school_name}**：{v.note}",
                ]
                if rec and rec.found_url:
                    lines.append(f"  - 官网证据：{rec.found_url}")
            lines.append("")
        if needs:
            lines += [
                f"### 🖐️ 需人工核对（{len(needs)} 所，官网为图片型）",
                f"",
            ]
            for r in needs:
                lines.append(f"- **{r.school_name}**：{r.note}")
            lines.append("")

    return "\n".join(lines) + "\n"


# ── 主流程 ────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(
        description="院校官网录取数据交叉验证（河南 2026 历史类普通本科批）"
    )
    ap.add_argument("--school", help="验证单所学校")
    ap.add_argument("--all", action="store_true", help="验证弟弟志愿组全部 16 所")
    ap.add_argument(
        "--refresh", action="store_true", help="强制重抓官网（忽略缓存）"
    )
    args = ap.parse_args()

    if not args.school and not args.all:
        ap.error("请指定 --school <校名> 或 --all")

    VERIFY_DIR.mkdir(parents=True, exist_ok=True)

    # 加载种子（一次性）
    print("加载种子数据…")
    universities = load_henan_universities(SEED_DIR)
    seed_records = load_henan_admission_history(SEED_DIR, years=(TARGET_YEAR,))
    print(f"  院校库 {len(universities)} 所，{TARGET_YEAR} 历史录取 {len(seed_records)} 条")

    # 确定验证清单
    schools = [args.school] if args.school else list(BROTHER_SCHOOLS)

    cache = load_cache()
    records: list[OfficialRecord] = []
    verdicts: list[Verdict] = []
    failed: list[str] = []

    for i, name in enumerate(schools, 1):
        print(f"\n[{i}/{len(schools)}] {name}")
        # 缓存命中且非 refresh
        cached = cache.get(name)
        if cached and not args.refresh and cached.get("status") in ("found", "needs_manual", "no_official_data"):
            print(f"  缓存命中（{cached.get('status')}），跳过抓取")
            rec = OfficialRecord(
                school_name=name,
                found_url=cached.get("found_url", ""),
                raw_text=cached.get("raw_text", ""),
                official_score=cached.get("official_score"),
                volunteer_group=cached.get("volunteer_group", ""),
                converted_rank=cached.get("converted_rank"),
                status=cached.get("status", "no_official_data"),
                note=cached.get("note", ""),
                candidate_links=cached.get("candidate_links", []),
                fetched_at=cached.get("fetched_at", ""),
            )
        else:
            try:
                rec = fetch_official_record(name, universities)
            except Exception as e:
                print(f"  ❌ 抓取异常：{e}")
                failed.append(f"{name}\t{e}")
                continue
            # 写缓存
            cache[name] = asdict(rec)
            save_cache(cache)
            time.sleep(0.5)  # 礼貌延迟

        records.append(rec)
        v = compare_with_seed(rec, seed_records)
        verdicts.append(v)
        icon = {"match": "✅", "conflict": "⚠️", "no_official_data": "❓"}
        print(
            f"  {icon[v.verdict]} {v.verdict}: "
            f"分={v.official_score or '—'} 换算位次={v.converted_rank or '—'} "
            f"种子位次={v.seed_rank or '—'} {v.note}"
        )

    # 写报告
    REPORT_FILE.write_text(render_report(verdicts, records), encoding="utf-8")
    print(f"\n报告已生成：{REPORT_FILE}")

    if failed:
        FAILED_FILE.write_text("\n".join(failed) + "\n", encoding="utf-8")
        print(f"失败 {len(failed)} 所 → {FAILED_FILE}")

    # 汇总
    n_match = sum(1 for v in verdicts if v.verdict == "match")
    n_conflict = sum(1 for v in verdicts if v.verdict == "conflict")
    n_nodata = sum(1 for v in verdicts if v.verdict == "no_official_data")
    print(
        f"\n汇总：✅match {n_match} / ⚠️conflict {n_conflict} / ❓no_data {n_nodata}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
