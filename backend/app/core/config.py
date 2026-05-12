from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """集中管理配置，避免在业务代码里散落硬编码。"""

    app_name: str = "Attendance System"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8
    database_url: str = "sqlite:///./database/attendance.db"
    face_threshold: float = 0.58
    upload_dir: Path = Path("uploads")
    face_db_dir: Path = Path("database/face_db")

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.face_db_dir.mkdir(parents=True, exist_ok=True)
    return settings
