from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Bantu Coding"
    app_env: str = "development"
    log_level: str = "INFO"

    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str

    cors_origins: str = "http://localhost:5173"

    @property
    def database_url(self) -> str:
        # Password is percent-encoded: an unescaped @ or / in it would be parsed
        # as a URL delimiter and produce a confusing connection error.
        password = quote_plus(self.db_password)
        return (
            f"postgresql+psycopg://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
