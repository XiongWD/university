"""heao book.heao.com.cn 客户端公共逻辑：token 读取 + headers + TLS 上下文 + GET。

token 从 cookie 文件读 Web-Token（浏览器导出），失败抛错提示刷新。
所有 heao 接口共用 Authorization: Bearer + Cookie: Web-Token 双发 + 禁用 TLS 校验
（本地 Python 证书链校验失败，与 scrape_heao_admission.py 一致）。
"""
import json
import ssl
import urllib.request
from pathlib import Path

# 最新 cookie 文件（用户每次刷新后更新此路径）
TOKEN_FILE = Path(r"C:\Users\Administrator\Downloads\cookies-2026-07-01 (1).json")

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def load_token() -> str:
    """从 cookie 文件读 Web-Token；缺失则抛错（避免静默用过期 token）。"""
    if not TOKEN_FILE.exists():
        raise SystemExit(
            f"❌ 找不到 cookie 文件 {TOKEN_FILE}\n"
            f"   请从浏览器导出最新 cookies-YYYY-MM-DD.json 并更新 TOKEN_FILE 路径。"
        )
    cookies = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    token = next((x["value"] for x in cookies if x.get("name") == "Web-Token"), "")
    if not token:
        raise SystemExit(f"❌ cookie 文件 {TOKEN_FILE} 中无 Web-Token，请重新导出。")
    return token


def build_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Cookie": f"Web-Token={token}",
        "Content-Language": "zh_CN",
        "Referer": "https://book.heao.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
    }


def get_json(url: str, token: str, timeout: int = 30) -> dict:
    """GET 一个 heao 接口并返回 JSON。token 失效（401/空 data）由调用方判别。"""
    req = urllib.request.Request(url, headers=build_headers(token))
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))
