import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings:
    ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "admin")
    SESSION_SECRET_KEY: str = os.environ.get("SESSION_SECRET_KEY", "dev-secret-change-me")
    DATABASE_URL: str = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR / 'app.db'}")
    MAX_DB_ROWS: int = int(os.environ.get("MAX_DB_ROWS", "5000"))


settings = Settings()
