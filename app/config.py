import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 自动加载项目根目录下的 .env 文件
try:
    from dotenv import load_dotenv
    _env_path = PROJECT_ROOT / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

DATA_DIR = PROJECT_ROOT / "data"
SEED_DIR = DATA_DIR / "seed"
DB_PATH = DATA_DIR / "llm_sim.db"


class Settings:
    db_path: Path = DB_PATH
    seed_dir: Path = SEED_DIR
    data_dir: Path = DATA_DIR
    api_prefix: str = "/api/v1"

    # --- LLM / AI 配置（从环境变量读取，兼容任意 OpenAI 兼容服务商）---
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "deepseek-chat")
    # AI 推荐使用的最大 token 数
    ai_max_tokens: int = int(os.getenv("AI_MAX_TOKENS", "4096"))
    # AI 温度参数（0-2，越低越确定性）
    ai_temperature: float = float(os.getenv("AI_TEMPERATURE", "0.7"))

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def llm_configured(self) -> bool:
        """检查 LLM 是否已配置（API Key 存在）"""
        return bool(self.openai_api_key)


settings = Settings()
