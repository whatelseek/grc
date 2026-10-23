from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://bia:bia@localhost:5432/bia"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 12 * 60
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # Evidence files attached to safeguards.
    evidence_dir: str = "/data/evidence"
    evidence_max_bytes: int = 25 * 1024 * 1024

    # Bootstrap admin, created by `python -m app.cli init` if absent.
    admin_email: str = "admin@example.com"
    admin_password: str = "admin"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
