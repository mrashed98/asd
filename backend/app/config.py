"""Application configuration."""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Database
    database_url: str = "sqlite:///./data/arabseed.db"
    
    # JDownloader
    jdownloader_host: str = "localhost"
    jdownloader_port: int = 3129
    myjd_email: str | None = None
    myjd_password: str | None = None
    myjd_device_name: str | None = None
    
    # Directories
    download_folder: str = "/downloads"
    english_series_dir: str = "/media/english-series"
    arabic_series_dir: str = "/media/arabic-series"
    english_movies_dir: str = "/media/english-movies"
    arabic_movies_dir: str = "/media/arabic-movies"
    
    # Background Tasks
    check_interval_hours: int = 1
    download_sync_interval_minutes: int = 5
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # API
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:3001"]
    
    @property
    def jdownloader_url(self) -> str:
        """Get JDownloader API URL."""
        return f"http://{self.jdownloader_host}:{self.jdownloader_port}"


settings = Settings()

