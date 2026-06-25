from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SEED_DIR = DATA_DIR / "seed"
DB_PATH = DATA_DIR / "llm_sim.db"


class Settings:
    db_path: Path = DB_PATH
    seed_dir: Path = SEED_DIR
    data_dir: Path = DATA_DIR
    api_prefix: str = "/api/v1"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"


settings = Settings()
